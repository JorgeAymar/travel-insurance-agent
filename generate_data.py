"""Genera data/claims.json con datos ficticios: 200 reclamaciones, 50 tipos, cada una con glosa detallada."""
import json, os, random, unicodedata
from datetime import date, timedelta

import config as cfg

N_RECLAMACIONES, N_POLIZAS = cfg.entero("GEN_RECLAMACIONES"), cfg.entero("GEN_POLIZAS")
if N_RECLAMACIONES > cfg.entero("MAX_RECLAMACIONES"):
    raise SystemExit("GEN_RECLAMACIONES no puede superar MAX_RECLAMACIONES (ver .env)")
FECHA_REF = date.fromisoformat(cfg.get("GEN_FECHA_REFERENCIA"))      # hoy, a efectos de «Vigente»/«Finalizada»
FECHA_INICIO_VIAJES = date.fromisoformat(cfg.get("GEN_FECHA_INICIO_VIAJES"))
DIAS_VIAJES = cfg.entero("GEN_DIAS_VIAJES")
random.seed(cfg.entero("GEN_SEMILLA"))

MESES = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre']
def iso(d): return d.isoformat()
def largo(d): return f'{d.day} de {MESES[d.month-1]} de {d.year}'
def plano(s): return unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode().lower()
def eur(v): return f'{v:,.0f}'.replace(',', '.') + ' €'

NOMBRES = ['Ana','Luis','María','Carlos','Lucía','Javier','Sofía','Miguel','Elena','Pablo','Laura','Diego','Marta','Andrés','Carmen','Jorge','Paula','Sergio','Irene','Rubén']
APELLIDOS = ['García','Martínez','López','Sánchez','Fernández','Gómez','Ruiz','Díaz','Moreno','Álvarez','Romero','Navarro','Torres','Domínguez','Vázquez']
DESTINOS = {  # destino: (país, nombre de hotel ficticio)
 'París':('Francia','Hôtel Lumière'),'Roma':('Italia','Hotel Forum Aurelio'),'Nueva York':('Estados Unidos','Hudson Park Hotel'),
 'Cancún':('México','Resort Caribe Azul'),'Tokio':('Japón','Hotel Sakura Shinjuku'),'Bangkok':('Tailandia','Chao Phraya Grand'),
 'Lisboa':('Portugal','Hotel Alfama Vista'),'Londres':('Reino Unido','The Kensington Court'),'Dubái':('Emiratos Árabes Unidos','Marina Palm Hotel'),
 'Buenos Aires':('Argentina','Hotel Palermo Soho'),'Marrakech':('Marruecos','Riad Medina Rosa'),'Estambul':('Turquía','Bosphorus Pera Hotel'),
}
AEROLINEAS = ['AirNorte','Vuelos Atlántico','TransMed Air','Iberoceanía','SkyLevante']
ESTADOS = ['Abierto','En revisión','Documentación pendiente','Aprobado','Rechazado','Pagado','Cerrado']
CANALES = ['Web','Teléfono','Email','App móvil','Agencia']
GESTORES = ['Mateo Ruiz','Nuria Esteve','Raúl Ibáñez','Alicia Prieto']
LETRAS = 'TRWAGMYFPDXBNJZSQVHLCKE'

# Categorías: lugar del suceso, conceptos del desglose, terceros, documentos, cobertura, referencia oficial
CAT = {
 'transporte': dict(lugar=['Aeropuerto de {d}, terminal 2','Aeropuerto de {d}, puerta de embarque B{n}','Estación central de {d}'],
   conceptos=['Billetes no reembolsados','Alojamiento adicional','Comidas y bebidas durante la espera','Traslados en taxi','Comunicaciones'],
   terceros=['Aerolínea','Agencia de viajes'], docs=['Billetes / reserva','Certificado de retraso o cancelación de la aerolínea','Facturas originales','Formulario de reclamación','Copia de la póliza'],
   cobertura='Retrasos, cancelaciones y transporte',limite=1500,ref=None),
 'equipaje': dict(lugar=['Cinta de equipajes del aeropuerto de {d}','Mostrador de equipajes perdidos, aeropuerto de {d}','Hotel {h}, recepción'],
   conceptos=['Contenido de la maleta (ropa y calzado)','Artículos de aseo y farmacia','Compras de primera necesidad','Reposición de maleta'],
   terceros=['Aerolínea','Hotel'], docs=['Parte de irregularidad de equipaje (PIR)','Facturas de compra / valoración','Billetes y etiquetas de equipaje','Formulario de reclamación','Copia de la póliza'],
   cobertura='Equipaje y efectos personales',limite=1200,ref='PIR'),
 'robo': dict(lugar=['Calle comercial del centro de {d}','Transporte público de {d}','Restaurante junto al Hotel {h}','Playa / zona turística de {d}'],
   conceptos=['Objetos sustraídos','Reposición de documentos y trámites','Gastos de gestión y transporte','Compras de primera necesidad'],
   terceros=['Policía local','Consulado'], docs=['Denuncia policial','Listado y valoración de objetos','Facturas originales','Formulario de reclamación','Copia de la póliza'],
   cobertura='Robo y pérdida de efectos personales',limite=1000,ref='DEN'),
 'documentos': dict(lugar=['Hotel {h}, habitación','Comisaría central de {d}','Zona turística de {d}'],
   conceptos=['Tasas del documento provisional','Traslado al consulado','Fotografías y trámites','Noche extra de alojamiento'],
   terceros=['Policía local','Consulado'], docs=['Denuncia policial','Documento provisional del consulado','Facturas originales','Formulario de reclamación'],
   cobertura='Documentación personal',limite=600,ref='DEN'),
 'medico': dict(lugar=['Hospital Central de {d}','Clínica Internacional de {d}','Servicio de urgencias de {d}','Hotel {h}'],
   conceptos=['Consulta y urgencias','Pruebas diagnósticas','Medicación','Hospitalización','Transporte sanitario'],
   terceros=['Centro médico','Aseguradora local de asistencia'], docs=['Informe médico','Facturas del centro médico','Recetas y justificantes de farmacia','Formulario de reclamación','Copia de la póliza'],
   cobertura='Gastos médicos en el extranjero',limite=30000,ref='INF'),
 'repatriacion': dict(lugar=['Hospital Central de {d}','Clínica Internacional de {d}','Aeropuerto de {d}'],
   conceptos=['Ambulancia aérea / medicalizada','Acompañante sanitario','Gastos hospitalarios previos','Traslado terrestre','Gestiones administrativas'],
   terceros=['Centro médico','Compañía de asistencia'], docs=['Informe médico','Autorización de traslado','Facturas del transporte sanitario','Formulario de reclamación','Copia de la póliza'],
   cobertura='Repatriación y evacuación',limite=100000,ref='INF'),
 'accidente': dict(lugar=['Carretera costera cerca de {d}','Estación / pista de actividades deportivas de {d}','Avenida principal de {d}','Zona de excursiones a las afueras de {d}'],
   conceptos=['Asistencia médica de urgencia','Rehabilitación y fisioterapia','Material ortopédico','Transporte y traslados','Gastos de acompañante'],
   terceros=['Policía local','Centro médico'], docs=['Atestado / parte del accidente','Informe médico','Facturas originales','Formulario de reclamación','Copia de la póliza'],
   cobertura='Accidentes personales',limite=20000,ref='INF'),
 'responsabilidad': dict(lugar=['Hotel {h}, habitación y zonas comunes','Local comercial de {d}','Vehículo de alquiler en {d}','Apartamento turístico en {d}'],
   conceptos=['Reparación de daños','Franquicia del seguro del alquiler','Gastos de peritación','Indemnización al tercero'],
   terceros=['Tercero perjudicado','Empresa de alquiler / alojamiento'], docs=['Parte amistoso o informe del daño','Presupuesto o factura de reparación','Contrato de alquiler / reserva','Formulario de reclamación','Copia de la póliza'],
   cobertura='Responsabilidad civil y daños a terceros',limite=6000,ref='PAR'),
 'cancelacion': dict(lugar=['Domicilio del asegurado','Centro médico de origen','Lugar de residencia en España'],
   conceptos=['Vuelos no reembolsables','Alojamiento no reembolsable','Excursiones y servicios prepagados','Gastos de cancelación de la agencia'],
   terceros=['Agencia de viajes','Aerolínea'], docs=['Justificante de la causa de cancelación','Billetes / reserva','Facturas de cancelación','Formulario de reclamación','Copia de la póliza'],
   cobertura='Cancelación de viaje',limite=5000,ref='CAN', previo=True),
 'externo': dict(lugar=['Aeropuerto de {d}','Zona afectada de {d}','Hotel {h}'],
   conceptos=['Alojamiento adicional','Billetes de reubicación','Servicios no disfrutados','Comidas y traslados'],
   terceros=['Autoridad local / aeroportuaria','Agencia de viajes'], docs=['Comunicado oficial del suceso','Billetes / reserva','Facturas originales','Formulario de reclamación','Copia de la póliza'],
   cobertura='Eventos de fuerza mayor',limite=2500,ref=None),
 'legal': dict(lugar=['Juzgado / comisaría de {d}','Despacho de abogados en {d}','Consulado en {d}'],
   conceptos=['Honorarios del abogado','Tasas y costas','Fianza adelantada','Traducciones juradas'],
   terceros=['Abogado local','Autoridad judicial'], docs=['Documentación judicial','Minuta del abogado','Justificante de fianza','Formulario de reclamación','Copia de la póliza'],
   cobertura='Defensa jurídica y fianzas',limite=6000,ref='JUD'),
 'electronico': dict(lugar=['Hotel {h}, habitación','Cafetería céntrica de {d}','Transporte público de {d}','Aeropuerto de {d}'],
   conceptos=['Valor del equipo (con depreciación)','Reparación / peritaje','Accesorios y datos','Alquiler de equipo sustitutivo'],
   terceros=['Policía local','Servicio técnico'], docs=['Denuncia policial','Factura de compra del equipo','Informe técnico de daños','Formulario de reclamación','Copia de la póliza'],
   cobertura='Equipos electrónicos',limite=1500,ref='DEN'),
 'prepago': dict(lugar=['Puerto / punto de embarque de {d}','Oficina del operador en {d}','Hotel {h}'],
   conceptos=['Servicio prepagado no prestado','Gastos de alternativas contratadas','Traslados adicionales','Comisiones y gastos de gestión'],
   terceros=['Operador turístico','Naviera / compañía'], docs=['Contrato y justificante de pago','Comunicación del operador','Facturas originales','Formulario de reclamación','Copia de la póliza'],
   cobertura='Servicios prepagados e insolvencia',limite=4000,ref=None),
}

