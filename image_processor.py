

import base64
import os
import requests

from clients.anthropic_client import anthropic_client
from dotenv import load_dotenv
from typing import Dict, Optional, Tuple

load_dotenv()

wasender_api_key = os.getenv("WASENDER_API_KEY")

def descargar_y_convertir_imagen(image_url: str, timeout: int = 10) -> Optional[Tuple[str, str]]:
    try:
        print(f"📥 Descargando imagen desde: {image_url[:50]}...")
        
        response = requests.get(image_url, timeout=timeout)
        response.raise_for_status()
        
        # CAMBIO: Forzar mime_type válido basado en la URL o header
        mime_type = response.headers.get('Content-Type', 'image/jpeg')
        
        # FIX: Asegurar que sea un mime type válido para Anthropic
        valid_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        if mime_type not in valid_types:
            mime_type = 'image/jpeg'  # Default seguro
        
        image_data = response.content
        base64_data = base64.b64encode(image_data).decode('utf-8')
        
        print(f"✅ Imagen convertida - MIME: {mime_type}")
        
        return base64_data, mime_type
    
    except requests.exceptions.Timeout:
        print(f"⏱️ Timeout descargando imagen: {image_url}")
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error descargando imagen: {e}")
        return None
        
    except Exception as e:
        print(f"❌ Error procesando imagen: {e}")
        return None

# def descargar_y_convertir_imagen(image_url: str, timeout: int = 10) -> Optional[Tuple[str, str]]:
#     """
#     Descarga una imagen de WASender y la convierte a base64
    
#     Args:
#         image_url: URL de la imagen desde WASender
#         timeout: Timeout para la descarga en segundos
        
#     Returns:
#         Tuple[str, str]: (base64_data, mime_type) o None si falla
#     """
#     try:
#         print(f"📥 Descargando imagen desde: {image_url[:50]}...")
        
#         # Descargar la imagen
#         response = requests.get(image_url, timeout=timeout)
#         response.raise_for_status()
        
#         # Obtener el mime type
#         mime_type = response.headers.get('Content-Type', 'image/jpeg')
        
#         # Convertir a base64
#         image_data = response.content
#         base64_data = base64.b64encode(image_data).decode('utf-8')
        
#         print(f"✅ Imagen descargada y convertida a base64 ({len(base64_data)} chars)")
#         print(f"   MIME Type: {mime_type}")
        
#         return base64_data, mime_type
        
#     except requests.exceptions.Timeout:
#         print(f"⏱️ Timeout descargando imagen: {image_url}")
#         return None
        
#     except requests.exceptions.RequestException as e:
#         print(f"❌ Error descargando imagen: {e}")
#         return None
        
#     except Exception as e:
#         print(f"❌ Error procesando imagen: {e}")
#         return None


# def procesar_imagen_con_anthropic(
#     image_url: str,
#     user_message: str = None,
#     chat_history: list = None,
#     telefono: str = None,
#     **kwargs
# ) -> Dict:
#     """
#     Procesa una imagen con Anthropic Vision API
    
#     Args:
#         image_url: URL de la imagen desde WASender
#         user_message: Mensaje/caption del usuario (opcional)
#         chat_history: Historial de conversación
#         telefono: Número de teléfono del usuario
#         **kwargs: Argumentos adicionales (user_data, id_conversacion, etc.)
        
#     Returns:
#         Dict con 'answer' y metadata
#     """
    
#     # Descargar y convertir imagen
#     # resultado = descargar_y_convertir_imagen(image_url)
#     wasender_api_key = os.getenv("WASENDER_API_KEY")
#     image_bytes = descargar_imagen_wasender(
#         {'url': image_url, 'mediaKey': kwargs.get('mediaKey', ''), 'mimetype': mime_type},
#         wasender_api_key
#     )
    
#     if not image_bytes:
#         return {'answer': '❌ No pude descargar la imagen.', 'error': 'download_failed'}
    
#     base64_data = base64.b64encode(image_bytes).decode('utf-8')
#     mime_type = 'image/jpeg'
    
#     # if not resultado:
#     #     return {
#     #         'answer': '❌ Lo siento, no pude procesar la imagen. Por favor intenta enviarla de nuevo.',
#     #         'error': 'image_download_failed'
#     #     }
    
#     # base64_data, mime_type = resultado
    
#     # Preparar el mensaje del usuario
#     if not user_message or user_message.strip() == "":
#         # Si no hay caption, pedimos descripción general
#         user_message = "¿Qué ves en esta imagen?"
    
#     print(f"🖼️ Procesando imagen con Anthropic")
#     print(f"   Mensaje del usuario: {user_message}")
    
