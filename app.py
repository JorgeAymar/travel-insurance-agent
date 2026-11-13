"""App Flask que lista reclamaciones de seguros de viaje desde un JSON en disco."""
import json
import os
import tempfile
import threading
import unicodedata
from datetime import datetime

import agent
import config as cfg
import corridas
from flask import Flask, abort, jsonify, render_template, request, url_for

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
REVIEWS_FILE = cfg.ruta("REVIEWS_FILE")

# --- Revisiones del agente: se guardan en disco y se ejecutan en segundo plano ---
_reviews_lock = threading.Lock()


def load_reviews():
    try:
        with open(REVIEWS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def _save_review(claim_id, data):
    """Actualiza la revisión de una reclamación (escritura atómica)."""
    with _reviews_lock:
        reviews = load_reviews()
        reviews[claim_id] = data
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(REVIEWS_FILE), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(reviews, f, ensure_ascii=False, indent=2)
        os.replace(tmp, REVIEWS_FILE)


# Nombres con los que se muestran las arquitecturas en pantalla (única fuente).
ARQ_NOMBRES = {"langgraph": "LangGraph", "pydantic_ai": "Pydantic AI", "claude_sdk": "Claude Agent SDK",
               "lineas": "Línea por línea", "una_llamada": "Una sola llamada", "reglas": "Reglas"}
app.jinja_env.globals["arq_nombre"] = lambda a: ARQ_NOMBRES.get(a, a)


def _run_review(claim_id, started, runs):
    """Proceso del agente (hilo): ejecuta una o varias corridas seguidas y guarda el veredicto de la última.

    runs: lista de opciones para agent.revisar (una por tecnología). Cada corrida queda en el historial.
    """
    try:
        claim = next(c for c in load_claims() if c["id"] == claim_id)
        policy = next(p for p in load_policies() if p["numero"] == claim["numeroPoliza"])
        clauses = load_clauses()
        for i, opts in enumerate(runs, 1):
            etiqueta = ARQ_NOMBRES.get(opts.get("arquitectura", ""), "") + (f" ({i}/{len(runs)})" if len(runs) > 1 else "")

            def progreso(lineas, fase, etiqueta=etiqueta):  # el agente avisa cada vez que marca una línea
                _save_review(claim_id, {"estado": "en_proceso", "iniciada": started, "lineas": lineas,
                                        "fase": f"[{etiqueta}] {fase}" if etiqueta else fase})

            result = agent.revisar(claim, policy, clauses, on_progress=progreso, **opts)
            corridas.registrar(claim, result, started)  # historial para comparar modelos y arquitecturas
        _save_review(claim_id, {"estado": "completada", "iniciada": started,
                                "finalizada": datetime.now().isoformat(timespec="seconds"), **result})
    except Exception as e:  # el proceso nunca debe quedarse «en proceso» para siempre
        _save_review(claim_id, {"estado": "error", "iniciada": started, "error": f"{type(e).__name__}: {e}"})

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
    sort, desc = a.get("sort", "fechaIngreso"), a.get("dir", "desc") == "desc"
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
        "index.html", rows=rows[start:start + per_page], found=len(rows), kpis=kpis, reviews=load_reviews(),
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
                           review=load_reviews().get(claim_id), agent_mode=agent.modo_efectivo(),
                           modelos=agent.listar_modelos(), modelo_def=cfg.opcional("OLLAMA_MODEL"),
                           arq_def=cfg.get("AGENT_ARCH"),
                           corridas_caso=[c for c in corridas.cargar() if c["claimId"] == claim_id][::-1][:15],
                           cmp=corridas.comparativa([c for c in corridas.cargar() if c["claimId"] == claim_id]),
                           back=request.args.get("back") or url_for("index"))


@app.route("/reclamaciones/<claim_id>/revision", methods=["POST"])
def start_review(claim_id):
    """Botón «Revisar con el agente»: arranca el proceso en segundo plano."""
    if not any(c["id"] == claim_id for c in load_claims()):
        abort(404)
    current = load_reviews().get(claim_id)
    if current and current.get("estado") == "en_proceso":
        return jsonify(current), 409
    body = request.get_json(silent=True) or {}
    arq = body.get("arquitectura")
    if arq not in agent.ARQUITECTURAS + ("todas",):
        arq = None
    modelo = body.get("modelo")
    if modelo:
        modelos = agent.listar_modelos()
        if modelo not in modelos and modelo != cfg.opcional("OLLAMA_MODEL"):
            return jsonify({"error": "modelo no disponible"}), 400
    tecnologias = corridas.TECNOLOGIAS if arq == "todas" else (arq,)
    runs = []
    for t in tecnologias:
        opts = {}
        if t:
            opts["arquitectura"] = t
        if t == "claude_sdk":  # solo Claude: ignora el modelo de Ollama elegido
            opts["motor"] = "claude"
        else:
            if body.get("motor") in ("reglas", "ollama", "claude"):
                opts["motor"] = body["motor"]
            elif t in agent.ARQ_EXTERNAS:
                opts["motor"] = "ollama"  # LangGraph y Pydantic AI usan el LLM de Ollama
            if modelo:
                opts["modelo"] = modelo
        runs.append(opts)
    started = datetime.now().isoformat(timespec="seconds")
    _save_review(claim_id, {"estado": "en_proceso", "iniciada": started})
    threading.Thread(target=_run_review, args=(claim_id, started, runs), daemon=True).start()
    return jsonify({"estado": "en_proceso", "iniciada": started}), 202


@app.route("/api/revisiones/<claim_id>")
def api_review(claim_id):
    return jsonify(load_reviews().get(claim_id, {"estado": "sin_revisar"}))


@app.route("/api/revisiones")
def api_reviews():
    return jsonify(load_reviews())


@app.route("/estadisticas")
def stats_page():
    todas = corridas.cargar()
    return render_template("estadisticas.html", filas=corridas.resumen(todas), total=len(todas),
                           ultimas=todas[::-1][:25])


@app.route("/api/estadisticas")
def api_stats():
    todas = corridas.cargar()
    return jsonify({"resumen": corridas.resumen(todas), "corridas": todas})


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
