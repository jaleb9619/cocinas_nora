# python3 fct_tools_ordenar.py

import os
import random

from clients.supabase_client import supabase_client
from collections import defaultdict
from decorador_costos import decorador_costo
from dotenv import load_dotenv
from fct_supabase import read_data

load_dotenv()

TLB_PLATILLOS=os.getenv('TLB_PLATILLOS')
TLB_TIEMPOS=os.getenv('TLB_TIEMPOS')
user_id = os.getenv('USER_ID')


def unaccent_simple(texto):
    reemplazos = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'ä': 'a', 'ë': 'e', 'ï': 'i', 'ö': 'o', 'ü': 'u',
        'à': 'a', 'è': 'e', 'ì': 'i', 'ò': 'o', 'ù': 'u',
    }
    return ''.join(reemplazos.get(c, c) for c in texto)

def extraer_ids_platillos(
        platillos,
        supabase_client=supabase_client,
        user_id=user_id):
    try:
        print(f"🔍 Buscando IDs para platillos: {platillos}")
        response = supabase_client.rpc(
            'buscar_platillos_flexible',
            {
                'nombres': platillos,
                'p_user_id': user_id
            }
        ).execute()

        data = response.data or []

        if len(data) < len(platillos):
            encontrados = [d['platillo'] for d in data]
            no_encontrados = [p for p in platillos if not any(
                unaccent_simple(p.lower()) == unaccent_simple(e.lower()) 
                for e in encontrados
            )]
            print(f"⚠️ Platillos NO encontrados en BD: {no_encontrados}")
        
        print(f"✅ {len(data)}/{len(platillos)} platillos encontrados")
        return data

    except Exception as error:
        print(f"❌ Error en extraer_ids_platillos: {error}")
        return []

# def extraer_ids_platillos(
#         platillos,
#         supabase_client=supabase_client,
#         table_platillos=TLB_PLATILLOS):
#     try:
#         print("platillos", platillos)
#         response = (
#             supabase_client
#             .table(table_platillos)
#             .select("platillo, id")
#             .in_("platillo", platillos)
#             .execute()
#         )
#         data = response.data or []
#         if data:
#             # print(f"{len(data)} platillo(s) activo(s) encontrados en '{table}'.")
#             pass

#         else:
#             print(f"No se encontraron platillos activos en '{table_platillos}'.")
#         return data

#     except Exception as error:
#         print(f"Error al consultar menú del día en '{table_platillos}': {error}")
#         return []

def determinar_costo_comanda(
        tool_input,
        config=None,
        supabase_client=supabase_client,
        table_platillos=TLB_PLATILLOS):

    precio_menu = float(config.get('precio_menu', 0.0)) if config else 0.0
    descuento_por_platillo = bool(config.get('descuento_por_platillo', False)) if config else False
    # NUEVO: leer descuento fijo opcional
    descuento_fijo_omision = config.get('descuento_fijo_omision', None) if config else None
    if descuento_fijo_omision is not None:
        try:
            descuento_fijo_omision = float(descuento_fijo_omision)
        except:
            descuento_fijo_omision = None

    costos_platillos = read_data(
        table_name=table_platillos,
        variables='platillo, precio',
        filters={'activo': 'TRUE'},
    )

    comida_estandar = ['primer_tiempo', 'segundo_tiempo', 'tercer_tiempo']

    if all(campo in tool_input for campo in comida_estandar):
        if descuento_por_platillo:
            platillos_omitidos = [
                tool_input[campo] for campo in comida_estandar
                if not tool_input.get(campo) or tool_input[campo] in ['', '<UNKNOWN>']
            ]
            # NUEVO: lógica de tres estados
            descuento = 0.0
            for platillo_omitido in platillos_omitidos:
                if descuento_fijo_omision is not None:
                    # Usa el descuento fijo configurado por el dueño
                    descuento += descuento_fijo_omision
                else:
                    # Usa el precio individual del platillo omitido
                    precio_individual = next(
                        (item['precio'] for item in costos_platillos
                         if item['platillo'] == platillo_omitido),
                        0.0
                    )
                    descuento += precio_individual
            monto_estandar = precio_menu - descuento
        else:
            monto_estandar = precio_menu

        a_la_carta = tool_input.get('a_la_carta')
        if a_la_carta and a_la_carta not in ['', '<UNKNOWN>']:
            precio_a_la_carta = next(
                (item['precio'] for item in costos_platillos 
                    if unaccent_simple(item['platillo'].lower()) == unaccent_simple(a_la_carta.lower())),
                    0.0
                )
            monto_estandar += precio_a_la_carta

        platillos_extra = [v for k, v in tool_input.items() if 'extra' in k]
        monto_extras = sum(
            item['precio'] for item in costos_platillos 
            if item['platillo'] in platillos_extra
        ) if platillos_extra else 0

    else:
        todos_platillos = []
        for k, v in tool_input.items():
            if k in ['nombre_completo', 'desechables']:
                continue
            if not v or v in ['', '<UNKNOWN>']:
                continue
            if isinstance(v, list):
                todos_platillos.extend([p for p in v if p and p not in ['', '<UNKNOWN>']])
            else:
                todos_platillos.append(v)

        todos_platillos_norm = [unaccent_simple(p.lower()) for p in todos_platillos]

        monto_estandar = sum(
            item['precio'] for item in costos_platillos
            if any(
                norm in unaccent_simple(item['platillo'].lower()) or
                unaccent_simple(item['platillo'].lower()) in norm
                for norm in todos_platillos_norm
            )
        )
        monto_extras = 0

    desechable = [v for k, v in tool_input.items() if 'desechables' in k]
    tot_platillos = sum(1 for k in tool_input if k != 'nombre_completo') if 'Sí' in desechable else 0
    monto_desechables = tot_platillos * 5

    montos = {
        'monto_estandar': monto_estandar,
        'monto_extras': monto_extras,
        'monto_desechables': monto_desechables,
        'monto_total': monto_estandar + monto_extras + monto_desechables
    }
    return montos