#     try:
#         # Construir el contenido del mensaje con la imagen
#         content = [
#             {
#                 "type": "image",
#                 "source": {
#                     "type": "base64",
#                     "media_type": mime_type,
#                     "data": base64_data
#                 }
#             },
#             {
#                 "type": "text",
#                 "text": user_message
#             }
#         ]
        
#         # Preparar mensajes para Anthropic
#         messages = []
        
#         # Agregar historial si existe
#         if chat_history and len(chat_history) > 0:
#             for msg in chat_history[-5:]:  # Últimos 5 mensajes para contexto
#                 if msg['role'] in ['user', 'assistant']:
#                     # messages.append({
#                     #     'role': msg['role'],
#                     #     'content': msg['content']
#                     # })
#                    content = msg.get('content', '').strip()
#                    if content:  # Solo si no está vacío
#                         messages.append({
#                             'role': msg['role'],
#                             'content': content
#                         })
        
#         # Agregar el mensaje actual con la imagen
#         # messages.append({
#         #     'role': 'user',
#         #     'content': content
#         # })
#         messages.append({
#             'role': 'user',
#             'content': [
#                 {
#                     "type": "image",
#                     "source": {
#                         "type": "base64",
#                         "media_type": mime_type,
#                         "data": base64_data
#                     }
#                 },
#                 {
#                     "type": "text",
#                     "text": user_message
#                 }
#             ]
#         })
        
#         # System prompt específico para análisis de imágenes
#         system_prompt = """Eres un asistente experto en análisis de imágenes. 
        
# Tu tarea es describir detalladamente lo que ves en las imágenes que te envían los usuarios.

# Para imágenes de vehículos o accidentes automovilísticos:
# - Identifica marca, modelo y color del vehículo si es posible
# - Describe los daños visibles en detalle
# - Indica la ubicación específica de los daños (frontal, lateral, trasero, etc.)
# - Evalúa la severidad aparente de los daños
# - Menciona cualquier otro detalle relevante

# Sé claro, preciso y profesional en tus descripciones."""
        
#         # Llamar a Anthropic
#         response = anthropic_client.messages.create(
#             model="claude-sonnet-4-20250514",
#             max_tokens=1024,
#             system=system_prompt,
#             messages=messages
#         )
        
#         # Extraer respuesta
#         respuesta_texto = ""
#         for block in response.content:
#             if block.type == "text":
#                 respuesta_texto += block.text
        
#         print(f"✅ Respuesta de Anthropic generada ({len(respuesta_texto)} chars)")
        
#         return {
#             'answer': respuesta_texto,
#             'success': True,
#             'tokens_used': {
#                 'input': response.usage.input_tokens,
#                 'output': response.usage.output_tokens
#             }
#         }
        
#     except Exception as e:
#         print(f"❌ Error llamando a Anthropic Vision API: {e}")
#         return {
#             'answer': '❌ Lo siento, hubo un error al analizar la imagen. Por favor intenta de nuevo.',
#             'error': str(e),
#             'success': False
#         }


