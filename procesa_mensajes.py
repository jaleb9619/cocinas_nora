# python3 procesa_mensajes.py

from agente import responder_usuario
from chat_history import (
    add_to_chat_history,
    get_chat_history, 
    reset_chat_history,
    delete_orden_temporal,
    delete_estado_entrega,
    delete_atencion_clientes
)
from clients.redis_client import redis_client as r
from datetime import datetime
from dotenv import load_dotenv
from utils import extract_phone_from_wa_sender

import certifi
import json
import os
import requests
import ssl
import time

load_dotenv()

wasender_api_key = os.getenv("WASENDER_API_KEY")

def enviar_mensaje(telefono, texto, api_key=wasender_api_key, max_retries=3):
    url = "https://wasenderapi.com/api/send-message"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "to": telefono,
        "text": texto
    }

    for intento in range(max_retries):
        try:
            print(f"📤 Enviando mensaje (intento {intento + 1}/{max_retries}): {texto[:20]}...")
            response = requests.post(url, headers=headers, json=data, timeout=30)
            print(f"STATUS CODE: {response.status_code}")

            # Manejo de rate limit (429)
            if response.status_code == 429:
                try:
                    retry_data = response.json()
                    wait_time = retry_data.get('retry_after', 60)
                except:
                    wait_time = 60

                print(f"⏳ Rate limit. Esperando {wait_time} segundos...")
                time.sleep(wait_time + 2)
                continue  # Reintentar en el siguiente loop

            # Manejo de errores del servidor (520, 502, 503, 504)
            if response.status_code in [520, 502, 503, 504]:
                wait_time = 5 * (intento + 1)  # Backoff exponencial: 5s, 10s, 15s
                print(f"⚠️ Error del servidor ({response.status_code}). Reintentando en {wait_time}s...")
                time.sleep(wait_time)
                continue  # Reintentar en el siguiente loop

            # Si llegamos aquí y el status es exitoso
            if 200 <= response.status_code < 300:
                print(f"✅ Mensaje enviado exitosamente")
                return {"success": True, "response": response.json()}

            # Otros errores HTTP
            response.raise_for_status()
            return {"success": True, "response": response.json()}

        except requests.exceptions.Timeout:
            print(f"⏱️ Timeout en intento {intento + 1}/{max_retries}")
            if intento < max_retries - 1:
                time.sleep(3 * (intento + 1))  # Esperar antes de reintentar
                continue

            else:
                print(f"❌ ERROR FINAL: Timeout después de {max_retries} intentos")
                return {"success": False, "error": "Timeout después de múltiples intentos"}

        except requests.exceptions.RequestException as e:
            print(f"❌ ERROR EN INTENTO {intento + 1}/{max_retries}: {str(e)}")
            if intento < max_retries - 1:
                time.sleep(3 * (intento + 1))
                continue

            else:
                print(f"❌ ERROR FINAL después de {max_retries} intentos: {str(e)}")
                return {"success": False, "error": str(e)}

    # Si salimos del loop sin éxito
    return {"success": False, "error": "Falló después de todos los reintentos"}

