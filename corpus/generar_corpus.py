"""
ECO - Paso 1: generador del mini-internet sintético.

Crea páginas de noticias ficticias organizadas en escenarios. Cada escenario
es un "pequeño internet" alrededor de una afirmación, con una de cuatro formas
de propagación:

  organico     -> varios medios reportan por su cuenta, cada uno con detalles propios
  literal      -> un origen y varios sitios que lo copian casi igual
  parafrasis   -> un origen y varios sitios que lo reescriben sin aportar nada nuevo
  comunicado   -> un comunicado oficial que otros sitios reproducen

Conjunto de estrés (ataques contra ECO):
  fabricado_literal     -> copias casi idénticas que agregan un testimonio y una cifra inventados
  fabricado_parafrasis  -> reescrituras que además agregan detalles inventados

Salida:
  corpus/sitios/<escenario>/<pagina>.html   páginas HTML
  corpus/index.html                         índice para navegar en la demo
  corpus/ground_truth.json                  respuesta correcta de cada escenario
  corpus/indice_busqueda.json               temas y URLs por escenario (sin respuestas), para el buscador simulado

Todo el contenido es ficticio: municipios, medios, entidades y personas son inventados.
Uso:
  python generar_corpus.py            (semilla 42 por defecto)
  python generar_corpus.py --semilla 7
Solo usa la biblioteca estándar de Python.
"""

import argparse
import os
import html
import json
import random
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DIR_SITIOS = RAIZ / "sitios"
URL_BASE = os.getenv("ECO_URL_BASE", "http://localhost:8765")

# ---------------------------------------------------------------------------
# Medios ficticios
# ---------------------------------------------------------------------------
MEDIOS = [
    {"nombre": "Noticias Altiplano", "dominio": "noticiasaltiplano.test", "tipo": "medio"},
    {"nombre": "El Faro Regional", "dominio": "elfaroregional.test", "tipo": "medio"},
    {"nombre": "Crónica Andina", "dominio": "cronicaandina.test", "tipo": "medio"},
    {"nombre": "Diario Sabana", "dominio": "diariosabana.test", "tipo": "medio"},
    {"nombre": "Voz del Valle", "dominio": "vozdelvalle.test", "tipo": "medio"},
    {"nombre": "El Mirador", "dominio": "elmirador.test", "tipo": "medio"},
]

GRANJAS = [
    {"nombre": "Última Hora 24", "dominio": "ultimahora24.test", "tipo": "granja"},
    {"nombre": "Alerta Nacional Ya", "dominio": "alertanacionalya.test", "tipo": "granja"},
    {"nombre": "Lo Que Pasa Hoy", "dominio": "loquepasahoy.test", "tipo": "granja"},
    {"nombre": "InfoExprés", "dominio": "infoexpres.test", "tipo": "granja"},
    {"nombre": "El Dato Viral", "dominio": "eldatoviral.test", "tipo": "granja"},
    {"nombre": "Noticias al Instante", "dominio": "noticiasalinstante.test", "tipo": "granja"},
    {"nombre": "Pulso Digital", "dominio": "pulsodigital.test", "tipo": "granja"},
]

NOMBRES = ["Marta", "Jorge", "Luz Dary", "Hernán", "Yolanda", "Fabio", "Carolina",
           "Wilson", "Gloria", "Andrés", "Sandra", "Édgar", "Nubia", "Ramiro"]
APELLIDOS = ["Rincón", "Bermúdez", "Salcedo", "Patiño", "Quintero", "Avendaño",
             "Cárdenas", "Ospina", "Lozano", "Mejía", "Galindo", "Toro"]
OFICIOS = ["comerciante", "docente", "líder comunal", "habitante",
           "integrante de la junta comunal"]
BARRIOS = ["El Carmen", "Las Brisas", "San José", "La Floresta", "El Prado",
           "Villa Nueva", "Los Almendros", "La Pradera", "Santa Rita", "El Bosque",
           "Las Acacias", "Primero de Mayo"]

RELLENO = [
    "La noticia ha generado preocupación entre los habitantes.",
    "Se espera que en las próximas horas haya más información.",
    "El tema se volvió tendencia en redes sociales.",
    "Muchas personas están compartiendo la información en grupos de WhatsApp.",
    "Te contamos lo que se sabe hasta el momento.",
    "La situación sigue en desarrollo.",
]
CIERRES_COPIA = ["Comparte esta noticia con tus contactos.", "Síguenos para más información."]
PREFIJOS_COPIA = ["ÚLTIMA HORA: ", "ATENCIÓN: ", "URGENTE | ", ""]
SINONIMOS = [("aseguró", "afirmó"), ("dijo", "señaló"), ("cerca de", "alrededor de"),
             ("unos", "aproximadamente"), ("según", "de acuerdo con")]

