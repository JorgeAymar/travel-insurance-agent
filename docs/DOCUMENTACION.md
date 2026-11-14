---
title: "Portal de Reclamaciones de Seguros de Viaje"
subtitle: "Documentación del proyecto"
lang: es
---

# 1. Qué es

Aplicación web, hecha con **Python y Flask**, que lista y muestra el detalle de reclamaciones de clientes de un seguro de viaje. Todos los datos salen de **ficheros JSON en disco**; no hay base de datos. Los datos son **ficticios**.

El objetivo es que cada reclamación llegue con toda la información necesaria para ser analizada después por un **agente**: quién, qué, cuándo, dónde, cómo y cuánto, la póliza del cliente, sus pagos y las cláusulas que dicen cuándo y cuánto paga el seguro.

# 2. Cómo ejecutarla

```bash
git clone <repositorio> && cd travel-insurance-agent
pip install -r requirements.txt
pip install -r requirements-extra.txt   # LangGraph, Pydantic AI y Claude Agent SDK
cp .env.example .env         # y rellena los valores (ver sección 11)
sh scripts/instalar_hooks.sh # activa la validación de datos privados al hacer commit y push
python3 generate_data.py     # regenera los JSON de ejemplo (opcional)
python3 app.py               # escucha en el HOST y PORT del .env
```

- **Toda la configuración vive en el `.env`**; el código no tiene valores por defecto. Si falta una variable obligatoria, la app no arranca y dice cuáles faltan.
- Los JSON se leen en **cada petición**: editar un fichero y recargar la página basta para ver los cambios.
- El puerto 5000 lo usa AirPlay Receiver en macOS; por eso el ejemplo usa otro.

# 3. Estructura del proyecto

| Ruta | Contenido |
|---|---|
| `app.py` | Servidor Flask: rutas, filtros, paginación, proceso de revisión en segundo plano |
| `agent.py` | Agente de revisión (reglas, Ollama o Claude; cinco arquitecturas) y sus estadísticas |
| `arq_langgraph.py`, `arq_pydantic_ai.py`, `arq_claude_sdk.py` | Las tres tecnologías que se comparan: LangGraph, Pydantic AI y Claude Agent SDK |
| `requirements-extra.txt` | Dependencias opcionales de esas tres tecnologías |
| `corridas.py` | Agregación **en memoria** de corridas (lo usa `bench.py`); no guarda nada |
| `static/agente.js` | Cliente del agente en el navegador: recibe la revisión en directo y dibuja líneas, veredicto, estadísticas y comparación |
| `tests/` | Tests de regresión (`python3 -m unittest discover -s tests`) |
| `bench.py` | Benchmark: corre el agente sobre las mismas reclamaciones con varios modelos y arquitecturas y resume en pantalla |
| `config.py` | Lee y valida el `.env`; único sitio donde se lee `os.environ` |
| `generate_data.py` | Genera los tres JSON con datos ficticios coherentes entre sí |
| `data/claims.json`, `polizas.json`, `clausulas.json` | 200 reclamaciones, 120 pólizas y 20 cláusulas de ejemplo |
| `templates/`, `static/style.css` | Plantillas y estilos (tema claro y oscuro) |
| `scripts/validar_subida.py` | Validación de datos privados y configuración fija antes de subir a GitHub |
| `.githooks/` | Hooks `pre-commit` y `pre-push` que ejecutan esa validación |
| `.env.example` | Plantilla pública de variables (sin secretos); el `.env` real no se sube |
| `docs/` | Esta documentación |

# 4. Pantallas y rutas

