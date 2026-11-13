"""Registro de corridas del agente y estadísticas agregadas para comparar modelos y arquitecturas."""
import json
import threading
import uuid
from datetime import datetime

import config as cfg

_lock = threading.Lock()


def archivo():
    return cfg.ruta("CORRIDAS_FILE")


def registrar(claim, resultado, iniciada):
    """Añade una corrida al historial (una línea JSON por corrida)."""
    reg = {"id": uuid.uuid4().hex[:10], "claimId": claim["id"], "tipo": claim["tipoReclamacion"],
           "iniciada": iniciada, "finalizada": datetime.now().isoformat(timespec="seconds"),
           "veredicto": resultado["veredicto"], "importeAPagar": resultado.get("importeAPagar"),
           "nota": resultado.get("nota"), "stats": resultado["stats"]}
    with _lock, open(archivo(), "a", encoding="utf-8") as f:
        f.write(json.dumps(reg, ensure_ascii=False) + "\n")
    return reg


def cargar():
    try:
        with open(archivo(), encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]
    except FileNotFoundError:
        return []


def _pct(valores, p):
    """Percentil por rango más cercano."""
    if not valores:
        return None
    v = sorted(valores)
    return v[min(len(v) - 1, max(0, -(-p * len(v) // 100) - 1))]


def _media(valores):
    return round(sum(valores) / len(valores), 1) if valores else None


def resumen(corridas):
    """Agrupa por (arquitectura, modelo) y calcula las métricas de comparación.

    Una corrida que cayó al revisor por reglas (fallback) NO entra en las métricas de «reglas»: se cuenta
    como fallo de la variante que se quería probar, para no mezclar tiempos de variantes distintas.
    """
    grupos = {}
    for c in corridas:
        s = c["stats"]
        if s.get("fallback") and s.get("intento"):
            clave = (s["intento"]["arquitectura"], s["intento"].get("modelo") or "—")
        else:
            clave = (s["arquitectura"], s.get("modelo") or "—")
        grupos.setdefault(clave, []).append(c)
    filas = []
    for (arq, modelo), todas in grupos.items():
        cs = [c for c in todas if not c["stats"].get("fallback")]
        dur = [c["stats"]["duracionSeg"] for c in cs]
        ac = [c["stats"]["acuerdoVeredicto"] for c in cs if c["stats"].get("acuerdoVeredicto") is not None]
        comp = sum(c["stats"].get("lineasComparables", 0) for c in cs)
        lin = sum(c["stats"].get("lineasAcuerdo", 0) for c in cs)
        filas.append({
            "arquitectura": arq, "modelo": modelo, "corridas": len(cs),
            "reclamaciones": len({c["claimId"] for c in cs}),
            "medianaSeg": _pct(dur, 50), "p95Seg": _pct(dur, 95), "maxSeg": max(dur) if dur else None,
            "llamadas": _media([c["stats"]["llamadas"] for c in cs]),
            "tokensEntrada": _media([c["stats"]["tokensEntrada"] for c in cs]),
            "tokensSalida": _media([c["stats"]["tokensSalida"] for c in cs]),
            "acuerdoVeredicto": round(100 * sum(ac) / len(ac)) if ac else None,
            "acuerdoLineas": round(100 * lin / comp) if comp else None,
            "veredictos": {v: sum(c["veredicto"] == v for c in cs) for v in ("Aprobado", "Rechazado", "Validar")},
            "fallbacks": len(todas) - len(cs),
        })
    filas.sort(key=lambda f: (f["medianaSeg"] is None, f["medianaSeg"] or 0))
    return filas
