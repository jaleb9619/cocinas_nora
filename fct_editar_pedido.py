# python3 fct_editar_pedido.py

import os
from clients.supabase_client import supabase_client
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

TBL_COMANDAS = os.getenv('TLB_COMANDAS')
TBL_DESGLOSE = os.getenv('TLB_DESGLOSE')
TBL_PLATILLOS = os.getenv('TLB_PLATILLOS')
TBL_CLIENTES = os.getenv('TLB_CLIENTES')


# def obtener_pedido_reciente_usuario(telefono, supabase_client=supabase_client, table_comandas=TBL_COMANDAS):
#     """
#     Obtiene el pedido más reciente de un usuario por su teléfono.
    
#     Args:
#         telefono: Número de teléfono del usuario
#         supabase_client: Cliente de Supabase
#         table_comandas: Nombre de la tabla de comandas
    
#     Returns:
#         dict con 'pedido_grupo', 'comandas' (lista), 'cliente_nombre'
#         o None si no se encuentra
#     """
#     try:
#         # Buscar en tabla de clientes para obtener user_id
#         response_cliente = (
#             supabase_client
#             .table(TBL_CLIENTES)
#             .select("id")
#             .eq("telefono", telefono)
#             .execute()
#         )
        
#         if not response_cliente.data:
#             print(f"⚠️ No se encontró cliente con teléfono: {telefono}")
#             return None
        
#         user_id = response_cliente.data[0]['id']
        
#         # Buscar comandas del usuario ordenadas por fecha (más reciente primero)
#         response = (
#             supabase_client
#             .table(table_comandas)
#             .select("*")
#             .eq("user_id", user_id)
#             .order("created_at", desc=True)
#             .limit(1)
#             .execute()
#         )
        
#         if not response.data:
#             print(f"⚠️ No se encontraron pedidos para el teléfono: {telefono}")
#             return None
        
#         # Obtener el pedido_grupo de la comanda más reciente
#         pedido_grupo = response.data[0]['pedido_grupo']
#         cliente_nombre = response.data[0]['cliente_nombre']
        
#         # Obtener TODAS las comandas de ese pedido_grupo
#         response_comandas = (
#             supabase_client
#             .table(table_comandas)
#             .select("*")
#             .eq("pedido_grupo", pedido_grupo)
#             .order("created_at", desc=False)
#             .execute()
#         )
        
#         return {
#             'pedido_grupo': pedido_grupo,
#             'comandas': response_comandas.data,
#             'cliente_nombre': cliente_nombre
#         }
        
#     except Exception as error:
#         print(f"❌ Error al obtener pedido reciente: {error}")
#         return None


