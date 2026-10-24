"""EnVivo · fase 2 · consultas e informes.

Cada consulta es un *pipeline* de agregación declarado como una **lista de
diccionarios de Python**, no como una cadena de texto. Así se ejecuta tal cual:

    from consultas import CONSULTAS
    c = CONSULTAS["C1"]
    resultado = list(db[c["coleccion"]].aggregate(c["pipeline"]))

Hay que rellenar los ocho pipelines. El diccionario `CONSULTAS` del final ya
está escrito y **no debe modificarse**: es el contrato de entrega.

Recordatorio del esquema, tal como quedó en la fase 1:

  recinto    nombre, direccion, direccion_loc (punto GeoJSON), ciudad, aforo,
             zonas [{nombre, asientos}], servicios []
  artista    nombre, generos [], pais, anio_inicio
  evento     titulo, artistas [] (nombres), recinto (nombre), fecha,
             precios_por_zona [{zona, precio, vendidas}], entradas_vendidas,
             estado
  asistente  nombre, email, fecha_alta, direccion, direccion_loc, preferencias []

Atención: `titulo` **no es único** (un mismo artista puede repetir recinto en
otra fecha), así que para contar eventos hay que usar `_id`.
"""

# ── C1 · Artistas por género musical ────────────────────────────────────────
# Colección: artista
# Devuelve, por cada género: genero, n (número de artistas) y artistas (lista
# de nombres, ORDENADA). Ordenado por n descendente y, a igualdad, por genero.
C1 = [
    {"$sort": {"nombre": 1}}, # Ordena los artistas por orden alfaebtico
    {"$unwind": "$generos"}, # Descompone el array generos de cada artista dependiendo del genero
    {
        "$group": {
            "_id": "$generos", # Se agrupa por genero
            "n": {"$sum":1}, # Cuenta el numero de artistas con ese genero
            "artistas": {"$push":"$nombre"} # Agrega el nombre del artista al array en el orden que entraron del sort
        }
    },
    {
        "$project": {
            "_id": 0, # Suprime el campo _id
            "genero": "$_id", # Renombra el campo _id a genero
            "n": 1, # Mantenemos el campo n
            "artistas": 1 # Mantenemos el campo artistas
        }
    },
    {"$sort": {"n": -1, "genero": 1}} #Ordena el resultado por n de artistas desdecendente y en caso de empate alfabetico por genero
]

# ── C2 · Ocupación media por recinto ────────────────────────────────────────
# Colección: evento
# Devuelve, por cada recinto: recinto, eventos y ocupacion_media, esta última
# en PORCENTAJE del aforo del recinto y redondeada a un decimal. Ordenado por
# ocupacion_media descendente y, a igualdad, por recinto.
C2 = [
    {
        "$lookup": {
            "from": "recinto", # Coleccion con la que vamos a hacer el join
            "localField": "recinto", # Campo de la coleccion evento que se corresopnde con el de la coleccion recinto
            "foreignField": "nombre", # Campo de la coleccion evento que se corresponde con el campo de la coleccion recinto
            "as": "datos_recinto", # Almacena los datos del recinto en un array llamado datos_recinto
        }
    },
    {"$unwind": "$datos_recinto"}, # Convertimos el array datos_recinto en un objeto plano
    {
        "$group": {
            "_id": "$recinto", # Agrupamos por recinto
            "eventos": {"$sum": 1}, # Contamos el total de evento en ese recinto
            "ocupacion_media_ratio": {"$avg": {"$divide": ["$entradas_vendidas", "$datos_recinto.aforo"]}} # Se calcula el promedio de la division entre entradas vendidas y el aforo del recinto obteniendo el ratio
        }
    },
    {
        "$project": {
            "_id": 0, # Suprime el campo _id
            "recinto": "$_id", # Renombramos el campo _id a recinto
            "eventos": 1, # Mantenemos el campo eventos
            "ocupacion_media": {"$round": [{"$multiply": ["$ocupacion_media_ratio", 100]}, 1]}, # Se multiplica el ratio por 100 para pasarlo a porcentaje y lo redondea a 1 decimal
        }
    },
    {"$sort": {"ocupacion_media": -1, "recinto": 1}} # Ordenamos por ocupacion_media descendente y por recinto asceendente en caso de empate
]