| Ruta | Qué muestra |
|---|---|
| `/` | Listado de reclamaciones (máximo `MAX_RECLAMACIONES`) con buscador (ID, tipo, cliente, póliza, destino y texto del relato, sin distinguir mayúsculas ni acentos), filtro por tipo, orden por columna y paginación. Permite revisar desde cada fila (con el último agente usado) y **revisar en lote**: el campo «Máximo de reclamaciones a revisar (X)» **siempre arranca en 5** (`ANALISIS_RECLAMACIONES_DEFECTO`; entre 1 y el total del listado filtrado, y se ajusta si se sale de rango). Al pulsar un botón de agente (LangGraph, Pydantic AI o Claude Agent SDK) se pide **confirmación**; si se acepta, revisa en secuencia las primeras X reclamaciones del listado filtrado (aunque no estén en la página) para ver si aplica devolución, con un botón «Detener». Pinta el cuadro **«Resultado de la ejecución»** con, por cada reclamación: fecha de ejecución, ID, tipo, agente, estado, si aplica devolución (Sí / No / Revisar a mano), importe a devolver y el comentario del agente |
| `/reclamaciones/<id>` | **Ficha** de una reclamación; se abre al hacer clic en una fila |
| `/polizas` | Listado de pólizas con búsqueda por póliza, tomador o DNI y filtro por plan |
| `/polizas/<número>` | Ficha de póliza: requisitos de pago, coberturas, cláusulas, pagos y reclamaciones |
| `/analisis` | **Análisis de las reclamaciones**: un campo numérico limita cuántas se ejecutan (valor inicial `ANALISIS_RECLAMACIONES_DEFECTO`, entre 1 y el total; si pones algo fuera de rango se ajusta). Ejecuta las 3 tecnologías **de forma secuencial** (una corrida cada vez: Pydantic AI → Claude Agent SDK → LangGraph, reclamación a reclamación; al final repite lo que haya fallado) y las compara con la referencia: acierto, aprobaciones indebidas, matrices de confusión, acierto por comprobación, lista con las discrepancias y la causa de cada error. Todo en el navegador y virtual |
| `/api/referencia` | Veredicto del revisor por reglas de cada reclamación (la referencia del análisis); se calcula al momento y no se guarda |
| `/reclamaciones/<id>/revision` (POST) | Ejecuta UNA revisión y la emite en directo (una línea JSON por evento). Exige `{"arquitectura": ...}`; si no, 400. Máximo `MAX_CORRIDAS_SIMULTANEAS` a la vez (429 si se supera) |
| `/api/claims`, `/api/policies`, `/api/clauses` | Los datos en JSON |

## 4.1 Listado de reclamaciones

Columnas: ID, tipo de reclamación, fecha de ingreso, abierto por el cliente, canal, inicio y fin del viaje, y destino. A propósito **no** se muestran el cliente, la póliza, los pagos, el importe ni el estado: esa información está en la ficha.

## 4.2 Ficha de reclamación

1. **Glosa**: relato completo en cuatro párrafos: el suceso (quién, cuándo, dónde y qué), la **declaración del asegurado** en primera persona, cómo se gestionó (con la referencia oficial, por ejemplo la denuncia) y cuánto se reclama con su cobertura.
2. **Resumen en seis cuadros**: quién, qué, cuándo, dónde, cómo se gestionó y cuánto.
3. **Desglose del importe** reclamado por conceptos, con el límite de cobertura y la franquicia.
4. **Cláusula aplicable**: texto, requisitos para que el seguro pague, tabla de % de pago (con la situación del caso resaltada) y exclusiones.
5. **Datos del cliente, del suceso, de la póliza y del viaje**, terceros implicados, documentación recibida o pendiente y pagos de la póliza.

## 4.3 Ficha de póliza

Abre con **«Qué debe cumplirse para que el seguro pague»**. Después, para cada cobertura contratada: requisitos específicos, tabla de situaciones con su **% de pago**, límite y franquicia, y exclusiones. Incluye también las cláusulas generales, los pagos de la prima y las reclamaciones de esa póliza.

# 5. Modelo de datos