# (tipo, categoría, hecho) — {vuelo} {aer} {h} {lugar} {horas} {obj} {acomp}
TIPOS = [
 ('Cancelación de viaje','cancelacion','El asegurado cancela el viaje contratado por un motivo sobrevenido e imprevisible antes de la salida, con servicios ya pagados y no reembolsables.'),
 ('Interrupción de viaje','cancelacion','Una vez iniciado el viaje, el asegurado debe interrumpirlo y regresar de forma anticipada por un motivo grave sobrevenido, perdiendo los servicios aún no disfrutados.'),
 ('Retraso de vuelo','transporte','El vuelo {vuelo} de {aer} sufre un retraso de {horas} horas por causas operativas de la aerolínea; los pasajeros permanecen en el aeropuerto sin información suficiente.'),
 ('Pérdida de conexión','transporte','Por el retraso del primer tramo, el asegurado pierde la conexión del vuelo {vuelo} de {aer} y debe esperar {horas} horas hasta la siguiente salida disponible.'),
 ('Overbooking','transporte','Al presentarse en el mostrador, {aer} deniega el embarque del vuelo {vuelo} por sobreventa de plazas y reubica a los pasajeros {horas} horas más tarde.'),
 ('Equipaje perdido','equipaje','Al llegar a destino, la maleta facturada en el vuelo {vuelo} de {aer} no aparece en la cinta; la aerolínea no logra localizarla y la da por perdida.'),
 ('Equipaje dañado','equipaje','Al recoger la maleta del vuelo {vuelo}, el asegurado comprueba que presenta la carcasa rota y el contenido deteriorado por golpes y humedad.'),
 ('Equipaje retrasado','equipaje','La maleta del vuelo {vuelo} de {aer} no llega con el pasajero y es entregada con {horas} horas de retraso, obligándole a comprar artículos de primera necesidad.'),
 ('Robo de equipaje','robo','Mientras el asegurado dejaba el equipaje bajo custodia momentánea, un desconocido sustrajo la maleta con ropa, calzado y objetos personales.'),
 ('Robo de documentos','documentos','El asegurado sufre la sustracción de su cartera con documento de identidad, tarjetas y documentación del viaje, sin que se produjera violencia.'),
 ('Pérdida de pasaporte','documentos','El asegurado extravía su pasaporte y no puede acreditar su identidad ni abandonar el país hasta obtener un documento provisional.'),
 ('Gastos médicos en el extranjero','medico','El asegurado sufre un cuadro agudo (gastroenteritis con deshidratación) y acude por su propio pie a urgencias, donde recibe tratamiento y observación.'),
 ('Hospitalización','medico','El asegurado ingresa de urgencia en el centro por un cuadro que requiere {horas} horas de observación y varios días de hospitalización.'),
 ('Repatriación sanitaria','repatriacion','Tras la estabilización inicial, el equipo médico recomienda el traslado sanitario del asegurado a España para continuar el tratamiento en su centro de referencia.'),
 ('Repatriación de restos','repatriacion','Tras el fallecimiento del asegurado, la familia solicita el traslado de los restos a España, con los trámites consulares y sanitarios correspondientes.'),
 ('Evacuación de emergencia','repatriacion','Por la gravedad del cuadro y la falta de medios en la zona, se ordena la evacuación médica urgente a un centro de mayor nivel.'),
 ('Asistencia dental urgente','medico','El asegurado sufre un dolor agudo por rotura dental (con infección) y precisa tratamiento odontológico urgente.'),
 ('Enfermedad preexistente','medico','El asegurado sufre una descompensación de una dolencia crónica conocida y recibe atención urgente; el caso requiere valorar si la cobertura aplica.'),
 ('Accidente deportivo','accidente','Durante una actividad de ocio (excursión / deporte), el asegurado se cae y se lesiona una extremidad, siendo atendido en el lugar y trasladado al centro.'),
 ('Accidente de tráfico','accidente','El taxi en el que viajaba el asegurado colisiona con otro vehículo en un cruce, causándole contusiones y lesión cervical.'),
 ('Muerte accidental','accidente','El asegurado fallece a consecuencia de un accidente durante el viaje; los beneficiarios designados reclaman la prestación por fallecimiento.'),
 ('Invalidez permanente','accidente','Como consecuencia de un accidente durante el viaje, el asegurado queda con secuelas permanentes que han sido valoradas médicamente.'),
 ('Responsabilidad civil','responsabilidad','El asegurado causa involuntariamente daños a un tercero (rotura de bienes) y este reclama una indemnización.'),
 ('Daños en alojamiento','responsabilidad','El asegurado provoca daños accidentales en la habitación (inundación del baño y deterioro del mobiliario) y el alojamiento le factura la reparación.'),
 ('Alquiler de coche dañado','responsabilidad','El vehículo de alquiler sufre un golpe lateral en un aparcamiento; la empresa de alquiler aplica la franquicia y cargos adicionales.'),
 ('Robo de vehículo de alquiler','responsabilidad','El vehículo de alquiler es sustraído durante la noche mientras estaba estacionado en la vía pública.'),
 ('Pérdida de llaves','documentos','El asegurado pierde las llaves del vehículo de alquiler y del alojamiento, requiriendo cerrajero y duplicado urgente.'),
 ('Desastre natural','externo','Una tormenta severa (inundaciones) afecta a la zona y obliga a modificar el alojamiento y los desplazamientos previstos.'),
 ('Huelga','externo','Una huelga del personal de transporte cancela los servicios previstos y el asegurado debe buscar alternativas por su cuenta.'),
 ('Disturbios civiles','externo','Unos disturbios en el centro de la ciudad impiden desplazarse con seguridad y obligan a cambiar de alojamiento.'),
 ('Cierre de espacio aéreo','externo','Las autoridades cierran el espacio aéreo durante {horas} horas; los vuelos se cancelan y el asegurado queda varado sin posibilidad de salir.'),
 ('Cuarentena obligatoria','externo','Las autoridades sanitarias imponen una cuarentena obligatoria al asegurado, que debe permanecer aislado y modificar su regreso.'),
 ('Resultado positivo COVID-19','externo','El asegurado da positivo en COVID-19 en una prueba antes del regreso y no puede viajar, debiendo prolongar su estancia.'),
 ('Cancelación por enfermedad familiar','cancelacion','Un familiar directo sufre una enfermedad grave sobrevenida días antes de la salida, y el asegurado cancela el viaje para atenderle.'),
 ('Cancelación por fallecimiento familiar','cancelacion','Fallece un familiar de primer grado días antes de la salida y el asegurado cancela el viaje.'),
 ('Cancelación por despido laboral','cancelacion','El asegurado recibe la notificación de despido de su empresa tras contratar el viaje y cancela por el cambio de su situación laboral.'),
 ('Cita judicial','cancelacion','El asegurado es citado a declarar por un órgano judicial en fechas coincidentes con el viaje, sin posibilidad de aplazamiento.'),
 ('Gastos de acompañante','medico','Por la hospitalización del asegurado, un familiar viaja hasta el destino para acompañarle y asume gastos de alojamiento y desplazamiento.'),
 ('Gastos de regreso anticipado','cancelacion','El asegurado debe regresar antes de lo previsto por un motivo grave en su domicilio y adquiere billetes de vuelta de urgencia.'),
 ('Retraso de equipaje superior a 24h','equipaje','La maleta del vuelo {vuelo} llega con más de {horas} horas de retraso, durante las cuales el asegurado carece de ropa y artículos básicos.'),
 ('Robo de dinero en efectivo','robo','El asegurado sufre el robo de efectivo que llevaba en la cartera / riñonera mediante un descuido en una zona concurrida.'),
 ('Robo de equipo electrónico','electronico','Es sustraído el equipo electrónico del asegurado (teléfono / portátil / cámara) mientras estaba en un lugar público.'),
 ('Daño de equipo electrónico','electronico','El equipo electrónico del asegurado sufre una caída accidental y queda inservible o con daños que impiden su uso.'),
 ('Pérdida de excursión prepagada','prepago','La excursión contratada y pagada por adelantado no se presta por causa ajena al asegurado, que no es reembolsado por el operador.'),
 ('Cancelación de crucero','prepago','La naviera cancela el crucero contratado y ofrece una compensación que no cubre los gastos ya realizados por el asegurado.'),
 ('Pérdida de equipo deportivo','equipaje','Los esquís / el equipo deportivo facturado se extravían durante el transporte y no son localizados.'),
 ('Secuestro de medio de transporte','externo','El medio de transporte en el que viajaba el asegurado es retenido durante {horas} horas por un incidente de seguridad, con importantes alteraciones del viaje.'),
 ('Quiebra de aerolínea','prepago','La aerolínea con la que el asegurado tenía contratado el vuelo cesa su actividad y los billetes quedan sin valor.'),
 ('Defensa jurídica en el extranjero','legal','El asegurado se ve envuelto en un procedimiento legal en el destino y necesita representación jurídica local.'),
 ('Adelanto de fianza','legal','Las autoridades exigen al asegurado el depósito de una fianza para poder continuar su viaje mientras se resuelve un procedimiento.'),
]
assert len(TIPOS) == 50

