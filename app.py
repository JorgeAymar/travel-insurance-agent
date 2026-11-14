"""App Flask que lista reclamaciones de seguros de viaje desde un JSON en disco."""
import json
import queue
import threading
import unicodedata
from datetime import datetime

import agent
import config as cfg
from flask import Flask, Response, abort, jsonify, render_template, request, stream_with_context, url_for

cfg.validar_entorno()  # si falta algo en el .env, la app no arranca y dice qué falta

app = Flask(__name__)
app.jinja_env.globals.update(max=max, min=min)


@app.context_processor
def marca():
    """Nombre de la app y del usuario para la cabecera (vienen del .env)."""
    nombre = cfg.get("APP_USER_NAME")
    return {"app_name": cfg.get("APP_NAME"), "app_tagline": cfg.get("APP_TAGLINE"), "user_name": nombre,
            "user_role": cfg.get("APP_USER_ROLE"), "user_initials": "".join(p[0] for p in nombre.split()[:2]).upper()}


@app.template_global()
def page_url(state, **changes):
    """URL del listado conservando filtros/orden y aplicando los cambios dados."""
    return url_for("index", **{**state, **changes})
DATA_FILE = cfg.ruta("CLAIMS_FILE")
POLICIES_FILE = cfg.ruta("POLICIES_FILE")
CLAUSES_FILE = cfg.ruta("CLAUSES_FILE")

# Nombres con los que se muestran las arquitecturas en pantalla (única fuente).
ARQ_NOMBRES = {"langgraph": "LangGraph", "pydantic_ai": "Pydantic AI", "claude_sdk": "Claude Agent SDK",
               "lineas": "Línea por línea", "una_llamada": "Una sola llamada", "reglas": "Reglas"}
app.jinja_env.globals["arq_nombre"] = lambda a: ARQ_NOMBRES.get(a, a)

# Los resultados del agente son SOLO virtuales: se emiten al navegador mientras se calculan y no se guardan
# en archivo ni en base de datos. Este cupo limita cuántas revisiones corren a la vez (protege al servidor LLM).
_cupo = threading.BoundedSemaphore(cfg.entero("MAX_CORRIDAS_SIMULTANEAS"))

PER_PAGE_OPTIONS = cfg.enteros("PER_PAGE_OPTIONS")


def _load(path):
    # Se lee en cada petición: editar el JSON y recargar basta para ver cambios.
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _norm(texto):
    """Minúsculas y sin acentos, para buscar sin que importen."""
    return "".join(ch for ch in unicodedata.normalize("NFD", str(texto).lower()) if unicodedata.category(ch) != "Mn")


def _texto_busqueda(c):
    """Todo lo que el buscador mira de una reclamación: ID, tipo, cliente, póliza, destino, canal y relato."""
    return _norm(" ".join([c["id"], c["tipoReclamacion"], c["nombreCliente"], c["dniCliente"], c["numeroPoliza"],
                           c["destino"], c["pais"], c["canal"], " ".join(c["glosa"])]))


def load_claims():
    return _load(DATA_FILE)[:cfg.entero("MAX_RECLAMACIONES")]  # nunca más de MAX_RECLAMACIONES


def load_policies():
    return _load(POLICIES_FILE)


def load_clauses():
    return {c["codigo"]: c for c in _load(CLAUSES_FILE)}


@app.template_filter("eur")
def eur(v):
    return "—" if v is None else f"{v:,.0f}".replace(",", ".") + " €"


@app.template_filter("fecha")
def fecha(s):
    y, m, d = s.split("-")
    return f"{d}/{m}/{y}"


