"""Arquitectura «pydantic_ai»: una sola ejecución de un Agent de Pydantic AI con salida tipada.

A diferencia de `una_llamada` (que interpreta el JSON de forma tolerante con `_extraer_json`), aquí la respuesta
se valida contra modelos Pydantic y, si no valida, Pydantic AI reintenta solo (PYDANTIC_REINTENTOS).
Solo habla con Ollama, mediante su API compatible con OpenAI. Contrato: ver «Contrato de cada módulo» en agent.py.
"""
import asyncio
import json
import time
from typing import Literal

import httpx
import pydantic_ai
from openai import AsyncOpenAI
from pydantic import BaseModel
from pydantic_ai import Agent, PromptedOutput
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

import agent
import config as cfg

RUTA_OPENAI = "/v1"  # la API compatible con OpenAI de Ollama cuelga de esta ruta del servidor (sin esquema ni host)


class LineaRevisada(BaseModel):
    id: str
    estado: Literal["cumple", "no_cumple", "duda"]
    detalle: str


class Revision(BaseModel):
    lineas: list[LineaRevisada]
    veredicto: Literal["Aprobado", "Rechazado", "Validar"]
    motivo: str
    comentario: str


def _cliente():
    """Cliente OpenAI hacia Ollama: User-Agent propio (el servidor veta el de Python) y reintentos 429/5xx."""
    return AsyncOpenAI(
        base_url=cfg.get("OLLAMA_URL").rstrip("/") + RUTA_OPENAI,
        api_key=cfg.get("OLLAMA_TOKEN"),
        default_headers={"User-Agent": cfg.get("AGENT_USER_AGENT")},
        max_retries=cfg.entero("OLLAMA_REINTENTOS"),  # el cliente respeta Retry-After y espera entre intentos
        timeout=httpx.Timeout(cfg.decimal("OLLAMA_TIMEOUT")),
    )


def _agente(nombre, cliente):
    return Agent(
        OpenAIChatModel(nombre, provider=OpenAIProvider(openai_client=cliente)),
        # PromptedOutput: el esquema va en el prompt y la respuesta se valida con Pydantic (ver informe: es el único modo fiable con Gemma)
        output_type=PromptedOutput(Revision),
        instructions=agent.SISTEMA_UNA,
        retries=cfg.entero("PYDANTIC_REINTENTOS"),
        model_settings={"temperature": cfg.decimal("OLLAMA_TEMPERATURE")},
    )


async def _ejecutar(nombre, usuario):
    cliente = _cliente()
    try:
        return await _agente(nombre, cliente).run(usuario)
    finally:
        await cliente.close()  # dentro del bucle de eventos: si no, al cerrarlo salen errores de «Event loop is closed»


def correr(spec, claim, policy, clauses, llm, med, avisar, motor, modelo):
    if motor != "ollama":
        raise RuntimeError("La arquitectura pydantic_ai solo está implementada para el motor Ollama.")
    modelo = modelo or cfg.get("OLLAMA_MODEL")
    for l in spec:
        l["estado"] = "analizando"
    avisar("Analizando todas las líneas con Pydantic AI (salida tipada)")
    pedido = {"lineas": [{"id": l["id"], "requisito": l["requisito"], "criterio": l["criterio"], "bloqueante": l["bloqueante"]} for l in spec]}
    usuario = ("LÍNEAS A EVALUAR:\n" + json.dumps(pedido, ensure_ascii=False) + "\n\nDATOS DEL CASO:\n"
               + json.dumps(agent._contexto(claim, policy, clauses), ensure_ascii=False))
    t = time.time()
    resultado = asyncio.run(_ejecutar(modelo, usuario))  # la corrida va en un hilo sin event loop
    seg = round(time.time() - t, 2)
    uso = resultado.usage
    med.llamadas += uso.requests
    med.entrada += uso.input_tokens
    med.salida += uso.output_tokens
    rev = resultado.output
    por_id = {x.id: x for x in rev.lineas}
    for l in spec:
        x = por_id.get(l["id"])
        l["estado"] = x.estado if x else "duda"
        l["detalle"] = (x.detalle.strip() if x else "") or "El modelo no evaluó esta línea."
        if l["regla"]:
            l["referencia"] = l["regla"]()[0]
    avisar("Líneas marcadas")
    veredicto = agent._ajustar_veredicto(claim, spec, {"veredicto": rev.veredicto, "motivo": rev.motivo, "comentario": rev.comentario})
    info = {"tipo": "ollama", "modelo": modelo, "framework": "pydantic-ai " + pydantic_ai.__version__}
    return veredicto, info, [{"id": "(todas)", "seg": seg}], 0.0