# ---------------- Sucesos con aire de película (sin nombrar la película) ----------------
# Cada tipo: (hecho en tercera persona, declaración del asegurado en primera persona).
HECHOS = {
 'Cancelación de viaje': ("el vuelo contratado fue reprogramado una y otra vez: cada mañana el mismo anuncio, la misma hora de salida, el mismo mostrador y la misma canción en la radio del hotel, como si el día se repitiera sin fin, hasta que el asegurado, agotado, canceló el viaje",
   "Cada mañana me despertaba y era el mismo día: el mismo anuncio, la misma canción en la radio y el mismo vuelo retrasado. Al final cancelé."),
 'Interrupción de viaje': ("una llamada de la familia, grave e inaplazable, de esas que no se pueden rechazar, obligó al asegurado a interrumpir el viaje y volver de inmediato para ocuparse de un asunto familiar delicado",
   "Me llamaron de la familia con una oferta que no podía rechazar y tuve que dejarlo todo y volver."),
 'Retraso de vuelo': ("el vuelo {vuelo} de {aer} sufrió {horas} horas de retraso y el asegurado, sin poder salir de la terminal ni embarcar, comió de las máquinas expendedoras, durmió en un banco y acabó conociendo por su nombre a todo el personal del aeropuerto",
   "Me quedé atrapado {horas} horas en la terminal: no podía salir ni embarcar, dormí en un banco y acabé siendo amigo de los empleados del aeropuerto."),
 'Pérdida de conexión': ("tras perder la conexión del vuelo {vuelo} de {aer}, el asegurado cayó en la cuenta de que había dejado a su hijo pequeño solo en casa mientras el resto de la familia ya viajaba; tuvo que comprar billetes de última hora y volver corriendo mientras el niño se las arreglaba solo",
   "Perdí mi vuelo y mi hijo se quedó solo en casa; tuve que retornar de inmediato."),
 'Overbooking': ("{aer} denegó el embarque del vuelo {vuelo} por sobreventa cuando el asegurado intentaba llegar a casa para la cena familiar de Nochebuena; para volver acabó encadenando tren, autobús, coche y habitación de motel con un desconocido muy hablador, vendedor de anillos para cortinas",
   "Solo quería llegar a casa para la cena de Nochebuena y acabé en trenes, autobuses y un motel, con un vendedor de anillos de cortina que no dejaba de hablar."),
 'Equipaje perdido': ("la maleta del vuelo {vuelo} de {aer} se dio por perdida tras desaparecer el carguero sobre el océano; lo único que apareció en la orilla fue un balón de voleibol con una mano dibujada, que el asegurado conservó como único recuerdo",
   "Mi equipaje se perdió en el mar y lo único que me devolvieron las olas fue un balón de voleibol al que ya le hablo como a un amigo."),
 'Equipaje dañado': ("al recoger la maleta del vuelo {vuelo}, el asegurado la encontró cubierta por una sustancia verde y viscosa derramada del contenedor de otro pasajero, que viajaba con trajes de color caqui, mochilas de protones y equipo para cazar fantasmas; toda la ropa quedó inservible",
   "Mi maleta salió de la cinta chorreando una baba verde de la mochila de unos tipos que decían cazar fantasmas. La ropa no tiene arreglo."),
 'Equipaje retrasado': ("el asegurado recogió por error una maleta idéntica a la suya que contenía una enorme suma de dinero y, tras devolverla al mostrador, su propia maleta del vuelo {vuelo} de {aer} le fue entregada con {horas} horas de retraso",
   "Me llevé por error una maleta igual a la mía, llena de billetes; la devolví y la mía llegó {horas} horas tarde, con el aeropuerto entero mirándonos."),
 'Robo de equipaje': ("once individuos impecablemente vestidos, con una coordinación milimétrica y sin levantar sospechas, sustrajeron el equipaje del asegurado y el de otros pasajeros mientras uno de ellos distraía a la seguridad con una conversación muy elegante",
   "Eran once, todos de traje y con una coordinación perfecta; mientras uno charlaba con el vigilante, los demás se llevaron mi maleta como si nada."),
 'Robo de documentos': ("un joven con uniforme de piloto, de aspecto muy seguro, sustrajo la cartera del asegurado y utilizó sus documentos para hacerse pasar por él, cobrando cheques y alojándose en hoteles a su nombre mientras la policía le seguía unos pasos por detrás",
   "Un chico vestido de piloto me robó la cartera y se hizo pasar por mí en hoteles y bancos, siempre un paso por delante de la policía."),
 'Pérdida de pasaporte': ("el asegurado se despertó sin pasaporte ni recuerdo de dónde lo había dejado, aunque conservaba una habilidad sospechosa para pelear y hablar varios idiomas; sin papeles no pudo cruzar la frontera hasta obtener un documento provisional en el consulado",
   "No sé dónde dejé el pasaporte ni qué hice la noche anterior; solo sé que hablo idiomas que no recordaba y que sin papeles no me dejan pasar."),
 'Gastos médicos en el extranjero': ("tras una despedida de soltero de la que no recuerda nada, el asegurado despertó en urgencias con una pulsera hospitalaria, un diente menos y una factura médica, sin saber cómo había llegado allí ni dónde estaba el novio",
   "Desperté en urgencias después de una despedida de soltero: sin memoria de la noche, sin un diente y con la factura del hospital."),
 'Hospitalización': ("tras un accidente en una carretera nevada, el asegurado ingresó en un centro aislado en el que la persona encargada de cuidarle, extremadamente entregada, se negaba a darle el alta y le impedía comunicarse con el exterior",
   "Tras el accidente en la nieve me atendió alguien tan atento que no quería dejarme marchar ni que llamara a nadie."),
 'Repatriación sanitaria': ("el paciente, lejos de casa y con un cuadro grave, repetía una única idea: llamar a casa y volver; el equipo médico organizó el traslado con la ambulancia rodeada de personal sanitario con trajes de aislamiento y una bicicleta que, según los testigos, parecía volar",
   "Lo único que quería era llamar a casa y volver; los médicos organizaron el traslado entre trajes de aislamiento y mucha emoción."),
 'Repatriación de restos': ("tras el fallecimiento del asegurado, la familia solicitó llevar sus restos a casa para que descansara en el panteón familiar y pudiera ser recordado en la ofrenda del Día de Muertos, con flores de cempasúchil, velas y su fotografía",
   "Mi abuelo murió lejos y queremos traerlo a casa para ponerle su foto, sus flores de cempasúchil y su ofrenda en la noche de los muertos."),
 'Evacuación de emergencia': ("un fallo grave en el suministro de oxígeno de la instalación donde se encontraba el asegurado desencadenó el aviso «tenemos un problema»; un equipo coordinó, a contrarreloj y con medios improvisados, su evacuación y regreso sano y salvo",
   "Se cortó el oxígeno y oímos el «tenemos un problema»; entre todos improvisaron la forma de sacarme y traerme de vuelta."),
 'Asistencia dental urgente': ("el asegurado acudió a un dentista local de aspecto inquietante que, taladro en mano y sin anestesia suficiente, le repetía una y otra vez si «era seguro», provocándole un dolor intenso y una infección posterior",
   "El dentista del lugar me hizo el tratamiento sin anestesia y no paraba de preguntarme si «es seguro»; ahora tengo una infección."),
 'Enfermedad preexistente': ("el asegurado, que no recordaba haber sufrido antes la dolencia ni haberla declarado, reconstruía su historial con notas, fotos y anotaciones que él mismo se había dejado por todas partes, hasta que sufrió una descompensación aguda",
   "No recuerdo si ya había tenido esto antes; me guío por las notas y fotos que me dejo a mí mismo, y hoy me descompensé."),
 'Accidente deportivo': ("tras una clase de artes marciales en la playa con un maestro anciano muy paciente, el asegurado intentó una patada de grulla sobre un poste, perdió el equilibrio y se lesionó la pierna",
   "Mi maestro me hizo encerar y pulir durante días y, cuando probé la patada de la grulla, me caí y me rompí la pierna."),
 'Accidente de tráfico': ("el taxi en el que viajaba el asegurado, con el conductor acelerando entre luces de neón y coches tuneados como en una carrera callejera ilegal, colisionó en un cruce con otro vehículo",
   "El taxista conducía como en una carrera ilegal de coches tuneados, rápido y furioso, y chocamos en un cruce."),
 'Muerte accidental': ("tras librarse por muy poco de un accidente a bordo gracias a una premonición que hizo que varios pasajeros bajaran a tiempo, una cadena de casualidades improbables acabó con la vida del asegurado; sus beneficiarios reclaman la prestación",
   "Mi hermano se salvó de milagro del accidente por una premonición, pero la muerte lo alcanzó después por una cadena de casualidades increíble."),
 'Invalidez permanente': ("tras un accidente de parapente sobre las montañas, el asegurado quedó con movilidad reducida; desde entonces necesita un asistente personal con quien comparte música, humor y paseos a toda velocidad en coche deportivo",
   "Desde mi accidente de parapente dependo de un asistente muy peculiar con el que escucho música y salgo a pasear en coche rápido."),
 'Responsabilidad civil': ("al abrir en el hotel un viejo juego de mesa, el asegurado liberó una manada de animales salvajes —monos, cebras y un león— que arrasó una calle comercial y dañó vehículos y escaparates de terceros",
   "Abrimos un viejo juego de mesa y, tras cada turno, salía una selva entera: monos, cebras y hasta un león destrozaron una calle."),
 'Daños en alojamiento': ("durante la noche, en la habitación, la televisión emitió estática, los muebles se desplazaron solos y una tubería reventó inundando el cuarto; el alojamiento atribuye los daños a una presencia sobrenatural y se los factura al asegurado",
   "La tele se llenó de estática, las sillas se movían solas y el cuarto se inundó; el hotel dice que fue cosa mía."),
 'Alquiler de coche dañado': ("el coche de alquiler, un deportivo plateado de puertas que se abren hacia arriba, alcanzó 140 km/h en una recta y desapareció en un fogonazo dejando dos rastros de llamas sobre el asfalto y la carrocería chamuscada",
   "Aceleré el deportivo plateado hasta 140 km/h y, en un fogonazo, desapareció dejando dos rayas de fuego en la carretera."),
 'Robo de vehículo de alquiler': ("el coche de alquiler fue sustraído en menos de sesenta segundos por una banda profesional que opera con una lista de modelos a robar cada noche",
   "Aparqué un minuto y en menos de sesenta segundos una banda con una lista de coches se llevó el mío."),
 'Pérdida de llaves': ("el asegurado dejó caer las llaves del coche y del alojamiento por una rejilla y, siguiendo un viejo mapa, un grupo de niños del barrio le ayudó a rastrear cuevas y túneles bajo el puerto hasta que tuvo que llamar a un cerrajero",
   "Se me cayeron las llaves por una rejilla y unos niños con un mapa antiguo me llevaron por cuevas y túneles hasta que tuve que llamar a un cerrajero."),
 'Desastre natural': ("un tornado de grandes dimensiones, perseguido por un equipo de cazadores de tormentas en camionetas, arrasó la zona del alojamiento del asegurado, arrancó el tejado y lanzó una vaca por los aires",
   "Un tornado arrasó el alojamiento mientras unos cazadores de tormentas lo perseguían; vi pasar una vaca volando."),
 'Huelga': ("una huelga de mineros y del sector del transporte, con piquetes y cordones policiales, paralizó la ciudad; en medio del conflicto, un niño de familia huelguista ensayaba ballet en plena calle mientras el asegurado buscaba alternativas por su cuenta",
   "Con la huelga de mineros y los piquetes no había transporte; vi a un niño de una familia huelguista practicando ballet en medio de la calle."),
 'Disturbios civiles': ("estudiantes y vecinos levantaron barricadas con carros y muebles en el centro de la ciudad mientras cantaban a coro; el asegurado quedó atrapado entre barricadas y tuvo que cambiar de alojamiento",
   "Levantaron barricadas con muebles y carros y cantaban todos juntos; yo quedé atrapado entre ellas y tuve que mudarme."),
 'Cierre de espacio aéreo': ("con el espacio aéreo cerrado durante {horas} horas, el asegurado esperó en un café repleto de viajeros desesperados por conseguir un visado de salida y un pasaje, mientras el pianista tocaba «otra vez» la misma canción",
   "Con el cielo cerrado esperé {horas} horas en un café lleno de gente desesperada por un visado y un pasaje; el pianista tocaba siempre la misma canción."),
 'Cuarentena obligatoria': ("ante un brote de un virus desconocido, las autoridades acordonaron el hotel con personal en trajes de aislamiento mientras los telediarios seguían, hora a hora, cómo el contagio pasaba de una persona a otra por un simple contacto",
   "Acordonaron el hotel por un virus desconocido y no pude salir: en la tele solo se hablaba del contagio, el brote y los trajes de aislamiento."),
 'Resultado positivo COVID-19': ("tras dar positivo, el asegurado debió quedarse inmovilizado en una habitación con vistas a un patio interior y, desde allí, observó con prismáticos a sus vecinos hasta sospechar de uno de ellos",
   "Di positivo y me quedé quieto en una habitación con vistas al patio; con unos prismáticos acabé espiando a los vecinos y sospechando de uno."),
 'Cancelación por enfermedad familiar': ("el padre del asegurado, un fabulador que siempre contaba historias increíbles sobre un pez gigante, un circo y una bruja, empeoró de una enfermedad grave y el asegurado canceló el viaje para despedirse de él",
   "Mi padre, que siempre contaba historias del pez gigante y del circo, empeoró; cancelé el viaje para estar a su lado."),
 'Cancelación por fallecimiento familiar': ("el asegurado tenía previsto asistir a varias bodas durante el viaje, pero el fallecimiento de un familiar cercano hizo coincidir el funeral con las fechas de salida, por lo que canceló",
   "Iba a cuatro bodas con el viaje, pero un familiar falleció y el funeral coincidió con la salida; tuve que cancelar."),
 'Cancelación por despido laboral': ("el asegurado escribió de madrugada un memorando sobre cómo debía cambiar su empresa, lo repartió a todos y a la mañana siguiente fue despedido; salió de la oficina con una caja de cartón y una pecera, y canceló el viaje",
   "Escribí un memorando sobre lo que debía cambiar en mi empresa y me despidieron; salí con una caja de cartón y una pecera, y cancelé el viaje."),
 'Cita judicial': ("el asegurado fue citado como jurado popular en un juicio y debía deliberar con otros once ciudadanos encerrados en una sala calurosa hasta alcanzar un veredicto unánime, en fechas coincidentes con el viaje",
   "Me han citado como jurado y debo estar encerrado con otros once en una sala calurosa hasta que todos digamos lo mismo; el viaje no puede ser."),
 'Gastos de acompañante': ("el padre del asegurado, muy protector, cruzó medio mundo entre mil apuros, ayudado por una compañera de viaje con muy mala memoria, para encontrar el hospital donde su hijo estaba ingresado, y asumió gastos de alojamiento y desplazamiento",
   "Crucé medio mundo con una compañera que olvidaba todo hasta encontrar el hospital donde estaba mi hijo; solo quería estar a su lado."),
 'Gastos de regreso anticipado': ("tras una tormenta que lo dejó en un lugar desconocido, el asegurado solo deseaba volver a casa («no hay lugar como el hogar») y compró billetes de regreso de urgencia golpeando tres veces los talones contra el suelo",
   "Después de la tormenta me vi en un lugar extraño y solo quería volver a casa; compré el billete de regreso entre tres golpes de talón."),
 'Retraso de equipaje superior a 24h': ("el asegurado llegó sin equipaje a una ciudad enorme y desconocida y, con jet lag y sin ropa durante más de un día, deambuló por el bar del hotel entre cantantes de karaoke y desconocidos hasta que le entregaron la maleta",
   "Llegué a una ciudad enorme sin maleta; más de un día sin ropa, con jet lag, en el bar del hotel entre karaokes."),
 'Robo de dinero en efectivo': ("dos individuos de traje negro y corbata fina, con aire muy tranquilo, exigieron al asegurado la cartera recitando un pasaje bíblico antes de llevarse todo el efectivo que llevaba",
   "Dos tipos de traje negro y corbata fina me quitaron el efectivo mientras citaban la Biblia con una calma que daba miedo."),
 'Robo de equipo electrónico': ("sonó un teléfono público en la calle y, de la nada, aparecieron varios individuos idénticos, de traje y gafas oscuras, que se acercaron al asegurado y se llevaron su teléfono y su portátil",
   "Sonó un teléfono público y de repente aparecieron varios tipos idénticos con traje y gafas oscuras que se llevaron mi móvil y mi portátil."),
 'Daño de equipo electrónico': ("el equipo del asegurado se mojó y, pasada la medianoche, empezó a fallar y a multiplicar los problemas, con pantallas parpadeando y aplicaciones fuera de control, como si le hubiera dado de comer después de la hora prohibida",
   "Se mojó el equipo y, pasada la medianoche, empezó a hacer cosas raras y a multiplicarse los fallos como si le hubiera dado de comer tarde."),
 'Pérdida de excursión prepagada': ("la excursión prepagada a una isla con un parque de dinosaurios clonados se canceló tras una avería eléctrica general que dejó sueltos a los animales; evacuaron a los visitantes y el operador no devolvió el importe",
   "Pagué la excursión a la isla de los dinosaurios, se fue la luz, se soltaron los animales, nos evacuaron y no me devuelven el dinero."),
 'Cancelación de crucero': ("el crucero inaugural, presentado como insumergible, fue cancelado tras chocar con un iceberg en plena noche y hundirse; la naviera ofrece una compensación que no cubre los gastos ya realizados por el asegurado",
   "El crucero «insumergible» chocó con un iceberg en plena noche y se hundió; la naviera me ofrece una compensación que no cubre nada."),
 'Quiebra de aerolínea': ("la aerolínea, fundada por un magnate excéntrico obsesionado con los aviones gigantes y con la limpieza, quebró y cesó todas sus operaciones, dejando sin valor los billetes del asegurado",
   "La aerolínea de aquel magnate obsesionado con los aviones gigantes quebró y mis billetes ya no valen nada."),
 'Secuestro de medio de transporte': ("el autobús en el que viajaba el asegurado fue retenido por un extorsionista con una bomba que estallaría si el vehículo bajaba de 80 km/h; durante {horas} horas los pasajeros circularon sin poder detenerse",
   "El autobús no podía bajar de 80 km/h o explotaba: estuvimos {horas} horas sin parar hasta que lograron desactivarlo."),
 'Defensa jurídica en el extranjero': ("el asegurado fue detenido en el aeropuerto con un paquete que otra persona había colocado en su equipaje y fue procesado en un país extranjero sin entender el idioma, por lo que necesitó un abogado local",
   "Me detuvieron en el aeropuerto por un paquete que no era mío, en un país cuyo idioma no entiendo, y necesito un abogado."),
 'Adelanto de fianza': ("el asegurado y un amigo fueron detenidos en un pueblo del sur por un malentendido en una tienda; las autoridades fijaron una fianza y un primo abogado, novato y de traje inadecuado, tuvo que adelantarla",
   "Nos detuvieron a mi amigo y a mí en un pueblo del sur por un malentendido en una tienda; mi primo, un abogado novato, tuvo que adelantar la fianza."),
 'Pérdida de equipo deportivo': ("el asegurado, integrante del equipo de trineo de un país cálido que viajaba por primera vez a unas competiciones de invierno, vio desaparecer el trineo y los cascos facturados y tuvo que competir con material prestado",
   "Veníamos de un país cálido a competir en trineo por primera vez y el trineo y los cascos desaparecieron; competimos con material prestado."),
}
assert set(HECHOS) == {t[0] for t in TIPOS}, set(t[0] for t in TIPOS) ^ set(HECHOS)