@app.route("/")
def index():
    claims = load_claims()
    a = request.args
    q, tipo = a.get("q", "").strip(), a.get("tipo", "")
    sort, desc = a.get("sort", "id"), a.get("dir", "asc") == "desc"
    per_page = a.get("n", PER_PAGE_OPTIONS[0], type=int)
    per_page = per_page if per_page in PER_PAGE_OPTIONS else PER_PAGE_OPTIONS[0]

    terminos = _norm(q).split()
    rows = [
        c for c in claims
        if (not tipo or c["tipoReclamacion"] == tipo)
        and all(t in _texto_busqueda(c) for t in terminos)
    ]
    if rows and sort in rows[0]:
        rows.sort(key=lambda c: (c[sort] is None, c[sort]), reverse=desc)

    pages = max(1, -(-len(rows) // per_page))
    page = min(max(a.get("p", 1, type=int), 1), pages)
    start = (page - 1) * per_page

    kpis = {
        "total": len(claims),
        "abiertas_cliente": sum(c["casoAbiertoPorCliente"] for c in claims),
        "tipos": len({c["tipoReclamacion"] for c in claims}),
        "importe": sum(c["importeReclamado"] for c in claims),
        "media": sum(c["importeReclamado"] for c in claims) // max(1, len(claims)),
    }
    state = dict(q=q, tipo=tipo, sort=sort, dir="desc" if desc else "asc", n=per_page)
    return render_template(
        "index.html", rows=rows[start:start + per_page], found=len(rows), kpis=kpis,
        ids_filtrados=[{"id": c["id"], "tipo": c["tipoReclamacion"]} for c in rows],  # todo el listado filtrado (no solo la página): lo usa la revisión en lote
        por_defecto=max(1, min(cfg.entero("ANALISIS_RECLAMACIONES_DEFECTO"), len(rows) or 1)),
        tipos=sorted({c["tipoReclamacion"] for c in claims}),
        page=page, pages=pages, start=start, per_page=per_page, per_page_options=PER_PAGE_OPTIONS,
        state=state, sort=sort, desc=desc, arq_def=cfg.get("AGENT_ARCH"),
    )


@app.route("/reclamaciones/<claim_id>")
def detail(claim_id):
    claim = next((c for c in load_claims() if c["id"] == claim_id), None)
    if claim is None:
        abort(404)
    policy = next((p for p in load_policies() if p["numero"] == claim["numeroPoliza"]), None)
    clauses = load_clauses()
    clause = clauses.get(claim["cobertura"].get("clausula"))
    return render_template("detail.html", c=claim, policy=policy, clause=clause,
                           modelos=agent.listar_modelos(), modelo_def=cfg.opcional("OLLAMA_MODEL"),
                           arq_def=cfg.get("AGENT_ARCH"),
                           back=request.args.get("back") or url_for("index"))


@app.route("/reclamaciones/<claim_id>/revision", methods=["POST"])
def start_review(claim_id):
    """Ejecuta UNA revisión y la emite en directo al navegador (una línea JSON por evento).

    Nada se guarda: si el navegador se va o se refresca, la corrida se descarta.
    Eventos: {"tipo": "progreso", "lineas": [...], "fase": "..."}, {"tipo": "fin", "resultado": {...}},
    {"tipo": "error", "error": "..."}.
    """
    claim = next((c for c in load_claims() if c["id"] == claim_id), None)
    if claim is None:
        abort(404)
    policy = next((p for p in load_policies() if p["numero"] == claim["numeroPoliza"]), None)
    body = request.get_json(silent=True)
    arq = body.get("arquitectura") if isinstance(body, dict) else None
    if arq not in agent.ARQUITECTURAS:  # una petición mal formada no debe arrancar una revisión (cuesta llamadas al LLM)
        return jsonify({"error": "Indica una arquitectura válida: " + ", ".join(agent.ARQUITECTURAS)}), 400
    opts = {"arquitectura": arq}
    modelo = body.get("modelo")
    if modelo:
        if modelo not in agent.listar_modelos() and modelo != cfg.opcional("OLLAMA_MODEL"):
            return jsonify({"error": "modelo no disponible"}), 400
        opts["modelo"] = modelo
    if body.get("motor") in ("reglas", "ollama", "claude"):
        opts["motor"] = body["motor"]
    elif arq in agent.ARQ_EXTERNAS:
        opts["motor"] = "ollama"  # LangGraph y Pydantic AI usan el LLM de Ollama
    if not _cupo.acquire(blocking=False):
        return jsonify({"error": "Hay demasiadas revisiones en curso; espera a que termine alguna."}), 429

    eventos, cancelado = queue.Queue(), threading.Event()
    clauses = load_clauses()

    def trabajo():
        try:
            def progreso(lineas, fase):  # el agente avisa cada vez que marca una línea
                if not cancelado.is_set():
                    eventos.put({"tipo": "progreso", "lineas": lineas, "fase": fase})

            eventos.put({"tipo": "fin", "resultado": agent.revisar(claim, policy, clauses, on_progress=progreso, **opts)})
        except Exception as e:  # la revisión nunca debe quedarse colgada para el navegador
            eventos.put({"tipo": "error", "error": cfg.ocultar(f"{type(e).__name__}: {e}")})
        finally:
            _cupo.release()
            eventos.put(None)

    threading.Thread(target=trabajo, daemon=True).start()

    def flujo():
        try:
            while (ev := eventos.get()) is not None:
                yield json.dumps(ev, ensure_ascii=False) + "\n"
        finally:
            cancelado.set()  # el navegador se fue (p. ej. refresco): se descarta el resto

    return Response(stream_with_context(flujo()), mimetype="application/x-ndjson",
                    headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.route("/analisis")
def analysis_page():
    """Análisis de las reclamaciones: ejecuta las 3 tecnologías y las compara con la referencia, todo en el navegador."""
    total = len(load_claims())
    return render_template("analisis.html", modelos=agent.listar_modelos(), modelo_def=cfg.opcional("OLLAMA_MODEL"),
                           total=total, por_defecto=max(1, min(cfg.entero("ANALISIS_RECLAMACIONES_DEFECTO"), total)))


@app.route("/api/referencia")
def api_referencia():
    """Veredicto del revisor por reglas de cada reclamación: la referencia con la que se mide a los agentes.

    Se calcula en el momento (son milisegundos) y no se guarda en ningún sitio.
    """
    clauses = load_clauses()
    pols = {p["numero"]: p for p in load_policies()}
    salida = []
    for c in load_claims():
        r = agent.revisar(c, pols[c["numeroPoliza"]], clauses, motor="reglas", pausa=0)
        salida.append({"id": c["id"], "tipo": c["tipoReclamacion"], "veredicto": r["veredicto"], "importe": r["importeAPagar"],
                       "lineas": {l["id"]: l["estado"] for l in r["lineas"]}})
    return jsonify(salida)


@app.route("/polizas")
def policies():
    claims = load_claims()
    n_claims = {}
    for c in claims:
        n_claims[c["numeroPoliza"]] = n_claims.get(c["numeroPoliza"], 0) + 1
    q = request.args.get("q", "").strip().lower()
    plan = request.args.get("plan", "")
    rows = [
        p for p in load_policies()
        if (not plan or p["plan"] == plan)
        and (not q or q in p["numero"].lower() or q in (p["tomador"]["nombre"] + " " + p["tomador"]["apellido1"]
                                                         + " " + p["tomador"]["apellido2"]).lower()
             or q in p["tomador"]["dni"].lower())
    ]
    rows.sort(key=lambda p: p["viaje"]["inicio"], reverse=True)
    return render_template("polizas.html", rows=rows, n_claims=n_claims, q=request.args.get("q", ""),
                           plan=plan, planes=sorted({p["plan"] for p in load_policies()}),
                           total=len(load_policies()))


@app.route("/polizas/<numero>")
def policy_detail(numero):
    policy = next((p for p in load_policies() if p["numero"] == numero), None)
    if policy is None:
        abort(404)
    clauses = load_clauses()
    coberturas = [(k, v, clauses.get(v["clausula"])) for k, v in policy["coberturas"].items()]
    generales = [clauses[g] for g in policy["clausulasGenerales"] if g in clauses]
    claims = [c for c in load_claims() if c["numeroPoliza"] == numero]
    return render_template("poliza.html", p=policy, coberturas=coberturas, generales=generales, claims=claims,
                           req_general=clauses["G-07"]["requisitos"] if "G-07" in clauses else [])


@app.route("/api/policies")
def api_policies():
    return jsonify(load_policies())


@app.route("/api/clauses")
def api_clauses():
    return jsonify(list(load_clauses().values()))


@app.route("/api/claims")
def api_claims():
    return jsonify(load_claims())


if __name__ == "__main__":
    app.run(host=cfg.get("HOST"), port=cfg.entero("PORT"), debug=cfg.booleano("FLASK_DEBUG"))
