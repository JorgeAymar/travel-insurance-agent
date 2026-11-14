# Portal de reclamaciones de seguros de viaje

[English](README.md)

App web en Flask que lista reclamaciones, pólizas y cláusulas de seguros de viaje leídas de archivos JSON en disco,
y permite ejecutar un **agente de revisión con IA** sobre cada reclamación. El agente comprueba el caso línea por
línea contra las cláusulas de la póliza y emite un veredicto: **Aprobado**, **Rechazado** o **Validar** (necesita a
una persona; el agente añade un comentario con lo que hay que comprobar). Todos los datos son ficticios.

> La documentación completa está en [docs/DOCUMENTACION.md](docs/DOCUMENTACION.md).

## Qué hace

- **Listado de reclamaciones**: hasta `MAX_RECLAMACIONES` (100) leídas de `data/claims.json`; busca por ID, tipo,
  cliente, póliza, destino o texto del relato (sin distinguir acentos ni mayúsculas), filtra por tipo, ordena y pagina.
- **Ficha de reclamación**: relato detallado (quién, qué, cuándo, dónde, cómo, cuánto), desglose del importe, la
  cláusula aplicable con sus requisitos de pago y el % de pago por situación, póliza, pagos y documentación.
- **Pólizas**: 120 pólizas con planes, coberturas, pagos de la prima (algunos impagados) y 20 cláusulas.
- **Agente de revisión** con tres tecnologías intercambiables, todas con el **mismo LLM de Ollama**:

| Tecnología | Cómo trabaja |
|---|---|
| **LangGraph** | Un grafo con un nodo por requisito y otro de veredicto; los requisitos corren en paralelo (`LANGGRAPH_CONCURRENCIA`) y se marcan en vivo. |
| **Pydantic AI** | Una sola consulta con salida tipada (modelos Pydantic) y reintento automático si la salida no valida. |
| **Claude Agent SDK** | El agente *no* recibe los datos: los busca y lee él con `Read`/`Grep`, en copias saneadas dentro de una carpeta temporal. |

**Criterio de decisión** (el mismo para el revisor por reglas y los tres agentes): (1) el pago de la prima de la
póliza está al día; (2) la reclamación se valida contra las cláusulas del seguro (póliza en vigor, cobertura
incluida, situación con derecho a pago, plazo, documentación, requisitos de la cobertura y exclusiones); (3) se
decide: se paga (Aprobado), no se paga (Rechazado) o se debe revisar a mano (Validar). El agente no juzga si la
historia es verosímil o extraña.

Cada ficha tiene un botón por tecnología y **Ejecutar las 3 y comparar**, que muestra veredicto, importe, duración,
llamadas, tokens, acuerdo con el revisor por reglas y una matriz por línea con las discrepancias resaltadas. El
listado tiene un selector de tecnología y un botón *Revisar* en cada fila. También hay dos arquitecturas de línea
base (línea por línea y una sola llamada) y un revisor determinista por reglas.

## Los resultados del agente son virtuales

Los resultados se emiten al navegador mientras se calculan y viven **solo en la página**. No se guarda nada en
archivo ni en base de datos (tampoco en `localStorage` ni `sessionStorage`); **al refrescar la página todo vuelve al
estado inicial**. Si el navegador se va a mitad de una revisión, el servidor la descarta. `bench.py` imprime su
resumen y tampoco guarda nada.

## Puesta en marcha

```bash
pip install -r requirements.txt
pip install -r requirements-extra.txt   # LangGraph, Pydantic AI y Claude Agent SDK (opcional)
cp .env.example .env                    # y rellena los valores
sh scripts/instalar_hooks.sh            # activa la validación de datos privados en commit y push
python3 generate_data.py                # regenera los JSON ficticios (opcional)
python3 app.py                          # escucha en HOST:PORT del .env
```

Para usar los agentes hace falta un servidor Ollama (`OLLAMA_URL`, `OLLAMA_TOKEN`, `OLLAMA_MODEL`). El Claude Agent
SDK necesita que el servidor acepte el protocolo de mensajes de Anthropic, cosa que Ollama hace. Con
`AGENT_MODE=reglas` la app funciona sin ningún LLM, con el revisor por reglas.

## Configuración

**Todo lo variable vive en el `.env`; el código no tiene valores por defecto.** Si falta una variable obligatoria,
la app no arranca y dice cuáles faltan. `.env.example` documenta todas las variables sin secretos. Grupos
principales:

| Grupo | Variables |
|---|---|
| App y servidor | `APP_NAME`, `APP_TAGLINE`, `APP_USER_NAME`, `APP_USER_ROLE`, `HOST`, `PORT`, `FLASK_DEBUG`, `PER_PAGE_OPTIONS` |
| Datos | `CLAIMS_FILE`, `POLICIES_FILE`, `CLAUSES_FILE`, `MAX_RECLAMACIONES` |
| Agente | `AGENT_MODE`, `AGENT_ARCH`, `MAX_CORRIDAS_SIMULTANEAS`, `IMPORTE_ALTO_VALIDAR`, `PLAZO_RECLAMACION_DIAS` |
| Ollama | `OLLAMA_URL`, `OLLAMA_TOKEN`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`, `OLLAMA_REINTENTOS`, `OLLAMA_TEMPERATURE` |
| Tecnologías | `LANGGRAPH_CONCURRENCIA`, `PYDANTIC_REINTENTOS`, `CLAUDE_SDK_MAX_TURNOS`, `CLAUDE_SDK_HERRAMIENTAS` |

## Benchmark y tests

```bash
python bench.py --n 10 --reglas --arq langgraph,pydantic_ai,claude_sdk   # compara tecnologías e imprime un resumen
python3 -m unittest discover -s tests                                     # tests de regresión y aislamiento
```

El acuerdo con el revisor por reglas es una referencia, no la verdad absoluta: el revisor por reglas es determinista
pero no juzga las exclusiones de las cláusulas (eso lo hace solo el LLM, y nunca rechaza por sí solo), y los veredictos de un LLM pueden variar entre corridas
aunque la temperatura sea 0.

## Seguridad: nada privado llega a GitHub

`scripts/validar_subida.py` se ejecuta en cada commit y push (mediante `.githooks/`) y bloquea la operación si
encuentra secretos, tokens, URLs, IPs o valores por defecto fijos en el código, correos reales, rutas personales,
archivos como `.env`, o cualquier valor de tu `.env` local dentro de un archivo versionado. Revisa todos los commits
que se suben, no solo el último. Se puede ejecutar a mano con `python3 scripts/validar_subida.py --todo`. Los hooks
son locales: cada clon debe ejecutar `sh scripts/instalar_hooks.sh`.

## Estructura del proyecto

| Ruta | Para qué sirve |
|---|---|
| `app.py` | Rutas de Flask, filtros, paginación y el flujo en directo de la revisión |
| `agent.py` | Agente de revisión: líneas a comprobar, revisor por reglas, llamadas al LLM y estadísticas |
| `arq_langgraph.py`, `arq_pydantic_ai.py`, `arq_claude_sdk.py` | Las tres tecnologías que se comparan |
| `config.py` | Lee y valida el `.env`; único sitio donde se lee `os.environ` |
| `static/agente.js` | Cliente del navegador: recibe el flujo y dibuja líneas, veredicto, estadísticas y comparación |
| `generate_data.py` | Genera las reclamaciones, pólizas y cláusulas ficticias |
| `corridas.py`, `bench.py` | Estadísticas en memoria y el benchmark por línea de comandos |
| `scripts/`, `.githooks/` | Validación de datos privados y sus hooks de git |
| `tests/` | Tests de regresión y aislamiento |