# ── C3 · Ingresos por mes ───────────────────────────────────────────────────
# Colección: evento
# El ingreso de un evento es la suma, por zona, de precio x vendidas.
# Devuelve, por cada mes: mes (formato "AAAA-MM"), ingresos redondeados a dos
# decimales y eventos (número de eventos de ese mes). Ordenado por mes.
C3 = [
    {"$unwind": "$precios_por_zona"}, # Se desglosa la zona de precios de cada evento para calcular el ingreso de cada zona por separado
    {"$addFields": {
        "ingreso_por_zona": {"$multiply": ["$precios_por_zona.precio", "$precios_por_zona.vendidas"]} # Se calcula el dinero recaudado en esa zona especifica
    }},
    {"$group": {
        "_id": "$_id", # Agrupamos por evento
        "ingresos_totales": {"$sum": "$ingreso_por_zona"}, # Suma los ingresos de todas las zonas
        "mes": {"$first": {"$dateToString": {"format": "%Y-%m", "date": "$fecha"}}}, # Extrae el mes sobre la fecha del evento
    }},
    {"$group": {
        "_id": "$mes", # Agrupamos por mes
        "ingresos": {"$sum": "$ingresos_totales"}, # Suma los ingresos de todos los eventos de ese mes
        "eventos": {"$sum": 1}, # Cuenta exactamente 1 por evento, obteniendo el total de eventos de ese mes
    }},
    {"$project": {
        "_id": 0, # Suprimimos el campo _id
        "mes": "$_id", # Renombramos el campo _id a mes
        "ingresos": {"$round": ["$ingresos", 2]}, # Se redondea el campo ingresos a 2 decimales
        "eventos": 1, # Mantenemos el campo eventos
    }},
    {"$sort": {"mes": 1}}, # Ordenamos cronologicamente ascendente por mes
]

# ── C4 · Los tres artistas más programados ──────────────────────────────────
# Colección: evento
# Devuelve, para cada uno de los tres primeros: artista, actuaciones y
# recintos (número de recintos DISTINTOS en los que ha actuado). Ordenado por
# actuaciones descendente y, a igualdad, por artista.
C4 = [
    {"$unwind": "$artistas"}, # Separamos para contar cada actuacion individualmente
    {"$group": {
        "_id": "$artistas", # Agrupamos por artista
        "actuaciones": {"$sum": 1}, # Contamos el numero de actuaciones de cada artista
        "recintos": {"$addToSet": "$recinto"}, # Se acumulan en un set los nombres de los recitnos sin duplicados
    }},
    {"$project": {
        "_id": 0, # Se suprime el campo _id
        "artista": "$_id", # Se renombra el campo _id a artista
        "actuaciones": 1, # Se mantiene el campo actuaciones
        "recintos": {"$size": "$recintos"}, # Se calcula el tam del set de recintos obteniendo el numero de recintos distintos
    }},
    {"$sort": {"actuaciones": -1, "artista": 1}}, # Ordenamos por actuaciones de forma descendente
    {"$limit": 3}, # Limitamos el resultado a los 3 primeros
]

# ── C5 · Recintos a menos de 5 km de la Puerta del Sol ──────────────────────
# Colección: recinto
# El punto de referencia es [-3.7038, 40.4168].
# Devuelve, por cada recinto: recinto, ciudad, distancia_km redondeada a dos
# decimales, y eventos (número de eventos de ese recinto).
C5 = [
    {"$geoNear": {
        "near": {"type": "Point", "coordinates": [-3.7038, 40.4168]}, # Punto de referencia 
        "distanceField": "distancia", # Campo donde se almacen la distancia calculada
        "maxDistance": 5000, # Maxima distancia en metros
        "spherical": True, # Se calcula la distancia en un radio de 5 km
    }},
    {"$lookup": {
        "from": "evento", # Es la coleccion con la que se va hacer el join
        "localField": "nombre", # Es el campo de la coleccion recinto que se corresopnde con el campo de la coleccion eventos
        "foreignField": "recinto", # Es el campo de la coleccion evento que se corresponde con el campo de la coleccion recinto
        "as": "datos_evento", # Almacena los datos del evento en un array llamando datos_evento
    }},
    {"$project": {
        "_id": 0, # Suprimimos el campo _id
        "recinto": "$nombre", # Renombramos el campo nombre a recinto
        "ciudad": 1, # Mantenemos el campo ciudad
        "distancia_km": {"$round": [{"$divide": ["$distancia", 1000]}, 2]}, # Se calcula las distancias en kilometros dividiendo en 10
        "eventos": {"$size": "$datos_evento"},
    }},
]