DOC_EXTRA = None

def personas(n):
    pool = ['su pareja','su hija','su hijo','su madre','su padre','un amigo','una amiga','un compañero de viaje']
    return random.sample(pool, n)

def reparto(total, n):
    """Divide total en n partes enteras > 0 que suman exactamente total."""
    pesos = [random.random() + 0.3 for _ in range(n)]
    partes = [max(1, round(total * p / sum(pesos))) for p in pesos]
    partes[0] += total - sum(partes)
    return partes



# ---------------- Requisitos y % de pago por situación ----------------
REQ = {
 'transporte': ['Certificado del transportista que acredite el retraso, la cancelación o la denegación de embarque','Billete o reserva a nombre del asegurado','Facturas originales de los gastos realizados durante la espera','Haber reclamado antes al transportista y no haber recibido asistencia suficiente'],
 'equipaje': ['Parte de irregularidad (PIR) presentado en el aeropuerto antes de salir de la terminal','Etiquetas de facturación del equipaje','Facturas o prueba de valor de los objetos (se aplica depreciación por antigüedad)','Equipaje facturado y bajo custodia del transportista'],
 'robo': ['Denuncia ante la autoridad local en las 24 horas siguientes al suceso','Relación valorada de los objetos sustraídos','Facturas o prueba de propiedad','Los objetos estaban bajo vigilancia razonable del asegurado'],
 'documentos': ['Denuncia ante la autoridad local','Documento provisional del consulado o de la autoridad competente','Facturas de las tasas y gastos de gestión','El documento era válido y necesario para el viaje'],
 'medico': ['Aviso a la Central de Asistencia lo antes posible (máximo 48 h en ingresos)','Informe médico con diagnóstico y tratamiento','Facturas originales del centro médico y recetas','La dolencia es sobrevenida y no preexistente (salvo descompensación aguda)'],
 'repatriacion': ['Autorización previa de la Central de Asistencia','Informe del equipo médico que determine la necesidad del traslado','Facturas del transporte sanitario','Documentación consular y sanitaria exigida por el país'],
 'accidente': ['Atestado, parte del accidente o informe de la autoridad','Informe médico con el diagnóstico y el pronóstico','Prueba de que la actividad estaba declarada en la póliza','El asegurado no estaba bajo los efectos del alcohol o las drogas'],
 'responsabilidad': ['Parte del daño firmado por las partes o informe de la autoridad','Presupuesto o factura de reparación','No reconocer responsabilidad ni pactar pagos sin autorización de la aseguradora','Daño causado de forma involuntaria'],
 'cancelacion': ['La causa es grave, sobrevenida e imprevisible y posterior a la contratación','Justificante documental de la causa (informe médico, certificado de defunción, carta de despido…)','Cancelación comunicada a la agencia y a los proveedores el mismo día de la causa','Facturas de cancelación y servicios no reembolsables'],
 'externo': ['Comunicado oficial o prueba del suceso (autoridad, aeropuerto, operador)','El suceso no era conocido ni anunciado al contratar','Facturas originales de los gastos adicionales','Haber seguido las instrucciones de las autoridades'],
 'legal': ['Documentación judicial del procedimiento','Los hechos son accidentales y no dolosos','Minuta del abogado y justificante de fianza o tasas','Compromiso de devolución de la fianza adelantada'],
 'electronico': ['Denuncia policial (robo) o informe técnico del daño','Factura de compra del equipo (se aplica depreciación)','El equipo no se dejó sin vigilancia en lugar público','Número de serie / identificador del equipo'],
 'prepago': ['Contrato y justificante de pago del servicio prepagado','Comunicación del operador de que no se presta o de la cancelación','Reclamación previa al proveedor sin reembolso','Facturas de las alternativas contratadas'],
}
SIT = {
 'transporte': [('Retraso inferior a 4 horas',0,'No da derecho a compensación.'),('Retraso de 4 a 8 horas',60,'Gastos justificados de comidas, traslados y comunicaciones.'),('Retraso superior a 8 horas',100,'Gastos justificados, incluido el alojamiento.'),('Pérdida de conexión por retraso del tramo previo',80,'Billetes y gastos de espera hasta la siguiente salida.'),('Denegación de embarque por sobreventa',100,'Gastos adicionales no compensados por el transportista.')],
 'equipaje': [('Pérdida definitiva del equipaje facturado',100,'Valor real de los objetos con depreciación por antigüedad.'),('Daño parcial del equipaje',70,'Reparación o valor de los objetos dañados.'),('Retraso de equipaje inferior a 6 horas',0,'No da derecho a compensación.'),('Retraso de equipaje de 6 a 24 horas',50,'Gastos de primera necesidad justificados.'),('Retraso de equipaje superior a 24 horas',100,'Gastos de primera necesidad justificados.'),('Pérdida de equipo deportivo',80,'Valor del equipo con depreciación.')],
 'robo': [('Robo o hurto con denuncia en 24 horas',80,'Valor de los objetos con depreciación.'),('Robo de dinero en efectivo',50,'Hasta un máximo de 300 € de efectivo.')],
 'documentos': [('Robo o pérdida de documentos con denuncia',100,'Tasas, gestión y traslados al consulado.'),('Pérdida de llaves',70,'Cerrajero y duplicado urgente.')],
 'medico': [('Gastos médicos por enfermedad o accidente sobrevenidos',100,'Asistencia, pruebas, medicación y hospitalización.'),('Asistencia dental urgente',60,'Solo tratamiento urgente del dolor o la infección.'),('Descompensación aguda de enfermedad preexistente',50,'Solo la fase aguda, no el tratamiento de la enfermedad.'),('Gastos de acompañante por hospitalización',80,'Alojamiento y desplazamiento de un familiar.')],
 'repatriacion': [('Repatriación o evacuación con autorización previa',100,'Traslado sanitario o de restos mortales autorizado por la Central.')],
 'accidente': [('Gastos de asistencia por accidente',100,'Atención médica y rehabilitación.'),('Accidente durante actividad deportiva declarada',80,'Asistencia y rehabilitación.'),('Fallecimiento accidental',100,'Capital contratado para los beneficiarios.'),('Invalidez permanente parcial',70,'Según baremo, tras la estabilización de las secuelas.')],
 'responsabilidad': [('Responsabilidad civil frente a terceros',100,'Indemnización al perjudicado y gastos de defensa.'),('Daños en el alojamiento',80,'Reparación facturada por el alojamiento.'),('Daños en vehículo de alquiler (franquicia)',100,'Franquicia y cargos del contrato de alquiler.'),('Robo del vehículo de alquiler',70,'Franquicia y gastos no cubiertos por el alquiler.')],
 'cancelacion': [('Cancelación por causa grave documentada',100,'Gastos no recuperables del viaje.'),('Interrupción del viaje',80,'Servicios no disfrutados desde el regreso.'),('Cancelación por causa laboral (despido)',90,'Gastos no recuperables del viaje.'),('Regreso anticipado por motivo grave',100,'Billetes de regreso y servicios no disfrutados.')],
 'externo': [('Huelga o disturbios civiles',70,'Gastos adicionales de alojamiento y transporte.'),('Desastre natural',100,'Alojamiento, transporte y manutención adicionales.'),('Cierre de espacio aéreo',100,'Gastos de espera y reubicación.'),('Cuarentena obligatoria o contagio impeditivo',90,'Alojamiento y regreso modificado.'),('Retención del medio de transporte',100,'Gastos adicionales justificados.')],
 'legal': [('Defensa jurídica por hechos accidentales',100,'Honorarios, tasas y traducciones.'),('Adelanto de fianza',100,'Anticipo reintegrable por el asegurado.')],
 'electronico': [('Robo de equipo electrónico con denuncia',80,'Valor con depreciación.'),('Daño accidental de equipo electrónico',60,'Reparación o valor con depreciación.')],
 'prepago': [('Servicio prepagado no prestado',100,'Importe del servicio no prestado.'),('Cancelación del servicio por el proveedor',80,'Importe no compensado por el proveedor.'),('Insolvencia del proveedor',100,'Importe del servicio no disfrutado.')],
}
TIPO_SIT = {
 'Pérdida de conexión':'Pérdida de conexión por retraso del tramo previo','Overbooking':'Denegación de embarque por sobreventa',
 'Equipaje perdido':'Pérdida definitiva del equipaje facturado','Equipaje dañado':'Daño parcial del equipaje','Retraso de equipaje superior a 24h':'Retraso de equipaje superior a 24 horas','Pérdida de equipo deportivo':'Pérdida de equipo deportivo',
 'Robo de equipaje':'Robo o hurto con denuncia en 24 horas','Robo de dinero en efectivo':'Robo de dinero en efectivo',
 'Robo de documentos':'Robo o pérdida de documentos con denuncia','Pérdida de pasaporte':'Robo o pérdida de documentos con denuncia','Pérdida de llaves':'Pérdida de llaves',
 'Gastos médicos en el extranjero':'Gastos médicos por enfermedad o accidente sobrevenidos','Hospitalización':'Gastos médicos por enfermedad o accidente sobrevenidos','Asistencia dental urgente':'Asistencia dental urgente','Enfermedad preexistente':'Descompensación aguda de enfermedad preexistente','Gastos de acompañante':'Gastos de acompañante por hospitalización',
 'Repatriación sanitaria':'Repatriación o evacuación con autorización previa','Repatriación de restos':'Repatriación o evacuación con autorización previa','Evacuación de emergencia':'Repatriación o evacuación con autorización previa',
 'Accidente deportivo':'Accidente durante actividad deportiva declarada','Accidente de tráfico':'Gastos de asistencia por accidente','Muerte accidental':'Fallecimiento accidental','Invalidez permanente':'Invalidez permanente parcial',
 'Responsabilidad civil':'Responsabilidad civil frente a terceros','Daños en alojamiento':'Daños en el alojamiento','Alquiler de coche dañado':'Daños en vehículo de alquiler (franquicia)','Robo de vehículo de alquiler':'Robo del vehículo de alquiler',
 'Cancelación de viaje':'Cancelación por causa grave documentada','Interrupción de viaje':'Interrupción del viaje','Cancelación por enfermedad familiar':'Cancelación por causa grave documentada','Cancelación por fallecimiento familiar':'Cancelación por causa grave documentada',
 'Cancelación por despido laboral':'Cancelación por causa laboral (despido)','Cita judicial':'Cancelación por causa grave documentada','Gastos de regreso anticipado':'Regreso anticipado por motivo grave',
 'Desastre natural':'Desastre natural','Huelga':'Huelga o disturbios civiles','Disturbios civiles':'Huelga o disturbios civiles','Cierre de espacio aéreo':'Cierre de espacio aéreo','Cuarentena obligatoria':'Cuarentena obligatoria o contagio impeditivo','Resultado positivo COVID-19':'Cuarentena obligatoria o contagio impeditivo','Secuestro de medio de transporte':'Retención del medio de transporte',
 'Defensa jurídica en el extranjero':'Defensa jurídica por hechos accidentales','Adelanto de fianza':'Adelanto de fianza',
 'Robo de equipo electrónico':'Robo de equipo electrónico con denuncia','Daño de equipo electrónico':'Daño accidental de equipo electrónico',
 'Pérdida de excursión prepagada':'Servicio prepagado no prestado','Cancelación de crucero':'Cancelación del servicio por el proveedor','Quiebra de aerolínea':'Insolvencia del proveedor',
}
def sit_for(tipo, cat_name, horas):
    if tipo == 'Retraso de vuelo':
        nombre = 'Retraso inferior a 4 horas' if horas < 4 else 'Retraso de 4 a 8 horas' if horas <= 8 else 'Retraso superior a 8 horas'
    elif tipo == 'Equipaje retrasado':
        nombre = 'Retraso de equipaje inferior a 6 horas' if horas < 6 else 'Retraso de equipaje de 6 a 24 horas'
    else:
        nombre = TIPO_SIT[tipo]
    return next(x for x in SIT[cat_name] if x[0] == nombre)

