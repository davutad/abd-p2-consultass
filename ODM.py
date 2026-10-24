
__author__ = 'Pablo Ramos Criado'
__students__ = 'David_SanMartin_Mateos_y_Daniel_Lopez_Vallejo'


from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import time
from typing import Generator, Any, Self
from geojson import Point
import pymongo
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId
import yaml
from datetime import datetime

def getLocationPoint(address: str) -> Point:
    """ 
    Obtiene las coordenadas de una dirección en formato geojson.Point
    Utilizar la API de geopy para obtener las coordenadas de la direccion
    Cuidado, la API es publica tiene limite de peticiones, utilizar sleeps.

    Parameters
    ----------
        address : str
            direccion completa de la que obtener las coordenadas
    Returns
    -------
        geojson.Point
            coordenadas del punto de la direccion
    """
    location = None
    intentos = 0
    maxIntentos = 5
    while location is None and intentos < maxIntentos:
        intentos += 1
        try:
            time.sleep(1)
            #TODO
            # Es necesario proporcionar un user_agent para utilizar la API
            # Utilizar un nombre aleatorio para el user_agent
            location = Nominatim(user_agent="Mi-Nombre-Aleatorio").geocode(address)
        except GeocoderTimedOut:
            # Puede lanzar una excepcion si se supera el tiempo de espera
            # Volver a intentarlo
            continue
    #TODO
    # Devolver un GeoJSON de tipo punto con la latitud y longitud almacenadas.
    # Si no se consiguieron coordenadas, lanzar ValueError: la funcion no puede
    # devolver un punto inventado ni None silenciosamente. Es lo que espera la
    # prueba test_get_location_point_timeout_failure.

    if location is None:
        raise ValueError(f"No se pudieron obtener coordenadas para '{address}'")

    return Point((location.longitude, location.latitude))

