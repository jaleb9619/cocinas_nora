# python3 worker_audio.py

from agente import responder_usuario
from clients.redis_client import redis_client as r
from chat_history import add_to_chat_history, get_chat_history
from procesa_mensajes import enviar_mensaje
from whisper import audio_a_texto

import json
import time
import traceback

def procesar_audio_job(job_data, r=r):
    """Procesa un audio de la cola"""
    try:
        message_data = job_data['message_data']
        phone_number = job_data['phone_number']  # Ya viene extraído
        from_jid = job_data['from']
        id_conversacion = job_data['id_conversacion']
        user_data = job_data['user_data']
        timestamp = job_data.get('timestamp', int(time.time()))

        id_phone_number = f"fp-idPhone:{phone_number}"

        # DEDUPLICACIÓN: Verificar si este audio ya fue procesado
        dedup_key = f"audio_processed:{phone_number}:{timestamp}"

        if r.exists(dedup_key):
            print(f"⚠️ [WORKER] Audio duplicado ignorado: {phone_number}:{timestamp}")
            return

        # Marcar como procesado por 10 minutos
        r.set(dedup_key, 'processed', ex=600)
        print(f"🎙️ [WORKER] Procesando audio de {phone_number}...")

        # Transcribir audio (sin timeout de servidor web)
        start_time = time.time()
        audio_result = audio_a_texto(message_data, id_phone_number)
        end_time = time.time()

        print(f"⏱️ Transcripción completada en {end_time - start_time:.2f} segundos")

        texto = audio_result['answer']

        if not texto or texto == 'Lo siento, no pude procesar tu audio.':
            enviar_mensaje(from_jid, "❌ Lo siento, no pude reconocer tu audio.")
            return

        print(f"📝 Texto transcrito: {texto}")

        # 💾 Guardar transcripción en Supabase
        id_chat_history = f'fp-chatHistory:{from_jid}'

        # Preparar data para responder_usuario
        data = {
            'body': texto,
            'from': from_jid,
            'user_data': user_data
        }

        # Obtener respuesta del agente
        messages = get_chat_history(id_chat_history, telefono=phone_number)

        print(f"🤖 Obteniendo respuesta del agente...")
        answer_data = responder_usuario(
            messages, 
            data, 
            telefono=phone_number,
            id_phone_number=id_phone_number,
            id_conversacion=id_conversacion
        )

        # Enviar respuesta
        resultado = enviar_mensaje(from_jid, str(answer_data['answer']))

        # Solo agregar al historial si el envío fue exitoso
        if resultado.get('success', False):
            add_to_chat_history(id_chat_history, texto, "user", phone_number)
            add_to_chat_history(id_chat_history, answer_data['answer'], "assistant", phone_number)
            print(f"✅ [WORKER] Audio procesado y enviado exitosamente para {phone_number}")

        else:
            print(f"⚠️ [WORKER] Audio procesado pero envío falló: {resultado.get('error')}")
        
    except Exception as e:
        print(f"❌ [WORKER] Error procesando audio: {e}")
        traceback.print_exc()
        
        # Intentar notificar al usuario del error
        try:
            enviar_mensaje(from_jid, "❌ Hubo un error procesando tu audio. Por favor intenta de nuevo.")
        except:
            pass

def run_worker(r=r):
    """Worker infinito que procesa la cola de audios"""
    print("🚀 [WORKER] Worker de audios iniciado...")
    print("📡 [WORKER] Conectado a Redis")
    
    while True:
        try:
            # Bloquea hasta que haya un job (BRPOP con timeout de 1 segundo)
            result = r.brpop('audio_queue', timeout=1)
            
            if result:
                _, job_json = result
                job_data = json.loads(job_json)
                print(f"📥 [WORKER] Job recibido de la cola")
                procesar_audio_job(job_data)
            
        except KeyboardInterrupt:
            print("\n👋 [WORKER] Worker detenido por usuario")
            break
        except Exception as e:
            print(f"❌ [WORKER] Error en worker: {e}")
            traceback.print_exc()
            time.sleep(5)  # Espera antes de reintentar

if __name__ == "__main__":
    run_worker()