# ---------------------------------------------------------------------------
# Eventos ficticios. h1-h4: hechos centrales con tres redacciones cada uno.
# h5: hecho exclusivo del origen (fuente anónima), con dos redacciones.
# ---------------------------------------------------------------------------
EVENTOS = [
    {
        "id": "e01",
        "afirmacion": "El acueducto de San Aurelio suspendió el servicio de agua por contaminación con mercurio.",
        "entidad": "Empresa de Aguas de San Aurelio",
        "articulo": "La",
        "dominio_entidad": "aguas-sanaurelio.test",
        "titulos": ["Suspenden el servicio de agua en San Aurelio por mercurio",
                    "San Aurelio, sin agua: detectan mercurio en la planta de tratamiento",
                    "Alerta en San Aurelio por agua contaminada con mercurio"],
        "hechos": {
            "h1": ["El acueducto de San Aurelio suspendió el suministro de agua potable en todo el casco urbano.",
                   "Todo el casco urbano de San Aurelio quedó sin agua potable luego de que el acueducto cortara el suministro.",
                   "La distribución de agua en la zona urbana de San Aurelio fue interrumpida por orden del acueducto."],
            "h2": ["Según los análisis, en la planta El Retiro se encontraron niveles de mercurio por encima del límite permitido.",
                   "Las pruebas de laboratorio hechas en la planta El Retiro mostraron mercurio en concentraciones superiores a la norma.",
                   "El motivo sería la presencia de mercurio, por encima de lo que permite la norma, en muestras de la planta El Retiro."],
            "h3": ["La medida afecta a cerca de 18.000 usuarios.",
                   "Alrededor de 18.000 suscriptores se ven afectados por el corte.",
                   "Unos 18.000 usuarios del servicio están sin agua."],
            "h4": ["El servicio no se restablecerá antes de 72 horas.",
                   "Se calcula que pasarán al menos tres días antes de que vuelva el agua.",
                   "La reconexión tardaría como mínimo 72 horas."],
            "h5": ["Un funcionario que pidió no ser identificado aseguró que el problema se conocía desde hace un mes.",
                   "De acuerdo con un funcionario que habló bajo reserva, la contaminación se había detectado un mes atrás."],
        },
        "observaciones": ["desde la madrugada hay filas frente a los carrotanques",
                          "el agua embotellada se agotó en las tiendas del sector",
                          "los colegios enviaron a los estudiantes a casa antes del mediodía",
                          "varias familias están recogiendo agua lluvia en baldes",
                          "el olor del agua había cambiado desde hacía una semana"],
        "plantilla_numero": "En el barrio {barrio}, la junta de acción comunal contó {n} hogares sin agua.",
    },
    {
        "id": "e02",
        "afirmacion": "El puente La Concordia de Villa Miranda fue cerrado por riesgo de colapso.",
        "entidad": "Secretaría de Infraestructura de Villa Miranda",
        "articulo": "La",
        "dominio_entidad": "infraestructura-villamiranda.test",
        "titulos": ["Cierran el puente La Concordia en Villa Miranda por riesgo de colapso",
                    "Villa Miranda: el puente La Concordia, cerrado por daños en su estructura",
                    "Riesgo de colapso obliga a cerrar el puente La Concordia"],
        "hechos": {
            "h1": ["El puente La Concordia, en Villa Miranda, fue cerrado al tránsito de vehículos y peatones.",
                   "Desde hoy no se puede cruzar el puente La Concordia de Villa Miranda, ni a pie ni en vehículo.",
                   "Las autoridades de Villa Miranda prohibieron el paso de carros y peatones por el puente La Concordia."],
            "h2": ["Una inspección técnica encontró grietas en dos de las vigas principales.",
                   "Los ingenieros que revisaron la estructura detectaron fisuras en dos vigas principales.",
                   "La revisión técnica halló que dos vigas de soporte presentan grietas."],
            "h3": ["Por el puente pasan a diario unos 9.000 vehículos.",
                   "Cerca de 9.000 vehículos usan el puente cada día.",
                   "El cierre afecta un corredor que transitan alrededor de 9.000 vehículos diarios."],
            "h4": ["El desvío habilitado por la vía El Cedral suma unos 40 minutos al recorrido.",
                   "Quienes antes cruzaban el puente deberán tomar la vía El Cedral, lo que agrega cerca de 40 minutos.",
                   "La ruta alterna por El Cedral alarga el trayecto en aproximadamente 40 minutos."],
            "h5": ["Un contratista que pidió reserva de su nombre dijo que las grietas se habían reportado hace un año.",
                   "Según un contratista que no quiso ser identificado, los daños se conocían desde hace un año."],
        },
        "observaciones": ["los buses intermunicipales están dejando a los pasajeros antes del puente",
                          "los comerciantes del otro lado del río ya notan menos clientes",
                          "hubo un trancón de más de dos horas en la vía El Cedral",
                          "los estudiantes tienen que madrugar una hora más",
                          "se escuchaban crujidos en el puente desde hace semanas"],
        "plantilla_numero": "En el barrio {barrio}, la junta de acción comunal contó {n} familias que dependen del puente para ir a trabajar.",
    },
    {
        "id": "e03",
        "afirmacion": "Puerto Celeste decretó toque de queda nocturno por una ola de robos.",
        "entidad": "Alcaldía de Puerto Celeste",
        "articulo": "La",
        "dominio_entidad": "alcaldia-puertoceleste.test",
        "titulos": ["Puerto Celeste decreta toque de queda nocturno",
                    "Toque de queda en Puerto Celeste tras aumento de robos",
                    "Puerto Celeste restringe la circulación nocturna por la inseguridad"],
        "hechos": {
            "h1": ["La Alcaldía de Puerto Celeste decretó toque de queda entre las 10:00 p. m. y las 5:00 a. m.",
                   "En Puerto Celeste no se podrá circular entre las diez de la noche y las cinco de la mañana.",
                   "Desde las 10 de la noche y hasta las 5 de la mañana regirá un toque de queda en Puerto Celeste."],
            "h2": ["La decisión se tomó tras un aumento de los robos a residencias en el último mes.",
                   "La medida responde al incremento de robos en viviendas durante las últimas semanas.",
                   "El alza en los hurtos a casas durante el último mes motivó la restricción."],
            "h3": ["La medida estará vigente durante 15 días.",
                   "El toque de queda regirá por quince días.",
                   "Durante los próximos 15 días se aplicará la restricción."],
            "h4": ["Quienes incumplan la medida podrán recibir multas de hasta 800.000 pesos.",
                   "Las multas por violar el toque de queda llegan a 800.000 pesos.",
                   "Incumplir la restricción puede costar una multa de hasta 800.000 pesos."],
            "h5": ["Un policía que pidió no ser citado aseguró que se planea extender la medida a todo el departamento.",
                   "De acuerdo con un uniformado que habló bajo reserva, la idea es ampliar la restricción a todo el departamento."],
        },
        "observaciones": ["los restaurantes del malecón cerraron más temprano",
                          "los taxistas no saben si podrán trabajar en el turno de la noche",
                          "en su cuadra robaron tres casas en una semana",
                          "los vecinos organizaron rondas antes de que saliera el decreto",
                          "los trabajadores del turno nocturno del puerto piden un permiso especial"],
        "plantilla_numero": "En el barrio {barrio}, la junta de acción comunal registró {n} denuncias de robo en el último mes.",
    },
    {
        "id": "e04",
        "afirmacion": "El hospital de Altamira del Río cerró su servicio de urgencias por falta de personal.",
        "entidad": "Hospital San Rafael de Altamira del Río",
        "articulo": "El",
        "dominio_entidad": "hospital-altamira.test",
        "titulos": ["Hospital de Altamira del Río cierra urgencias por falta de médicos",
                    "Sin urgencias en Altamira del Río: el hospital no tiene personal",
                    "Altamira del Río se queda sin servicio de urgencias"],
        "hechos": {
            "h1": ["El Hospital San Rafael de Altamira del Río cerró su servicio de urgencias.",
                   "El servicio de urgencias del Hospital San Rafael, en Altamira del Río, dejó de atender.",
                   "Las urgencias del Hospital San Rafael de Altamira del Río fueron cerradas."],
            "h2": ["El cierre se debe a que no hay médicos suficientes para cubrir los turnos.",
                   "La falta de médicos para completar los turnos obligó a suspender la atención.",
                   "No hay personal médico suficiente para mantener abiertos los turnos, según el hospital."],
            "h3": ["Los pacientes están siendo remitidos al hospital de Santa Brígida, a 50 kilómetros.",
                   "Quienes necesiten atención de urgencia deberán ir a Santa Brígida, a unos 50 kilómetros.",
                   "Las remisiones se están haciendo hacia Santa Brígida, que queda a 50 kilómetros."],
            "h4": ["El hospital atendía unas 120 urgencias al día.",
                   "En promedio, el servicio recibía cerca de 120 pacientes diarios.",
                   "Por las urgencias pasaban alrededor de 120 personas cada día."],
            "h5": ["Una enfermera que pidió reserva dijo que a varios médicos les deben tres meses de salario.",
                   "Según una enfermera que no quiso dar su nombre, hay médicos con tres meses de sueldo atrasado."],
        },
        "observaciones": ["la ambulancia tardó dos horas en llevar a su vecino a Santa Brígida",
                          "en la entrada del hospital pusieron un letrero escrito a mano",
                          "los turnos se venían cubriendo con médicos recién graduados",
                          "las farmacias del pueblo están recibiendo más consultas",
                          "su madre tuvo que esperar toda la noche para que la remitieran"],
        "plantilla_numero": "En el barrio {barrio}, la junta de acción comunal contó {n} personas remitidas a otro municipio esta semana.",
    },
    {
        "id": "e05",
        "afirmacion": "Santa Brígida canceló el Festival de la Cosecha por una plaga en los cultivos.",
        "entidad": "Alcaldía de Santa Brígida",
        "articulo": "La",
        "dominio_entidad": "alcaldia-santabrigida.test",
        "titulos": ["Cancelan el Festival de la Cosecha en Santa Brígida por una plaga",
                    "Santa Brígida se queda sin Festival de la Cosecha este año",
                    "Una plaga en los cultivos acaba con el Festival de la Cosecha"],
        "hechos": {
            "h1": ["La Alcaldía de Santa Brígida canceló la edición de este año del Festival de la Cosecha.",
                   "Este año no habrá Festival de la Cosecha en Santa Brígida, anunció la alcaldía.",
                   "El Festival de la Cosecha de Santa Brígida no se realizará este año."],
            "h2": ["La decisión se debe a una plaga de gusano cogollero que afectó los cultivos de maíz.",
                   "El gusano cogollero dañó buena parte del maíz, y por eso se suspendió el evento.",
                   "Una plaga de gusano cogollero en los maizales motivó la cancelación."],
            "h3": ["Se estima que se perdió el 60 % de la cosecha de maíz del municipio.",
                   "Las pérdidas llegarían al 60 % del maíz sembrado en el municipio.",
                   "Cerca del 60 % de la cosecha de maíz del municipio se habría perdido."],
            "h4": ["El festival reunía cada año a unos 25.000 visitantes.",
                   "Al evento llegaban cerca de 25.000 turistas cada año.",
                   "Unas 25.000 personas visitaban el festival en cada edición."],
            "h5": ["Un concejal que pidió reserva aseguró que el dinero del festival se destinará a otra cosa.",
                   "Según un concejal que habló sin dar su nombre, los recursos del festival se usarán para otro fin."],
        },
        "observaciones": ["los artesanos ya habían comprado los materiales para sus puestos",
                          "en su vereda no quedó una sola mazorca sana",
                          "los hoteles empezaron a recibir cancelaciones",
                          "los agricultores llevan un mes fumigando sin resultados",
                          "la banda del colegio llevaba meses ensayando para el desfile"],
        "plantilla_numero": "En la vereda {barrio}, la asociación de productores contó {n} hectáreas afectadas.",
    },
    {
        "id": "e06",
        "afirmacion": "Una falla eléctrica dejó sin energía a La Esperanza del Norte durante dos días.",
        "entidad": "Electrificadora de La Esperanza del Norte",
        "articulo": "La",
        "dominio_entidad": "electrificadora-esperanza.test",
        "titulos": ["La Esperanza del Norte, dos días sin luz por una falla eléctrica",
                    "Apagón de dos días en La Esperanza del Norte",
                    "Falla en subestación deja sin energía a La Esperanza del Norte"],
        "hechos": {
            "h1": ["La Esperanza del Norte estuvo dos días sin servicio de energía.",
                   "Durante dos días el municipio de La Esperanza del Norte no tuvo electricidad.",
                   "El servicio de energía en La Esperanza del Norte se cayó por dos días seguidos."],
            "h2": ["La causa fue una falla en un transformador de la subestación Las Palmas.",
                   "Un transformador de la subestación Las Palmas se dañó y provocó el corte.",
                   "El origen del apagón estuvo en un transformador averiado de la subestación Las Palmas."],
            "h3": ["El corte afectó a unos 32.000 usuarios.",
                   "Alrededor de 32.000 usuarios se quedaron sin luz.",
                   "Cerca de 32.000 suscriptores resultaron afectados."],
            "h4": ["La electrificadora instaló un transformador provisional mientras repara el original.",
                   "Mientras se arregla el equipo dañado, funciona un transformador provisional.",
                   "Un transformador temporal fue puesto en servicio mientras se repara el averiado."],
            "h5": ["Un técnico que pidió reserva dijo que el transformador llevaba 30 años sin cambiarse.",
                   "Según un técnico que habló bajo reserva, el equipo tenía 30 años de uso sin reemplazo."],
        },
        "observaciones": ["se le dañó toda la comida de la nevera",
                          "los comerciantes tuvieron que cerrar por falta de datáfonos",
                          "los pacientes con oxígeno en casa fueron llevados al hospital",
                          "las noches fueron de completa oscuridad en el barrio",
                          "las plantas eléctricas se agotaron en la ferretería"],
        "plantilla_numero": "En el barrio {barrio}, la junta de acción comunal contó {n} negocios que tuvieron pérdidas.",
    },
]