def procesar_mensajes_entrantes(json_data, redis_client=r):
    # print("JSON DATA", json_data)

    eventos_validos = ['messages.received', 'chats.update', 'messages-personal.received']

    if json_data.get('event') not in eventos_validos:
        print(f"Evento ignorado: {json_data.get('event')}")
        return 'NoCommand'

    # Inicializar message_type por defecto
    message_type = 'text'

    if json_data.get('event') == 'chats.update':
        if 'data' not in json_data or 'chats' not in json_data['data']:
            return 'NoCommand'

        chats_data = json_data['data']['chats']
        if 'messages' not in chats_data or not chats_data['messages']:
            return 'NoCommand'

        # El mensaje está dentro de un array y luego en 'message'
        message_wrapper = chats_data['messages'][0]
        messages_data = message_wrapper['message']

        # FIX CRÍTICO: Verificar fromMe ANTES de procesar
        is_from_me = messages_data.get('key', {}).get('fromMe', False)
        if is_from_me:
            print(f"⚠️ Mensaje propio detectado en chats.update - IGNORADO")
            return 'NoCommand'

        # Para chats.update, necesitamos extraer más datos manualmente
        data = {
            'id': messages_data.get('key', {}).get('id', ''),
            'from': messages_data.get('key', {}).get('remoteJid', ''),
            'to': json_data.get('sessionId', ''),
            'body': '',
            'fromMe': is_from_me,
            'type': 'chat',
            'pushName': messages_data.get('pushName', ''),
            'timestamp': messages_data.get('messageTimestamp', 0),
            'media': ''
        }

        # Detecta el tipo de mensaje
        if 'message' in messages_data:
            message_content = messages_data['message']
            if 'conversation' in message_content:
                data['type'] = 'chat'
                message_type = 'text'
                data['body'] = message_content['conversation']

            elif 'audioMessage' in message_content:
                data['type'] = 'audio'
                message_type = 'audio'
                data['media'] = message_content['audioMessage'].get('url', '')

            elif 'pttMessage' in message_content:
                data['type'] = 'ptt'
                message_type = 'audio'
                data['media'] = message_content['pttMessage'].get('url', '')

            elif 'imageMessage' in message_content:
                data['type'] = 'image'
                message_type = 'image'
                data['media'] = message_content['imageMessage'].get('url', '')

    else:
        
        if ('data' not in json_data or 'messages' not in json_data['data']) and data['type'] != 'image':
            return 'NoCommand'

        messages_data = json_data['data']['messages']

        # Adapta la estructura de WASender a la estructura que usa tu función
        data = {
            'id': messages_data.get('id', ''),
            'from': messages_data.get('remoteJid', ''),
            'to': json_data.get('sessionId', ''),
            'body': messages_data.get('messageBody', ''),
            'fromMe': messages_data.get('key', {}).get('fromMe', False),
            'type': 'chat',
            'pushName': messages_data.get('pushName', ''),
            'timestamp': messages_data.get('messageTimestamp', 0),
            'media': ''
        }

        # Detecta el tipo de mensaje
        if 'message' in messages_data:
            message_content = messages_data['message']
            if 'conversation' in message_content:
                data['type'] = 'chat'
                message_type = 'text'
                data['body'] = message_content['conversation']
            elif 'audioMessage' in message_content or 'pttMessage' in message_content:
                message_type = 'audio'
                data['type'] = 'ptt' if 'pttMessage' in message_content else 'audio'
                audio_msg = message_content.get('pttMessage') or message_content.get('audioMessage')
                data['media'] = audio_msg.get('url', '') if audio_msg else ''
            elif 'imageMessage' in message_content:
                message_type = 'image'
                data['type'] = 'image'
                data['media'] = message_content['imageMessage'].get('url', '')

    # print("DATA procesada:", data)

    # Verifica que tengamos los datos mínimos necesarios
    if not data['from']:
        print("Mensaje sin remitente")
        return 'NoCommand'

    if not data['body'] and data['type'] not in ['audio', 'ptt', 'image']:
        print("Mensaje de texto sin contenido")
        return 'NoCommand'

    # Extraer teléfono
    phone_number = extract_phone_from_wa_sender(data['from'])
    print(f"📱 PHONE NUMBER: {phone_number}")

    # Verificar si el agente está silenciado para este teléfono
    flag_agente = redis_client.get(f"agente_activo:{phone_number}")
    if flag_agente and flag_agente.decode() == "false":
        print(f"🔇 Agente silenciado para {phone_number} — pedido en proceso")
        return 'AgenteSilenciado'

    # Filtros de grupo y mensajes propios ANTES de deduplicación
    is_group_from = data['from'].find('@g.us') != -1
    is_group_to = data['to'].find('@g.us') != -1 if isinstance(data['to'], str) else False

    if is_group_from or is_group_to:
        print("⚠️ Mensaje de grupo detectado - IGNORADO")
        return 'NoCommand'

    if data['fromMe'] is True:
        print("⚠️ Mensaje propio detectado - IGNORADO")
        return 'NoCommand'

    # DEDUPLICACIÓN POR TELÉFONO + TIMESTAMP
    dedup_key = f"msg:{phone_number}:{data['timestamp']}"

    if redis_client.exists(dedup_key):
        print(f"⚠️ Mensaje duplicado detectado: {dedup_key}")
        return 'NoCommand'

    # ⚠️ NO marcar como procesado aquí
    print(f"🔍 Procesando mensaje nuevo: {dedup_key}")

    # 🗑️ COMANDO: BORRAR MEMORIA
    if 'borrar memoria' in data['body'].lower():
        print(f"🗑️ Ejecutando borrado de memoria para: {phone_number}")
        # 1. Borrar chat history
        reset_chat_history(f"521{phone_number}")

        # 2. Borrar orden temporal (esto es lo que faltaba)
        delete_orden_temporal(phone_number)
        delete_estado_entrega(phone_number)
        delete_atencion_clientes(phone_number)
        print(f"✅ Orden temporal, estado entrega y atención clientes eliminados para: {phone_number}")
        
        resultado = enviar_mensaje(
            data["from"],
            "✅ Tu memoria ha sido borrada completamente."
        )
        
        if resultado.get('success', False):
            redis_client.set(dedup_key, 'exists', ex=600)
            print(f"✅ Borrar memoria procesado: {dedup_key}")
        
        return resultado
        # reset_chat_history(f"521{phone_number}")
        # resultado = enviar_mensaje(
        #     data["from"],
        #     "✅ Tu memoria ha sido borrada."
        # )
        # # Marcar como procesado solo si el envío fue exitoso
        # if resultado.get('success', False):
        #     redis_client.set(dedup_key, 'exists', ex=600)
        #     print(f"✅ Borrar memoria procesado: {dedup_key}")
        # return resultado

    # Variables para el resto del flujo
    id_phone_number = f"fp-idPhone:{phone_number}"
    # id_conversacion = f"fp-idPhone:{phone_number}_{datetime.now().strftime('%Y-%m-%d_%H:%M')}"
    id_conversacion = f"fp-idPhone:{phone_number}_{datetime.now().strftime('%Y-%m-%d_%H')}"

    # ✅ Procesa mensajes de audio encolándolos para procesamiento asíncrono
    if data["type"] == "ptt" or data["type"] == "audio":

        audio_dedup_key = f"audio_queued:{phone_number}:{data['timestamp']}"

        if redis_client.exists(audio_dedup_key):
            print(f"⚠️ Audio ya fue encolado anteriormente: {audio_dedup_key}")
            return 'NoCommand'

        redis_client.set(audio_dedup_key, 'queued', ex=300)

        # Obtener user_data
        if not redis_client.exists(id_phone_number):
            user_data = {
                'Usuario': '',
                'Telefono': phone_number
            }
            redis_client.set(id_phone_number, json.dumps(user_data), ex=600)
        else:
            user_data = json.loads(redis_client.get(id_phone_number))

        # Crear job para el worker
        audio_job = {
            'message_data': messages_data,
            'phone_number': phone_number,
            'from': data['from'],
            'id_conversacion': id_conversacion,
            'timestamp': data['timestamp'],
            'user_data': user_data
        }

        # Encolar para procesamiento asíncrono
        redis_client.lpush('audio_queue', json.dumps(audio_job))

        print(f"✅ Audio encolado para procesamiento: {phone_number}")
        return 'AudioQueued'

    # ✅ Procesa mensajes de IMAGEN síncronamente (3-6 segundos)
    if data["type"] == "image":
        from image_processor import (
            extraer_datos_imagen_wasender,
            procesar_imagen_con_anthropic,
            log_image_processing_info
        )
        
        print(f"🖼️ Procesando imagen de: {phone_number}")
        
        # Extraer información de la imagen
        image_info = extraer_datos_imagen_wasender(json_data)
        
        if not image_info or not image_info.get('url'):
            print("❌ No se pudo extraer la URL de la imagen")
            return 'NoCommand'
        
        # Log de información
        log_image_processing_info(image_info)
        
        # Obtener o crear user_data
        if not redis_client.exists(id_phone_number):
            user_data = {
                'Usuario': '',
                'Telefono': phone_number
            }
            redis_client.set(id_phone_number, json.dumps(user_data), ex=600)
        else:
            user_data = json.loads(redis_client.get(id_phone_number))
        
        # ID para el historial de chat
        id_chat_history = f'fp-chatHistory:{data["from"]}'
        
        # Obtener historial
        messages = get_chat_history(id_chat_history, telefono=phone_number)
        
        # Procesar imagen con Anthropic (SÍNCRONO - 3-6 segundos)
        # answer_data = procesar_imagen_con_anthropic(
        #     image_url=image_info['url'],
        #     user_message=image_info.get('caption', ''),
        #     chat_history=messages,
        #     telefono=phone_number,
        #     user_data=user_data,
        #     id_conversacion=id_conversacion,
        #     mediaKey=image_info.get('mediaKey', '') 
        # )
        answer_data = procesar_imagen_con_anthropic(
            image_url=image_info['url'],
            user_message=image_info.get('caption', ''),
            chat_history=messages,
            telefono=phone_number,
            user_data=user_data,
            id_conversacion=id_conversacion,
            mediaKey=image_info.get('mediaKey', ''),
            mimetype=image_info.get('mimetype', 'image/jpeg')#,
            # message_id=data['message_id']
        )
        
        # Preparar mensaje del usuario para el historial
        user_message_text = image_info.get('caption', '[Imagen enviada]')
        
        # Guardar en Supabase (conversación usuario)
        dict_conversation_user_supabase = {
            "session_id": str(id_chat_history),
            "phone_number": phone_number,
            "message": user_message_text,
            "role": "user",
            "type": "image"
        }
        try:
            print("DICT CONVERSATION USER SUPABASE (IMAGE)", dict_conversation_user_supabase)
        except:
            print("ERROR AL IMPRIMIR DICT CONVERSATION USER SUPABASE (IMAGE)")
        
        # Guardar en Supabase (conversación asistente)
        dict_conversation_assistant_supabase = {
            "session_id": str(id_chat_history),
            "phone_number": phone_number,
            "message": str(answer_data['answer']),
            "role": "assistant",
            "type": "text"
        }
        try:
            print("DICT CONVERSATION ASSISTANT SUPABASE", dict_conversation_assistant_supabase)
        except:
            print("ERROR AL IMPRIMIR DICT CONVERSATION ASSISTANT SUPABASE")
        
        # Enviar respuesta al usuario
        resultado_envio = enviar_mensaje(
            data["from"],
            str(answer_data['answer'])
        )
        
        # Solo completar si el envío fue exitoso
        if not resultado_envio.get('success', False):
            print(f"⚠️ ADVERTENCIA: Mensaje no enviado. Error: {resultado_envio.get('error', 'Desconocido')}")
            return 'ErrorEnvio'
        
        # ✅ Marcar como procesado y guardar en historial
        redis_client.set(dedup_key, 'exists', ex=600)
        print(f"✅ Imagen procesada y marcada: {dedup_key}")
        
        # add_to_chat_history(id_chat_history, user_message_text, "user", phone_number)
        # add_to_chat_history(id_chat_history, answer_data['answer'], "assistant", phone_number)
        add_to_chat_history(id_chat_history, user_message_text, "user", phone_number, message_type="text")
        add_to_chat_history(id_chat_history, answer_data['answer'], "assistant", phone_number, message_type="text")
        
        print('✅ Procesamiento de imagen completado exitosamente.')
        return 'ImageProcessed'
    
    # Verifica si el número existe en caché
    if not redis_client.exists(id_phone_number):
        user_data = {
            'Usuario': '',
            'Telefono': phone_number
        }
        data["user_data"] = user_data
        redis_client.set(id_phone_number, json.dumps(user_data), ex=600)

    else:
        print(id_phone_number)
        data["user_data"] = json.loads(redis_client.get(id_phone_number))
        print(data["user_data"])

    # ID para el historial de chat
    id_chat_history = f'fp-chatHistory:{data["from"]}'

    dict_conversation_user_supabase = {
        "session_id": str(id_chat_history),
        "phone_number": phone_number,
        "message": data['body'],
        "role": "user",
        "type": message_type
    }
    try: 
        print("DICT CONVERSATION SUPABASE", dict_conversation_user_supabase)

    except:
        print("ERROR AL IMPRIMIR DICT CONVERSATION USER SUPABASE")

    messages = get_chat_history(id_chat_history, telefono=phone_number)

    is_new_user = len(messages) == 0
    print(f"{'🆕 NUEVO USUARIO' if is_new_user else '👤 Usuario con historial'}: {phone_number}")

    answer_data = responder_usuario(messages, data, telefono=phone_number, is_new_user=is_new_user, id_conversacion=id_conversacion)
    # print("--------------------------")
    # print('ANSWER DATA', answer_data)
    # print("--------------------------")

    dict_conversation_assistant_supabase = {
        "session_id": str(id_chat_history),
        "phone_number": phone_number,
        "message": str(answer_data['answer']),
        "role": "assistant",
        "type": "text"
    }
    try: 
        print("DICT CONVERSATION ASSISTANT SUPABASE", dict_conversation_assistant_supabase)

    except:
        print("ERROR AL IMPRIMIR DICT CONVERSATION ASSISTANT SUPABASE")

    # Envía respuesta al usuario
    resultado_envio = enviar_mensaje(
        data["from"],
        str(answer_data['answer'])
    )

    # CRÍTICO: Solo completar si el envío fue exitoso
    if not resultado_envio.get('success', False):
        print(f"⚠️ ADVERTENCIA: Mensaje no enviado. Error: {resultado_envio.get('error', 'Desconocido')}")
        # NO agregamos al historial si falló el envío
        # NO marcamos como completado
        return 'ErrorEnvio'

    # ✅ Solo si el envío fue exitoso, marcar como procesado
    redis_client.set(dedup_key, 'exists', ex=600)
    print(f"✅ Mensaje marcado como procesado: {dedup_key}")

    # add_to_chat_history(id_chat_history, data['body'], "user", phone_number)
    # add_to_chat_history(id_chat_history, answer_data['answer'], "assistant", phone_number)
    add_to_chat_history(id_chat_history, data['body'], "user", phone_number, message_type="text")
    add_to_chat_history(id_chat_history, answer_data['answer'], "assistant", phone_number, message_type="text")

    print('✅ Procesamiento completado exitosamente.')