class Model:
    """ 
    Clase de modelo abstracta
    Crear tantas clases que hereden de esta clase como  
    colecciones/modelos se deseen tener en la base de datos.

    Attributes
    ----------
        required_vars : set[str]
            conjunto de atributos requeridos por el modelo
        admissible_vars : set[str]
            conjunto de atributos admitidos por el modelo
        db : pymongo.collection.Collection
            conexion a la coleccion de la base de datos
    
    Methods
    -------
        __setattr__(name: str, value: str | dict) -> None
            Sobreescribe el metodo de asignacion de valores a los 
            atributos del objeto con el fin de controlar qué atributos 
            son modificados y cuando son modificados.
        __getattr__(name: str) -> Any
            Sobreescribe el metodo de acceso a atributos del objeto 
        save()  -> None
            Guarda el modelo en la base de datos
        delete() -> None
            Elimina el modelo de la base de datos
        find(filter: dict[str, str | dict]) -> ModelCursor
            Realiza una consulta de lectura en la BBDD.
            Devuelve un cursor de modelos ModelCursor
        aggregate(pipeline: list[dict]) -> pymongo.command_cursor.CommandCursor
            Devuelve el resultado de una consulta aggregate.
        find_by_id(id: str) -> dict | None
            Busca un documento por su id utilizando la cache y lo devuelve.
            Si no se encuentra el documento, devuelve None.
        init_class(db_collection: pymongo.collection.Collection, required_vars: set[str], admissible_vars: set[str]) -> None
            Inicializa las variables de clase en la inicializacion del sistema.

    """
    _required_vars: set[str]
    _admissible_vars: set[str]
    _location_var: str | None = None
    _db: pymongo.collection.Collection
    _internal_vars: set[str] = frozenset(('_modified_vars', '_required_vars', '_admissible_vars', '_db', '_data', '_location_var'))

    @classmethod
    def _location_field(cls) -> str | None:
        """Nombre del campo que guarda el punto GeoJSON (<campo>_loc)."""
        return f"{cls._location_var}_loc" if cls._location_var else None

    def __init__(self, **kwargs: dict[str, str | dict | list]) -> None:
        """
        Inicializa el modelo con los valores proporcionados en kwargs
        Comprueba que los valores proporcionados en kwargs son admitidos
        por el modelo y que las atributos requeridos son proporcionadas.

        Parameters
        ----------
            kwargs : dict[str, str | dict]
                diccionario con los valores de las atributos del modelo
        """
        self._data: dict[str, str | dict | list] = {}
        self._modified_vars = set()

        #TODO
        # Realizar las comprabociones y gestiones necesarias
        # antes de la asignacion.

        # Asigna todos los valores en kwargs a las atributos con 
        # nombre las claves en kwargs
        # Utilizamos el atributo data para guardar los variables 
        # almacenadas en la base de datos en una solo atributo
        # Encapsular los datos en una sola variable facilita la 
        # gestion en metodos como save.

        permitidos = self._required_vars | self._admissible_vars | {"_id"}
        if self._location_field():
            permitidos.add(self._location_field())
        faltan = self._required_vars - kwargs.keys()

        if faltan:
            raise ValueError(f"Faltan atributos requeridos: {sorted(faltan)}")
        sobran = kwargs.keys() - permitidos

        if sobran:
            raise ValueError(f"Atributos no permitidos: {sorted(sobran)}")

        self._data.update(kwargs)

    def __setattr__(self, name: str, value: str | dict) -> None:
        """ Sobreescribe el metodo de asignacion de valores a los 
        atributos del objeto con el fin de controlar que atributos 
        son modificados y cuando son modificados.
        """
        if name in self._internal_vars:
            super().__setattr__(name, value)
            return
        #TODO
        # Realizar las comprabociones y gestiones necesarias
        # antes de la asignacion.

        # Asigna el valor value a la variable name

        if name not in self._required_vars | self._admissible_vars:
            raise ValueError(f"Atributo no admitido: {name}")

        self._modified_vars.add(name)
        self._data[name] = value

    def __getattr__(self, name: str) -> Any:
        """ Sobreescribe el metodo de acceso a atributos del objeto
        __getattr__ solo es llamado cuando no encuentra el atributo
        en el objeto 
        """
        if name in self._internal_vars:
            return super().__getattribute__(name)
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError
        
    def save(self) -> None:
        """
        Guarda el modelo en la base de datos
        Si el modelo no existe en la base de datos, se crea un nuevo
        documento con los valores del modelo. En caso contrario, se
        actualiza el documento existente con los nuevos valores del
        modelo..
        """
        #TODO
        if "_id" not in self._data:
            # Documento nuevo: si hay dirección, guarda también su punto GeoJSON
            if self._location_var and self._location_var in self._data:
                direccion = self._data[self._location_var]
                self._data[self._location_var + "_loc"] = getLocationPoint(direccion)
            # insert_one añade el _id a self._data
            self._db.insert_one(self._data)
        else:
            # TODO (paso 5): actualizar solo los campos modificados
            if not self._modified_vars:
                return
            cambios = {v: self._data[v] for v in self._modified_vars}

            if self._location_var and self._location_var in cambios:
                cambios[self._location_var + "_loc"] = getLocationPoint(cambios[self._location_var])
                self._data[self._location_var + "_loc"] = cambios[self._location_var + "_loc"]
            self._db.update_one({"_id": self._data["_id"]}, {"$set": cambios})
        self._modified_vars.clear()

    def delete(self) -> None:
        """
        Elimina el modelo de la base de datos
        """
        #TODO
        if "_id" in self._data:
            self._db.delete_one({"_id": self._data["_id"]})
            del self._data["_id"]
    
    @classmethod
    def find(cls, filter: dict[str, str | dict]) -> Any:
        """ 
        Utiliza el metodo find de pymongo para realizar una consulta
        de lectura en la BBDD.
        find debe devolver un cursor de modelos ModelCursor

        Parameters
        ----------
            filter : dict[str, str | dict]
                diccionario con el criterio de busqueda de la consulta
        Returns
        -------
            ModelCursor
                cursor de modelos
        """ 
        #TODO
        # cls es el puntero a la clase
        return ModelCursor(cls, cls._db.find(filter))

    @classmethod
    def aggregate(cls, pipeline: list[dict]) -> pymongo.command_cursor.CommandCursor:
        """ 
        Devuelve el resultado de una consulta aggregate. 
        No hay nada que hacer en esta funcion.
        Se utilizara para las consultas solicitadas
        en el segundo proyecto de la practica.

        Parameters
        ----------
            pipeline : list[dict]
                lista de etapas de la consulta aggregate 
        Returns
        -------
            pymongo.command_cursor.CommandCursor
                cursor de pymongo con el resultado de la consulta
        """ 
        return cls._db.aggregate(pipeline)
    
    @classmethod
    def find_by_id(cls, id: str) -> Self | None:
        """ 
        NO IMPLEMENTAR HASTA EL TERCER PROYECTO
        Busca un documento por su id utilizando la cache y lo devuelve.
        Si no se encuentra el documento, devuelve None.

        Parameters
        ----------
            id : str
                id del documento a buscar
        Returns
        -------
            Self | None
                Modelo del documento encontrado o None si no se encuentra
        """ 
        #TODO
        pass

    @classmethod
    def init_class(cls, db_collection: pymongo.collection.Collection, indexes:dict[str,str], required_vars: set[str], admissible_vars: set[str]) -> None:
        """ 
        Inicializa los atributos de clase en la inicializacion del sistema.
        Aqui se deben inicializar o asegurar los indices. Tambien se puede
        alguna otra inicialización/comprobaciones o cambios adicionales
        que estime el alumno.

        Parameters
        ----------
            db_collection : pymongo.collection.Collection
                Conexion a la collecion de la base de datos.
            indexes: Dict[str,str]
                Set de indices y tipo de indices para la coleccion
            required_vars : set[str]
                Set de atributos requeridos por el modelo
            admissible_vars : set[str] 
                Set de atributos admitidos por el modelo
        """
        cls._db = db_collection
        cls._required_vars = required_vars
        cls._admissible_vars = admissible_vars
        cls._location_var = None
        # TODO
        # Recorrer indexes y crear cada índice segun su tipo: 'unique', 'asc'
        # y 'geosphere'. Comparar el tipo por igualdad, no con el operador 'in'.
        # Ojo con el índice geoespacial: save() guarda el GeoJSON Point en
        # <campo>_loc, luego el índice 2dsphere va sobre <campo>_loc, mientras
        # que _location_var debe guardar el nombre del campo base.
        for field, kind in (indexes or {}).items():
            if kind == 'unique':
                cls._db.create_index([(field, pymongo.ASCENDING)], unique=True)
            elif kind == 'asc':
                cls._db.create_index([(field, pymongo.ASCENDING)])
            elif kind == 'geosphere':
                cls._location_var = field
                cls._db.create_index([(f"{field}_loc", pymongo.GEOSPHERE)])
            else:
                raise ValueError(f"Tipo de índice desconocido: {kind}")