**Reclamación** (`claims.json`): `id`, `tipoReclamacion` (50 tipos), datos del cliente, `numeroPoliza`, `planPoliza`, `pagosAlDia`, `fechaIngreso`, `casoAbiertoPorCliente`, `canal`, fechas y destino del viaje, `incidente` (fecha, hora, lugar, referencia oficial), `glosa`, `declaracion`, `hechos`, `desglose`, `cobertura`, `situacion` (nombre y %), `calculo`, `requisitos`, `terceros`, `documentos`, `historial`, y los campos de resultado (`estado`, `importeAprobado`, `motivoRechazo`, `comprobaciones`).

**Póliza** (`polizas.json`): `numero`, `plan`, `tomador`, `acompanantes`, `viaje` (destino, inicio, fin), `fechaContratacion`, `prima`, `coberturas` (límite, franquicia y cláusula de cada una), `pagos` (cuotas con fecha, importe y estado), `primaPagada`, `primaPendiente` y `pagosAlDia`.

**Cláusula** (`clausulas.json`): `codigo`, `categoria`, `titulo`, `texto`, `exclusiones`, `plazoReclamacionDias`, `documentosRequeridos`, `requisitos` y `porcentajes` (situación, % y qué se paga).

Los tres ficheros están enlazados: cada reclamación apunta a una póliza (`numeroPoliza`) y cada cobertura de la póliza apunta a una cláusula (`clausula`).

# 6. Reglas de negocio

## 6.1 Planes de la póliza

| Plan | Límites | Coberturas excluidas |
|---|---|---|
| Básico | × 0,5 | Defensa jurídica, equipos electrónicos y servicios prepagados |
| Estándar | × 1 | Defensa jurídica |
| Premium | × 2 | Ninguna |

## 6.2 Requisitos para que el seguro pague

Deben cumplirse **todos** (cláusula G-07):

1. Póliza registrada y en vigor en la fecha del suceso.
2. **Prima al día**: ninguna cuota vencida impagada en la fecha del suceso (cláusula G-06: si no, la cobertura está suspendida).
3. La cobertura reclamada está incluida en el plan contratado.
4. El suceso ocurre dentro del viaje y no está excluido.
5. Se comunica en un máximo de 7 días y se reclama en un máximo de 30 días.
6. Se aporta la documentación original exigida por la cláusula.

Cada cobertura añade sus requisitos específicos (por ejemplo: parte de irregularidad de equipaje, denuncia en 24 horas, autorización previa de la Central de Asistencia).

## 6.3 Cómo se calcula el pago

```
importe a pagar = mín( gasto justificado × % de la situación ,  límite de la cobertura ) − franquicia
```

Cada tipo de reclamación corresponde a una **situación** con su porcentaje. Ejemplos:

| Cobertura | Situación | % de pago |
|---|---|---|
| Transporte | Retraso inferior a 4 horas | 0 % |
| Transporte | Retraso de 4 a 8 horas | 60 % |
| Transporte | Retraso superior a 8 horas | 100 % |
| Equipaje | Daño parcial | 70 % |
| Equipaje | Retraso de 6 a 24 horas | 50 % |
| Robo | Efectivo (máx. 300 €) | 50 % |
| Médica | Asistencia dental urgente | 60 % |
| Médica | Enfermedad preexistente (solo fase aguda) | 50 % |
| Cancelación | Causa grave documentada | 100 % |
| Cancelación | Causa laboral (despido) | 90 % |
| Eventos externos | Huelga o disturbios | 70 % |

Todas las situaciones y porcentajes están en `data/clausulas.json` y se ven en la ficha de cada póliza.

## 6.4 Criterio de decisión del agente

El análisis es el mismo para el revisor por reglas y para los tres agentes con LLM:

1. **El pago de la prima está al día** en la fecha del suceso (ninguna cuota vencida impagada).
2. **La reclamación se valida contra las cláusulas del seguro**: póliza en vigor, cobertura incluida en el plan, situación con derecho a pago (% de pago mayor que 0), plazo de reclamación, documentación completa, requisitos específicos de la cobertura y exclusiones.
3. **Se decide**: se paga (**Aprobado**, con el importe a pagar), no se paga (**Rechazado**) o se debe **revisar a mano** (**Validar**, con un comentario del agente).

