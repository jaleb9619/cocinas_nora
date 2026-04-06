# python3 whisper.py

import json
import librosa
import math
import os
import requests
import tempfile
import time
import traceback

from clients.openai_client import openai_client as client
from decorador_costos import decorador_costo

wasender_api_key = os.getenv("WASENDER_API_KEY")

# @decorador_costo
def audio_a_texto(message_data, id_phone_number, api_key=wasender_api_key, client=client):
    try:
        print("🎙️ Procesando mensaje de audio")

        start_time = time.time()
        audio_message = message_data.get('message', {}).get('audioMessage', {})
        print("Audio message data:", audio_message)

        if not audio_message:
            print("No se encontró audioMessage")
            return {
                'answer': 'No se encontró el audio en el mensaje.',
                'input_tokens': 0,
                'id_conversacion': id_phone_number,
                'model_name': 'whisper-1'
            }

        decrypt_url = "https://www.wasenderapi.com/api/decrypt-media"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # Payload simplificado según la documentación
        payload = {
            "data": {
                "messages": {
                    "key": {
                        "id": message_data.get('key', {}).get('id')
                    },
                    "message": {
                        "audioMessage": {
                            "url": audio_message.get('url'),
                            "mimetype": audio_message.get('mimetype'),
                            "mediaKey": audio_message.get('mediaKey')
                        }
                    }
                }
            }
        }

        print("📡 Enviando request a decrypt-media...")

        # Timeout razonable pero no excesivo
        decrypt_response = requests.post(
            url=decrypt_url, 
            headers=headers, 
            data=json.dumps(payload), 
            timeout=120  # 2 minutos
        )

        print(f"✅ Status code: {decrypt_response.status_code}")
        
        decrypt_response.raise_for_status()

        decrypted_data = decrypt_response.json()
        end_time = time.time()
        print(f"⏱️ TIEMPO DE DESENCRIPTACION: {end_time - start_time:.2f} segundos")
        
        audio_url = decrypted_data.get('publicUrl')
        
        print(f"🔗 Audio URL desencriptada: {audio_url}")

        if not audio_url:
            print("No se obtuvo URL del audio desencriptado")
            return {
                'answer': 'No se pudo obtener el audio desencriptado.',
                'input_tokens': 0,
                'id_conversacion': id_phone_number,
                'model_name': 'whisper-1'
            }

        print("📥 Descargando audio...")
        response = requests.get(audio_url, timeout=120)  # 2 minutos

        suffix = '.ogg' if 'ogg' in audio_message.get('mimetype', '') else '.mp3'

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
            tmp_file.write(response.content)
            tmp_file_path = tmp_file.name

        print(f"💾 Audio guardado en: {tmp_file_path}")

        try:
            duracion_segundos = math.ceil(librosa.get_duration(filename=tmp_file_path))
        except:
            duracion_segundos = 0

        print("🤖 Transcribiendo con Whisper...")
        with open(tmp_file_path, 'rb') as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                timeout=180  # 3 minutos
            )

        os.unlink(tmp_file_path)
        
        print(f"✅ Transcripción exitosa: {transcript.text}")

        return {
            'answer': transcript.text,
            'input_tokens': duracion_segundos,
            'id_conversacion': id_phone_number,
            'model_name': 'whisper-1'
        }

    except Exception as e:
        print(f"❌ Error en audio_a_texto: {e}")
        traceback.print_exc()
        return {
            'answer': 'Lo siento, no pude procesar tu audio.',
            'input_tokens': 0,
            'id_conversacion': id_phone_number,
            'model_name': 'whisper-1'
        }