def obtener_pedido_reciente_usuario(telefono, supabase_client=supabase_client, table_comandas=TBL_COMANDAS):
    try:
        # Buscar directamente por telefono_cliente en comandas
        # response = (
        #     supabase_client
        #     .table(table_comandas)
        #     .select("*")
        #     .eq("telefono_cliente", telefono)
        #     .eq("status", "PENDIENTE")
        #     .order("created_at", desc=True)
        #     .limit(1)
        #     .execute()
        # )
        hoy = datetime.now(timezone.utc).date()
        manana = hoy + timedelta(days=1)

        response = (
            supabase_client
            .table(table_comandas)
            .select("*")
            .eq("telefono_cliente", telefono)
            .eq("status", "PENDIENTE")
            .gte("created_at", f"{hoy.isoformat()}T00:00:00")
            .lt("created_at", f"{manana.isoformat()}T00:00:00")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        
        if not response.data:
            print(f"⚠️ No se encontraron pedidos para el teléfono: {telefono}")
            return None
        
        pedido_grupo = response.data[0]['pedido_grupo']
        cliente_nombre = response.data[0]['cliente_nombre']
        
        # Obtener TODAS las comandas de ese pedido_grupo
        response_comandas = (
            supabase_client
            .table(table_comandas)
            .select("*")
            .eq("pedido_grupo", pedido_grupo)
            .order("created_at", desc=False)
            .execute()
        )
        
        return {
            'pedido_grupo': pedido_grupo,
            'comandas': response_comandas.data,
            'cliente_nombre': cliente_nombre
        }
        
    except Exception as error:
        print(f"❌ Error al obtener pedido reciente: {error}")
        return None

def validar_pedido_editable(pedido_grupo, supabase_client=supabase_client, table_comandas=TBL_COMANDAS):
    """
    Valida si un pedido puede ser editado (todas las comandas deben estar en PENDIENTE).
    
    Args:
        pedido_grupo: UUID del grupo de pedido
        supabase_client: Cliente de Supabase
        table_comandas: Nombre de la tabla de comandas
    
    Returns:
        dict con 'editable' (bool), 'mensaje' (str), 'estados' (list)
    """
    try:
        response = (
            supabase_client
            .table(table_comandas)
            .select("id, status")
            .eq("pedido_grupo", pedido_grupo)
            .execute()
        )
        
        if not response.data:
            return {
                'editable': False,
                'mensaje': 'No se encontraron comandas para este pedido.',
                'estados': []
            }
        
        estados = [comanda['status'] for comanda in response.data]
        
        # Verificar que TODAS estén en PENDIENTE o MODIFICANDO
        if all(estado in ('PENDIENTE', 'MODIFICANDO') for estado in estados):
            return {
                'editable': True,
                'mensaje': 'El pedido puede ser editado.',
                'estados': estados
            }
        
        # Si alguna está en otro estado
        estados_no_pendientes = [e for e in estados if e != 'PENDIENTE']
        
        if 'EN_PROCESO' in estados_no_pendientes or 'LISTO_COCINA' in estados_no_pendientes:
            return {
                'editable': False,
                'mensaje': 'Lo siento, tu pedido ya está siendo preparado y no puede modificarse.',
                'estados': estados
            }
        
        if 'TERMINADO' in estados_no_pendientes or 'ENTREGADO' in estados_no_pendientes:
            return {
                'editable': False,
                'mensaje': 'Lo siento, tu pedido ya fue completado y no puede modificarse.',
                'estados': estados
            }
        
        if 'CANCELADO' in estados_no_pendientes:
            return {
                'editable': False,
                'mensaje': 'Este pedido ya fue cancelado.',
                'estados': estados
            }
        
        return {
            'editable': False,
            'mensaje': 'El pedido no puede ser editado en su estado actual.',
            'estados': estados
        }
        
    except Exception as error:
        print(f"❌ Error al validar pedido: {error}")
        return {
            'editable': False,
            'mensaje': f'Error al validar el pedido: {error}',
            'estados': []
        }

def obtener_comandas_con_platillos(pedido_grupo, supabase_client=supabase_client):
    """
    Obtiene todas las comandas de un pedido con sus platillos.
    
    Args:
        pedido_grupo: UUID del grupo de pedido
        supabase_client: Cliente de Supabase
    
    Returns:
        list de dict con estructura de cada comanda y sus platillos
    """
    try:
        # Obtener comandas
        response_comandas = (
            supabase_client
            .table(TBL_COMANDAS)
            .select("*")
            .eq("pedido_grupo", pedido_grupo)
            .order("created_at", desc=False)
            .execute()
        )
        
        if not response_comandas.data:
            return []
        
        comandas_con_platillos = []
        
        for idx, comanda in enumerate(response_comandas.data, 1):
            # Obtener platillos de esta comanda desde desglose
            # response_desglose = (
            #     supabase_client
            #     .table(TBL_DESGLOSE)
            #     .select(f"platillo_id, {TBL_PLATILLOS}(platillo, tiempo_id)")
            #     .eq("comanda_id", comanda['id'])
            #     .execute()
            # )
            
            # platillos = []
            # if response_desglose.data:
            #     platillos = [
            #         {
            #             'platillo_id': item['platillo_id'],
            #             'platillo': item[TBL_PLATILLOS]['platillo'],
            #             'tiempo_id': item[TBL_PLATILLOS]['tiempo_id']
            #         }
            #         for item in response_desglose.data
            #     ]
            
            response_desglose = (
                supabase_client
                .table(TBL_DESGLOSE)
                .select(f"platillo_id, {TBL_PLATILLOS}(platillo, tiempo_id, tbl_cocina_tiempos(nombre, orden))")
                .eq("comanda_id", comanda['id'])
                .execute()
            )

            platillos = []
            if response_desglose.data:
                for item in response_desglose.data:
                    platillo_data = item[TBL_PLATILLOS]
                    tiempo_data = platillo_data.get('tbl_cocina_tiempos', {})
                    # Convertir nombre del tiempo a snake_case igual que utils.py
                    tiempo_nombre = tiempo_data.get('nombre', '')
                    campo = tiempo_nombre.lower().replace(" ", "_") if tiempo_nombre else ''
                    platillos.append({
                        'platillo_id': item['platillo_id'],
                        'platillo': platillo_data['platillo'],
                        'tiempo_id': platillo_data['tiempo_id'],
                        'campo': campo,  # ← nuevo: ej. "primer_tiempo", "postre"
                    })

            comandas_con_platillos.append({
                'numero': idx,
                'comanda_id': comanda['id'],
                'platillos': platillos,
                'monto_total': comanda['monto_total'],
                'status': comanda['status']
            })
        
        return comandas_con_platillos
        
    except Exception as error:
        print(f"❌ Error al obtener comandas con platillos: {error}")
        return []

def eliminar_comanda(comanda_id, supabase_client=supabase_client):
    """
    Elimina una comanda y sus platillos asociados.

    Args:
        comanda_id: UUID de la comanda a eliminar
        supabase_client: Cliente de Supabase

    Returns:
        dict con 'success' (bool) y 'mensaje' (str)
    """
    try:
        # Primero eliminar desglose
        response_desglose = (
            supabase_client
            .table(TBL_DESGLOSE)
            .delete()
            .eq("comanda_id", comanda_id)
            .execute()
        )

        # Luego eliminar comanda
        response_comanda = (
            supabase_client
            .table(TBL_COMANDAS)
            .delete()
            .eq("id", comanda_id)
            .execute()
        )

        return {
            'success': True,
            'mensaje': f'Comanda {comanda_id} eliminada exitosamente.'
        }

    except Exception as error:
        print(f"❌ Error al eliminar comanda: {error}")
        return {
            'success': False,
            'mensaje': f'Error al eliminar comanda: {error}'
        }

def actualizar_platillos_comanda(comanda_id, nuevos_platillos_ids, nuevos_costos, supabase_client=supabase_client):
    """
    Actualiza los platillos y costos de una comanda.

    Args:
        comanda_id: UUID de la comanda
        nuevos_platillos_ids: Lista de IDs de platillos nuevos
        nuevos_costos: Dict con monto_estandar, monto_extras, monto_desechables, monto_total
        supabase_client: Cliente de Supabase

    Returns:
        dict con 'success' (bool) y 'mensaje' (str)
    """
    try:
        # 1. Eliminar platillos viejos del desglose
        response_delete = (
            supabase_client
            .table(TBL_DESGLOSE)
            .delete()
            .eq("comanda_id", comanda_id)
            .execute()
        )

        # 2. Insertar nuevos platillos
        if nuevos_platillos_ids:
            nuevos_registros = [
                {
                    'comanda_id': comanda_id,
                    'platillo_id': platillo_id
                }
                for platillo_id in nuevos_platillos_ids
            ]

            response_insert = (
                supabase_client
                .table(TBL_DESGLOSE)
                .insert(nuevos_registros)
                .execute()
            )

        # 3. Actualizar costos en la comanda
        response_update = (
            supabase_client
            .table(TBL_COMANDAS)
            .update({
                'monto_estandar': nuevos_costos.get('monto_estandar', 0),
                'monto_extras': nuevos_costos.get('monto_extras', 0),
                'monto_desechables': nuevos_costos.get('monto_desechables', 0),
                'monto_total': nuevos_costos.get('monto_total', 0)
            })
            .eq("id", comanda_id)
            .execute()
        )

        return {
            'success': True,
            'mensaje': f'Comanda {comanda_id} actualizada exitosamente.'
        }

    except Exception as error:
        print(f"❌ Error al actualizar platillos: {error}")
        return {
            'success': False,
            'mensaje': f'Error al actualizar platillos: {error}'
        }

def congelar_pedido(pedido_grupo, supabase_client=supabase_client):
    """
    Cambia todas las comandas del grupo a MODIFICANDO para bloquear
    cambios de status mientras Lucía procesa la edición.
    """
    try:
        supabase_client.table(TBL_COMANDAS)\
            .update({"status": "MODIFICANDO"})\
            .eq("pedido_grupo", pedido_grupo)\
            .in_("status", ["PENDIENTE"])\
            .execute()
        print(f"🔒 Pedido {pedido_grupo[:8]}... congelado")
        return True
    except Exception as e:
        print(f"❌ Error congelando pedido: {e}")
        return False

def descongelar_pedido(pedido_grupo, supabase_client=supabase_client):
    """
    Regresa todas las comandas del grupo de MODIFICANDO a PENDIENTE.
    Se llama al terminar la edición (exitosa o con error).
    """
    try:
        supabase_client.table(TBL_COMANDAS)\
            .update({"status": "PENDIENTE"})\
            .eq("pedido_grupo", pedido_grupo)\
            .in_("status", ["MODIFICANDO"])\
            .execute()
        print(f"🔓 Pedido {pedido_grupo[:8]}... descongelado")
        return True
    except Exception as e:
        print(f"❌ Error descongelando pedido: {e}")
        return False