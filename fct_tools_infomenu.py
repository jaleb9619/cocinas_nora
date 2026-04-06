# python3 fct_tools_infomenu.py

from anthropic import Anthropic
from collections import defaultdict
from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import models, QdrantClient
from qdrant_client.models import PointStruct
from supabase import create_client, Client

import os
import random
import tiktoken

from decorador_costos import (
    decorador_costo
)

load_dotenv()

# anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME")
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

# supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_API_KEY")
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TLB_PLATILLOS=os.getenv('TLB_PLATILLOS')
TLB_TIEMPOS=os.getenv('TLB_TIEMPOS')

# openai
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_EMBEDDINGS_MODEL = os.getenv('OPENAI_EMBEDDINGS_MODEL')
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# qdrant
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, check_compatibility=False)

def num_tokens_from_string(string: str, encoding_name: str) -> int:

    encoding = tiktoken.get_encoding("cl100k_base")

    if isinstance(string, str):
        tokens = len(encoding.encode(string))
    elif isinstance(string, list):
        tokens = sum(len(encoding.encode(t)) for t in string)

    return tokens

# @decorador_costo
def create_embeddings(
    texto, 
    # id_conversacion, 
    client=openai_client, 
    model=OPENAI_EMBEDDINGS_MODEL
    ):

    respuesta = client.embeddings.create(
        input=texto,
        model=model,
        dimensions=1024,
    )

    input_tokens=num_tokens_from_string(
        string=texto,
        encoding_name=model
    )

    return {
        'answer':respuesta.data[0].embedding,
        'input_tokens':input_tokens,
        'model_name':model
        # 'id_conversacion': id_conversacion
    }

def insert_info_business(secciones, client_qdrant=qdrant_client, COLECCION="COCINA"):

    collections = client_qdrant.get_collections().collections
    collection_names = [collection.name for collection in collections]

    if COLECCION not in collection_names:
        client_qdrant.create_collection(
            collection_name=COLECCION,
            vectors_config={
                "embeddings": {
                    "size": 1024,
                    "distance": "Cosine"
                }
            }
        )
        print(f"Colección '{COLECCION}' creada exitosamente.")

    puntos = []

    for index, seccion in enumerate(secciones):
        embedding_data = create_embeddings(seccion["texto"])
        embedding = embedding_data["answer"]

        punto = PointStruct(
            id=index,
            vector={"embeddings": embedding},
            payload={
                "nombre": seccion["nombre"],
                "texto": seccion["texto"]
            }
        )

        puntos.append(punto)

    client_qdrant.upsert(collection_name=COLECCION, points=puntos)
    print(f"{len(puntos)} secciones insertadas en Qdrant.")

def get_text_by_relevance(
        consulta, 
        # id_conversacion, 
        cliente=qdrant_client, 
        coleccion="COCINA", 
        n=1
        ):
    texto_relevante = []
    embedding = create_embeddings(consulta)

    search_params = models.SearchParams(
        hnsw_ef=128,
        exact=False
    )

    resultado_busqueda = cliente.search(
        collection_name=coleccion,
        query_vector= models.NamedVector(
            name="embeddings",
            vector=embedding["answer"]
        ),
        search_params=search_params,
        limit=n
    )
    # print(resultado_busqueda)

    for resultado in resultado_busqueda:
        texto_relevante.append(
            (resultado.payload["nombre"], resultado.payload["texto"], resultado.score)
        )

    texto_relevante.sort(key=lambda x: x[2], reverse=True)
    return texto_relevante[:n]

def consultar_menu_del_dia_orig(
        supabase_client=supabase_client, 
        table_platillos=TLB_PLATILLOS,
        table_tiempos=TLB_TIEMPOS):
    try:
        response = (
            supabase_client
            .table(table_platillos)
            .select(
                f"platillo, tiempo_id, " +
                f"{table_tiempos}(id, nombre)"
            )
            .eq("activo", True)
            .execute()
        )

        data = response.data or []

        if not data:
            print(f"No se encontraron platillos activos en '{table_platillos}'.")
            return {}  # ← Devolver dict vacío en vez de lista

        # Procesar data para agrupar por tiempos
        from collections import defaultdict
        menu_por_tiempos = defaultdict(list)

        for item in data:
            tiempo_info = item.get('tbl_cocina_tiempos', {})
            nombre_tiempo = tiempo_info.get('nombre', 'Desconocido')
            platillo = item.get('platillo', 'Sin nombre')
            menu_por_tiempos[nombre_tiempo].append(platillo)

        # Convertir a dict normal
        return dict(menu_por_tiempos)  # ← Devolver dict procesado

    except Exception as error:
        print(f"Error al consultar menú del día en '{table_platillos}': {error}")
        return {}  # ← Devolver dict vacío en caso de error

