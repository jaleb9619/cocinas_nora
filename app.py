# python3 app.py

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fct_supabase import read_data
from procesa_mensajes import procesar_mensajes_entrantes
import os
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Nueva funcion agregada para leer conversaciones desde Supabase, filtrando por user_id y phone_number
def leer_conversaciones_supabase(phone_number: str, limit: int = 100):
    try:
        user_id = os.getenv('USER_ID')

        if not user_id:
            print("⚠️ USER_ID no configurado en .env")
            return []

        # Leer de Supabase con DOBLE filtro: user_id Y phone_number
        response = read_data(
            table='conversations',
            filters={
                'user_id': user_id,  # 👈 FILTRO POR COCINA
                'phone_number': phone_number
            },
            order_by='created_at',
            ascending=True,
            limit=limit
        )

        return response if response else []

    except Exception as e:
        print(f"❌ Error al leer conversaciones: {e}")
        return []

# NUEVO Endpoint para obtener conversaciones de un cliente específico, filtrando solo por USER_ID
@app.get('/api/v1/conversations/{phone_number}')
def obtener_conversacion(phone_number: str, limit: int = 100):
    mensajes = leer_conversaciones_supabase(phone_number, limit)
    
    return {
        "phone_number": phone_number,
        "total_messages": len(mensajes),
        "messages": mensajes
    }

# NUEVO Endpoint para listar clientes que han conversado, SOLO de la cocina actual
@app.get('/api/v1/conversations')
def listar_clientes_con_conversaciones():
    try:
        user_id = os.getenv('USER_ID')
        
        if not user_id:
            return {"error": "USER_ID no configurado"}, 500
        
        from clients.supabase_client import supabase_client
        
        # Query filtrando por user_id
        response = supabase_client.table('conversations') \
            .select('phone_number, message, created_at, role') \
            .eq('user_id', user_id) \
            .order('created_at', desc=True) \
            .execute()
        
        # Agrupar por phone_number y tomar el último mensaje
        clientes = {}
        for msg in response.data:
            phone = msg['phone_number']
            if phone not in clientes:
                clientes[phone] = {
                    'phone_number': phone,
                    'last_message': msg['message'],
                    'last_message_time': msg['created_at'],
                    'last_role': msg['role']
                }
        
        return {
            "total_clients": len(clientes),
            "clients": list(clientes.values())
        }
        
    except Exception as e:
        print(f"❌ Error al listar clientes: {e}")
        return {"error": str(e)}, 500

@app.api_route('/', methods=['GET', 'HEAD'])
def index():
    '''Route de bienvenida'''
    return 'La API de Cocinas App funciona correctamente.'

@app.get('/health')
def health_check():
    return {"status": "ok"}

@app.api_route('/api/v1/webhook', methods=['GET', 'POST'])
async def webhook(request: Request):
    if request.method == "GET":
        params = dict(request.query_params)
        procesar_mensajes_entrantes(params)
        return JSONResponse(content={"status": "ok-get"}, status_code=200)

    elif request.method == "POST":
        json_data = await request.json()
        procesar_mensajes_entrantes(json_data)
        return JSONResponse(content={'status': 'ok-post'}, status_code=200)

# @app.post('/api/v1/notify/status')
# async def notify_status_change(request: Request):
#     """
#     Recibe webhook de Supabase cuando cambia el status de una comanda.
#     Envía WhatsApp al cliente según el nuevo status.
#     """
#     try:
#         from procesa_mensajes import enviar_mensaje

#         payload = await request.json()
#         print(f"🔔 Webhook recibido: {payload}")

#         record = payload.get('record', {})
#         status = record.get('status')
#         cliente_nombre = record.get('cliente_nombre')
#         telefono_cliente = record.get('telefono_cliente')
#         monto_total = record.get('monto_total') or 0

#         # Solo disparar para estos dos estados
#         if status not in ['EN_PROCESO', 'ENVIADO']:
#             print(f"⏭️ Status '{status}' ignorado")
#             return JSONResponse(content={"status": "ignored"}, status_code=200)

#         if not telefono_cliente:
#             print(f"⚠️ No hay teléfono para notificar - comanda: {record.get('id')}")
#             return JSONResponse(content={"status": "no_phone"}, status_code=200)

#         # Construir mensaje según status
#         if status == 'EN_PROCESO':
#             mensaje = f"¡Hola {cliente_nombre}! Tu pedido ya está siendo preparado. 🍳"
#         elif status == 'ENVIADO':
#             mensaje = f"¡Hola {cliente_nombre}! Tu pedido ya va en camino. 🛵"

#         # Formatear teléfono para WASender (necesita formato 521XXXXXXXXXX@s.whatsapp.net)
#         telefono_formateado = f"521{telefono_cliente}@s.whatsapp.net"

#         resultado = enviar_mensaje(telefono_formateado, mensaje)

#         if resultado.get('success'):
#             print(f"✅ Notificación enviada a {telefono_cliente} - status: {status}")
#             return JSONResponse(content={"status": "ok"}, status_code=200)
#         else:
#             print(f"❌ Error enviando notificación: {resultado.get('error')}")
#             return JSONResponse(content={"status": "error"}, status_code=500)