class ModelCursor:
    """ 
    Cursor para iterar sobre los documentos del resultado de una
    consulta. Los documentos deben ser devueltos en forma de objetos
    modelo.

    Attributes
    ----------
        model_class : Model
            Clase para crear los modelos de los documentos que se iteran.
        cursor : pymongo.cursor.Cursor
            Cursor de pymongo a iterar

    Methods
    -------
        __iter__() -> Generator
            Devuelve un iterador que recorre los elementos del cursor
            y devuelve los documentos en forma de objetos modelo.
    """

    def __init__(self, model_class: Model, cursor: pymongo.cursor.Cursor):
        """
        Inicializa el cursor con la clase de modelo y el cursor de pymongo

        Parameters
        ----------
            model_class : Model
                Clase para crear los modelos de los documentos que se iteran.
            cursor: pymongo.cursor.Cursor
                Cursor de pymongo a iterar
        """
        self.model = model_class
        self.cursor = cursor
    
    def __iter__(self) -> Generator:
        """
        Devuelve un iterador que recorre los elementos del cursor
        y devuelve los documentos en forma de objetos modelo.
        Utilizar yield para generar el iterador
        Utilizar la funcion next para obtener el siguiente documento del cursor
        Utilizar alive para comprobar si existen mas documentos.
        """
        #TODO
        while self.cursor.alive:
            try:
                doc = next(self.cursor)
            except StopIteration:
                return
            yield self.model(**doc)