Rechazado solo si falla con claridad un requisito bloqueante: prima impagada, póliza fuera de vigencia, cobertura no incluida, situación sin derecho a pago (0 %) o fuera de plazo. Validar si falta documentación, un requisito de la cobertura no está acreditado o hay una exclusión que podría aplicar (ese juicio lo hace el LLM y por eso **nunca rechaza por sí solo**: una persona lo confirma).

El agente **no juzga si la historia es verosímil, extraña o dramática**, ni aplica ninguna regla que no salga de las cláusulas (por ejemplo, no hay umbral de importe alto). El plazo de reclamación se lee de la cláusula de la cobertura, no del `.env`.

# 7. Datos de ejemplo

- **100 reclamaciones** (máximo `MAX_RECLAMACIONES`), **50 tipos** distintos (2 por tipo), **120 pólizas** (56 Estándar, 39 Básico, 25 Premium) y **20 cláusulas**.
- Todas las reclamaciones tienen una póliza registrada (74 de las pólizas tienen reclamaciones).
- **18 pólizas** tienen una cuota vencida impagada, lo que afecta a **19 reclamaciones**.
- **7 reclamaciones** piden una cobertura que no incluye el plan de su póliza.
- Los desgloses suman exactamente el importe reclamado y los pagos suman la prima.
- **Cada tipo de reclamación tiene un suceso inspirado en una película reconocible**, escrito sin nombrar nunca la película, más una declaración del asegurado en primera persona. Sirve para probar al agente con relatos variados y fáciles de identificar.
- Se leen del archivo `CLAIMS_FILE`; si el archivo trae más de `MAX_RECLAMACIONES`, la app solo carga las primeras.

# 8. Decisiones de diseño

- **JSON en disco, sin base de datos**: simple de editar y de sustituir por datos reales.
- **Los resultados del agente son virtuales.** No se persisten en archivo ni base de datos y se pierden al refrescar.
- **El estado y el resultado de ejemplo se ocultan en la web.** Las reclamaciones las va a analizar un agente, así que la interfaz no muestra el estado, el importe aprobado, el motivo de rechazo ni las comprobaciones previas. Esos campos siguen existiendo en `claims.json`.
- **Diseño**: generado con Google Stitch (estilo corporativo en azul marino y cian) y adaptado a Flask, con tema claro y oscuro.
- **Sin dependencias de front-end**: HTML, CSS y una pizca de JavaScript para abrir la ficha al hacer clic en la fila.

# 9. Agente de revisión

Cada reclamación tiene un botón **Revisar con el agente**. Al pulsarlo arranca un proceso en segundo plano que analiza el caso **línea por línea** (requisitos generales de la cláusula G-07, requisitos de la cobertura y un análisis del relato). Cada línea se marca en pantalla, en vivo, como *cumple*, *no cumple* o *duda*. Al final emite el veredicto:

- **Aprobado**: todo cumple. Indica el importe a pagar.
- **Rechazado**: falla un requisito bloqueante (póliza fuera de vigencia, cuota impagada, cobertura no incluida, 0 %, fuera de plazo, exclusión aplicable).
- **Validar**: hay dudas o incumplimientos no bloqueantes. Añade un **comentario del agente** con lo que una persona debe comprobar.

El agente decide solo con los hechos del caso, la póliza y las cláusulas: no ve el estado ni el resultado que traen los datos de ejemplo.

**Modos** (`AGENT_MODE`): `reglas` (determinista, sin LLM), `ollama` (un LLM de un servidor Ollama), `claude` (API de Anthropic) o `auto`. Si un modo con LLM falla, se usa el de reglas y queda anotado.

**Las tres tecnologías (botones)**. En el listado y en la ficha hay un botón por tecnología; el agente que procesa es el que elijas. En la ficha, «Ejecutar las 3 y comparar» las encadena.

