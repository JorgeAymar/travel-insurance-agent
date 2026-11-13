"""Arquitectura «langgraph»: el análisis línea por línea orquestado como un grafo de LangGraph.

Topología (se construye en cada corrida, porque el número de líneas varía):
    START ──► linea_<id> (una por línea, en paralelo) ──► veredicto ──► END
La concurrencia máxima sale de LANGGRAPH_CONCURRENCIA (max_concurrency de la ejecución).
"""
import json
import operator
import threading
import time
from importlib import metadata
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

import agent
import config as cfg


def _fusionar(a, b):
    """Reducer: fusiona los dicts de nodos paralelos por id de línea."""
    return {**(a or {}), **(b or {})}


class Estado(TypedDict):
    lineas: Annotated[dict, _fusionar]
    tiempos: Annotated[list, operator.add]
    veredicto: dict
    veredicto_seg: float
    info: dict


def correr(spec, claim, policy, clauses, llm, med, avisar, motor, modelo):
    if llm is None:
        raise RuntimeError("La arquitectura langgraph necesita un LLM (ollama o claude); con el motor de reglas no se puede usar.")
    ctx = json.dumps(agent._contexto(claim, policy, clauses), ensure_ascii=False)
    cerrojo = threading.Lock()  # med se incrementa desde varios hilos
    info_linea = {}

    # Contadores locales por consulta, sumados al Medidor bajo cerrojo.
    def consultar(sistema, usuario):
        m = agent.Medidor()
        j, info = agent._preguntar(llm, sistema, usuario, m)
        with cerrojo:
            med.llamadas += m.llamadas
            med.entrada += m.entrada
            med.salida += m.salida
        return j, info

    def nodo_linea(l):
        def ejecutar(_estado):
            t = time.time()
            l["estado"] = "analizando"
            j, info = consultar(agent.SISTEMA_LINEA,
                                f"REQUISITO A EVALUAR: {l['requisito']}\nCRITERIO: {l['criterio']}\n\nDATOS DEL CASO:\n{ctx}")
            info_linea.update(info)
            estado = j.get("estado")
            l["estado"] = estado if estado in agent.ESTADOS_LINEA else "duda"
            l["detalle"] = str(j.get("detalle", "")).strip() or "Sin detalle."
            if l["regla"]:
                l["referencia"] = l["regla"]()[0]
            seg = round(time.time() - t, 2)
            return {"lineas": {l["id"]: l["estado"]}, "tiempos": [{"id": l["id"], "seg": seg}]}
        return ejecutar

    def nodo_veredicto(_estado):
        t = time.time()
        v, info = agent._veredicto_llm(llm, claim, spec, med)
        return {"veredicto": v, "info": info, "veredicto_seg": round(time.time() - t, 2)}

    g = StateGraph(Estado)
    ids = []
    for l in spec:
        nombre = f"linea_{l['id']}"
        ids.append(nombre)
        g.add_node(nombre, nodo_linea(l))
        g.add_edge(START, nombre)
    g.add_node("veredicto", nodo_veredicto)
    g.add_edge(ids, "veredicto")  # fan-in: espera a que terminen todas las líneas
    g.add_edge("veredicto", END)
    grafo = g.compile()

    por_nombre = dict(zip(ids, spec))
    config = {"max_concurrency": cfg.entero("LANGGRAPH_CONCURRENCIA")}
    avisar("Ejecutando el grafo de LangGraph")
    hechas, final = 0, {}
    for paso in grafo.stream({"lineas": {}, "tiempos": []}, config, stream_mode="updates"):
        for nombre, salida in paso.items():
            if nombre == "veredicto":
                final.update(salida)
                avisar("Veredicto emitido")
            else:
                hechas += 1
                final.setdefault("tiempos", []).extend(salida["tiempos"])
                avisar(f"Línea {hechas} de {len(spec)} marcada: {por_nombre[nombre]['requisito']}")
    if "veredicto" not in final:
        raise RuntimeError("El grafo de LangGraph terminó sin veredicto.")
    info = dict(final["info"])
    info["framework"] = f"langgraph {metadata.version('langgraph')}"
    return final["veredicto"], info, final["tiempos"], final["veredicto_seg"]
