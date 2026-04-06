# python3 chat_history.py

import json
import os
import tiktoken

from clients.redis_client import redis_client
from dotenv import load_dotenv
from fct_supabase import insert_data

load_dotenv()

TIEMPO_NUEVO = os.getenv("TIEMPO_NUEVO") if os.getenv("TIEMPO_NUEVO") else 60 * 8

def guardar_mensaje_en_supabase(session_id, phone_number, message, role, type="text"):
    try:
        # Obtener user_id del .env
        user_id = os.getenv('USER_ID')

        if not user_id:
            print("⚠️ USER_ID no configurado en .env - No se guardará en Supabase")
            return False

        mensaje_data = {
            'user_id': user_id,  # 👈 AGREGADO
            'session_id': session_id,
            'phone_number': phone_number,
            'message': message,
            'role': role,
            'type': type
        }

        insert_data(mensaje_data, 'conversations')
        print(f"✅ Mensaje guardado en Supabase: {role} - {type} - user: {user_id}")
        return True

    except Exception as e:
        print(f"❌ Error al guardar mensaje en Supabase: {e}")
        return False

def get_chat_history(chat_historiy_id, telefono=None, redis_client=redis_client):

    # Obtiene los mensajes almacenados en Redis
    stored_messages_json = redis_client.get(chat_historiy_id)
    if stored_messages_json:
        return json.loads(stored_messages_json)
    return []

def num_tokens(text, model="gpt-4o"):
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

def add_to_chat_history_orig(chat_historiy_id, mensaje, rol, telefono, redis_client=redis_client):

    redis_messages = get_chat_history(chat_historiy_id, telefono)

    token_budget = 30000
    current_count = 0

    for message in redis_messages:
        current_count += num_tokens(message["content"])

    # Elimina mensajes antiguos si se excede el presupuesto de tokens
    while current_count + num_tokens(mensaje) > token_budget:
        if len(redis_messages) == 0:
            return False
        current_count -= num_tokens(redis_messages.pop(0)["content"])

    redis_messages.append({"content": mensaje, "role": rol})

    # Almacena en Redis con tiempo de expiración
    redis_client.setex(
        chat_historiy_id, TIEMPO_NUEVO, json.dumps(redis_messages)
    )

    return redis_messages

def add_to_chat_history(chat_historiy_id, mensaje, rol, telefono, message_type="text", redis_client=redis_client):

    redis_messages = get_chat_history(chat_historiy_id, telefono)

    token_budget = 30000
    current_count = 0

    for message in redis_messages:
        current_count += num_tokens(message["content"])

    # Elimina mensajes antiguos si se excede el presupuesto de tokens
    while current_count + num_tokens(mensaje) > token_budget:
        if len(redis_messages) == 0:
            return False
        current_count -= num_tokens(redis_messages.pop(0)["content"])

    redis_messages.append({"content": mensaje, "role": rol})

    # Almacena en Redis con tiempo de expiración
    redis_client.setex(
        chat_historiy_id, TIEMPO_NUEVO, json.dumps(redis_messages)
    )

    guardar_mensaje_en_supabase(
        session_id=chat_historiy_id,
        phone_number=telefono,
        message=mensaje,
        role=rol,
        type=message_type
    )

    return redis_messages

def reset_chat_history(chat_history_id, redis_client=redis_client):
    """
    Elimina el historial de chat de Redis (versión mejorada)
    """
    if not chat_history_id.startswith('fp-chatHistory:'):
        chat_history_id = f'fp-chatHistory:{chat_history_id}'

    existe = redis_client.exists(chat_history_id)

    if not existe:
        print(f"⚠️  La key '{chat_history_id}' NO existe en Redis")

        telefono = chat_history_id.replace('fp-chatHistory:', '')
        pattern = f'fp-chatHistory:*{telefono}*'
        keys_similares = redis_client.keys(pattern)

        if keys_similares:
            print(f"💡 Keys similares encontradas:")
            for key in keys_similares:
                print(f"   - {key}")

            if keys_similares:
                ans = redis_client.delete(keys_similares[0])
                print(f"✅ Historial '{keys_similares[0]}' eliminado")
                return ans

        return 0

    ans = redis_client.delete(chat_history_id)

    if ans > 0:
        print(f"✅ Historial '{chat_history_id}' reiniciado exitosamente")
    else:
        print(f"❌ Error al eliminar '{chat_history_id}'")

    return ans

def listar_chat_histories(redis_client=redis_client):
    """
    Lista todos los chat histories almacenados en Redis
    """
    # Buscar todas las keys que empiezan con 'fp-chatHistory:'
    pattern = 'fp-chatHistory:*'
    keys = redis_client.keys(pattern)
    
    print(f"\n{'='*60}")
    print(f"📊 TOTAL DE CHAT HISTORIES: {len(keys)}")
    print(f"{'='*60}\n")
    
    if not keys:
        print("❌ No hay chat histories almacenados en Redis")
        return []
    
    for key in keys:
        # Obtener el contenido
        content = redis_client.get(key)
        
        # Extraer el número de teléfono
        telefono = key.replace('fp-chatHistory:', '')
        
        # Contar mensajes (si es JSON list)
        try:
            mensajes = json.loads(content) if content else []
            num_mensajes = len(mensajes)
        except:
            num_mensajes = "N/A"
        
        print(f"📱 {telefono}")
        print(f"   Key completa: {key}")
        print(f"   Mensajes: {num_mensajes}")
        print(f"   TTL: {redis_client.ttl(key)} segundos")
        print("-" * 60)
    
    return keys