| Tecnología | Cómo trabaja | Modelo |
|---|---|---|
| **LangGraph** | Un grafo con un nodo por requisito y otro de veredicto. Las líneas se analizan en paralelo (`LANGGRAPH_CONCURRENCIA`) y se marcan en vivo | Ollama o Claude |
| **Pydantic AI** | Una sola consulta con salida tipada (modelos Pydantic) y reintento si no valida | Ollama |
| **Claude Agent SDK** | El agente no recibe los datos: los consulta él con Read y Grep en copias saneadas (sin campos de resultado), confinado a una carpeta temporal | El mismo LLM de Ollama (cualquiera de sus modelos); no necesita clave de Anthropic |

Además hay dos arquitecturas propias como línea base: `lineas` (una consulta por línea y otra para el veredicto) y `una_llamada` (una sola consulta). Se ejecutan desde un desplegable de la ficha o con `bench.py`.

El servidor Ollama acepta el protocolo de mensajes de Anthropic, así que el SDK (cuyo CLI se apunta a `OLLAMA_URL` con el token de Ollama) habla con el mismo modelo que las otras dos. Su proceso queda aislado: carpeta de configuración vacía (sin sesión, ajustes ni plugins del usuario), credenciales de Claude vacías, tráfico no esencial desactivado, y el selector de modelo de la ficha aplica a las tres tecnologías.

Si una tecnología no puede correr (falta el paquete o el servidor), cae al revisor por reglas, queda anotado como «No disponible» y no se mezcla con las métricas de las demás.

El LLM no tiene por qué respetar el esquema JSON que se le pide (con algunos modelos, el servidor lo ignora), así que las respuestas se interpretan de forma tolerante y el veredicto se ajusta si contradice las líneas marcadas.

## 9.1 Resultados virtuales y estadísticas

**El resultado del agente es solo virtual.** No se guarda en ningún archivo ni base de datos (ni en `localStorage` o `sessionStorage`): el servidor lo emite en directo mientras se calcula y vive solo en la memoria de la página. **Al refrescar la página todo vuelve al estado inicial limpio.** Si el navegador se va a mitad de una revisión, el servidor la descarta. Cambiar de página (por ejemplo, del listado a una ficha) también empieza de cero.

Al terminar cada corrida se sabe cuánto ha costado:

- **En la ficha**: bajo el veredicto, una línea con la duración, la tecnología, las llamadas y los tokens; debajo, el detalle (tiempo por línea, acuerdo con las reglas).
- **En el listado**: cada fila muestra su tecnología, duración y llamadas, y un panel resume lo procesado en esa página (veredictos, duración total, media, mediana y máximo, llamadas, tokens, acuerdo con las reglas y corridas que cayeron a reglas).
- **Comparación de las 3 tecnologías** (ficha): veredicto, importe, duración (marca la más rápida), llamadas, tokens, acuerdo con las reglas, motivo y una matriz de resultado por línea con las discrepancias resaltadas, más la lista de corridas hechas en esa página.
- **Página de análisis (`/analisis`)**: ejecuta las 3 tecnologías sobre las primeras N reclamaciones (N lo fija un campo que **siempre arranca en 5**, valor de `ANALISIS_RECLAMACIONES_DEFECTO`) una corrida cada vez, y calcula en vivo el acierto frente a la referencia, las aprobaciones indebidas, las matrices de confusión, el acierto por comprobación, si las 3 coinciden y la causa de cada error. Unos 1 a 2 minutos por reclamación; nada se guarda.
- **`bench.py`**: para comparar muchas reclamaciones a la vez; resume mediana, p95, llamadas, tokens y acuerdo por arquitectura y modelo, en pantalla, sin guardar nada.

Para comparar con justicia hay que usar las **mismas reclamaciones** en todas las variantes:

```bash
python bench.py --n 10 --modelos modelo1,modelo2 --arq lineas,una_llamada --reglas
```

El «acuerdo» se mide contra el revisor por reglas, que es una referencia y no la verdad absoluta.

# 10. Configuración (`.env`)

