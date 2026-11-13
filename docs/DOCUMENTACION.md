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
cd Travel-Insurance-agent
pip install -r requirements.txt
python3 generate_data.py     # regenera los JSON de ejemplo (opcional)
python3 app.py               # http://localhost:5001
```

- El puerto por defecto es **5001**, porque en macOS el 5000 lo usa AirPlay Receiver. Se cambia con `PORT=8000 python3 app.py`.
- Los JSON se leen en **cada petición**: editar un fichero y recargar la página basta para ver los cambios.
- Rutas de los ficheros configurables con las variables `CLAIMS_FILE`, `POLICIES_FILE` y `CLAUSES_FILE`.

# 3. Estructura del proyecto

| Ruta | Contenido |
|---|---|
| `app.py` | Servidor Flask: rutas, filtros, paginación y carga de los JSON |
| `generate_data.py` | Genera los tres JSON con datos ficticios coherentes entre sí |
| `data/claims.json` | 200 reclamaciones |
| `data/polizas.json` | 120 pólizas, con coberturas y calendario de pagos |
| `data/clausulas.json` | 20 cláusulas: 13 por cobertura y 7 generales |
| `templates/` | Plantillas: `base`, `index` (listado), `detail` (ficha de reclamación), `polizas`, `poliza` |
| `static/style.css` | Estilos (tema claro y oscuro) |
| `docs/` | Esta documentación |

# 4. Pantallas y rutas

| Ruta | Qué muestra |
|---|---|
| `/` | Listado de reclamaciones con buscador, filtro por tipo, orden por columna y paginación (10, 25, 50 o 100 filas) |
| `/reclamaciones/<id>` | **Ficha** de una reclamación; se abre al hacer clic en una fila |
| `/polizas` | Listado de pólizas con búsqueda por póliza, tomador o DNI y filtro por plan |
| `/polizas/<número>` | Ficha de póliza: requisitos de pago, coberturas, cláusulas, pagos y reclamaciones |
| `/api/claims`, `/api/policies`, `/api/clauses` | Los datos en JSON, pensados para que los consuma el agente |

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

# 9. Pendiente y próximos pasos

- Conectar el **agente** que analiza cada reclamación, por ejemplo leyendo `/api/claims`, `/api/policies` y `/api/clauses`.
- Sustituir los datos ficticios, las cláusulas y los límites por los textos reales de las pólizas.
- Los botones del menú «Proveedores» e «Informes» son decorativos por ahora.
- Añadir autenticación y registro de las decisiones del agente antes de usarlo con datos reales.
