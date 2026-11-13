"""Estadísticas de corridas del agente, SOLO EN MEMORIA (nada se guarda en archivo ni en base de datos).

Lo usa bench.py para comparar modelos y arquitecturas; la web hace lo mismo en el navegador (static/agente.js).
Cada corrida es un dict {"claimId", "veredicto", "stats": {...}} como el que devuelve agent.revisar().
"""


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


# Las tres tecnologías que se comparan.
TECNOLOGIAS = ("langgraph", "pydantic_ai", "claude_sdk")