def initApp(definitions_path: str = "./models.yml", mongodb_uri="mongodb://localhost:27017/", db_name="abd", scope=globals()) -> None:
    """ 
    Declara las clases que heredan de Model para cada uno de los 
    modelos de las colecciones definidas en definitions_path.
    Inicializa las clases de los modelos proporcionando los indices y 
    atributos admitidos y requeridos para cada una de ellas y la conexión a la
    collecion de la base de datos.
    
    Parameters
    ----------
        definitions_path : str
            ruta al fichero de definiciones de modelos
        mongodb_uri : str
            uri de conexion a la base de datos
        db_name : str
            nombre de la base de datos
    """
    #Conexion a la base de datos
    client = MongoClient(mongodb_uri, server_api=ServerApi('1'))
    db = client[db_name]

    # Leer el YAML
    with open(definitions_path, encoding='utf-8') as f:
        definitions = yaml.safe_load(f) or {}
    #TODO
    # Declarar tantas clases modelo colecciones existan en la base de datos
    # Leer el fichero de definiciones de modelos para obtener las colecciones,
    # indices y los atributos admitidos y requeridos para cada una de ellas.
    # Ejemplo de declaracion de modelo para colecion llamada MiModelo
    for model_name, spec in definitions.items():
        spec = spec or {}
        indexes = {}
        for field in spec.get("regular_indexes", []):
            indexes[field] = 'asc'
        for field in spec.get("unique_indexes", []):
            indexes[field] = 'unique'
        if spec.get('location_index'):
            indexes[spec['location_index']] = 'geosphere'
        scope[model_name] = type(model_name, (Model,), {})
        scope[model_name].init_class(
            db_collection=db[model_name],
            indexes=indexes,
            required_vars=set(spec.get("required_vars", [])),
            admissible_vars=set(spec.get("admissible_vars", [])),
        )

if __name__ == '__main__':
    
    # Inicializar base de datos y modelos con initApp
    #TODO
    scope = {}
    initApp(db_name="abd", scope=scope)
    Recinto, Artista, Evento, Asistente = (scope[n] for n in ("Recinto", "Artista", "Evento", "Asistente"))
    for modelo in (Recinto, Artista, Evento, Asistente):
        modelo._db.delete_many({})

    # Crear modelo
    recinto = Recinto(
        nombre="WiZink Center",
        direccion="Avenida de Felipe II, Madrid, España",
        aforo=15000,
        zonas={"Pista": 5000, "Grada": 10000},
        servicios=["Bar", "Restaurante", "Aseos"],
    )
    artista = Artista(
        nombre="Coldplay",
        generos=["rock", "pop"],
        pais="Reino Unido",
        anio_inicio=1996,
    )
    evento = Evento(
        titulo="Concierto de Coldplay",
        recinto="WiZink Center",
        artistas=["Coldplay"],
        fecha=datetime(2024, 6, 15, 20, 0),
        precios={"Pista": 100, "Grada": 50},
    )
    asistente = Asistente(
        nombre="Juan Pérez",
        email="juannnn@gmail.com",
        fecha_alta=datetime(2024, 6, 1, 10, 0),
        direccion="Calle de Alcalá, Madrid, España",
    )

    # Asignar nuevo valor a variable admitida del objeto
    evento.entradas_vendidas = 1200

    # Asignar nuevo valor a variable no admitida del objeto
    try:
        recinto.color = "rojo"
    except ValueError as e:
        print("Error:", e)

    try:
        Artista(nombre="Sin pais")
    except ValueError as e:
        print("Error:", e)

    # Guardar
    for doc in (recinto, artista, evento, asistente):
        doc.save()
    print("Guardados los 4 modelos")

    # Asignar nuevo valor a variable admitida del objeto
    recinto.aforo = 16000

    # Guardar
    recinto.save()

    # Buscar nuevo documento con find
    result = Recinto.find({"nombre": "WiZink Center"})

    # Obtener primer documento
    recinto_result = next(iter(result))

    # Modificar valor de variable admitida
    recinto_result.aforo = 17000

    # Guardar
    recinto_result.save()
    print("Aforo final:", Recinto._db.find_one({"nombre": "WiZink Center"})["aforo"])