# ── C6 · Cartel completo de los eventos con varios artistas ─────────────────
# Colección: evento
# Solo los eventos con MÁS DE UN artista. Devuelve: titulo, recinto y cartel,
# una lista con {nombre, pais, generos} de cada artista, ORDENADA por nombre.
# Ordenado por titulo.
C6 = [
    {"$match": {"$expr": {"$gt": [{"$size": "$artistas"}, 1]}}},
    {"$lookup": {
        "from": "artista",
        "localField": "artistas",
        "foreignField": "nombre",
        "as": "datos_artista",
        "pipeline": [
            {"$sort": {"nombre": 1}},
            {"$project": {"_id": 0, "nombre": 1, "pais": 1, "generos": 1}},
        ],
    }},
    {"$project": {
        "_id": 0,
        "titulo": 1,
        "recinto": 1,
        "cartel": "$datos_artista",
    }},
    {"$sort": {"titulo": 1}},
]

# ── C7 · Eventos por franja de ocupación ────────────────────────────────────
# Colección: evento
# Clasifica cada evento según su ocupación sobre el aforo del recinto:
#   agotado  >= 0,99      alta  >= 0,85      media  >= 0,70      baja  el resto
# Devuelve, por franja: franja y eventos. Ordenado por eventos descendente y,
# a igualdad, por franja.
C7 = [
    {"$lookup": {
        "from": "recinto",
        "localField": "recinto",
        "foreignField": "nombre",
        "as": "datos_recinto"
    }},
    {"$unwind": "$datos_recinto"},
    {"$addFields": {
        "franja": {
            "$switch": {
                "branches": [
                    {"case": {"$gte": [{"$divide": ["$entradas_vendidas", "$datos_recinto.aforo"]}, 0.99]}, "then": "agotado"},
                    {"case": {"$gte": [{"$divide": ["$entradas_vendidas", "$datos_recinto.aforo"]}, 0.85]}, "then": "alta"},
                    {"case": {"$gte": [{"$divide": ["$entradas_vendidas", "$datos_recinto.aforo"]}, 0.70]}, "then": "media"}
                ],
                "default": "baja"
            }
        }
    }},
    {"$group": {
        "_id": "$franja",
        "eventos": {"$sum": 1}
    }},
    {"$project": {
        "_id": 0,
        "franja": "$_id",
        "eventos": 1
    }},
    {"$sort": {"eventos": -1, "franja": 1}}
]

# ── C8 · Informe materializado por recinto ──────────────────────────────────
# Colección: evento
# Escribe en la colección `informe_recintos` un documento por recinto, con
# _id = nombre del recinto, ingresos, eventos y aforo.
# Requisito: una SEGUNDA ejecución debe ACTUALIZAR la colección, no
# reemplazarla, de modo que se conserven los campos que se le hayan añadido
# por fuera.
C8 = [
    {"$unwind": "$precios_por_zona"},
    {"$group": {
        "_id": "$recinto",
        "ingresos": {"$sum": {"$multiply": ["$precios_por_zona.precio", "$precios_por_zona.vendidas"]}},
        "eventos": {"$addToSet": "$_id"},
    }},
    {"$lookup": {
        "from": "recinto",
        "localField": "_id",
        "foreignField": "nombre",
        "as": "datos_recinto",
    }},
    {"$project": {
        "ingresos": 1,
        "eventos": {"$size": "$eventos"},
        "aforo": {"$arrayElemAt": ["$datos_recinto.aforo", 0]},
    }},
    {"$merge": {
        "into": "informe_recintos",
        "on": "_id",
        "whenMatched": "merge",
        "whenNotMatched": "insert",
    }},
]


# ── Contrato de entrega · no modificar ──────────────────────────────────────
CONSULTAS = {
    "C1": {"coleccion": "artista", "pipeline": C1,
           "descripcion": "Artistas por género musical"},
    "C2": {"coleccion": "evento", "pipeline": C2,
           "descripcion": "Ocupación media por recinto"},
    "C3": {"coleccion": "evento", "pipeline": C3,
           "descripcion": "Ingresos por mes"},
    "C4": {"coleccion": "evento", "pipeline": C4,
           "descripcion": "Los tres artistas más programados"},
    "C5": {"coleccion": "recinto", "pipeline": C5,
           "descripcion": "Recintos a menos de 5 km de la Puerta del Sol"},
    "C6": {"coleccion": "evento", "pipeline": C6,
           "descripcion": "Cartel completo de los eventos con varios artistas"},
    "C7": {"coleccion": "evento", "pipeline": C7,
           "descripcion": "Eventos por franja de ocupación"},
    "C8": {"coleccion": "evento", "pipeline": C8,
           "descripcion": "Informe materializado por recinto"},
}