# ---------------------------------------------------------------------------
# Conjunto de PRUEBA retenido: eventos escritos después de ajustar el método,
# que no se usaron para diseñar ni calibrar ECO. Se generan con un generador
# aleatorio aparte para no alterar los mundos principal y de estrés.
# ---------------------------------------------------------------------------
EVENTOS_PRUEBA = [
    {
        "id": "e07",
        "afirmacion": "El hospital de Puerto Celeste cerró su servicio de urgencias por falta de médicos.",
        "entidad": "Hospital Regional de Puerto Celeste",
        "articulo": "El",
        "dominio_entidad": "hospital-puertoceleste.test",
        "titulos": ["Cierran las urgencias del hospital de Puerto Celeste por falta de médicos",
                    "Puerto Celeste se queda sin urgencias: no hay médicos",
                    "Sin médicos, el hospital de Puerto Celeste suspende la atención de urgencias"],
        "hechos": {
            "h1": ["El Hospital Regional de Puerto Celeste cerró temporalmente su servicio de urgencias.",
                   "El servicio de urgencias del hospital regional de Puerto Celeste dejó de funcionar de manera temporal.",
                   "Las urgencias del principal hospital de Puerto Celeste fueron cerradas por un tiempo."],
            "h2": ["El cierre se debe a que renunciaron 9 de los 14 médicos de urgencias.",
                   "De los 14 médicos que atendían urgencias, 9 presentaron su renuncia.",
                   "Nueve médicos de un equipo de catorce dejaron sus cargos en urgencias."],
            "h3": ["Los pacientes están siendo remitidos al hospital de San Mateo, a dos horas de camino.",
                   "Quienes necesiten urgencias deben ser trasladados a San Mateo, a unas dos horas.",
                   "Las remisiones se hacen al hospital de San Mateo, ubicado a dos horas por carretera."],
            "h4": ["La gerencia espera reabrir el servicio en un plazo de 15 días.",
                   "Según la gerencia, las urgencias volverían a abrir en unas dos semanas.",
                   "La reapertura está prevista para dentro de quince días."],
            "h5": ["Una enfermera que pidió reserva dijo que a los médicos les deben cuatro meses de salario.",
                   "Según una enfermera que habló sin dar su nombre, los médicos llevan cuatro meses sin recibir pago."],
        },
        "observaciones": ["esperó toda la noche en la puerta antes de que le dijeran que no había atención",
                          "las ambulancias del municipio no dan abasto con los traslados",
                          "las farmacias del centro están atendiendo heridas menores",
                          "una mujer en trabajo de parto tuvo que ser llevada en carro particular a San Mateo",
                          "el puesto de salud del barrio amaneció con filas desde las cinco de la mañana"],
        "plantilla_numero": "En el barrio {barrio}, la junta de acción comunal contó {n} vecinos que no pudieron ser atendidos.",
    },
    {
        "id": "e08",
        "afirmacion": "Un deslizamiento bloqueó la vía entre Altamira y Río Claro y dejó a cientos de vehículos atrapados.",
        "entidad": "Secretaría de Infraestructura de Altamira",
        "articulo": "La",
        "dominio_entidad": "infraestructura-altamira.test",
        "titulos": ["Deslizamiento cierra la vía Altamira–Río Claro",
                    "Cientos de vehículos atrapados por un derrumbe entre Altamira y Río Claro",
                    "Bloqueada la carretera a Río Claro tras un deslizamiento"],
        "hechos": {
            "h1": ["Un deslizamiento de tierra bloqueó por completo la vía entre Altamira y Río Claro.",
                   "La carretera que une Altamira con Río Claro quedó totalmente cerrada por un derrumbe.",
                   "Un alud de tierra cerró en su totalidad el paso entre Altamira y Río Claro."],
            "h2": ["El derrumbe ocurrió en el kilómetro 23, en el sector conocido como La Curva del Diablo.",
                   "La tierra cayó sobre el kilómetro 23, en el punto que llaman La Curva del Diablo.",
                   "El sector afectado es La Curva del Diablo, a la altura del kilómetro 23."],
            "h3": ["Unos 400 vehículos quedaron atrapados a lado y lado del derrumbe.",
                   "Cerca de 400 carros y camiones no pudieron seguir su camino.",
                   "Alrededor de 400 vehículos permanecen detenidos en la vía."],
            "h4": ["Las autoridades calculan que la vía se habilitará en 48 horas.",
                   "Se estima que el paso se reabrirá en un plazo de dos días.",
                   "La reapertura de la carretera tomaría unas 48 horas."],
            "h5": ["Un operario de maquinaria que pidió reserva dijo que en la zona ya había grietas desde hace meses.",
                   "Según un operario que habló sin dar su nombre, el terreno mostraba grietas desde hacía meses."],
        },
        "observaciones": ["llevaba catorce horas dentro del bus sin poder avanzar",
                          "los camiones con leche empezaron a botar la carga",
                          "los vecinos están regalando agua y comida a los conductores",
                          "los niños de la vereda no pudieron llegar a la escuela",
                          "los comerciantes de la vía se quedaron sin mercancía"],
        "plantilla_numero": "En la vereda {barrio}, la asociación de transportadores contó {n} viajes cancelados.",
    },
    {
        "id": "e09",
        "afirmacion": "El colegio público de Villa Rosales suspendió las clases por una intoxicación masiva con el almuerzo escolar.",
        "entidad": "Secretaría de Educación de Villa Rosales",
        "articulo": "La",
        "dominio_entidad": "educacion-villarosales.test",
        "titulos": ["Intoxicación masiva en colegio de Villa Rosales: suspenden clases",
                    "Decenas de estudiantes intoxicados con el almuerzo escolar en Villa Rosales",
                    "Villa Rosales: cierran colegio tras intoxicación con alimentos"],
        "hechos": {
            "h1": ["El colegio público José Celestino Mutis de Villa Rosales suspendió las clases.",
                   "Las clases en el colegio José Celestino Mutis, en Villa Rosales, quedaron suspendidas.",
                   "El colegio José Celestino Mutis de Villa Rosales cerró sus aulas temporalmente."],
            "h2": ["Un total de 63 estudiantes presentaron síntomas de intoxicación después del almuerzo.",
                   "Tras comer el almuerzo escolar, 63 alumnos tuvieron síntomas de intoxicación.",
                   "Sesenta y tres estudiantes resultaron intoxicados luego de almorzar en el colegio."],
            "h3": ["Los menores fueron atendidos en el hospital local y ninguno está en estado grave.",
                   "Los niños recibieron atención en el hospital del municipio y ninguno reviste gravedad.",
                   "Todos los estudiantes afectados fueron atendidos en el hospital y están fuera de peligro."],
            "h4": ["Las muestras del pollo servido fueron enviadas al laboratorio departamental.",
                   "El laboratorio departamental analizará muestras del pollo que se sirvió.",
                   "Se tomaron muestras del pollo del almuerzo para enviarlas al laboratorio del departamento."],
            "h5": ["Una manipuladora de alimentos que pidió reserva dijo que la nevera del colegio llevaba una semana dañada.",
                   "Según una manipuladora que habló bajo reserva, el refrigerador del comedor estaba averiado desde hacía una semana."],
        },
        "observaciones": ["su hijo llegó a la casa con fiebre y dolor de estómago",
                          "los padres hicieron fila toda la tarde frente al hospital",
                          "los profesores llevaron a los niños en sus propios carros",
                          "el comedor ya había recibido quejas por el olor de la comida",
                          "la asociación de padres pide cambiar al operador del programa de alimentación"],
        "plantilla_numero": "En el barrio {barrio}, la asociación de padres contó {n} familias con niños afectados.",
    },
]