# ---------------- Cláusulas y pólizas ----------------
CLAUSULA_TXT = {
 'transporte': ('Retrasos, cancelaciones y denegación de embarque', 'Se reembolsan los gastos razonables y justificados de alojamiento, comidas, traslados y comunicaciones cuando el medio de transporte sufra un retraso superior a 4 horas, una cancelación o una denegación de embarque, siempre que el transportista no haya prestado la asistencia debida. El asegurado debe obtener el certificado del transportista.', ['Retrasos anunciados antes de contratar la póliza','Huelgas conocidas en la fecha de contratación']),
 'equipaje': ('Pérdida, daño y retraso de equipaje', 'Se indemniza la pérdida definitiva o el daño del equipaje facturado, con depreciación por antigüedad, y los gastos de primera necesidad si el equipaje se retrasa más de 6 horas. Es obligatorio presentar el parte de irregularidad (PIR) en el aeropuerto antes de abandonar la terminal.', ['Equipaje sin facturar y dejado sin vigilancia','Joyas, dinero y documentos dentro de maletas facturadas','Daños por desgaste normal']),
 'robo': ('Robo y pérdida de efectos personales', 'Se indemniza el robo con violencia o intimidación y el hurto de efectos personales siempre que haya denuncia presentada en las 24 horas siguientes ante la autoridad local. Se aplica depreciación por antigüedad y un sublímite por objeto.', ['Pérdida simple o extravío sin denuncia','Robo en vehículo sin signos de fuerza','Dinero en efectivo superior a 300 €']),
 'documentos': ('Documentación personal', 'Se reembolsan las tasas y gastos de gestión para obtener documentos de identidad o de viaje provisionales en caso de robo o pérdida, incluyendo traslados al consulado y una noche adicional de alojamiento cuando sea necesaria.', ['Documentos caducados o no válidos para el viaje','Multas o sanciones administrativas']),
 'medico': ('Gastos médicos en el extranjero', 'Se cubren los gastos médicos, quirúrgicos, farmacéuticos y de hospitalización ocurridos durante el viaje a consecuencia de enfermedad o accidente sobrevenidos, hasta el límite indicado. La Central de Asistencia debe ser avisada en cuanto sea posible.', ['Enfermedades preexistentes o crónicas sin descompensación aguda','Tratamientos estéticos o programados','Embarazo a partir de la semana 28']),
 'repatriacion': ('Repatriación y evacuación', 'Se organiza y se asume el traslado sanitario del asegurado, o de los restos mortales, hasta su domicilio o centro hospitalario de referencia cuando lo determine el equipo médico de la aseguradora. Es imprescindible la autorización previa de la Central de Asistencia.', ['Traslados no autorizados previamente','Evacuaciones por motivos de comodidad']),
 'accidente': ('Accidentes personales', 'Se garantiza el pago de las prestaciones por fallecimiento, invalidez permanente o gastos de asistencia cuando el asegurado sufra un accidente durante el viaje. La invalidez se valora según el baremo contratado, una vez estabilizadas las secuelas.', ['Deportes de riesgo no declarados','Accidentes bajo los efectos del alcohol o las drogas','Participación en competiciones']),
 'responsabilidad': ('Responsabilidad civil y daños a terceros', 'Se cubren las indemnizaciones que el asegurado deba pagar a terceros por daños materiales o personales causados involuntariamente durante el viaje, así como los gastos de defensa. El asegurado no debe reconocer responsabilidad ni acordar pagos sin autorización.', ['Daños dolosos','Daños a bienes que el asegurado posea o alquile bajo contrato de larga duración','Responsabilidad profesional']),
 'cancelacion': ('Cancelación y regreso anticipado', 'Se reembolsan los gastos no recuperables de viaje cuando el asegurado deba cancelarlo, o interrumpirlo, por una causa grave, sobrevenida e imprevisible posterior a la contratación: enfermedad grave, fallecimiento de familiares de primer grado, despido, citación judicial, entre otras. La causa debe acreditarse documentalmente.', ['Causas conocidas antes de contratar','Cambios de opinión o de planes','Enfermedades preexistentes sin agravamiento imprevisible']),
 'externo': ('Eventos de fuerza mayor', 'Se cubren los gastos adicionales de alojamiento, transporte y manutención derivados de huelgas, desastres naturales, disturbios, cierres de espacio aéreo o cuarentenas impuestas por la autoridad que impidan continuar el viaje según lo previsto.', ['Hechos previsibles o anunciados antes de la contratación','Guerras declaradas','Desastres en zonas con alerta oficial previa']),
 'legal': ('Defensa jurídica y fianzas', 'Se cubren los honorarios de abogado y procurador y se adelanta la fianza penal exigida por las autoridades locales por hechos accidentales ocurridos durante el viaje. El importe adelantado debe devolverse a la aseguradora al ser liberado.', ['Delitos dolosos','Conflictos con el tomador o con la propia aseguradora','Infracciones administrativas']),
 'electronico': ('Equipos electrónicos', 'Se indemniza el robo o el daño accidental de teléfonos, ordenadores portátiles, cámaras y equipos electrónicos de uso personal, con depreciación por antigüedad, siempre que haya denuncia o informe técnico del daño.', ['Daños por mal uso o desgaste','Pérdida simple','Equipos dejados sin vigilancia en lugares públicos']),
 'prepago': ('Servicios prepagados e insolvencia', 'Se reembolsan los servicios turísticos prepagados no prestados por causa ajena al asegurado, incluida la insolvencia o quiebra del proveedor, y los gastos de alternativas necesarias para continuar el viaje.', ['Cancelaciones por voluntad del asegurado','Servicios no contratados a través de proveedor autorizado']),
}
REQ_GENERALES = [
 'La póliza está registrada y en vigor en la fecha del suceso (entre la fecha de contratación y el fin del viaje).',
 'La prima está al día: ninguna cuota vencida estaba impagada en la fecha del suceso.',
 'La cobertura reclamada está incluida en el plan contratado (Básico, Estándar o Premium).',
 'El suceso ocurre dentro del viaje asegurado y no está incluido en las exclusiones de la cláusula ni en las exclusiones generales.',
 'El suceso se comunica en un máximo de 7 días y la reclamación se presenta en un máximo de 30 días desde el suceso.',
 'Se aporta toda la documentación original exigida por la cláusula de la cobertura.',
 'El pago se calcula así: gasto justificado × % de la situación → tope del límite de cobertura → menos la franquicia.',
]
GENERALES = [
 ('G-07','Requisitos generales para que el seguro pague','Para que la aseguradora abone una reclamación deben cumplirse todos los requisitos siguientes. Si falla alguno, la reclamación se rechaza o queda en suspenso hasta su subsanación. El importe a pagar es el gasto justificado multiplicado por el porcentaje de la situación, con el tope del límite de la cobertura y descontada la franquicia.', [], 'general'),
 ('G-01','Objeto y ámbito territorial','La póliza garantiza al asegurado, durante las fechas del viaje indicado en las condiciones particulares y en el destino contratado, las coberturas incluidas en su plan. La cobertura comienza a las 00:00 del día de salida y termina a las 24:00 del día de regreso.', [], 'general'),
 ('G-02','Obligaciones del asegurado ante un siniestro','El asegurado debe comunicar el siniestro en un plazo máximo de 7 días desde que lo conozca y presentar la reclamación con la documentación requerida dentro de los 30 días siguientes al suceso, conservando todos los justificantes originales.', [], 'general'),
 ('G-03','Exclusiones generales','Quedan excluidos los siniestros causados por dolo o mala fe del asegurado, los derivados de guerras, actos terroristas en zonas con alerta previa, radiaciones nucleares y las consecuencias de la práctica de deportes profesionales.', ['Dolo o mala fe','Guerra y terrorismo declarado','Deportes profesionales'], 'general'),
 ('G-04','Franquicia, límites y reembolso','Los importes reembolsables no podrán superar el límite de cada cobertura ni el valor real de lo perdido; en cada siniestro se descontará la franquicia indicada. Los pagos se efectúan en un plazo máximo de 15 días desde la aceptación del siniestro.', [], 'general'),
 ('G-06','Pago de la prima y suspensión de cobertura','El pago de la prima es condición para la vigencia de las coberturas. Si una cuota no se abona en su fecha de vencimiento, la cobertura queda suspendida desde ese día y la aseguradora no responde de los siniestros ocurridos durante la suspensión, aunque el pago se regularice después.', ['Siniestros ocurridos con cuotas vencidas e impagadas'], 'general'),
 ('G-05','Fraude y prescripción','La declaración falsa o la documentación manipulada libera a la aseguradora de toda prestación. Las acciones derivadas de la póliza prescriben a los dos años contados desde la fecha del siniestro.', [], 'general'),
]
clausulas = []
CODIGO = {}
for n, (k, (titulo, texto, excl)) in enumerate(CLAUSULA_TXT.items(), 1):
    CODIGO[k] = f'C-{n:02d}'
    clausulas.append({'codigo': CODIGO[k], 'categoria': k, 'titulo': titulo, 'texto': texto, 'exclusiones': excl,
                      'plazoReclamacionDias': 30, 'documentosRequeridos': CAT[k]['docs'],
                      'requisitos': REQ[k], 'porcentajes': [{'situacion': n_, 'porcentaje': p_, 'condicion': c_} for n_, p_, c_ in SIT[k]]})
