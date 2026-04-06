# python3 utils.py

import tiktoken

from clients.supabase_client import supabase_client

def extract_phone_from_wa_sender(data_from: str) -> str:
    posicion_arroba = data_from.find('@')
    return data_from[posicion_arroba-10:posicion_arroba]

def num_tokens_from_string(string: str) -> int:

    encoding = tiktoken.get_encoding("cl100k_base")

    if isinstance(string, str):
        tokens = len(encoding.encode(string))

    elif isinstance(string, list):
        tokens = sum(len(encoding.encode(t)) for t in string)

    return tokens

def obtener_campos_platillos_validos(user_id):
    """
    Consulta tbl_cocina_tiempos para obtener los campos de platillos
    que esta cocina específica tiene configurados.
    
    Returns:
        list: Nombres de campos (ej: ['primer_tiempo', 'segundo_tiempo', 'postre', 'agua'])
    """
    try:
        
        result = supabase_client.table("tbl_cocina_tiempos")\
            .select("nombre")\
            .eq("user_id", user_id)\
            .order("orden")\
            .execute()
        
        if result.data:
            # Convertir nombres a formato snake_case para usar como keys
            # Ej: "Primer Tiempo" → "primer_tiempo"
            campos = []
            for tiempo in result.data:
                nombre = tiempo.get("nombre", "")
                # Convertir a snake_case
                campo = nombre.lower().replace(" ", "_")
                campos.append(campo)
            
            # Siempre incluir a_la_carta por defecto
            if "a_la_carta" not in campos:
                campos.append("a_la_carta")
            
            return campos
        else:
            # Si no hay tiempos configurados, usar defaults mínimos
            return ["primer_tiempo", "segundo_tiempo", "tercer_tiempo", "a_la_carta"]
            
    except Exception as e:
        print(f"❌ Error consultando tiempos: {e}")
        # Fallback a defaults
        return ["primer_tiempo", "segundo_tiempo", "tercer_tiempo", "a_la_carta"]

# def construir_platillos_dict(tool_input, campos_validos):
#     """
#     Construye diccionario de platillos validando contra campos permitidos DINÁMICOS.
#     """
#     platillos_dict = {}

#     CAMPOS_NO_PLATILLOS = ['nombre_completo', 'desechables']

#     for key, value in tool_input.items():
#         # Ignorar campos que no son platillos
#         if key in CAMPOS_NO_PLATILLOS:
#             continue
        
#         # Solo procesar campos válidos para ESTA cocina
#         if key in campos_validos:
#             if value and value not in ['', '<UNKNOWN>']:
#                 if isinstance(value, list):
#                     platillos_dict[key] = value
#                 else:
#                     platillos_dict[key] = [value] if value else []
#             else:
#                 platillos_dict[key] = []
#         else:
#             print(f"⚠️ Campo '{key}' no configurado para esta cocina - ignorado")
    
#     return platillos_dict

def construir_platillos_dict(tool_input, campos_validos):
    platillos_dict = {}
    CAMPOS_NO_PLATILLOS = ['nombre_completo', 'desechables']
    CAMPOS_EXTRA = ['extra_1', 'extra_2', 'extra_3', 'a_la_carta']

    for key, value in tool_input.items():
        if key in CAMPOS_NO_PLATILLOS:
            continue

        if key in campos_validos or key in CAMPOS_EXTRA:
            if value and value not in ['', '<UNKNOWN>']:
                if isinstance(value, list):
                    platillos_dict[key] = value
                else:
                    platillos_dict[key] = [value] if value else []
            else:
                platillos_dict[key] = []
        else:
            print(f"⚠️ Campo '{key}' no configurado para esta cocina - ignorado")

    return platillos_dict

if __name__ == "__main__":

    import os
    from dotenv import load_dotenv

    load_dotenv()
    user_id = os.getenv("USER_ID")
    campos = obtener_campos_platillos_validos(user_id)
    print(campos)