TIPOS = ["organico", "literal", "parafrasis", "comunicado"]
TIPOS_ESTRES = ["fabricado_literal", "fabricado_parafrasis"]


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def persona(rng):
    return f"{rng.choice(NOMBRES)} {rng.choice(APELLIDOS)}"


def aplicar_sinonimo(texto, rng):
    """Cambia una palabra por un sinónimo (edición mínima típica de una copia)."""
    opciones = [(a, b) for a, b in SINONIMOS if re.search(rf"\b{a}\b", texto, re.IGNORECASE)]
    if not opciones:
        return texto
    a, b = rng.choice(opciones)
    return re.sub(rf"\b{a}\b", b, texto, count=1)


def nueva_pagina(escenario_id, indice, medio, fecha, titulo, parrafos, rol,
                 deriva_de=None, enlace=None, autor="Redacción"):
    """
    parrafos: lista de dicts {"hecho": id o None, "texto": str}
    enlace:   dict {"texto": str, "a": id_pagina} o None
    """
    slug = f"{escenario_id}-p{indice:02d}"
    return {
        "id": slug,
        "escenario": escenario_id,
        "medio": medio,
        "fecha": fecha,
        "titulo": titulo,
        "parrafos": parrafos,
        "rol": rol,
        "deriva_de": deriva_de,
        "enlace": enlace,
        "autor": autor,
    }