Todo valor variable está en el `.env`; el código no tiene valores por defecto. `.env.example` es la plantilla sin secretos. Si falta una variable obligatoria, la app no arranca y lista las que faltan (`config.py`). Las variables de Ollama solo son obligatorias si `AGENT_MODE` las necesita; las de `BENCH_*` y `GEN_*`, solo al usar `bench.py` y `generate_data.py`.

| Variable | Para qué sirve |
|---|---|
| `APP_NAME`, `APP_TAGLINE` | Nombre y subtítulo de la cabecera |
| `APP_USER_NAME`, `APP_USER_ROLE` | Nombre y cargo que se muestran arriba a la derecha |
| `HOST`, `PORT`, `FLASK_DEBUG` | Dirección, puerto y modo depuración (1 = recarga automática) |
| `PER_PAGE_OPTIONS` | Filas por página del listado, separadas por coma; la primera es la de por defecto |
| `CLAIMS_FILE`, `POLICIES_FILE`, `CLAUSES_FILE` | Rutas de los tres JSON de datos (relativas al proyecto o absolutas) |
| `MAX_RECLAMACIONES` | Tope de reclamaciones que carga la app (y que acepta el generador) |
| `MAX_CORRIDAS_SIMULTANEAS` | Revisiones que pueden correr a la vez; la siguiente recibe 429 |
| `ANALISIS_RECLAMACIONES_DEFECTO` | Valor inicial del campo «máximo de reclamaciones» del listado y de la página de análisis |
| `AGENT_MODE` | `reglas`, `ollama`, `claude` o `auto` (claude si hay clave; si no, ollama si está configurado; si no, reglas) |
| `AGENT_ARCH` | Arquitectura por defecto: `lineas` o `una_llamada` (las 3 tecnologías se eligen con sus botones) |
| `AGENT_STEP_DELAY` | Pausa (s) entre líneas del revisor por reglas, para que se vea cómo se marcan |
| `AGENT_USER_AGENT` | `User-Agent` de las peticiones al LLM (algunos servidores bloquean el de Python) |
| `LANGGRAPH_CONCURRENCIA` | Líneas que LangGraph analiza a la vez (1 = en serie) |
| `PYDANTIC_REINTENTOS`, `PYDANTIC_AI_NO_BANNER` | Reintentos si la salida tipada no valida; silencia el banner de Pydantic AI |
| `CLAUDE_SDK_MAX_TURNOS`, `CLAUDE_SDK_HERRAMIENTAS` | Tope de vueltas y herramientas de lectura del Claude Agent SDK |
| `OLLAMA_URL`, `OLLAMA_TOKEN`, `OLLAMA_MODEL` | Servidor Ollama, su token (Bearer) y el modelo por defecto |
| `OLLAMA_TIMEOUT`, `OLLAMA_REINTENTOS`, `OLLAMA_REINTENTO_SEG` | Tiempo máximo por consulta; reintentos y espera base ante 429/5xx |
| `OLLAMA_MODELS_TIMEOUT`, `OLLAMA_MODELS_CACHE_SEG`, `OLLAMA_TEMPERATURE` | Tiempo y caché de la lista de modelos; temperatura de las consultas |
| `ANTHROPIC_API_KEY`, `AGENT_MODEL`, `AGENT_MAX_TOKENS` | Solo para `AGENT_MODE=claude` (API de Anthropic) |
| `BENCH_N`, `BENCH_SEMILLA`, `BENCH_MODELOS`, `BENCH_ARQ`, `BENCH_REPETICIONES`, `BENCH_STEP_DELAY` | Valores por defecto de `bench.py` |
| `GEN_RECLAMACIONES`, `GEN_POLIZAS`, `GEN_SEMILLA`, `GEN_FECHA_REFERENCIA`, `GEN_FECHA_INICIO_VIAJES`, `GEN_DIAS_VIAJES` | Tamaño, semilla y fechas del generador de datos |

Los datos ficticios (nombres, catálogos de tipos, textos de las cláusulas y de los sucesos) son contenido del generador, no configuración.