def determinar_costo_comanda_orig(
        tool_input,
        config=None,
        supabase_client=supabase_client,
        table_platillos=TLB_PLATILLOS):

    # Obtener precio_menu y descuento_por_platillo del config
    precio_menu = float(config.get('precio_menu', 0.0)) if config else 0.0
    descuento_por_platillo = bool(config.get('descuento_por_platillo', False)) if config else False

    # NUEVO: leer descuento fijo opcional
    descuento_fijo_omision = config.get('descuento_fijo_omision', None) if config else None
    if descuento_fijo_omision is not None:
        try:
            descuento_fijo_omision = float(descuento_fijo_omision)
        except:
            descuento_fijo_omision = None

    # Consultar precios de platillos
    costos_platillos = read_data(
        table_name=table_platillos,
        variables='platillo, precio',
        filters={'activo': 'TRUE'},
    )

    comida_estandar = ['primer_tiempo', 'segundo_tiempo', 'tercer_tiempo']

    if all(campo in tool_input for campo in comida_estandar):
        if descuento_por_platillo:
            # Calcular descuentos por platillos omitidos
            platillos_omitidos = [
                tool_input[campo] for campo in comida_estandar
                if not tool_input.get(campo) or tool_input[campo] in ['', '<UNKNOWN>']
            ]
            descuento = sum(
                item['precio'] for item in costos_platillos 
                if item['platillo'] in platillos_omitidos
            )
            monto_estandar = precio_menu - descuento
        else:
            monto_estandar = precio_menu
        
        # Costo a la carta: precio_menu + precio del platillo a la carta
        a_la_carta = tool_input.get('a_la_carta')
        if a_la_carta and a_la_carta not in ['', '<UNKNOWN>']:
            precio_a_la_carta = next(
                (item['precio'] for item in costos_platillos 
                    if unaccent_simple(item['platillo'].lower()) == unaccent_simple(a_la_carta.lower())),
                    0.0
                )
            monto_estandar += precio_a_la_carta

        # Extras
        platillos_extra = [v for k, v in tool_input.items() if 'extra' in k]
        monto_extras = sum(
            item['precio'] for item in costos_platillos 
            if item['platillo'] in platillos_extra
        ) if platillos_extra else 0

    # else:
    #     # Caso parcial: sumar precio individual de cada platillo pedido
    #     todos_platillos = [
    #         v for k, v in tool_input.items()
    #         if k not in ['nombre_completo', 'desechables']
    #         and v and v not in ['', '<UNKNOWN>']
    #     ]
    #     monto_estandar = sum(
    #         item['precio'] for item in costos_platillos 
    #         if item['platillo'] in todos_platillos
    #     )
    #     monto_extras = 0

    # else:
    #     # Caso parcial: sumar precio individual de cada platillo pedido
    #     todos_platillos = []
    #     for k, v in tool_input.items():
    #         if k in ['nombre_completo', 'desechables']:
    #             continue
    #         if not v or v in ['', '<UNKNOWN>']:
    #             continue
    #         # Normalizar: puede venir como lista o string
    #         if isinstance(v, list):
    #             todos_platillos.extend([p for p in v if p and p not in ['', '<UNKNOWN>']])
    #         else:
    #             todos_platillos.append(v)

    #     # Normalizar nombres para comparación (quitar acentos, lowercase)
    #     todos_platillos_norm = [unaccent_simple(p.lower()) for p in todos_platillos]

    #     monto_estandar = sum(
    #         item['precio'] for item in costos_platillos
    #         if unaccent_simple(item['platillo'].lower()) in todos_platillos_norm
    #     )
    #     monto_extras = 0

    else:
        todos_platillos = []
        for k, v in tool_input.items():
            if k in ['nombre_completo', 'desechables']:
                continue
            if not v or v in ['', '<UNKNOWN>']:
                continue
            if isinstance(v, list):
                todos_platillos.extend([p for p in v if p and p not in ['', '<UNKNOWN>']])
            else:
                todos_platillos.append(v)

        todos_platillos_norm = [unaccent_simple(p.lower()) for p in todos_platillos]

        monto_estandar = sum(
            item['precio'] for item in costos_platillos
            if any(
                norm in unaccent_simple(item['platillo'].lower()) or
                unaccent_simple(item['platillo'].lower()) in norm
                for norm in todos_platillos_norm
            )
        )
        monto_extras = 0

    # Desechables
    desechable = [v for k, v in tool_input.items() if 'desechables' in k]
    tot_platillos = sum(1 for k in tool_input if k != 'nombre_completo') if 'Sí' in desechable else 0
    monto_desechables = tot_platillos * 5

    montos = {
        'monto_estandar': monto_estandar,
        'monto_extras': monto_extras,
        'monto_desechables': monto_desechables,
        'monto_total': monto_estandar + monto_extras + monto_desechables
    }
    return(montos)