def consultar_menu_del_dia(
        supabase_client=supabase_client, 
        table_platillos=TLB_PLATILLOS,
        table_tiempos=TLB_TIEMPOS,
        user_id=None):
    try:
        if user_id is None:
            user_id = os.getenv('USER_ID')
        
        if not user_id:
            print("⚠️ USER_ID no configurado - No se puede consultar menú")
            return {}
        
        # Consultar platillos
        response = (
            supabase_client
            .table(table_platillos)
            .select(
                f"platillo, tiempo_id, precio, " +
                f"{table_tiempos}(id, nombre)"
            )
            .eq("user_id", user_id)
            .eq("activo", True)
            .execute()
        )

        data = response.data or []

        if not data:
            print(f"No se encontraron platillos activos para user_id '{user_id}' en '{table_platillos}'.")
            return {}

        # Consultar precio del menú desde config
        config_response = supabase_client.table('tbl_cocina_config')\
            .select('precio_menu, descuento_por_platillo')\
            .eq('user_id', user_id)\
            .execute()
        
        precio_menu = 0.0
        descuento_por_platillo = False
        if config_response.data and len(config_response.data) > 0:
            precio_menu = float(config_response.data[0].get('precio_menu') or 0.0)
            descuento_por_platillo = bool(config_response.data[0].get('descuento_por_platillo') or False)

        # Procesar platillos agrupados por tiempo
        menu_por_tiempos = defaultdict(list)
        for item in data:
            tiempo_info = item.get('tbl_cocina_tiempos', {})
            nombre_tiempo = tiempo_info.get('nombre', 'Desconocido')
            platillo = item.get('platillo', 'Sin nombre')
            precio = float(item.get('precio') or 0.0)
            menu_por_tiempos[nombre_tiempo].append({
                'platillo': platillo,
                'precio': precio
            })

        return {
            'menu': dict(menu_por_tiempos),
            'precio_menu': precio_menu,
            'descuento_por_platillo': descuento_por_platillo
        }

    except Exception as error:
        print(f"Error al consultar menú del día en '{table_platillos}': {error}")
        return {}

def consultar_menu_del_dia_orig(
        supabase_client=supabase_client, 
        table_platillos=TLB_PLATILLOS,
        table_tiempos=TLB_TIEMPOS,
        user_id=None):
    try:
        # Obtener user_id del .env si no se proporciona
        if user_id is None:
            user_id = os.getenv('USER_ID')
        
        if not user_id:
            print("⚠️ USER_ID no configurado - No se puede consultar menú")
            return {}
        
        response = (
            supabase_client
            .table(table_platillos)
            .select(
                f"platillo, tiempo_id, " +
                f"{table_tiempos}(id, nombre)"
            )
            .eq("user_id", user_id)  # FILTRO POR COCINA
            .eq("activo", True)
            .execute()
        )

        data = response.data or []

        if not data:
            print(f"No se encontraron platillos activos para user_id '{user_id}' en '{table_platillos}'.")
            return {}

        # Procesar data para agrupar por tiempos
        menu_por_tiempos = defaultdict(list)

        for item in data:
            tiempo_info = item.get('tbl_cocina_tiempos', {})
            nombre_tiempo = tiempo_info.get('nombre', 'Desconocido')
            platillo = item.get('platillo', 'Sin nombre')
            menu_por_tiempos[nombre_tiempo].append(platillo)

        # Convertir a dict normal
        return dict(menu_por_tiempos)

    except Exception as error:
        print(f"Error al consultar menú del día en '{table_platillos}': {error}")
        return {}

# def formatear_menu(menu_por_tiempos):
#     lineas = ["Menú del día:\n"]