# 11. Validación antes de subir a GitHub

`scripts/validar_subida.py` bloquea el commit o el push si encuentra datos privados o configuración fija. Se ejecuta solo, con los hooks de `.githooks/` (se activan una vez por clon con `sh scripts/instalar_hooks.sh`), y a mano con `python3 scripts/validar_subida.py --todo`.

| Regla | Qué detecta |
|---|---|
| Archivos prohibidos | `.env`, `data/revisiones.json`, `data/corridas.jsonl`, claves y certificados |
| Secretos | Tokens `Bearer`, claves de Anthropic, GitHub o AWS, claves privadas, cadenas hexadecimales largas |
| Valores del `.env` local | Cualquier token, clave, URL de servidor o nombre de usuario del `.env` que aparezca en un archivo |
| `.env.example` | Los valores de tokens, claves y URLs deben estar vacíos |
| Código | URLs, IPs, valores por defecto en `os.environ.get` y lecturas directas de `os.environ` fuera de `config.py` |
| Datos personales | Correos que no sean `@example.*` y rutas absolutas de la carpeta personal del equipo |

El push se valida **commit a commit**: un secreto añadido y borrado después sigue en el historial y también se bloquea. `git push --no-verify` se salta los hooks; no lo uses.

# 12. Arquitectura y flujo de una revisión

```
Navegador (static/agente.js)           Servidor Flask (app.py)                 agent.py
────────────────────────────           ───────────────────────                 ────────
clic en una tecnología  ──POST──►  valida arquitectura / modelo
                                    reserva un hueco (cupo)            ──►  construir_lineas()  (12 o 14 líneas)
                                    lanza un hilo de trabajo                 │
líneas marcadas en vivo ◄─NDJSON─   cola de eventos ◄── progreso ◄──────────┤ _correr(): reglas | lineas | una_llamada
veredicto + estadísticas ◄────────  evento «fin»                              │            | arq_langgraph | arq_pydantic_ai
                                                                              │            | arq_claude_sdk (módulos externos)
                                                                              └► veredicto → salvaguardas → estadísticas
```

1. **Líneas a comprobar.** `construir_lineas` genera los requisitos del caso: 6 generales de la cláusula G-07 (póliza en vigor, prima al día, cobertura incluida, situación con derecho a pago, plazo, documentación), los requisitos específicos de la cobertura y el límite. Para los LLM se añade una línea más, las exclusiones de las cláusulas (que solo puede juzgar el LLM): 12 líneas frente a 11 del revisor por reglas.
2. **Ejecución.** `_correr` elige la arquitectura. Las tres tecnologías viven en módulos `arq_<nombre>.py` que se importan al usarse y cumplen un contrato común (ver el comentario en `agent.py`).
3. **Veredicto.** El revisor por reglas rechaza si falla un requisito bloqueante, pide validar si falla uno no bloqueante y aprueba en el resto. Con un LLM, el veredicto se ajusta si contradice las líneas: no puede aprobar con líneas sin cumplir, ni rechazar sin una línea bloqueante incumplida, y «Validar» siempre lleva comentario. La línea de exclusiones no es bloqueante: si parece aplicar, el caso pasa a «Validar».
4. **Estadísticas.** Cada corrida mide duración, llamadas, tokens, tiempo por línea y su acuerdo con el revisor por reglas, que se ejecuta aparte como referencia.
5. **Caída a reglas.** Si una tecnología falla (paquete, servidor, respuesta inválida), la corrida se rehace con el revisor por reglas y queda anotada como `fallback`, sin mezclarse con las métricas de las demás.
6. **Aislamiento del Claude Agent SDK.** Recibe copias saneadas de los datos (sin campos de resultado) en una carpeta temporal, con una carpeta de configuración vacía, credenciales de Claude vacías, solo Read y Grep, y un hook que solo permite leer los tres archivos.

# 13. Referencia de la API de revisión