for cod, titulo, texto, excl, _ in GENERALES:
    clausulas.append({'codigo': cod, 'categoria': 'general', 'titulo': titulo, 'texto': texto,
                      'exclusiones': excl, 'plazoReclamacionDias': 30, 'documentosRequeridos': [],
                      'requisitos': REQ_GENERALES if cod == 'G-07' else [], 'porcentajes': []})

PLANES = {'Básico': (0.5, {'legal', 'electronico', 'prepago'}), 'Estándar': (1.0, {'legal'}), 'Premium': (2.0, set())}
POLIZAS = []
numeros = random.sample(range(100000, 999999), N_POLIZAS)
for n in range(N_POLIZAS):
    nombre, a1, a2 = random.choice(NOMBRES), random.choice(APELLIDOS), random.choice(APELLIDOS)
    dni = random.randint(10_000_000, 99_999_999)
    plan = random.choices(list(PLANES), weights=[3, 4, 2])[0]
    mult, excl = PLANES[plan]
    inicio = FECHA_INICIO_VIAJES + timedelta(days=random.randint(0, DIAS_VIAJES))
    fin = inicio + timedelta(days=random.randint(3, 20))
    acomp = personas(random.choice([0, 0, 1, 1, 2, 3]))
    contratacion = inicio - timedelta(days=random.randint(25, 60))
    POLIZAS.append({
        'numero': f'POL-{numeros[n]}', 'plan': plan,
        'estado': 'Vigente' if fin >= FECHA_REF else 'Finalizada',
        'tomador': {'nombre': nombre, 'apellido1': a1, 'apellido2': a2, 'dni': f'{dni}{LETRAS[dni % 23]}',
                    'email': plano(f'{nombre}.{a1}{n}') + '@example.com', 'telefono': f'+34 6{random.randint(10_000_000, 99_999_999)}'},
        'acompanantes': acomp,
        'viaje': {'destino': random.choice(list(DESTINOS)), 'inicio': iso(inicio), 'fin': iso(fin)},
        'fechaContratacion': iso(contratacion),
        'prima': round((18 + 4.5 * (fin - inicio).days) * mult * (1 + 0.15 * len(acomp))), 'moneda': 'EUR',
        'coberturas': {k: {'nombre': CAT[k]['cobertura'], 'limite': int(CAT[k]['limite'] * mult),
                           'franquicia': random.choice([0, 50, 100]), 'clausula': CODIGO[k]}
                       for k in CAT if k not in excl},
        'clausulasGenerales': [g[0] for g in GENERALES],
    })
    pol_n = POLIZAS[-1]
    n_cuotas = random.choice([1, 1, 2, 3])
    partes = reparto(pol_n['prima'], n_cuotas)
    metodo = random.choice(['Tarjeta', 'Transferencia', 'Domiciliación'])
    pol_n['pagos'] = [{'cuota': k + 1, 'fecha': iso(contratacion + timedelta(days=2 * k)), 'importe': partes[k],
                       'metodo': metodo, 'referencia': f'PAG-{random.randint(1000000, 9999999)}', 'estado': 'Pagado'}
                      for k in range(n_cuotas)]
    if random.random() < 0.15:  # ~15% de pólizas con una cuota vencida sin pagar
        pol_n['pagos'][-1]['estado'] = 'Impagada'
    pol_n['primaPagada'] = sum(p['importe'] for p in pol_n['pagos'] if p['estado'] == 'Pagado')
    pol_n['primaPendiente'] = pol_n['prima'] - pol_n['primaPagada']
    pol_n['pagosAlDia'] = all(p['estado'] == 'Pagado' for p in pol_n['pagos'])

