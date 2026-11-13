"""Benchmark: corre el agente sobre N reclamaciones con varios modelos y arquitecturas.

Ejemplo:
  python bench.py --n 10 --modelos modelo1,modelo2 --arq lineas,una_llamada --reglas
Cada corrida se guarda en el archivo CORRIDAS_FILE del .env y se ve en /estadisticas.
Los valores por defecto de los argumentos salen del .env (BENCH_*).
Usa las MISMAS reclamaciones para todas las variantes, para que la comparación sea justa.
"""
import argparse
import json
import os
import random
import sys

import agent
import config as cfg
import corridas


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=cfg.entero("BENCH_N"), help="número de reclamaciones")
    ap.add_argument("--semilla", type=int, default=cfg.entero("BENCH_SEMILLA"), help="semilla para elegir las reclamaciones")
    ap.add_argument("--modelos", default=cfg.opcional("BENCH_MODELOS") or cfg.opcional("OLLAMA_MODEL"), help="modelos de Ollama separados por coma")
    ap.add_argument("--arq", default=cfg.get("BENCH_ARQ"), help="arquitecturas: lineas, una_llamada")
    ap.add_argument("--reglas", action="store_true", help="incluir también el revisor por reglas (sin LLM)")
    ap.add_argument("--repeticiones", type=int, default=cfg.entero("BENCH_REPETICIONES"), help="veces que se repite cada combinación")
    a = ap.parse_args()

    claims = json.load(open(cfg.ruta("CLAIMS_FILE"), encoding="utf-8"))[:cfg.entero("MAX_RECLAMACIONES")]
    pols = {p["numero"]: p for p in json.load(open(cfg.ruta("POLICIES_FILE"), encoding="utf-8"))}
    clau = {c["codigo"]: c for c in json.load(open(cfg.ruta("CLAUSES_FILE"), encoding="utf-8"))}
    muestra = random.Random(a.semilla).sample(claims, min(a.n, len(claims)))

    variantes = [("reglas", None, "reglas")] if a.reglas else []
    for m in [x for x in a.modelos.split(",") if x]:
        for arq in a.arq.split(","):
            variantes.append(("ollama", m, arq))
    if not variantes:
        sys.exit("No hay variantes: indica --modelos y/o --reglas")

    os.environ["AGENT_STEP_DELAY"] = cfg.get("BENCH_STEP_DELAY")  # sin pausa entre líneas al medir
    total = len(variantes) * len(muestra) * a.repeticiones
    n = 0
    for motor, modelo, arq in variantes:
        for _ in range(a.repeticiones):
            for c in muestra:
                n += 1
                try:
                    r = agent.revisar(c, pols[c["numeroPoliza"]], clau, motor=motor, modelo=modelo, arquitectura=arq)
                    corridas.registrar(c, r, r.get("iniciada") or "")
                    s = r["stats"]
                    print(f"[{n}/{total}] {c['id']} {s['arquitectura']:<11} {str(s['modelo']):<26} {r['veredicto']:<9} "
                          f"{s['duracionSeg']:>6.1f}s {s['llamadas']} llamadas{' (FALLBACK)' if s['fallback'] else ''}", flush=True)
                except Exception as e:
                    print(f"[{n}/{total}] {c['id']} ERROR {type(e).__name__}: {e}", flush=True)
    print("\nResumen:")
    for f in corridas.resumen(corridas.cargar()):
        print(f"  {f['arquitectura']:<11} {f['modelo']:<26} n={f['corridas']:<3} mediana={f['medianaSeg']}s p95={f['p95Seg']}s "
              f"acuerdo veredicto={f['acuerdoVeredicto']}% líneas={f['acuerdoLineas']}% fallos={f['fallbacks']}")


if __name__ == "__main__":
    main()