#     # Ordenar por el nombre del tiempo (alfabéticamente)
#     for tiempo in sorted(menu_por_tiempos.keys()):
#         platillos = menu_por_tiempos[tiempo]

#         if not platillos:
#             continue

#         lineas.append(f"{tiempo}")
#         for platillo in platillos:
#             lineas.append(f"- {platillo}")
#         lineas.append("")

#     return "\n".join(lineas).strip()

def formatear_menu(menu_data):
    # Soporta tanto el formato nuevo (dict con 'menu') como el viejo (dict directo)
    if 'menu' in menu_data:
        menu_por_tiempos = menu_data['menu']
        precio_menu = menu_data.get('precio_menu', 0.0)
        descuento_por_platillo = menu_data.get('descuento_por_platillo', False)
    else:
        menu_por_tiempos = menu_data
        precio_menu = 0.0
        descuento_por_platillo = False

    lineas = ["Menú del día:\n"]

    for tiempo in sorted(menu_por_tiempos.keys()):
        platillos = menu_por_tiempos[tiempo]
        if not platillos:
            continue

        lineas.append(f"{tiempo}")
        for item in platillos:
            if isinstance(item, dict):
                nombre = item.get('platillo', '')
                precio = item.get('precio', 0.0)
                lineas.append(f"- {nombre} (${precio:.2f})")
            else:
                lineas.append(f"- {item}")
        lineas.append("")

    # Agregar precio del menú completo
    if precio_menu > 0:
        lineas.append(f"Precio menú completo: ${precio_menu:.2f}")
        if descuento_por_platillo:
            lineas.append("(Se aplica descuento si no pides algún platillo del menú)")

    return "\n".join(lineas).strip()

def generar_menu_aleatorio(
        supabase_client=supabase_client, 
        table_platillos=TLB_PLATILLOS,
        table_tiempos=TLB_TIEMPOS):
    # Esta funcion es para uso en dev.
    # En la tabla de platillos, modifica los valores de status de manera aleatoria
    # para generar un menu aleatorio con los tiempo suficientes (primero, segundo, etc)
    try:
        response = (
            supabase_client
            .table(table_platillos)
            .select(
                "*"
            )
            .execute()
        )

        tiempos=defaultdict(list)
        for registro in response.data:
            tiempos[registro["tiempo"]].append(registro)

        nuevos_status = []

        for tiempo, registros in tiempos.items():
            if len(registros) >= 2:
                ids_elegidos = set(reg["id"] for reg in random.sample(registros, 2))
            else:
                ids_elegidos = {registros[0]["id"]}

            for reg in registros:
                nuevo = reg.copy()
                nuevo["status"] = reg["id"] in ids_elegidos
                nuevos_status.append(nuevo)

        response_update = (
            supabase_client
            .table(table_platillos)
            .upsert(nuevos_status)
            .execute()
        )

        data = response.data or []
        if data:
            # print(f"{len(data)} platillo(s) actualizados '{table_platillos}'.")
            pass
        else:
            print(f"No se encontraron platillos activos en '{table_platillos}'.")

        return data

    except Exception as error:
        print(f"Error al consultar menú del día en '{table_platillos}': {error}")
        return []

if __name__ == "__main__":
    informacion = [
        {
            "nombre": "Ubicación y horarios",
            "texto": """
            Cocina Doña Lupita
            Calle Emiliano Zapata #102, Col. Centro, Cuernavaca, Morelos, México CP 62000
            Horario:
            Lunes a viernes: 7:00 a 17:00 hrs
            Domingo: cerrado
            Servicio en sitio y para llevar
            """
        },
        {
            "nombre": "Menú del día",
            "texto": """
            
            Primero tiempo
            - Sopa de fideos
            - Consomé de pollo

            Segundo tiempo
            - Ensalada
            - Pasta
            - Arroz

            Tercer tiempo
            - Pollo en mole poblano
            - Mole de olla
            - Pescado empanizado
            - Enchiladas verdes

            Agua
            - Limón
            - Jamaica
            """
        }
    ]

    menu = consultar_menu_del_dia()
    menu_vf = formatear_menu(menu)
    print("menu", menu)
    print("menu formateado", menu_vf)
    
    # hola=insert_info_business(informacion)
    # print(hola)

    
