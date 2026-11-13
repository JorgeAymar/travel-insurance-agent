"""App Flask que lista reclamaciones de seguros de viaje desde un JSON en disco."""
import json
import os
import tempfile
import threading
from datetime import datetime

from dotenv import load_dotenv
import agent
from flask import Flask, abort, jsonify, render_template, request, url_for

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))  # las variables ya definidas en el entorno tienen prioridad

app = Flask(__name__)
app.jinja_env.globals.update(max=max, min=min)


@app.template_global()
def page_url(state, **changes):
    """URL del listado conservando filtros/orden y aplicando los cambios dados."""
    return url_for("index", **{**state, **changes})
DATA_DIR = os.path.join(BASE_DIR, "data")


def _path(var, default):
    """Ruta desde la variable de entorno (relativa al proyecto si no es absoluta)."""
    return os.path.join(BASE_DIR, os.environ.get(var, default))


DATA_FILE = _path("CLAIMS_FILE", "data/claims.json")
POLICIES_FILE = _path("POLICIES_FILE", "data/polizas.json")
CLAUSES_FILE = _path("CLAUSES_FILE", "data/clausulas.json")
REVIEWS_FILE = _path("REVIEWS_FILE", "data/revisiones.json")

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


def _run_review(claim_id, started):
    """Proceso del agente (hilo): carga los datos, revisa y guarda el veredicto."""
    try:
        claim = next(c for c in load_claims() if c["id"] == claim_id)
        policy = next(p for p in load_policies() if p["numero"] == claim["numeroPoliza"])
        def progreso(lineas, fase):  # el agente avisa cada vez que marca una línea
            _save_review(claim_id, {"estado": "en_proceso", "iniciada": started, "lineas": lineas, "fase": fase})

        result = agent.revisar(claim, policy, load_clauses(), on_progress=progreso)
        _save_review(claim_id, {"estado": "completada", "iniciada": started,
                                "finalizada": datetime.now().isoformat(timespec="seconds"), **result})
    except Exception as e:  # el proceso nunca debe quedarse «en proceso» para siempre
        _save_review(claim_id, {"estado": "error", "iniciada": started, "error": f"{type(e).__name__}: {e}"})

PER_PAGE_OPTIONS = (10, 25, 50, 100)


def _load(path):
    # Se lee en cada petición: editar el JSON y recargar basta para ver cambios.
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_claims():
    return _load(DATA_FILE)


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
    per_page = a.get("n", 10, type=int)
    per_page = per_page if per_page in PER_PAGE_OPTIONS else 10

    rows = [
        c for c in claims
        if (not tipo or c["tipoReclamacion"] == tipo)
        and (not q or q.lower() in c["nombreCliente"].lower() or q.lower() in c["id"].lower()
             or q.lower() in c["numeroPoliza"].lower())
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
        state=state, sort=sort, desc=desc,
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
                           back=request.args.get("back") or url_for("index"))


@app.route("/reclamaciones/<claim_id>/revision", methods=["POST"])
def start_review(claim_id):
    """Botón «Revisar con el agente»: arranca el proceso en segundo plano."""
    if not any(c["id"] == claim_id for c in load_claims()):
        abort(404)
    current = load_reviews().get(claim_id)
    if current and current.get("estado") == "en_proceso":
        return jsonify(current), 409
    started = datetime.now().isoformat(timespec="seconds")
    _save_review(claim_id, {"estado": "en_proceso", "iniciada": started})
    threading.Thread(target=_run_review, args=(claim_id, started), daemon=True).start()
    return jsonify({"estado": "en_proceso", "iniciada": started}), 202


@app.route("/api/revisiones/<claim_id>")
def api_review(claim_id):
    return jsonify(load_reviews().get(claim_id, {"estado": "sin_revisar"}))


@app.route("/api/revisiones")
def api_reviews():
    return jsonify(load_reviews())


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
                           plan=plan, planes=["Básico", "Estándar", "Premium"],
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
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 5001)),
            debug=os.environ.get("FLASK_DEBUG", "1") == "1")