def url_local(pagina):
    return f"{URL_BASE}/sitios/{pagina['escenario']}/{pagina['id']}.html"


def url_canonica(pagina):
    f = pagina["fecha"]
    return f"https://{pagina['medio']['dominio']}/{f:%Y/%m}/{pagina['id']}"


# ---------------------------------------------------------------------------
# Constructores de escenarios
# ---------------------------------------------------------------------------
def escenario_organico(ev, esc_id, rng, t0):
    """Medios independientes: cada uno cubre parte de los hechos con redacción propia
    y agrega dos hechos exclusivos (testimonio y cifra local). No se enlazan entre sí."""
    medios = rng.sample(MEDIOS, rng.randint(4, 5))
    barrios = rng.sample(BARRIOS, len(medios) * 2)
    observaciones = rng.sample(ev["observaciones"], len(medios))
    paginas, unicos = [], {}
    for i, medio in enumerate(medios, start=1):
        fecha = t0 + timedelta(minutes=rng.randint(30, 60 * 30))
        centrales = ["h1"] + rng.sample(["h2", "h3", "h4"], 2)
        parrafos = [{"hecho": h, "texto": rng.choice(ev["hechos"][h])} for h in centrales]
        u1 = f"{esc_id}-p{i:02d}-u1"
        u2 = f"{esc_id}-p{i:02d}-u2"
        texto_u1 = (f"{persona(rng)}, {rng.choice(OFICIOS)} del barrio {barrios[2 * i - 2]}, "
                    f"contó a {medio['nombre']} que {observaciones[i - 1]}.")
        texto_u2 = ev["plantilla_numero"].format(barrio=barrios[2 * i - 1], n=rng.randint(12, 480))
        parrafos.insert(1, {"hecho": u1, "texto": texto_u1})
        parrafos.append({"hecho": u2, "texto": texto_u2})
        unicos[u1] = texto_u1
        unicos[u2] = texto_u2
        paginas.append(nueva_pagina(esc_id, i, medio, fecha, rng.choice(ev["titulos"]),
                                    parrafos, "independiente", autor=persona(rng)))
    paginas.sort(key=lambda p: p["fecha"])
    return paginas, unicos, None


def arbol_de_derivacion(rng, k):
    """Devuelve, para cada página derivada (1..k), el índice de su página madre.
    Mitad de las veces la madre es el origen (0); si no, una página anterior."""
    padres = []
    for i in range(1, k + 1):
        padres.append(0 if rng.random() < 0.5 else rng.randint(0, i - 1))
    return padres


def escenario_literal(ev, esc_id, rng, t0):
    """Un origen y K copias casi idénticas, encadenadas en árbol."""
    k = rng.randint(4, 6)
    sitios = rng.sample(GRANJAS, k + 1)
    variante = {h: rng.randrange(len(v)) for h, v in ev["hechos"].items()}
    parrafos_origen = [{"hecho": h, "texto": ev["hechos"][h][variante[h]]}
                       for h in ["h1", "h2", "h3", "h5", "h4"]]
    titulo = rng.choice(ev["titulos"])
    origen = nueva_pagina(esc_id, 1, sitios[0], t0, titulo, parrafos_origen, "origen")
    paginas = [origen]
    for i, madre_idx in enumerate(arbol_de_derivacion(rng, k), start=1):
        madre = paginas[madre_idx]
        parrafos = [dict(p) for p in madre["parrafos"] if p["hecho"] is not None]
        j = rng.randrange(len(parrafos))
        parrafos[j]["texto"] = aplicar_sinonimo(parrafos[j]["texto"], rng)
        cierre = rng.choice(CIERRES_COPIA)
        parrafos.append({"hecho": None, "texto": cierre})
        fecha = madre["fecha"] + timedelta(minutes=rng.randint(5, 120))
        enlace = {"texto": "Fuente", "a": madre["id"]} if rng.random() < 0.5 else None
        titulo_copia = rng.choice(PREFIJOS_COPIA) + madre["titulo"].replace("ÚLTIMA HORA: ", "") \
            .replace("ATENCIÓN: ", "").replace("URGENTE | ", "")
        paginas.append(nueva_pagina(esc_id, i + 1, sitios[i], fecha, titulo_copia, parrafos,
                                    "copia", deriva_de=madre["id"], enlace=enlace))
    return paginas, {}, origen["id"]