#     except Exception as e:
#         print(f"❌ Error en notify_status_change: {e}")
#         return JSONResponse(content={"status": "error", "detail": str(e)}, status_code=500)

@app.post('/api/v1/notify/status')
async def notify_status_change(request: Request):
    try:
        from procesa_mensajes import enviar_mensaje
        from clients.supabase_client import supabase_client as _sc

        payload = await request.json()
        print(f"🔔 Webhook recibido: {payload}")

        record = payload.get('record', {})
        status = record.get('status')
        cliente_nombre = record.get('cliente_nombre')
        telefono_cliente = record.get('telefono_cliente')
        pedido_grupo = record.get('pedido_grupo')
        user_id = record.get('user_id')  # 👈 NUEVO

        if status not in ['EN_PROCESO', 'ENVIADO']:
            print(f"⏭️ Status '{status}' ignorado")
            return JSONResponse(content={"status": "ignored"}, status_code=200)

        if not telefono_cliente:
            print(f"⚠️ No hay teléfono - comanda: {record.get('id')}")
            return JSONResponse(content={"status": "no_phone"}, status_code=200)

        # 👇 NUEVO: lookup de credenciales por user_id
        if not user_id:
            print(f"⚠️ No hay user_id en la comanda: {record.get('id')}")
            return JSONResponse(content={"status": "no_user_id"}, status_code=200)

        config_result = _sc.table('tbl_cocina_config')\
            .select('wasender_api_key, wasender_token')\
            .eq('user_id', user_id)\
            .single()\
            .execute()

        if not config_result.data:
            print(f"❌ No se encontró config para user_id: {user_id}")
            return JSONResponse(content={"status": "no_config"}, status_code=200)

        wasender_api_key = config_result.data['wasender_api_key']
        # wasender_token disponible si lo necesitas: config_result.data['wasender_token']
        
        # NUEVO: verificar que TODAS las comandas no-extra del grupo
        # estén en el mismo status antes de notificar
        if pedido_grupo:
            grupo_result = _sc.table(os.getenv('TLB_COMANDAS'))\
                .select('id, status')\
                .eq('pedido_grupo', pedido_grupo)\
                .eq('es_extra', False)\
                .execute()

            comandas_principales = grupo_result.data or []
            todas_en_status = all(
                c['status'] == status for c in comandas_principales
            )

            if not todas_en_status:
                print(f"⏳ Grupo {pedido_grupo[:8]}... aún no está completo en {status}, esperando")
                return JSONResponse(content={"status": "waiting_group"}, status_code=200)

        if status == 'EN_PROCESO':
            mensaje = f"¡Hola {cliente_nombre}! Tu pedido ya está siendo preparado. 🍳"
        elif status == 'ENVIADO':
            mensaje = f"¡Hola {cliente_nombre}! Tu pedido ya va en camino. 🛵"

        # telefono_formateado = f"521{telefono_cliente}@s.whatsapp.net"
        telefono_formateado = f"52{telefono_cliente}@s.whatsapp.net"
        # resultado = enviar_mensaje(telefono_formateado, mensaje)
        print(f"📞 Teléfono formateado: {telefono_formateado}")
        print(f"🔑 API Key usada: {wasender_api_key[:10]}...")
        print(f"📝 Mensaje: {mensaje}")

        # import requests as _req
        # _test_response = _req.post(
        #     "https://wasenderapi.com/api/send-message",
        #     headers={
        #         "Authorization": f"Bearer {wasender_api_key}",
        #         "Content-Type": "application/json"
        #     },
        #     json={"to": telefono_formateado, "text": mensaje},
        #     timeout=30
        # )
        # print(f"🧪 STATUS: {_test_response.status_code}")
        # print(f"🧪 BODY: {_test_response.text}")

        # # resultado = enviar_mensaje(...)  ← comentar esta línea por ahora
        # return JSONResponse(content={"status": "test"}, status_code=200)

        # import requests as _req
        # _response = _req.post(
        #     "https://wasenderapi.com/api/send-message",
        #     headers={
        #         "Authorization": f"Bearer {wasender_api_key}",
        #         "Content-Type": "application/json"
        #     },
        #     json={"to": telefono_formateado, "text": mensaje},
        #     timeout=30
        # )
        # print(f"📤 STATUS: {_response.status_code}")
        # print(f"📤 BODY: {_response.text}")

        # if _response.status_code == 200:
        #     print(f"✅ Notificación enviada a {telefono_cliente} - status: {status}")
        #     return JSONResponse(content={"status": "ok"}, status_code=200)
        # else:
        #     print(f"❌ Error enviando notificación: {_response.text}")
        #     return JSONResponse(content={"status": "error"}, status_code=500)
        from procesa_mensajes import enviar_mensaje

        telefono_limpio = telefono_cliente.strip().replace(" ", "").replace("-", "").replace("+", "")
        if telefono_limpio.startswith("521"):
            numero_base = telefono_limpio[3:]
        elif telefono_limpio.startswith("52"):
            numero_base = telefono_limpio[2:]
        else:
            numero_base = telefono_limpio

        # Intentar con 521 primero, luego con 52
        enviado = False
        for prefijo in ["521", "52"]:
            telefono_formateado = f"{prefijo}{numero_base}@s.whatsapp.net"
            resultado = enviar_mensaje(telefono_formateado, mensaje, api_key=wasender_api_key)
            if resultado.get("success"):
                print(f"✅ Notificación enviada con prefijo {prefijo}")
                enviado = True
                break
            print(f"⚠️ Falló con prefijo {prefijo}: {resultado}")

        if enviado:
            return JSONResponse(content={"status": "ok"}, status_code=200)
        else:
            print(f"❌ No se pudo enviar con ningún prefijo")
            return JSONResponse(content={"status": "error"}, status_code=500)
        
        # esto es lo que debe de ir ORIGINALMENTE 
        # resultado = enviar_mensaje(telefono_formateado, mensaje, api_key=wasender_api_key)

        # if resultado.get('success'):
        #     print(f"✅ Notificación enviada a {telefono_cliente} - status: {status}")
        #     return JSONResponse(content={"status": "ok"}, status_code=200)
        # else:
        #     print(f"❌ Error enviando notificación: {resultado.get('error')}")
        #     return JSONResponse(content={"status": "error"}, status_code=500)

    except Exception as e:
        print(f"❌ Error en notify_status_change: {e}")
        return JSONResponse(content={"status": "error", "detail": str(e)}, status_code=500)