**`POST /reclamaciones/<id>/revision`**. Cuerpo JSON: `{"arquitectura": "<nombre>", "modelo": "<modelo de Ollama>" }`. La arquitectura es obligatoria: `langgraph`, `pydantic_ai`, `claude_sdk`, `lineas` o `una_llamada`. El modelo es opcional y debe estar en el servidor Ollama. Opcionalmente `"motor": "reglas"` fuerza el revisor por reglas.

| Código | Cuándo |
|---|---|
| 200 | Flujo en directo (`application/x-ndjson`) |
| 400 | Cuerpo mal formado, arquitectura no válida o modelo no disponible; no se ejecuta nada |
| 404 | La reclamación no existe |
| 405 | Cualquier método distinto de POST |
| 429 | Ya hay `MAX_CORRIDAS_SIMULTANEAS` revisiones en curso |

El flujo emite una línea JSON por evento:

```json
{"tipo": "progreso", "fase": "Analizando la línea 3 de 12: ...", "lineas": [{"id": "...", "grupo": "General", "requisito": "...", "estado": "cumple|no_cumple|duda|analizando|pendiente", "detalle": "..."}]}
{"tipo": "fin", "resultado": {"veredicto": "Aprobado|Rechazado|Validar", "motivo": "...", "comentario": "solo con Validar", "importeAPagar": 0, "lineas": [...], "agente": {}, "nota": null, "stats": {"arquitectura": "...", "modelo": "...", "duracionSeg": 0, "llamadas": 0, "tokensEntrada": 0, "tokensSalida": 0, "tiempos": [], "acuerdoVeredicto": true, "fallback": false}}}
{"tipo": "error", "error": "..."}
```

**`GET /api/claims`, `/api/policies`, `/api/clauses`**: los datos en JSON (las reclamaciones, como máximo `MAX_RECLAMACIONES`).

# 14. Solución de problemas

| Síntoma | Causa y solución |
|---|---|
| La app no arranca y dice «Faltan variables en el .env» | Copia `.env.example` a `.env` y rellena las que se listan |
| En macOS el puerto 5000 da 403 | Lo usa AirPlay Receiver; usa otro `PORT` |
| Una tecnología aparece como «No disponible» | Cayó a reglas; la nota dice por qué: paquete sin instalar (`pip install -r requirements-extra.txt`), servidor inalcanzable o modelo inexistente |
| HTTP 403 del servidor Ollama | Bloquea el `User-Agent` por defecto de Python: define `AGENT_USER_AGENT` |
| HTTP 429 del servidor Ollama | Límite de peticiones. Hay reintentos con espera; baja `LANGGRAPH_CONCURRENCIA` o `MAX_CORRIDAS_SIMULTANEAS` |
| El modelo ignora el esquema JSON | Ocurre con algunos modelos (Gemma); las respuestas se interpretan de forma tolerante |
| El veredicto cambia entre corridas | Los LLM varían aunque la temperatura sea 0; por eso hay revisor por reglas de referencia |
| Un resultado desaparece al refrescar | Es el comportamiento previsto: los resultados son solo virtuales |
| La búsqueda no encuentra nada | Todas las palabras deben aparecer (Y lógico); se ignoran acentos y mayúsculas |
| Aviso `unrecognized_model` al usar el Claude Agent SDK | Es un log inocuo de su CLI con modelos que no son de Anthropic |
| Se bloquea un commit o un push | Lee el listado del validador, quita el dato y muévelo al `.env`. No uses `--no-verify` |

# 15. Pendiente y próximos pasos

- Probar el modo `claude` (API de Anthropic) con una clave real: no se ha ejecutado. Las tres tecnologías ya se han ejecutado con modelos de Ollama.
- Correr `bench.py` con los modelos y arquitecturas a comparar.
- Sustituir los datos ficticios, las cláusulas y los límites por los textos reales de las pólizas.
- El botón «Proveedores» del menú es decorativo por ahora.
- Añadir autenticación y registro de las decisiones del agente antes de usarlo con datos reales.