def escenario_parafrasis(ev, esc_id, rng, t0):
    """Un origen y K reescrituras: mismos hechos con otra redacción y otro orden,
    algo de relleno, ningún dato nuevo."""
    k = rng.randint(4, 6)
    sitios = rng.sample(GRANJAS, k + 1)
    variante_origen = {h: rng.randrange(len(v)) for h, v in ev["hechos"].items()}
    parrafos_origen = [{"hecho": h, "texto": ev["hechos"][h][variante_origen[h]], "v": variante_origen[h]}
                       for h in ["h1", "h2", "h3", "h5", "h4"]]
    origen = nueva_pagina(esc_id, 1, sitios[0], t0, rng.choice(ev["titulos"]),
                          parrafos_origen, "origen")
    paginas = [origen]
    for i, madre_idx in enumerate(arbol_de_derivacion(rng, k), start=1):
        madre = paginas[madre_idx]
        hechos_madre = [p for p in madre["parrafos"] if p["hecho"] is not None]
        # A veces se omite un hecho secundario (nunca h1).
        if rng.random() < 0.3:
            omitible = [p for p in hechos_madre if p["hecho"] != "h1"]
            quitar = rng.choice(omitible)
            hechos_madre = [p for p in hechos_madre if p is not quitar]
        nuevos = []
        for p in hechos_madre:
            opciones = [n for n in range(len(ev["hechos"][p["hecho"]])) if n != p["v"]]
            v = rng.choice(opciones)
            nuevos.append({"hecho": p["hecho"], "texto": ev["hechos"][p["hecho"]][v], "v": v})
        primero = [p for p in nuevos if p["hecho"] == "h1"]
        resto = [p for p in nuevos if p["hecho"] != "h1"]
        rng.shuffle(resto)
        parrafos = primero + resto
        for frase in rng.sample(RELLENO, rng.randint(1, 2)):
            parrafos.insert(rng.randint(1, len(parrafos)), {"hecho": None, "texto": frase})
        titulos_otros = [t for t in ev["titulos"] if t != madre["titulo"]]
        fecha = madre["fecha"] + timedelta(minutes=rng.randint(10, 180))
        enlace = {"texto": "Con información de otros medios", "a": madre["id"]} if rng.random() < 0.2 else None
        paginas.append(nueva_pagina(esc_id, i + 1, sitios[i], fecha, rng.choice(titulos_otros),
                                    parrafos, "copia", deriva_de=madre["id"], enlace=enlace))
    return paginas, {}, origen["id"]


def escenario_comunicado(ev, esc_id, rng, t0):
    """Un comunicado oficial y K sitios que lo reproducen textualmente en parte."""
    k = rng.randint(4, 6)
    entidad = {"nombre": ev["entidad"], "dominio": ev["dominio_entidad"], "tipo": "entidad"}
    parrafos_com = [{"hecho": None, "texto": f"{ev['articulo']} {ev['entidad']} informa a la ciudadanía lo siguiente:"}]
    parrafos_com += [{"hecho": h, "texto": ev["hechos"][h][0]} for h in ["h1", "h2", "h3", "h4"]]
    parrafos_com.append({"hecho": None,
                         "texto": "Recomendamos a la comunidad informarse únicamente por los canales oficiales."})
    comunicado = nueva_pagina(esc_id, 1, entidad, t0, "Comunicado oficial: " + ev["titulos"][0],
                              parrafos_com, "comunicado", autor="Oficina de Comunicaciones")
    paginas = [comunicado]
    sitios = rng.sample(MEDIOS + GRANJAS, k)
    hechos_com = [p for p in parrafos_com if p["hecho"] is not None]
    for i, sitio in enumerate(sitios, start=1):
        elegidos = [hechos_com[0]] + rng.sample(hechos_com[1:], rng.randint(1, 3))
        parrafos = [{"hecho": None,
                     "texto": f"{ev['articulo']} {ev['entidad']} confirmó la situación mediante un comunicado."}]
        parrafos += [dict(p) for p in elegidos]
        parrafos.append({"hecho": None, "texto": rng.choice(RELLENO)})
        fecha = t0 + timedelta(minutes=rng.randint(20, 300))
        enlace = {"texto": "Lea el comunicado completo", "a": comunicado["id"]} if rng.random() < 0.7 else None
        paginas.append(nueva_pagina(esc_id, i + 1, sitio, fecha, rng.choice(ev["titulos"]), parrafos,
                                    "reproduccion", deriva_de=comunicado["id"], enlace=enlace,
                                    autor=persona(rng) if sitio["tipo"] == "medio" else "Redacción"))
    return paginas, {}, comunicado["id"]


def _detalles_inventados(ev, rng, medio, pid, usados):
    """Testimonio y cifra inventados, con el mismo formato que usa un medio independiente."""
    barrio1, barrio2 = rng.sample([b for b in BARRIOS if b not in usados], 2)
    usados.update([barrio1, barrio2])
    t1 = (f"{persona(rng)}, {rng.choice(OFICIOS)} del barrio {barrio1}, "
          f"contó a {medio['nombre']} que {rng.choice(ev['observaciones'])}.")
    t2 = ev["plantilla_numero"].format(barrio=barrio2, n=rng.randint(12, 480))
    return [{"hecho": f"{pid}-u1", "texto": t1}, {"hecho": f"{pid}-u2", "texto": t2}]


def escenario_fabricado_literal(ev, esc_id, rng, t0):
    """Ataque: copias casi idénticas que agregan un testimonio y una cifra inventados
    para parecer reportería propia. Sigue habiendo un solo origen."""
    paginas, unicos, origen = escenario_literal(ev, esc_id, rng, t0)
    usados = set()
    for p in paginas[1:]:
        p["rol"] = "copia_con_inventos"
        extra = _detalles_inventados(ev, rng, p["medio"], p["id"], usados)
        cuerpo = [x for x in p["parrafos"] if x["hecho"] is not None]
        cierre = [x for x in p["parrafos"] if x["hecho"] is None]
        p["parrafos"] = cuerpo[:1] + extra[:1] + cuerpo[1:] + extra[1:] + cierre
        unicos.update({x["hecho"]: x["texto"] for x in extra})
    return paginas, unicos, origen