@app.post('/api/v1/ordenes/manual')
async def crear_orden_manual_endpoint(request: Request):
    """
    Crea una orden manual desde el dashboard (sin WhatsApp).
    Recibe: cliente_nombre, tipo_entrega, direccion,
            comidas, extras, precio_menu, descuento_por_platillo
    """
    try:
        from fct_orden_manual import crear_orden_manual

        body = await request.json()

        cliente_nombre = body.get('cliente_nombre', '').strip()
        tipo_entrega = body.get('tipo_entrega', 'local')
        direccion = body.get('direccion', '')
        comidas = body.get('comidas', [])
        extras = body.get('extras', [])
        precio_menu = float(body.get('precio_menu', 0.0))
        descuento_por_platillo = bool(body.get('descuento_por_platillo', False))

        if not cliente_nombre:
            return JSONResponse(content={"ok": False, "error": "Falta el nombre del cliente"}, status_code=400)

        if not comidas and not extras:
            return JSONResponse(content={"ok": False, "error": "La orden no tiene items"}, status_code=400)

        resultado = crear_orden_manual(
            cliente_nombre=cliente_nombre,
            tipo_entrega=tipo_entrega,
            direccion=direccion,
            comidas=comidas,
            extras=extras,
            precio_menu=precio_menu,
            descuento_por_platillo=descuento_por_platillo,
        )

        if resultado["ok"]:
            return JSONResponse(content=resultado, status_code=200)
        else:
            return JSONResponse(content=resultado, status_code=500)

    except Exception as e:
        print(f"❌ Error en endpoint orden manual: {e}")
        return JSONResponse(content={"ok": False, "error": str(e)}, status_code=500)

@app.put('/api/v1/ordenes/grupo/{pedido_grupo}/editar')
async def editar_grupo_endpoint(pedido_grupo: str, request: Request):
    """
    Edita todas las comandas de un grupo (o solo las que vengan en el payload).
    Recibe: lista de {comanda_id, platillos: [...], precio_menu, descuento_por_platillo}
    """
    try:
        from fct_orden_manual import editar_comanda
        from fct_supabase import read_data

        body = await request.json()
        comandas = body.get("comandas", [])
        precio_menu = float(body.get("precio_menu", 0.0))
        descuento_por_platillo = bool(body.get("descuento_por_platillo", False))

        if not comandas:
            return JSONResponse(content={"ok": False, "error": "No hay comandas para editar"}, status_code=400)

        todos_los_platillos = read_data(
            table_name=os.getenv("TLB_PLATILLOS"),
            variables="id, platillo, precio",
            filters={"activo": "TRUE"},
        )

        resultados = []
        for comanda in comandas:
            resultado = editar_comanda(
                comanda_id=comanda["comanda_id"],
                platillos=comanda.get("platillos", []),
                precio_menu=precio_menu,
                descuento_por_platillo=descuento_por_platillo,
                todos_los_platillos=todos_los_platillos,
            )
            resultados.append(resultado)

        todos_ok = all(r["ok"] for r in resultados)
        return JSONResponse(
            content={"ok": todos_ok, "resultados": resultados},
            status_code=200 if todos_ok else 500
        )

    except Exception as e:
        print(f"❌ Error en editar_grupo_endpoint: {e}")
        return JSONResponse(content={"ok": False, "error": str(e)}, status_code=500)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    # Timeout de 2 segundos para liberar memoria rápido
    uvicorn.run(
        "app:app", 
        host="0.0.0.0", 
        port=port, 
        reload=False,
        timeout_keep_alive=2
    )