def get_orden_temporal(telefono, redis_client=redis_client):
    """
    Obtiene la orden temporal del usuario desde Redis
    
    Args:
        telefono: número de teléfono del usuario
        redis_client: cliente de Redis
    
    Returns:
        dict o None: estructura de la orden temporal o None si no existe
    """
    key = f"orden_temporal:{telefono}"
    orden_json = redis_client.get(key)

    if orden_json:
        return json.loads(orden_json)

    return None

def save_orden_temporal(telefono, orden_data, redis_client=redis_client, ttl=1800):
    """
    Guarda o actualiza la orden temporal en Redis
    
    Args:
        telefono: número de teléfono del usuario
        orden_data: diccionario con la estructura de la orden temporal
        redis_client: cliente de Redis
        ttl: tiempo de expiración en segundos (default: 1800 = 30 minutos)
    
    Returns:
        bool: True si se guardó exitosamente
    """
    key = f"orden_temporal:{telefono}"

    try:
        redis_client.setex(
            key,
            ttl,
            json.dumps(orden_data)
        )
        return True

    except Exception as e:
        print(f"Error al guardar orden temporal: {e}")
        return False

def delete_orden_temporal(telefono, redis_client=redis_client):
    """
    Elimina la orden temporal de Redis (cuando se confirma o cancela)

    Args:
        telefono: número de teléfono del usuario
        redis_client: cliente de Redis

    Returns:
        int: número de keys eliminadas (1 si exitoso, 0 si no existía)
    """
    key = f"orden_temporal:{telefono}"
    return redis_client.delete(key)

def get_estado_entrega(telefono, redis_client=redis_client):
    """
    Obtiene el estado de espera de entrega desde Redis.
    Se activa después de que el pedido fue persistido en BD
    pero aún falta confirmar tipo de entrega y dirección.

    Args:
        telefono: número de teléfono del usuario
        redis_client: cliente de Redis

    Returns:
        dict o None: estructura del estado o None si no existe
    """
    key = f"estado_entrega:{telefono}"
    estado_json = redis_client.get(key)

    if estado_json:
        return json.loads(estado_json)

    return None

def save_estado_entrega(telefono, estado_data, redis_client=redis_client, ttl=1800):
    """
    Guarda el estado de espera de entrega en Redis.
    Contiene los comandas_ids ya creados en BD para poder
    actualizarlos cuando llegue la dirección.

    Args:
        telefono: número de teléfono del usuario
        estado_data: dict con comandas_ids, pedido_grupo, nombre_cliente
        redis_client: cliente de Redis
        ttl: tiempo de expiración en segundos (default: 1800 = 30 minutos)

    Returns:
        bool: True si se guardó exitosamente
    """
    key = f"estado_entrega:{telefono}"

    try:
        redis_client.setex(
            key,
            ttl,
            json.dumps(estado_data)
        )
        print(f"✅ Estado de entrega guardado para {telefono}")
        return True

    except Exception as e:
        print(f"❌ Error al guardar estado de entrega: {e}")
        return False

def delete_estado_entrega(telefono, redis_client=redis_client):
    """
    Elimina el estado de entrega de Redis (cuando se confirma la entrega).

    Args:
        telefono: número de teléfono del usuario
        redis_client: cliente de Redis

    Returns:
        int: número de keys eliminadas (1 si exitoso, 0 si no existía)
    """
    key = f"estado_entrega:{telefono}"
    result = redis_client.delete(key)
    print(f"🗑️ Estado de entrega eliminado para {telefono}")
    return result

def get_atencion_clientes(telefono, redis_client=redis_client):
    """
    Obtiene si el usuario fue canalizado antes como atención al cliente desde Redis
    
    Args:
        telefono: número de teléfono del usuario
        redis_client: cliente de Redis
    
    Returns:
        dict o None: estructura de la orden temporal o None si no existe
    """
    key = f"atencion_clientes:{telefono}"
    orden_json = redis_client.get(key)

    if orden_json:
        return json.loads(orden_json)

    return None

def save_atencion_clientes(telefono, atencion_clientes_data, redis_client=redis_client, ttl=1800):
    """
    Guarda o actualiza si el usuario es atención a clientes o no en Redis
    
    Args:
        telefono: número de teléfono del usuario
        atencion_clientes_data: diccionario con la estructura de la atención a clientes
        redis_client: cliente de Redis
        ttl: tiempo de expiración en segundos (default: 1800 = 30 minutos)
    
    Returns:
        bool: True si se guardó exitosamente
    """
    key = f"atencion_clientes:{telefono}"

    try:
        redis_client.setex(
            key,
            ttl,
            json.dumps(atencion_clientes_data)
        )
        return True

    except Exception as e:
        print(f"Error al guardar atención a clientes: {e}")
        return False

def delete_atencion_clientes(telefono, redis_client=redis_client):
    """
    Elimina la atención a clientes de Redis (cuando se confirma o cancela)

    Args:
        telefono: número de teléfono del usuario
        redis_client: cliente de Redis

    Returns:
        int: número de keys eliminadas (1 si exitoso, 0 si no existía)
    """
    key = f"atencion_clientes:{telefono}"
    return redis_client.delete(key)


if __name__ == "__main__":
    
    # reset_chat_history("5215566098295")
    listar_chat_histories()