def procesar_imagen_con_anthropic(
    image_url: str,
    user_message: str = None,
    chat_history: list = None,
    telefono: str = None,
    wasender_api_key: str = wasender_api_key,
    **kwargs
) -> Dict:
    """Procesa imagen con Anthropic usando la API de descifrado de WASender"""
    
    # Construir el payload exacto según la documentación
    decrypt_payload = {
        "data": {
            "messages": {
                "key": {
                    "id": kwargs.get('message_id', 'temp_id')
                },
                "message": {
                    "imageMessage": {
                        "url": image_url,
                        "mimetype": kwargs.get('mimetype', 'image/jpeg'),
                        "mediaKey": kwargs.get('mediaKey', '')
                    }
                }
            }
        }
    }
    
    try:
        # Llamar a la API de descifrado de WASender
        print("🔐 Descifrando imagen con WASender API...")
        response = requests.post(
            "https://www.wasenderapi.com/api/decrypt-media",
            headers={
                "Authorization": f"Bearer {wasender_api_key}",
                "Content-Type": "application/json"
            },
            json=decrypt_payload,
            timeout=15
        )
        response.raise_for_status()
        
        result = response.json()
        if not result.get('success') or not result.get('publicUrl'):
            return {'answer': '❌ Error al descifrar la imagen.', 'error': 'decrypt_failed'}
        
        public_url = result['publicUrl']
        print(f"✅ Imagen descifrada, URL pública: {public_url[:50]}...")
        
        # Descargar la imagen descifrada
        img_response = requests.get(public_url, timeout=10)
        img_response.raise_for_status()
        
        # Convertir a base64
        base64_data = base64.b64encode(img_response.content).decode('utf-8')
        mime_type = 'image/jpeg'
        
        print(f"✅ Imagen descargada y convertida a base64")
        
    except Exception as e:
        print(f"❌ Error en descifrado/descarga: {e}")
        return {'answer': '❌ No pude procesar la imagen.', 'error': str(e)}
    
    # Preparar mensaje
    if not user_message or user_message.strip() == "":
        user_message = "¿Qué ves en esta imagen?"
    
    print(f"🖼️ Procesando con Anthropic - Mensaje: {user_message}")
    
    try:
        # Preparar mensajes
        messages = []
        
        # Agregar historial (solo texto)
        if chat_history and len(chat_history) > 0:
            for msg in chat_history[-10:]:
                if msg['role'] in ['user', 'assistant']:
                    content = msg.get('content', '').strip()
                    if content:
                        messages.append({'role': msg['role'], 'content': content})
        
        # Agregar mensaje con imagen
        messages.append({
            'role': 'user',
            'content': [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": base64_data
                    }
                },
                {"type": "text", "text": user_message}
            ]
        })
        
        # Llamar a Anthropic
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system="""Eres un asistente experto en análisis de imágenes de vehículos.
Para imágenes de vehículos o accidentes:
- Identifica marca, modelo y color
- Describe daños en detalle
- Indica ubicación de daños
- Evalúa severidad
Sé claro y profesional.""",
            messages=messages
        )
        
        respuesta_texto = "".join([block.text for block in response.content if block.type == "text"])
        
        print(f"✅ Respuesta generada ({len(respuesta_texto)} chars)")
        
        return {
            'answer': respuesta_texto,
            'success': True,
            'tokens_used': {
                'input': response.usage.input_tokens,
                'output': response.usage.output_tokens
            }
        }
        
    except Exception as e:
        print(f"❌ Error en Anthropic: {e}")
        return {'answer': '❌ Error al analizar la imagen.', 'error': str(e)}


def extraer_datos_imagen_wasender(json_data: Dict) -> Optional[Dict]:
    """
    Extrae los datos de imagen del webhook de WASender
    
    Args:
        json_data: Payload del webhook
        
    Returns:
        Dict con datos de la imagen o None
    """
    try:
        messages_data = json_data.get('data', {}).get('messages', {})
        message_content = messages_data.get('message', {})
        
        # Verificar si es una imagen
        if 'imageMessage' not in message_content:
            return None
        
        image_data = message_content['imageMessage']
        
        # return {
        #     'url': image_data.get('url', ''),
        #     'mimetype': image_data.get('mimetype', 'image/jpeg'),
        #     'caption': image_data.get('caption', ''),  # El mensaje/caption del usuario
        #     'width': image_data.get('width', 0),
        #     'height': image_data.get('height', 0),
        #     'file_length': image_data.get('fileLength', '0')
        # }

        return {
            'url': image_data.get('url', ''),
            'mimetype': image_data.get('mimetype', 'image/jpeg'),
            'caption': image_data.get('caption', ''),
            'mediaKey': image_data.get('mediaKey', ''),  # ← AGREGAR
            'width': image_data.get('width', 0),
            'height': image_data.get('height', 0),
            'file_length': image_data.get('fileLength', '0')
        }
        

    except Exception as e:
        print(f"❌ Error extrayendo datos de imagen: {e}")
        return None


# Función de utilidad para logging
def log_image_processing_info(image_info: Dict):
    """Helper para loggear información de la imagen"""
    if image_info:
        print("📸 Información de imagen:")
        print(f"   URL: {image_info.get('url', '')[:50]}...")
        print(f"   MIME Type: {image_info.get('mimetype', 'unknown')}")
        print(f"   Dimensiones: {image_info.get('width')}x{image_info.get('height')}")
        print(f"   Tamaño: {image_info.get('file_length')} bytes")
        if image_info.get('caption'):
            print(f"   Caption: {image_info.get('caption')}")


def descargar_imagen_wasender(image_data: dict, wasender_api_key: str) -> Optional[bytes]:
    """
    Descarga y descifra imagen de WASender usando su API
    """
    try:
        # Usar la API de WASender para descifrar
        url = "https://wasenderapi.com/api/decrypt-media"
        headers = {
            "Authorization": f"Bearer {wasender_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "url": image_data.get('url'),
            "mediaKey": image_data.get('mediaKey'),
            "mimetype": image_data.get('mimetype', 'image/jpeg')
        }
        
        print(f"🔐 Descifrando imagen con WASender API...")
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        
        return response.content
        
    except Exception as e:
        print(f"❌ Error descifrando imagen: {e}")
        return None