for _ruta in ('CLAUSES_FILE', 'POLICIES_FILE', 'CLAIMS_FILE'):
    os.makedirs(os.path.dirname(cfg.ruta(_ruta)), exist_ok=True)
with open(cfg.ruta('CLAUSES_FILE'), 'w', encoding='utf-8') as fh: json.dump(clausulas, fh, ensure_ascii=False, indent=2)
with open(cfg.ruta('POLICIES_FILE'), 'w', encoding='utf-8') as fh: json.dump(POLIZAS, fh, ensure_ascii=False, indent=2)

claims = []
for i in range(N_RECLAMACIONES):
    tipo, cat_name, hecho = TIPOS[i % 50]
    cat = CAT[cat_name]
    pol = random.choice(POLIZAS)
    destino = pol['viaje']['destino']; pais, hotel = DESTINOS[destino]
    inicio = date.fromisoformat(pol['viaje']['inicio']); fin = date.fromisoformat(pol['viaje']['fin'])
    pcob = pol['coberturas'].get(cat_name); cubierta = pcob is not None
    limite = pcob['limite'] if cubierta else 0
    if cat.get('previo') and tipo != 'Interrupción de viaje' and tipo != 'Gastos de regreso anticipado':
        incidente = inicio - timedelta(days=random.randint(2, 20))
    else:
        incidente = inicio + timedelta(days=random.randint(0, (fin - inicio).days))
    ingreso = incidente + timedelta(days=random.randint(0, 36))
    hora = f'{random.randint(0, 23):02d}:{random.choice(["00","10","15","20","30","40","45","50"])}'
    estado = random.choice(ESTADOS)
    canal = random.choice(CANALES)
    horas = random.randint(3, 14)
    sit = sit_for(tipo, cat_name, horas); pct = sit[1]
    cuotas_vencidas = [q for q in pol['pagos'] if q['fecha'] <= iso(incidente)]
    impagadas = [q for q in cuotas_vencidas if q['estado'] != 'Pagado']
    al_dia = not impagadas
    if (not cubierta or not al_dia or pct == 0) and estado in ('Aprobado', 'Pagado', 'Cerrado'): estado = 'Rechazado'

    t = pol['tomador']; nombre, a1, a2 = t['nombre'], t['apellido1'], t['apellido2']
    dni_txt = t['dni']; acomp = pol['acompanantes']
    aer, vuelo = random.choice(AEROLINEAS), f'{random.choice(["AN","VA","TM","IO","SL"])}{random.randint(100, 9999)}'
    lugar = random.choice(cat['lugar']).format(d=destino, h=hotel, n=random.randint(1, 40))
    hecho_txt, decl_txt = HECHOS[tipo]
    fmt = dict(vuelo=vuelo, aer=aer, horas=horas, h=hotel, lugar=lugar)
    hecho_t = hecho_txt.format(**fmt) + '.'
    declaracion = decl_txt.format(**fmt)

    # Importe y desglose
    importe = random.randint(120, min(cat['limite'] * 1.3, 12000)) if cat['limite'] <= 10000 else random.randint(2500, 45000)
    n_items = random.randint(2, min(4, len(cat['conceptos'])))
    conceptos = random.sample(cat['conceptos'], n_items)
    desglose = [{'concepto': c, 'importe': v} for c, v in zip(conceptos, reparto(importe, n_items))]
    franquicia = pcob['franquicia'] if cubierta else 0
    tras_pct = round(importe * pct / 100)
    cubierto = min(tras_pct, limite)
    propuesto = max(0, cubierto - franquicia)
    aprobado = {'Aprobado': propuesto, 'Pagado': propuesto, 'Rechazado': 0, 'Cerrado': propuesto}.get(estado)
    calculo = {'reclamado': importe, 'porcentaje': pct, 'trasPorcentaje': tras_pct, 'limite': limite,
               'trasLimite': cubierto, 'franquicia': franquicia, 'aPagar': propuesto}

    # Terceros y referencias
    terceros = []
    for rol in cat['terceros']:
        if rol == 'Aerolínea': nom = aer
        elif rol == 'Hotel' or 'alojamiento' in rol: nom = hotel
        elif rol == 'Policía local': nom = f'Comisaría central de {destino}'
        elif rol == 'Consulado': nom = f'Consulado de España en {destino}'
        elif rol == 'Centro médico': nom = random.choice([f'Hospital Central de {destino}', f'Clínica Internacional de {destino}'])
        elif rol == 'Agencia de viajes': nom = random.choice(['Viajes Horizonte','Mundo Ruta','Travelia Club'])
        else: nom = f'{rol} (identificado en el expediente)'
        terceros.append({'rol': rol, 'nombre': nom})
    ref = None
    if cat['ref']: ref = f"{cat['ref']}-{destino[:3].upper()}-{random.randint(10000, 99999)}"

    # Documentación
    docs = [{'nombre': d, 'recibido': random.random() > 0.2} for d in cat['docs']]
    if estado in ('Aprobado', 'Pagado', 'Cerrado', 'Rechazado'):
        for d in docs: d['recibido'] = True

    # Glosa
    comp_txt = f'junto a {", ".join(acomp[:-1]) + " y " + acomp[-1] if len(acomp) > 1 else acomp[0]}' if acomp else 'en solitario'
    dias_ingreso = (ingreso - incidente).days
    if cat.get('previo') and incidente < inicio:
        p1 = (f'{nombre} {a1} {a2} (DNI {dni_txt}), titular de la póliza, tenía contratado un viaje a {destino} ({pais}) del {largo(inicio)} al {largo(fin)}, '
              f'{comp_txt}, alojado en el Hotel {hotel}. El {largo(incidente)}, {hecho_t[0].lower() + hecho_t[1:]}')
    else:
        p1 = (f'El {largo(incidente)} a las {hora} h, en {destino} ({pais}), concretamente en «{lugar}», {nombre} {a1} {a2} (DNI {dni_txt}), '
              f'titular de la póliza, que viajaba {comp_txt} del {largo(inicio)} al {largo(fin)}, vivió el siguiente suceso: {hecho_t[0].lower() + hecho_t[1:]}')
    gest = {
        'transporte': f'Reclamó a {aer} y a su agencia, pero no recibió compensación ni asistencia suficiente; sufragó por su cuenta los gastos necesarios mientras duró la incidencia.',
        'equipaje': 'Presentó de inmediato el parte de irregularidad ante la compañía y conserva las etiquetas de facturación; realizó compras imprescindibles mientras duró la incidencia.',
        'robo': 'Presentó la denuncia ante la policía local y gestionó con las entidades correspondientes el bloqueo de tarjetas y la reposición de lo sustraído.',
        'documentos': 'Presentó denuncia, acudió al consulado para obtener documentación provisional y asumió los gastos de gestión y de alojamiento adicionales.',
        'medico': 'Fue atendido por el centro indicado, que emitió el informe médico y las facturas; el asegurado abonó los gastos y solicita su reembolso.',
        'repatriacion': 'La Central de Asistencia fue avisada, se coordinó el traslado con el equipo médico y se emitió el informe de aptitud para el transporte.',
        'accidente': 'Fue atendido en el lugar y trasladado al centro médico; se levantó el parte del accidente y se emitió el informe médico con el pronóstico y el tratamiento.',
        'responsabilidad': 'Se levantó el parte con las partes implicadas, se obtuvo el presupuesto o la factura de la reparación y el asegurado abonó los gastos exigidos.',
        'cancelacion': 'Comunicó la cancelación a la agencia y a los proveedores en cuanto se produjo la causa, y recibió la liquidación de los gastos de cancelación aplicados.',
        'externo': 'Siguió las instrucciones de las autoridades, reorganizó por su cuenta alojamiento y desplazamientos, y conserva los comunicados y justificantes.',
        'legal': 'Contrató asistencia jurídica local, abonó los importes exigidos y aporta la documentación del procedimiento y las minutas del letrado.',
        'electronico': 'Denunció los hechos / obtuvo un informe técnico del daño y aporta la factura de compra del equipo para su valoración con depreciación.',
        'prepago': 'Reclamó al operador, que no reembolsó el servicio; el asegurado contrató alternativas y conserva el contrato, los pagos y las comunicaciones.',
    }[cat_name]
    if ref: gest += f' Referencia oficial: {ref}.'
    p2 = gest
    desglose_txt = '; '.join(d['concepto'].lower() + ': ' + eur(d['importe']) for d in desglose)
    cob_nombre, cob_limite = cat['cobertura'], limite
    sit_txt = ' Situación: «' + sit[0] + '», con derecho al ' + str(pct) + ' % del gasto justificado' + (', hasta el límite y con la franquicia indicada.' if pct else ' (no da derecho a pago).')
    impago_txt = (f' Atención: en la fecha del suceso la cuota {impagadas[0]["cuota"]} de la prima ({eur(impagadas[0]["importe"])}, vencida el {largo(date.fromisoformat(impagadas[0]["fecha"]))}) figuraba impagada.'
                  if impagadas else '')
    cob_txt = ('La cobertura aplicable es «' + cob_nombre + '» (límite ' + eur(cob_limite) + ', franquicia ' + eur(franquicia) + ') según la cláusula '
               + (pcob['clausula'] if cubierta else '') + ' del plan ' + pol['plan'] + '.') if cubierta else (
               'La póliza (plan ' + pol['plan'] + ') no incluye la cobertura «' + cob_nombre + '».')
    p3 = (f'El asegurado ingresó la reclamación el {largo(ingreso)} por {canal.lower()}, {dias_ingreso} días después del suceso, solicitando el reembolso de '
          f'{eur(importe)} según el desglose ({desglose_txt}). '
          '') + cob_txt + sit_txt + impago_txt

    # Comprobaciones del analista
    checks = [
        {'texto': 'Suceso dentro de la vigencia de la póliza y del viaje', 'ok': True},
        {'texto': f'Reclamación presentada en plazo (30 días): {dias_ingreso} días', 'ok': dias_ingreso <= 30},
        {'texto': 'Documentación completa', 'ok': all(d['recibido'] for d in docs)},
        {'texto': f'Importe dentro del límite de cobertura ({eur(cob_limite)})', 'ok': cubierta and importe <= cob_limite},
    ]
    if ref: checks.append({'texto': f'Referencia oficial aportada ({ref})', 'ok': True})
    motivo = None
    if estado == 'Rechazado':
        checks[1]['ok'] = False if dias_ingreso > 30 else checks[1]['ok']
        motivo = ('Póliza con la cuota ' + str(impagadas[0]['cuota']) + ' impagada en la fecha del suceso: cobertura suspendida (cláusula G-06).' if not al_dia else
                  f'La cobertura «{cob_nombre}» no está incluida en el plan {pol["plan"]}.' if not cubierta else
                  f'Situación sin derecho a pago: «{sit[0]}» ({pct} %).' if pct == 0 else
                  'Reclamación presentada fuera de plazo.' if dias_ingreso > 30 else
                  'El importe excede el límite y los hechos no quedan acreditados con la documentación aportada.' if tras_pct > cob_limite else
                  'La causa alegada no queda amparada por las condiciones de la póliza.')

    checks.insert(0, {'texto': (f'Póliza {pol["numero"]} registrada y pagos al día en la fecha del suceso' if al_dia else f'Póliza {pol["numero"]} registrada, pero con la cuota {impagadas[0]["cuota"]} impagada en la fecha del suceso'), 'ok': al_dia})
    checks.insert(1, {'texto': f'Cobertura «{cob_nombre}» incluida en el plan {pol["plan"]}', 'ok': cubierta})
    reqs = [{'texto': r_, 'ok': True} for r_ in REQ[cat_name]]
    if estado == 'Documentación pendiente': random.choice(reqs[1:])['ok'] = False
    if motivo and motivo.startswith('La causa'): reqs[0]['ok'] = False
    hist = [{'fecha': iso(ingreso), 'evento': 'Reclamación registrada', 'detalle': 'Expediente creado y asignado.'}]
    f = ingreso
    for ev, det in [('Documentación recibida', 'Se recibió la documentación aportada por el cliente.'),
                    ('En revisión', 'Análisis de cobertura y de la documentación.'),
                    (f'Resolución: {estado}', motivo or 'Estado actualizado por el gestor.')][:{'Abierto':0,'En revisión':2,'Documentación pendiente':1}.get(estado, 3)]:
        f += timedelta(days=random.randint(1, 5))
        hist.append({'fecha': iso(f), 'evento': ev, 'detalle': det})

    claims.append({
        'id': f'CLM-{i+1:04d}', 'tipoReclamacion': tipo,
        'nombreCliente': f'{nombre} {a1} {a2}', 'dniCliente': f'{dni_txt}',
        'email': t['email'], 'telefono': t['telefono'],
        'numeroPoliza': pol['numero'], 'planPoliza': pol['plan'], 'pagosAlDia': al_dia,
        'fechaIngreso': iso(ingreso), 'casoAbiertoPorCliente': random.random() > 0.2, 'canal': canal,
        'fechaInicioViaje': iso(inicio), 'fechaFinViaje': iso(fin), 'destino': destino, 'pais': pais,
        'estado': estado, 'importeReclamado': importe, 'importeAprobado': aprobado, 'moneda': 'EUR',
        'gestor': random.choice(GESTORES), 'ultimaActualizacion': hist[-1]['fecha'],
        'incidente': {'fecha': iso(incidente), 'hora': hora, 'lugar': lugar, 'ciudad': destino, 'pais': pais, 'referenciaOficial': ref},
        'acompanantes': acomp,
        'glosa': [p1, 'Declaración del asegurado: «' + declaracion + '»', p2, p3], 'declaracion': declaracion,
        'hechos': {
            'quien': f'{nombre} {a1} {a2} (DNI {dni_txt}), {comp_txt}',
            'que': hecho_t[0].upper() + hecho_t[1:],
            'cuando': f'{largo(incidente)}, {hora} h',
            'donde': f'{lugar} — {destino}, {pais}',
            'como': gest,
            'cuanto': f'{eur(importe)} reclamados en {len(desglose)} conceptos',
        },
        'desglose': desglose,
        'cobertura': {'nombre': cat['cobertura'], 'limite': limite, 'franquicia': franquicia, 'incluida': cubierta, 'clausula': pcob['clausula'] if cubierta else None},
        'situacion': {'nombre': sit[0], 'porcentaje': pct, 'condicion': sit[2]}, 'calculo': calculo, 'requisitos': reqs,
        'terceros': terceros, 'documentos': docs, 'comprobaciones': checks, 'motivoRechazo': motivo,
        'historial': hist, 'notas': '',
    })

with open(cfg.ruta('CLAIMS_FILE'), 'w', encoding='utf-8') as fh:
    json.dump(claims, fh, ensure_ascii=False, indent=2)
print(f'Generadas {len(claims)} reclamaciones, {len({c["tipoReclamacion"] for c in claims})} tipos.')
