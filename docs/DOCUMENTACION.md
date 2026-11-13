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
| `agent.py` | Agente de revisión (reglas, Ollama o Claude; dos arquitecturas) y sus estadísticas |
| `corridas.py` | Historial de corridas y agregación para comparar modelos y arquitecturas |
| `bench.py` | Benchmark: corre el agente sobre las mismas reclamaciones con varios modelos y arquitecturas |
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
| `/` | Listado de reclamaciones con buscador, filtro por tipo, orden por columna y paginación (10, 25, 50 o 100 filas) |
| `/reclamaciones/<id>` | **Ficha** de una reclamación; se abre al hacer clic en una fila |
| `/polizas` | Listado de pólizas con búsqueda por póliza, tomador o DNI y filtro por plan |
| `/polizas/<número>` | Ficha de póliza: requisitos de pago, coberturas, cláusulas, pagos y reclamaciones |
| `/estadisticas` | Comparación de modelos y arquitecturas del agente a partir del historial de corridas |
| `/reclamaciones/<id>/revision` (POST) | Arranca la revisión del agente en segundo plano |
| `/api/claims`, `/api/policies`, `/api/clauses`, `/api/revisiones`, `/api/estadisticas` | Los datos en JSON, pensados para que los consuma el agente |

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

# 7. Datos de ejemplo

- **200 reclamaciones**, **50 tipos** distintos (4 por tipo), **120 pólizas** (56 Estándar, 39 Básico, 25 Premium) y **20 cláusulas**.
- Todas las reclamaciones tienen una póliza registrada.
- **18 pólizas** tienen una cuota vencida impagada, lo que afecta a **35 reclamaciones**.
- **13 reclamaciones** piden una cobertura que no incluye el plan de su póliza.
- Los desgloses suman exactamente el importe reclamado y los pagos suman la prima.
- **Cada tipo de reclamación tiene un suceso inspirado en una película reconocible**, escrito sin nombrar nunca la película, más una declaración del asegurado en primera persona. Sirve para probar al agente con relatos variados y fáciles de identificar.

# 8. Decisiones de diseño

- **JSON en disco, sin base de datos**: simple de editar y de sustituir por datos reales.
- **El estado y el resultado se ocultan en la web.** Las reclamaciones las va a analizar un agente, así que la interfaz no muestra el estado, el importe aprobado, el motivo de rechazo ni las comprobaciones previas. Esos campos siguen existiendo en `claims.json`.
- **Diseño**: generado con Google Stitch (estilo corporativo en azul marino y cian) y adaptado a Flask, con tema claro y oscuro.
- **Sin dependencias de front-end**: HTML, CSS y una pizca de JavaScript para abrir la ficha al hacer clic en la fila.

# 9. Agente de revisión

Cada reclamación tiene un botón **Revisar con el agente**. Al pulsarlo arranca un proceso en segundo plano que analiza el caso **línea por línea** (requisitos generales de la cláusula G-07, requisitos de la cobertura y un análisis del relato). Cada línea se marca en pantalla, en vivo, como *cumple*, *no cumple* o *duda*. Al final emite el veredicto:

- **Aprobado**: todo cumple. Indica el importe a pagar.
- **Rechazado**: falla un requisito bloqueante (póliza fuera de vigencia, cuota impagada, cobertura no incluida, 0 %, fuera de plazo, exclusión aplicable).
- **Validar**: hay dudas o incumplimientos no bloqueantes. Añade un **comentario del agente** con lo que una persona debe comprobar.

El agente decide solo con los hechos del caso, la póliza y las cláusulas: no ve el estado ni el resultado que traen los datos de ejemplo.

**Modos** (`AGENT_MODE`): `reglas` (determinista, sin LLM), `ollama` (un LLM de un servidor Ollama), `claude` (API de Anthropic) o `auto`. Si un modo con LLM falla, se usa el de reglas y queda anotado.

**Arquitecturas** (`AGENT_ARCH` o el selector de la ficha): `lineas` (una consulta por línea y otra para el veredicto) o `una_llamada` (una sola consulta con todo). Los modelos de Ollama se eligen en la ficha; se listan desde el servidor.

El LLM no tiene por qué respetar el esquema JSON que se le pide (con algunos modelos, el servidor lo ignora), así que las respuestas se interpretan de forma tolerante y el veredicto se ajusta si contradice las líneas marcadas.

## 9.1 Estadísticas de las corridas

Cada corrida guarda su duración total, el tiempo por línea, las llamadas al LLM, los tokens, y su acuerdo con el revisor por reglas (veredicto y líneas). La ficha muestra las de la corrida y compara con otras corridas de la misma reclamación. La página `/estadisticas` agrupa por arquitectura y modelo: mediana, p95 y máximo de duración, llamadas, tokens, acuerdo y reparto de veredictos.

Para comparar con justicia hay que usar las **mismas reclamaciones** en todas las variantes:

```bash
python bench.py --n 10 --modelos modelo1,modelo2 --arq lineas,una_llamada --reglas
```

El «acuerdo» se mide contra el revisor por reglas, que es una referencia y no la verdad absoluta.

# 10. Configuración (`.env`)

Todo valor variable está en el `.env`; `.env.example` lista todas las variables sin secretos. Grupos:

| Grupo | Variables |
|---|---|
| Marca y usuario de la cabecera | `APP_NAME`, `APP_TAGLINE`, `APP_USER_NAME`, `APP_USER_ROLE` |
| Servidor | `HOST`, `PORT`, `FLASK_DEBUG`, `PER_PAGE_OPTIONS` |
| Archivos de datos | `CLAIMS_FILE`, `POLICIES_FILE`, `CLAUSES_FILE`, `REVIEWS_FILE`, `CORRIDAS_FILE` |
| Reglas del agente | `IMPORTE_ALTO_VALIDAR`, `PLAZO_RECLAMACION_DIAS` |
| Agente | `AGENT_MODE`, `AGENT_ARCH`, `AGENT_STEP_DELAY`, `AGENT_USER_AGENT` |
| Ollama (si `AGENT_MODE=ollama`) | `OLLAMA_URL`, `OLLAMA_TOKEN`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`, `OLLAMA_MODELS_TIMEOUT`, `OLLAMA_MODELS_CACHE_SEG`, `OLLAMA_TEMPERATURE` |
| Claude (si `AGENT_MODE=claude`) | `ANTHROPIC_API_KEY`, `AGENT_MODEL`, `AGENT_MAX_TOKENS` |
| Benchmark | `BENCH_N`, `BENCH_SEMILLA`, `BENCH_MODELOS`, `BENCH_ARQ`, `BENCH_REPETICIONES`, `BENCH_STEP_DELAY` |
| Generador de datos | `GEN_RECLAMACIONES`, `GEN_POLIZAS`, `GEN_SEMILLA`, `GEN_FECHA_REFERENCIA`, `GEN_FECHA_INICIO_VIAJES`, `GEN_DIAS_VIAJES` |

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

# 12. Pendiente y próximos pasos

- Probar el modo `claude` con una clave real (aún no se ha ejecutado).
- Correr `bench.py` con los modelos y arquitecturas a comparar.
- Sustituir los datos ficticios, las cláusulas y los límites por los textos reales de las pólizas.
- El botón «Proveedores» del menú es decorativo por ahora.
- Añadir autenticación y registro de las decisiones del agente antes de usarlo con datos reales.