def escenario_fabricado_parafrasis(ev, esc_id, rng, t0):
    """Ataque más fuerte: reescrituras que además agregan detalles inventados."""
    paginas, unicos, origen = escenario_parafrasis(ev, esc_id, rng, t0)
    usados = set()
    for p in paginas[1:]:
        p["rol"] = "copia_con_inventos"
        extra = _detalles_inventados(ev, rng, p["medio"], p["id"], usados)
        p["parrafos"] = p["parrafos"][:1] + extra[:1] + p["parrafos"][1:] + extra[1:]
        unicos.update({x["hecho"]: x["texto"] for x in extra})
    return paginas, unicos, origen


CONSTRUCTORES = {
    "organico": escenario_organico,
    "literal": escenario_literal,
    "parafrasis": escenario_parafrasis,
    "comunicado": escenario_comunicado,
    "fabricado_literal": escenario_fabricado_literal,
    "fabricado_parafrasis": escenario_fabricado_parafrasis,
}


# ---------------------------------------------------------------------------
# Render HTML
# ---------------------------------------------------------------------------
def render_pagina(pagina, por_id):
    e = html.escape
    medio = pagina["medio"]
    fecha_iso = pagina["fecha"].strftime("%Y-%m-%dT%H:%M:00-05:00")
    fecha_txt = pagina["fecha"].strftime("%d/%m/%Y %I:%M %p")
    cuerpo = "\n".join(f"      <p>{e(p['texto'])}</p>" for p in pagina["parrafos"])
    figuras = "".join(f'\n      <figure><img src="{e(f["src"])}" alt="{e(f["pie"])}" width="640">'
                      f'<figcaption>{e(f["pie"])}</figcaption></figure>' for f in pagina.get("figuras", []))
    enlace_html = ""
    if pagina["enlace"]:
        destino = por_id[pagina["enlace"]["a"]]
        enlace_html = (f'\n      <p class="fuente">{e(pagina["enlace"]["texto"])}: '
                       f'<a href="{e(url_local(destino))}">{e(destino["medio"]["nombre"])}</a></p>')
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>{e(pagina['titulo'])} | {e(medio['nombre'])}</title>
  <meta name="eco:sintetico" content="true">
  <meta property="og:site_name" content="{e(medio['nombre'])}">
  <meta property="og:title" content="{e(pagina['titulo'])}">
  <meta property="article:published_time" content="{fecha_iso}">
  <meta name="author" content="{e(pagina['autor'])}">
  <link rel="canonical" href="{e(url_canonica(pagina))}">
  <style>
    body {{ font-family: Georgia, serif; max-width: 720px; margin: 0 auto; padding: 0 16px; color: #222; }}
    header {{ border-bottom: 3px solid #333; padding: 12px 0; }}
    header .marca {{ font: bold 22px Arial, sans-serif; }}
    nav a {{ margin-right: 12px; color: #555; font: 13px Arial, sans-serif; }}
    .meta {{ color: #666; font: 13px Arial, sans-serif; }}
    .fuente {{ font-style: italic; }}
    footer {{ border-top: 1px solid #ccc; margin-top: 32px; padding: 12px 0; color: #777; font: 12px Arial, sans-serif; }}
    .aviso {{ background: #f3ece4; padding: 6px 10px; font: 12px Arial, sans-serif; }}
  </style>
</head>
<body>
  <div class="aviso">Contenido sintético creado para el laboratorio ECO. Medios, lugares y personas son ficticios.</div>
  <header>
    <div class="marca">{e(medio['nombre'])}</div>
    <nav><a href="#">Inicio</a><a href="#">Regiones</a><a href="#">Política</a><a href="#">Opinión</a><a href="#">Contacto</a></nav>
  </header>
  <main>
    <article>
      <h1>{e(pagina['titulo'])}</h1>
      <p class="meta">Por <span class="autor">{e(pagina['autor'])}</span> · <time datetime="{fecha_iso}">{fecha_txt}</time></p>{figuras}
{cuerpo}{enlace_html}
    </article>
  </main>
  <footer>© 2026 {e(medio['nombre'])} · {e(medio['dominio'])} · Todos los derechos reservados.</footer>
</body>
</html>
"""


def render_indice(escenarios):
    e = html.escape
    filas = []
    for esc in escenarios:
        enlaces = "".join(
            f'<li><a href="sitios/{esc["id"]}/{p["id"]}.html">{e(p["medio"])} — {e(p["titulo"])}</a></li>'
            for p in sorted(esc["paginas"], key=lambda x: x["id"])
        )
        filas.append(f"<h2>{e(esc['id'])}</h2><p>{e(esc['afirmacion'])}</p><ul>{enlaces}</ul>")
    return ("<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'><title>ECO · mini-internet sintético</title>"
            "<style>body{font-family:Arial,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;color:#222}"
            "h2{color:#B4532A;margin-bottom:4px}li{margin:3px 0}</style></head><body>"
            "<h1>ECO · mini-internet sintético</h1>"
            "<p>Contenido ficticio para pruebas. El tipo de cada escenario no se muestra aquí, "
            "para poder evaluar a ciegas; está en ground_truth.json.</p>"
            + "".join(filas) + "</body></html>")


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------
def construir_escenario(ev, esc_id, tipo, rng, t0, decorar=None):
    paginas, unicos, origen = CONSTRUCTORES[tipo](ev, esc_id, rng, t0)

    # Renumerar páginas en orden aleatorio para que el número no revele el origen.
    orden = list(range(1, len(paginas) + 1))
    rng.shuffle(orden)
    mapa = {p["id"]: f"{esc_id}-p{orden[i]:02d}" for i, p in enumerate(paginas)}
    renombrar_unicos = {}
    for p in paginas:
        viejo = p["id"]
        p["id"] = mapa[viejo]
        if p["deriva_de"]:
            p["deriva_de"] = mapa[p["deriva_de"]]
        if p["enlace"]:
            p["enlace"]["a"] = mapa[p["enlace"]["a"]]
    # Los hechos únicos se nombran con el id original de la página que los creó.
    for p in paginas:
        for par in p["parrafos"]:
            h = par["hecho"]
            if h and "-u" in h and h not in renombrar_unicos.values():
                base, sufijo = h.rsplit("-u", 1)
                if base in mapa:
                    renombrar_unicos[h] = f"{mapa[base]}-u{sufijo}"
    for p in paginas:
        for par in p["parrafos"]:
            if par["hecho"] in renombrar_unicos:
                par["hecho"] = renombrar_unicos[par["hecho"]]
    unicos = {renombrar_unicos.get(k, k): v for k, v in unicos.items()}
    origen = mapa[origen] if origen else None

    por_id = {p["id"]: p for p in paginas}
    carpeta = DIR_SITIOS / esc_id
    carpeta.mkdir()
    if decorar:  # mundos de procedencia: agrega fotos firmadas (y puede cambiar fechas) antes de escribir
        decorar(paginas, carpeta)
    for p in paginas:
        (carpeta / f"{p['id']}.html").write_text(render_pagina(p, por_id), encoding="utf-8", newline="\n")

    esperadas = len(paginas) if tipo == "organico" else 1
    return {
        "id": esc_id,
        "evento": ev["id"],
        "tipo": tipo,
        "conjunto": "estres" if tipo in TIPOS_ESTRES else "principal",
        "afirmacion": ev["afirmacion"],
        "fuentes_aparentes": len(paginas),
        "fuentes_efectivas_esperadas": esperadas,
        "origen": origen,
        "paginas": [{
            "id": p["id"],
            "url": url_local(p),
            "url_canonica": url_canonica(p),
            "medio": p["medio"]["nombre"],
            "dominio": p["medio"]["dominio"],
            "tipo_sitio": p["medio"]["tipo"],
            "fecha": p["fecha"].strftime("%Y-%m-%dT%H:%M:00-05:00"),
            "titulo": p["titulo"],
            "rol": p["rol"],
            "deriva_de": p["deriva_de"],
            "enlaza_a": p["enlace"]["a"] if p["enlace"] else None,
            "hechos": sorted({par["hecho"] for par in p["parrafos"] if par["hecho"]}),
        } for p in sorted(paginas, key=lambda x: x["fecha"])],
        "hechos_unicos": unicos,
    }


def generar(semilla, sin_procedencia=False):
    rng = random.Random(semilla)
    if DIR_SITIOS.exists():
        shutil.rmtree(DIR_SITIOS)
    DIR_SITIOS.mkdir(parents=True)

    escenarios = []
    t_base = datetime(2026, 10, 1, 6, 0)
    for n_ev, ev in enumerate(EVENTOS):
        tipos = TIPOS[:]
        rng.shuffle(tipos)  # el número de escenario no revela el tipo
        for s, tipo in enumerate(tipos, start=1):
            esc_id = f"{ev['id']}-s{s}"
            t0 = t_base + timedelta(days=n_ev * 4 + s, minutes=rng.randint(0, 600))
            escenarios.append(construir_escenario(ev, esc_id, tipo, rng, t0))

    # Conjunto de estrés: generador aparte para no alterar el conjunto principal.
    rng_estres = random.Random(semilla + 1000)
    for n_ev, ev in enumerate(EVENTOS):
        tipos = TIPOS_ESTRES[:]
        rng_estres.shuffle(tipos)
        for s, tipo in enumerate(tipos, start=1):
            esc_id = f"{ev['id']}-x{s}"
            t0 = t_base + timedelta(days=30 + n_ev * 3 + s, minutes=rng_estres.randint(0, 600))
            escenarios.append(construir_escenario(ev, esc_id, tipo, rng_estres, t0))

    # Conjunto de prueba retenido: eventos nuevos, generador aparte (no altera los anteriores).
    rng_prueba = random.Random(semilla + 2000)
    for n_ev, ev in enumerate(EVENTOS_PRUEBA):
        tipos = TIPOS[:] + TIPOS_ESTRES[:]
        rng_prueba.shuffle(tipos)
        for s, tipo in enumerate(tipos, start=1):
            esc_id = f"{ev['id']}-t{s}"
            t0 = t_base + timedelta(days=60 + n_ev * 7 + s, minutes=rng_prueba.randint(0, 600))
            esc = construir_escenario(ev, esc_id, tipo, rng_prueba, t0)
            esc["conjunto"] = "prueba"
            escenarios.append(esc)

    # Conjunto de procedencia (C2PA): fotos firmadas sobre los eventos de prueba, generador aparte.
    if not sin_procedencia:
        try:
            from procedencia_corpus import generar_mundos
        except ImportError:
            from corpus.procedencia_corpus import generar_mundos
        escenarios.extend(generar_mundos(EVENTOS_PRUEBA, construir_escenario, t_base, semilla))

    catalogo_hechos = {ev["id"]: ev["hechos"] for ev in EVENTOS + EVENTOS_PRUEBA}
    salida = {
        "semilla": semilla,
        "url_base": URL_BASE,
        "nota": "Corpus sintético de ECO. Todo el contenido es ficticio.",
        "catalogo_hechos": catalogo_hechos,
        "escenarios": escenarios,
    }
    (RAIZ / "ground_truth.json").write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    # Índice para el buscador simulado: solo temas y URLs, sin respuestas.
    indice = [{"id": e["id"], "afirmacion": e["afirmacion"],
               "paginas": [{"id": p["id"], "url": p["url"], "titulo": p["titulo"], "medio": p["medio"]}
                           for p in sorted(e["paginas"], key=lambda x: x["id"])]}
              for e in escenarios]
    (RAIZ / "indice_busqueda.json").write_text(json.dumps(indice, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    (RAIZ / "index.html").write_text(render_indice(escenarios), encoding="utf-8", newline="\n")
    return escenarios


def resumen(escenarios):
    total = sum(e["fuentes_aparentes"] for e in escenarios)
    print(f"Escenarios: {len(escenarios)} | Páginas: {total}")
    print(f"{'tipo':<22}{'escenarios':>11}{'páginas':>9}{'aparentes prom.':>17}{'efectivas esperadas':>21}")
    for t in TIPOS + TIPOS_ESTRES:
        sub = [e for e in escenarios if e["tipo"] == t]
        pags = sum(e["fuentes_aparentes"] for e in sub)
        efect = sorted({e["fuentes_efectivas_esperadas"] for e in sub})
        print(f"{t:<22}{len(sub):>11}{pags:>9}{pags / len(sub):>17.1f}{str(efect):>21}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Genera el mini-internet sintético de ECO.")
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--sin-procedencia", action="store_true", help="no generar los mundos con fotos firmadas")
    args = parser.parse_args()
    resumen(generar(args.semilla, args.sin_procedencia))
    print("Listo. Para navegarlo: uvicorn api.servidor:app --port 8765 (desde la carpeta eco)")
