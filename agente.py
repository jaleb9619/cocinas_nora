
import os
import uuid

from atencion_clientes import responder_pregunta
from chat_history import (
    delete_orden_temporal,
    get_orden_temporal,
    save_orden_temporal,
    save_estado_entrega,
    get_estado_entrega,
    delete_estado_entrega,
    save_atencion_clientes, 
    get_atencion_clientes,
    delete_atencion_clientes ### TIENE QUE IR EN PROCESAR MENSAJES EN BORRAR MEMORIA 
)
from clients.anthropic_client import anthropic_client
from clients.supabase_client import supabase_client as _sc
from collections import Counter
from decorador_costos import decorador_costo
from dotenv import load_dotenv
from fct_config import obtener_config_cocina
from fct_editar_pedido import (
    obtener_pedido_reciente_usuario,
    validar_pedido_editable,
    obtener_comandas_con_platillos,
    eliminar_comanda,
    actualizar_platillos_comanda,
    congelar_pedido,
    descongelar_pedido
)
from fct_supabase import insert_data, update_data
from fct_tools_infomenu import consultar_menu_del_dia, formatear_menu
from fct_tools_ordenar import (
    extraer_ids_platillos,
    determinar_costo_comanda,
    unaccent_simple
)
# from system_prompts import prompt_first_response, prompt_saludo
from system_prompts import generar_prompt_first_response, generar_prompt_saludo, prompt_cat_atencion_clientes, prompt_atencion_clientes
from tools import tools
from utils import (
    obtener_campos_platillos_validos, 
    construir_platillos_dict
)

load_dotenv()

# Anthropic
ANTHROPIC_MODEL_NAME = os.getenv('MODEL_NAME')

# Supabase
TLB_COMANDAS=os.getenv('TLB_COMANDAS')
TLB_DESGLOSE=os.getenv('TLB_DESGLOSE')

user_id=os.getenv('USER_ID')

# @decorador_costo
def responder_usuario(
    messages, 
    data, 
    telefono,
    id_conversacion,
    model_name=ANTHROPIC_MODEL_NAME,
    user_id=user_id,
    is_new_user=False,
    anthropic_client=anthropic_client,
    tools=tools
):

    config = obtener_config_cocina(user_id)

    # ✅ NUEVO: Obtener campos válidos para esta cocina
    campos_platillos_validos = obtener_campos_platillos_validos(user_id)
    print(f"📋 Campos de platillos configurados: {campos_platillos_validos}")

    system_prompt = generar_prompt_first_response(config)
    prompt_saludo_dinamico = generar_prompt_saludo(config)

    input_tokens = 0
    output_tokens = 0

    new_messages = messages + [
        {"role": "user",
         "content": data["body"]}
    ]

    atencion_clientes_flag = get_atencion_clientes(telefono)

    if atencion_clientes_flag is None:
        cat_atencion_clientes = anthropic_client.messages.create(
            system=prompt_cat_atencion_clientes,
            model=model_name,
            messages=new_messages,
            max_tokens=500
        )
        es_atencion_clientes = 'yes' in cat_atencion_clientes.content[0].text.lower()

        if es_atencion_clientes:    
            save_atencion_clientes(telefono, new_messages)
    else:
        es_atencion_clientes = True

    if es_atencion_clientes:
        output = responder_pregunta(
            pregunta=data["body"],
            new_messages=new_messages
        )
        return output

    if is_new_user:
        anthropic_client_response = anthropic_client.messages.create(
            system=prompt_saludo_dinamico,
            model=model_name,
            messages=new_messages,
            max_tokens=4096
        )

        output={
            "answer": anthropic_client_response.content[0].text,
            "output": anthropic_client_response.content,
            "input_tokens": anthropic_client_response.usage.input_tokens,
            "output_tokens": anthropic_client_response.usage.output_tokens,
            'model_name':model_name
        }

        return output

    # Primera llamada a Anthropic
    anthropic_client_response = anthropic_client.messages.create(
        system=system_prompt,
        model=model_name,
        messages=new_messages,
        max_tokens=4096,
        tools=tools,
        tool_choice={"type": "any"}
    )
    print("🔵 ANTHROPIC FIRST RESPONSE", anthropic_client_response)

    input_tokens += anthropic_client_response.usage.input_tokens
    output_tokens += anthropic_client_response.usage.output_tokens
    
    # Contador para evitar duplicados en confirmación
    j = 0

    # ============================================================================
    # WHILE LOOP PRINCIPAL - Procesa tool calls
    # ============================================================================
    while anthropic_client_response.stop_reason == 'tool_use':
        print("\n" + "="*80)
        print("🔄 ENTRANDO AL WHILE LOOP - stop_reason:", anthropic_client_response.stop_reason)
        print("="*80)
        
        # Extraer tool_use_blocks DENTRO del while
        tool_use_blocks = [block for block in anthropic_client_response.content if block.type == "tool_use"]
        
        print(f"📊 Total de tool_use_blocks encontrados: {len(tool_use_blocks)}")
        for idx, block in enumerate(tool_use_blocks):
            print(f"  [{idx}] Tool: {block.name} | ID: {block.id}")
        
        if len(tool_use_blocks) == 0:
            print("⚠️ No hay tool_use_blocks, saliendo del while")
            break
        
        # Agregar mensaje del assistant con los tool_use UNA SOLA VEZ
        print("➕ Agregando mensaje assistant con tool_use a new_messages")
        new_messages.append({
            "role": "assistant",
            "content": anthropic_client_response.content
        })
        
        # Procesar cada tool_use
        for tool_use in tool_use_blocks:
            print(f"\n🔧 Procesando tool: {tool_use.name} (ID: {tool_use.id})")
            
            try:
                tool_name = tool_use.name
                tool_input = tool_use.input
            except:
                print('❌ Error: no se determinó el uso del tool')
                continue

            # ========================================================================
            # TOOL: informacion_menu
            # ========================================================================
            if 'informacion_menu' in tool_name.lower():
                print("📋 Ejecutando: informacion_menu")
                menu = consultar_menu_del_dia()
                content = formatear_menu(menu)
                tool_response = {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": content
                        }
                    ]
                }
                new_messages.append(tool_response)
                print(f"✅ tool_result agregado para {tool_use.id}")

            # ========================================================================
            # TOOL: ordenar
            # ========================================================================
            elif 'ordenar' in tool_name.lower():
                print("🍽️ Ejecutando: ordenar")

                if get_estado_entrega(telefono):
                    print("🔒 BLOQUEADO: Ya existe estado_entrega en Redis - pedido ya confirmado")
                    content = {
                        "status": "pedido_ya_confirmado",
                        "mensaje": "El pedido ya fue guardado. NO crear nueva comanda. Continúa recopilando datos de entrega del cliente.",
                        "instruccion": "USA confirmar_entrega cuando tengas dirección y referencias completas."
                    }
                    tool_response = {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use.id,
                                "content": str(content)
                            }
                        ]
                    }
                    new_messages.append(tool_response)
                    print(f"✅ tool_result agregado para {tool_use.id} (bloqueado globalmente)")
                    continue

                # NUEVO: Validación para rechazar nombres placeholder
                if 'nombre_completo' in tool_input:
                    nombre = str(tool_input['nombre_completo']).strip().upper()
                    placeholders_invalidos = ['PENDIENTE', '<UNKNOWN>', 'UNKNOWN', 'N/A', 'NA', 'SIN NOMBRE']
                    
                    if nombre in placeholders_invalidos:
                        print(f"⚠️ RECHAZADO - nombre_completo es placeholder: {nombre}")
                        
                        content = {
                            "status": "error",
                            "mensaje": "No se puede confirmar la orden con un nombre placeholder. Solicita el nombre real del cliente."
                        }
                        
                        tool_response = {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_use.id,
                                    "content": str(content)
                                }
                            ]
                        }
                        new_messages.append(tool_response)
                        print(f"✅ tool_result agregado para {tool_use.id} (placeholder rechazado)")
                        continue

                tiene_nombre = (
                    'nombre_completo' in tool_input and
                    str(tool_input['nombre_completo']).strip() not in ['', '<UNKNOWN>']
                )

                # ✅ CAMBIO: Usar campos_platillos_validos dinámicamente
                tiene_platillos = any(
                    str(tool_input.get(campo, '')).strip() not in ['', '<UNKNOWN>']
                    for campo in campos_platillos_validos
                )

                # CASO 1: SIN NOMBRE - (orden temporal)
                if not tiene_nombre and tiene_platillos:
                    print("📝 Guardando orden temporal en Redis...")

                    # Leer orden temporal actual (si existe)
                    orden_temporal = get_orden_temporal(telefono)
                    
                    # Si no existe, crear estructura inicial
                    # if not orden_temporal:
                    #     orden_temporal = {
                    #         "pedido_grupo": str(uuid.uuid4()),
                    #         "ordenes": [],
                    #         "total_ordenes": 0,
                    #         "monto_total_general": 0,
                    #         "nombre_cliente": None
                    #     }

                    # # Calcular costos de orden
                    # costo_orden = determinar_costo_comanda(tool_input)
                    # Si no existe, crear estructura inicial
                    if not orden_temporal:
                        orden_temporal = {
                            "pedido_grupo": str(uuid.uuid4()),
                            "ordenes": [],
                            "total_ordenes": 0,
                            "monto_total_general": 0,
                            "nombre_cliente": None
                        }

                    # ✅ FIX: Verificar duplicado ANTES de agregar
                    nueva_comida_platillos_check = construir_platillos_dict(tool_input, campos_platillos_validos)
                    print(f"🔍 CHECK nueva_comida: {nueva_comida_platillos_check}")

                    # es_duplicado = False
                    # for orden_existente in orden_temporal.get("ordenes", []):
                    #     print(f"🔍 CHECK existente: {orden_existente['platillos']}")
                    #     if orden_existente["platillos"] == nueva_comida_platillos_check:
                    #         es_duplicado = True
                    #         print(f"⚠️ Orden temporal duplicada - NO agregando")
                    #         break

                    # es_duplicado = False
                    # for orden_existente in orden_temporal.get("ordenes", []):
                    #     existente_normalizado = {
                    #         k: [p.lower() for p in v] if isinstance(v, list) else v.lower() if v else v
                    #         for k, v in orden_existente["platillos"].items()
                    #     }
                    #     nueva_normalizada = {
                    #         k: [p.lower() for p in v] if isinstance(v, list) else v.lower() if v else v
                    #         for k, v in nueva_comida_platillos_check.items()
                    #     }
                    #     if existente_normalizado == nueva_normalizada:
                    #         es_duplicado = True
                    #         break
                    es_duplicado = False
                    for orden_existente in orden_temporal["ordenes"]:
                        existente_vals = set()
                        for v in orden_existente["platillos"].values():
                            if isinstance(v, list):
                                existente_vals.update(unaccent_simple(p.lower()) for p in v if p)
                            elif v:
                                existente_vals.add(unaccent_simple(v.lower()))

                        nueva_vals = set()
                        for v in nueva_comida_platillos_check.values():
                            if isinstance(v, list):
                                nueva_vals.update(unaccent_simple(p.lower()) for p in v if p)
                            elif v:
                                nueva_vals.add(unaccent_simple(v.lower()))

                        # Comparación parcial en ambas direcciones
                        if nueva_vals and existente_vals:
                            match = all(
                                any(nv in ev or ev in nv for ev in existente_vals)
                                for nv in nueva_vals
                            ) and all(
                                any(ev in nv or nv in ev for nv in nueva_vals)
                                for ev in existente_vals
                            )
                            if match:
                                es_duplicado = True
                                break

                    if es_duplicado:
                        resumen_todas_ordenes = []
                        for orden in orden_temporal["ordenes"]:
                            platillos_orden = []
                            for tiempo_key, platillos_tiempo in orden["platillos"].items():
                                if platillos_tiempo and platillos_tiempo not in ['', '<UNKNOWN>', []]:
                                    if isinstance(platillos_tiempo, list):
                                        platillos_orden.extend(platillos_tiempo)
                                    else:
                                        platillos_orden.append(platillos_tiempo)
                            resumen_todas_ordenes.append({
                                "numero": orden["orden_numero"],
                                "platillos": platillos_orden,
                                "costo": orden["costos"].get("monto_total", 0),
                                "texto": f"Comida {orden['orden_numero']}: {', '.join(platillos_orden)} (${orden['costos'].get('monto_total', 0)})"
                            })

                        content = {
                            "status": "orden_ya_existe",
                            "mensaje": "Esta orden ya fue registrada. No se agregó duplicado.",
                            "total_ordenes": orden_temporal["total_ordenes"],
                            "monto_total_acumulado": orden_temporal["monto_total_general"],
                            "todas_las_ordenes": resumen_todas_ordenes
                        }
                        tool_response = {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_use.id,
                                    "content": str(content)
                                }
                            ]
                        }
                        new_messages.append(tool_response)
                        print(f"✅ tool_result agregado para {tool_use.id} (duplicado bloqueado)")
                        continue

                    # Calcular costos de orden
                    # costo_orden = determinar_costo_comanda(tool_input, config=config)
                    costo_orden = determinar_costo_comanda(tool_input, config=config, campos_platillos=campos_platillos_validos)

                    # ✅ CAMBIO: Usar construir_platillos_dict
                    nueva_orden = {
                        "orden_numero": len(orden_temporal["ordenes"]) + 1,
                        "platillos": construir_platillos_dict(tool_input, campos_platillos_validos),
                        "desechables": tool_input.get('desechables', False),
                        "costos": costo_orden
                    }

                    orden_temporal["ordenes"].append(nueva_orden)
                    orden_temporal["total_ordenes"] = len(orden_temporal["ordenes"])
                    orden_temporal["monto_total_general"] += costo_orden.get('monto_total', 0)

                    # Construir resumen de esta orden para la IA
                    platillos_lista = []
                    for tiempo_key, platillos_tiempo in nueva_orden["platillos"].items():
                        if platillos_tiempo and platillos_tiempo not in ['', '<UNKNOWN>', []]:
                            if isinstance(platillos_tiempo, list):
                                platillos_lista.extend(platillos_tiempo)
                            else:
                                platillos_lista.append(platillos_tiempo)
                    
                    resumen_esta_orden = f"Orden {nueva_orden['orden_numero']}: {', '.join(platillos_lista)} (${costo_orden.get('monto_total', 0)})"
                    
                    # Construir resumen de TODAS las órdenes actuales
                    resumen_todas_ordenes = []
                    for orden in orden_temporal["ordenes"]:
                        platillos_orden = []
                        for tiempo_key, platillos_tiempo in orden["platillos"].items():
                            if platillos_tiempo and platillos_tiempo not in ['', '<UNKNOWN>', []]:
                                if isinstance(platillos_tiempo, list):
                                    platillos_orden.extend(platillos_tiempo)
                                else:
                                    platillos_orden.append(platillos_tiempo)
                        
                        resumen_todas_ordenes.append({
                            "numero": orden["orden_numero"],
                            "platillos": platillos_orden,
                            "costo": orden["costos"].get("monto_total", 0),
                            "texto": f"Comida {orden['orden_numero']}: {', '.join(platillos_orden)} (${orden['costos'].get('monto_total', 0)})"
                        })

                    print(f"✅ Orden temporal guardada. Total órdenes: {orden_temporal['total_ordenes']}")
                    print(f"💰 Monto total acumulado: ${orden_temporal['monto_total_general']}")

                    save_orden_temporal(telefono, orden_temporal)

                    # Construir respuesta para el tool_result
                    content = {
                        "status": "orden_temporal_guardada",
                        "orden_numero": nueva_orden["orden_numero"],
                        "resumen_orden_agregada": resumen_esta_orden,
                        "platillos": nueva_orden["platillos"],
                        "costo_orden": costo_orden.get('monto_total', 0),
                        "total_ordenes": orden_temporal["total_ordenes"],
                        "monto_total_acumulado": orden_temporal["monto_total_general"],
                        "todas_las_ordenes": resumen_todas_ordenes
                    }

                    tool_response = {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use.id,
                                "content": str(content)
                            }
                        ]
                    }
                    new_messages.append(tool_response)
                    print(f"✅ tool_result agregado para {tool_use.id}")
                
                # CASO 2: CON NOMBRE - Confirmar y persistir en BD
                elif tiene_nombre and tiene_platillos:
                    if j > 0:
                        print("⚠️ Orden ya fue procesada en este turno, saltando...")
                        content = str(tool_input)
                        tool_response = {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_use.id,
                                    "content": content
                                }
                            ]
                        }
                        new_messages.append(tool_response)
                        print(f"✅ tool_result agregado para {tool_use.id} (ya procesado)")
                        continue
                    
                    j = 1
                    
                    print("💾 Confirmando orden con nombre - Persistiendo en BD...")
                    
                    # Leer orden temporal de Redis
                    orden_temporal = get_orden_temporal(telefono)

                    # DEBUG
                    if orden_temporal:
                        print(f"🔍 DEBUG Redis - Total órdenes: {len(orden_temporal.get('ordenes', []))}")
                        for idx, orden in enumerate(orden_temporal.get('ordenes', [])):
                            print(f"  📦 Orden {idx+1}:")
                            print(f"     Platillos: {orden.get('platillos')}")
                    else:
                        print("🔍 DEBUG: NO hay orden temporal en Redis")
                    
                    # Si NO hay orden temporal pero trae platillos en esta llamada
                    if not orden_temporal:
                        print("⚠️ No hay orden temporal, creando orden única...")
                        # costo_orden = determinar_costo_comanda(tool_input, config=config)
                        # En agente.py, donde se llama determinar_costo_comanda
                        costo_orden = determinar_costo_comanda(tool_input, config=config, campos_platillos=campos_platillos_validos)
                        
                        # ✅ CAMBIO: Usar construir_platillos_dict
                        orden_temporal = {
                            "pedido_grupo": str(uuid.uuid4()),
                            "ordenes": [
                                {
                                    "orden_numero": 1,
                                    "platillos": construir_platillos_dict(tool_input, campos_platillos_validos),
                                    "desechables": tool_input.get('desechables', False),
                                    "costos": costo_orden
                                }
                            ],
                            "total_ordenes": 1,
                            "monto_total_general": costo_orden.get('monto_total', 0),
                            "nombre_cliente": None
                        }
                    else:
                        # Si trae platillos en esta llamada CON nombre, verificar si son nuevos
                        if tiene_platillos:
                            # ✅ CAMBIO: Usar construir_platillos_dict
                            # PRIMERO construir la variable
                            nueva_comida_platillos = construir_platillos_dict(tool_input, campos_platillos_validos)

                            # DESPUÉS hacer el check de duplicados con normalización
                            es_duplicado = False
                            for orden_existente in orden_temporal["ordenes"]:
                                existente_normalizado = {
                                    k: [p.lower() for p in v] if isinstance(v, list) else v.lower() if v else v
                                    for k, v in orden_existente["platillos"].items()
                                }
                                nueva_normalizada = {
                                    k: [p.lower() for p in v] if isinstance(v, list) else v.lower() if v else v
                                    for k, v in nueva_comida_platillos.items()
                                }
                                if existente_normalizado == nueva_normalizada:
                                    es_duplicado = True
                                    break
                            # nueva_comida_platillos = construir_platillos_dict(tool_input, campos_platillos_validos)

                            # # Verificar si ya existe una comida idéntica
                            # es_duplicado = False
                            # for orden_existente in orden_temporal.get("ordenes", []):
                            #     existente_normalizado = {
                            #         k: [p.lower() for p in v] if isinstance(v, list) else v.lower() if v else v
                            #         for k, v in orden_existente["platillos"].items()
                            #     }
                            #     nueva_normalizada = {
                            #         k: [p.lower() for p in v] if isinstance(v, list) else v.lower() if v else v
                            #         for k, v in nueva_comida_platillos_check.items()
                            #     }
                            #     if existente_normalizado == nueva_normalizada:
                            #         es_duplicado = True
                            #         break
                            # es_duplicado = False
                            # for orden_existente in orden_temporal["ordenes"]:
                            #     if orden_existente["platillos"] == nueva_comida_platillos:
                            #         es_duplicado = True
                            #         print(f"⚠️ Comida duplicada detectada - NO agregando")
                            #         break

                            # Solo agregar si NO es duplicado
                            if not es_duplicado:
                                print("➕ Agregando comida nueva antes de confirmar...")
                                # costo_orden = determinar_costo_comanda(tool_input, config=config)
                                costo_orden = determinar_costo_comanda(tool_input, config=config, campos_platillos=campos_platillos_validos)

                                nueva_orden = {
                                    "orden_numero": len(orden_temporal["ordenes"]) + 1,
                                    "platillos": nueva_comida_platillos,
                                    "desechables": tool_input.get('desechables', False),
                                    "costos": costo_orden
                                }

                                orden_temporal["ordenes"].append(nueva_orden)
                                orden_temporal["total_ordenes"] = len(orden_temporal["ordenes"])
                                orden_temporal["monto_total_general"] += costo_orden.get('monto_total', 0)
                            else:
                                print("✅ No se agregó comida duplicada - procediendo a confirmar")
                    
                    # Asignar nombre del cliente
                    nombre_completo = tool_input['nombre_completo']
                    orden_temporal["nombre_cliente"] = nombre_completo
                    
                    # Obtener pedido_grupo
                    pedido_grupo = orden_temporal["pedido_grupo"]
                    
                    print(f"👤 Cliente: {nombre_completo}")
                    print(f"📦 Pedido grupo: {pedido_grupo}")
                    print(f"🍽️ Total órdenes: {orden_temporal['total_ordenes']}")
                    print(f"💰 Monto total: ${orden_temporal['monto_total_general']}")
                    
                    # Persistir cada orden en la BD
                    comandas_ids = []
                    
                    for orden in orden_temporal["ordenes"]:
                        # Insertar en tbl_cocina_comandas
                        comanda = {
                            'user_id': user_id,
                            'cliente_nombre': nombre_completo,
                            'pedido_grupo': pedido_grupo,
                            'monto_estandar': orden['costos'].get('monto_estandar', 0),
                            'monto_extras': orden['costos'].get('monto_extras', 0),
                            'monto_desechables': orden['costos'].get('monto_desechables', 0),
                            'monto_total': orden['costos'].get('monto_total', 0),
                            'telefono_cliente': telefono
                        }
                        
                        comanda_id = insert_data(comanda, TLB_COMANDAS, return_id=True)
                        comandas_ids.append(comanda_id)
                        
                        print(f"✅ Comanda {orden['orden_numero']} creada con ID: {comanda_id}")
                        
                        # ✅ CAMBIO: Extraer platillos dinámicamente con .items()
                        todos_platillos = []
                        for tiempo_key, platillos_tiempo in orden['platillos'].items():
                            if platillos_tiempo and platillos_tiempo not in ['', '<UNKNOWN>']:
                                if isinstance(platillos_tiempo, list):
                                    todos_platillos.extend(platillos_tiempo)
                                else:
                                    todos_platillos.append(platillos_tiempo)
                        
                        print(f"platillos {todos_platillos}")
                        
                        # Insertar platillos en tbl_cocina_desglose
                        if todos_platillos:
                            ids_platillos = extraer_ids_platillos(todos_platillos)
                            
                            for id_platillo_obj in ids_platillos:
                                desglose = {
                                    'comanda_id': comanda_id,
                                    'platillo_id': id_platillo_obj.get('id')
                                }
                                insert_data(desglose, TLB_DESGLOSE)
                                print(f"  ↳ Platillo agregado: {id_platillo_obj.get('id')}")
                    
                    # Limpiar Redis
                    # delete_orden_temporal(telefono)
                    # print("🗑️ Orden temporal eliminada de Redis")
                    
                    # # Construir respuesta para el tool_result
                    # content = {
                    #     "status": "orden_confirmada",
                    #     "nombre_cliente": nombre_completo,
                    #     "pedido_grupo": pedido_grupo,
                    #     "total_ordenes": orden_temporal["total_ordenes"],
                    #     "monto_total": orden_temporal["monto_total_general"],
                    #     "comandas_ids": comandas_ids
                    # }

                    # Limpiar Redis orden temporal
                    delete_orden_temporal(telefono)
                    print("🗑️ Orden temporal eliminada de Redis")

                    # Guardar estado esperando_entrega en Redis
                    estado_entrega = {
                        "comandas_ids": comandas_ids,
                        "pedido_grupo": pedido_grupo,
                        "nombre_cliente": nombre_completo,
                        "monto_total": orden_temporal["monto_total_general"],
                        "total_ordenes": orden_temporal["total_ordenes"]
                    }
                    save_estado_entrega(telefono, estado_entrega)
                    print("📦 Estado esperando_entrega guardado en Redis")

                    # Construir respuesta para el tool_result
                    content = {
                        "status": "pedido_guardado_esperando_entrega",
                        "nombre_cliente": nombre_completo,
                        "pedido_grupo": pedido_grupo,
                        "total_ordenes": orden_temporal["total_ordenes"],
                        "monto_total": orden_temporal["monto_total_general"],
                        "comandas_ids": comandas_ids,
                        "instruccion": "El pedido fue guardado. Ahora DEBES preguntar al cliente si desea entrega a domicilio o si va a recoger su pedido."
                    }
                    
                    tool_response = {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use.id,
                                "content": str(content)
                            }
                        ]
                    }
                    new_messages.append(tool_response)
                    print(f"✅ tool_result agregado para {tool_use.id}")

                # CASO 3: Solo nombre sin platillos
                elif tiene_nombre and not tiene_platillos:
                    print("⚠️ Se recibió nombre pero sin platillos")
                    
                    content = {
                        "status": "error",
                        "mensaje": "Se recibió nombre sin platillos. Solicita primero qué desea ordenar."
                    }
                    
                    tool_response = {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use.id,
                                "content": str(content)
                            }
                        ]
                    }
                    new_messages.append(tool_response)
                    print(f"✅ tool_result agregado para {tool_use.id}")
                
                # CASO 4: Ni nombre ni platillos
                else:
                    print("⚠️ No hay nombre ni platillos válidos")
                    
                    content = str(tool_input)
                    
                    tool_response = {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use.id,
                                "content": content
                            }
                        ]
                    }
                    new_messages.append(tool_response)
                    print(f"✅ tool_result agregado para {tool_use.id}")

            # ========================================================================
            # TOOL: editar_orden (temporal)
            # ========================================================================
            elif 'editar_orden' in tool_name.lower():
                print("✏️ EDITANDO ORDEN TEMPORAL", tool_input)
                
                # Leer orden temporal de Redis
                orden_temporal = get_orden_temporal(telefono)
                if orden_temporal:
                    print(f"🔍 DEBUG Redis - Total órdenes: {len(orden_temporal.get('ordenes', []))}")
                    for idx, orden in enumerate(orden_temporal.get('ordenes', [])):
                        print(f"  Orden {idx+1} platillos: {orden.get('platillos')}")
                
                # Validar que existe orden temporal
                if not orden_temporal or len(orden_temporal.get('ordenes', [])) == 0:
                    print("⚠️ No hay orden temporal para editar")
                    
                    content = {
                        "status": "error",
                        "mensaje": "No tienes ninguna orden en proceso para editar. Primero realiza un pedido."
                    }
                    
                    tool_response = {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use.id,
                                "content": str(content)
                            }
                        ]
                    }
                    new_messages.append(tool_response)
                    print(f"✅ tool_result agregado para {tool_use.id}")
                    continue
                
                # Obtener parámetros
                accion = tool_input.get('accion')
                orden_numero = tool_input.get('orden_numero')
                tiempo = tool_input.get('tiempo')
                platillo_quitar = tool_input.get('platillo_quitar')
                platillo_agregar = tool_input.get('platillo_agregar')
                aplicar_a_todas = tool_input.get('aplicar_a_todas', False)
                
                # Si no especifica orden_numero, usar la última
                if not orden_numero:
                    orden_numero = len(orden_temporal['ordenes'])
                
                # ACCIÓN: ELIMINAR ORDEN COMPLETA
                if accion == 'eliminar_orden':
                    print(f"🗑️ Eliminando orden número {orden_numero}")
                    
                    if orden_numero < 1 or orden_numero > len(orden_temporal['ordenes']):
                        content = {
                            "status": "error",
                            "mensaje": f"La orden número {orden_numero} no existe. Tienes {len(orden_temporal['ordenes'])} órdenes."
                        }
                    else:
                        orden_eliminada = orden_temporal['ordenes'][orden_numero - 1]
                        monto_eliminado = orden_eliminada['costos'].get('monto_total', 0)
                        
                        orden_temporal['ordenes'].pop(orden_numero - 1)
                        
                        for idx, orden in enumerate(orden_temporal['ordenes']):
                            orden['orden_numero'] = idx + 1
                        
                        orden_temporal['total_ordenes'] = len(orden_temporal['ordenes'])
                        orden_temporal['monto_total_general'] -= monto_eliminado
                        
                        if len(orden_temporal['ordenes']) == 0:
                            delete_orden_temporal(telefono)
                            print("🗑️ Todas las órdenes eliminadas - Redis limpiado")
                            
                            content = {
                                "status": "orden_vacia",
                                "mensaje": "Se eliminó la última orden. Tu pedido está vacío ahora."
                            }
                        else:
                            save_orden_temporal(telefono, orden_temporal)
                            
                            content = {
                                "status": "orden_eliminada",
                                "orden_eliminada": orden_numero,
                                "monto_eliminado": monto_eliminado,
                                "ordenes_restantes": orden_temporal['total_ordenes'],
                                "nuevo_total": orden_temporal['monto_total_general']
                            }
                
                # ACCIÓN: CAMBIAR PLATILLO
                elif accion == 'cambiar_platillo':
                    print(f"🔄 Cambiando platillo en orden {orden_numero}")
                    
                    if not tiempo or not platillo_quitar or not platillo_agregar:
                        content = {
                            "status": "error",
                            "mensaje": "Para cambiar un platillo necesito: tiempo, platillo_quitar y platillo_agregar"
                        }
                    elif orden_numero < 1 or orden_numero > len(orden_temporal['ordenes']):
                        content = {
                            "status": "error",
                            "mensaje": f"La orden número {orden_numero} no existe."
                        }
                    else:
                        orden = orden_temporal['ordenes'][orden_numero - 1]
                        
                        platillos_tiempo = orden['platillos'].get(tiempo, [])
                        if isinstance(platillos_tiempo, str):
                            platillos_tiempo = [platillos_tiempo] if platillos_tiempo else []
                        
                        if platillo_quitar in platillos_tiempo:
                            platillos_tiempo.remove(platillo_quitar)
                        
                        if platillo_agregar:
                            platillos_tiempo.append(platillo_agregar)
                        
                        orden['platillos'][tiempo] = platillos_tiempo
                        
                        # ✅ CAMBIO: Recalcular dinámicamente
                        tool_input_recalculo = {campo: orden['platillos'].get(campo, []) for campo in campos_platillos_validos}
                        tool_input_recalculo['desechables'] = orden.get('desechables', False)
                        
                        costo_viejo = orden['costos'].get('monto_total', 0)
                        # nuevos_costos = determinar_costo_comanda(tool_input_recalculo, config=config)
                        nuevos_costos = determinar_costo_comanda(tool_input, config=config, campos_platillos=campos_platillos_validos)
                        costo_nuevo = nuevos_costos.get('monto_total', 0)
                        
                        orden['costos'] = nuevos_costos
                        
                        orden_temporal['monto_total_general'] = orden_temporal['monto_total_general'] - costo_viejo + costo_nuevo
                        
                        save_orden_temporal(telefono, orden_temporal)
                        
                        content = {
                            "status": "platillo_cambiado",
                            "orden_numero": orden_numero,
                            "tiempo": tiempo,
                            "platillo_quitado": platillo_quitar,
                            "platillo_agregado": platillo_agregar,
                            "nuevo_costo_orden": costo_nuevo,
                            "nuevo_total_general": orden_temporal['monto_total_general']
                        }
                
                # ACCIÓN: AGREGAR PLATILLO
                elif accion == 'agregar_platillo':
                    print(f"➕ Agregando platillo")
                    
                    if not tiempo or not platillo_agregar:
                        content = {
                            "status": "error",
                            "mensaje": "Para agregar un platillo necesito: tiempo y platillo_agregar"
                        }
                    elif not aplicar_a_todas and (orden_numero < 1 or orden_numero > len(orden_temporal['ordenes'])):
                        content = {
                            "status": "error",
                            "mensaje": f"La orden número {orden_numero} no existe."
                        }
                    else:
                        ordenes_a_modificar = []
                        if aplicar_a_todas:
                            ordenes_a_modificar = list(range(len(orden_temporal['ordenes'])))
                        else:
                            ordenes_a_modificar = [orden_numero - 1]
                        
                        cambios_realizados = []
                        
                        for idx in ordenes_a_modificar:
                            orden = orden_temporal['ordenes'][idx]
                            
                            platillos_tiempo = orden['platillos'].get(tiempo, [])
                            if isinstance(platillos_tiempo, str):
                                platillos_tiempo = [platillos_tiempo] if platillos_tiempo else []
                            
                            platillos_tiempo.append(platillo_agregar)
                            orden['platillos'][tiempo] = platillos_tiempo
                            
                            # ✅ CAMBIO: Recalcular dinámicamente
                            tool_input_recalculo = {campo: orden['platillos'].get(campo, []) for campo in campos_platillos_validos}
                            tool_input_recalculo['desechables'] = orden.get('desechables', False)
                            
                            costo_viejo = orden['costos'].get('monto_total', 0)
                            # nuevos_costos = determinar_costo_comanda(tool_input_recalculo, config=config)
                            nuevos_costos = determinar_costo_comanda(tool_input, config=config, campos_platillos=campos_platillos_validos)
                            costo_nuevo = nuevos_costos.get('monto_total', 0)
                            
                            orden['costos'] = nuevos_costos
                            
                            orden_temporal['monto_total_general'] = orden_temporal['monto_total_general'] - costo_viejo + costo_nuevo
                            
                            cambios_realizados.append({
                                "orden_numero": idx + 1,
                                "costo_nuevo": costo_nuevo
                            })
                        
                        save_orden_temporal(telefono, orden_temporal)
                        
                        content = {
                            "status": "platillo_agregado",
                            "tiempo": tiempo,
                            "platillo": platillo_agregar,
                            "ordenes_modificadas": cambios_realizados,
                            "nuevo_total_general": orden_temporal['monto_total_general']
                        }
                
                # ACCIÓN: QUITAR PLATILLO
                elif accion == 'quitar_platillo':
                    print(f"➖ Quitando platillo")
                    
                    if not tiempo or not platillo_quitar:
                        content = {
                            "status": "error",
                            "mensaje": "Para quitar un platillo necesito: tiempo y platillo_quitar"
                        }
                    elif not aplicar_a_todas and (orden_numero < 1 or orden_numero > len(orden_temporal['ordenes'])):
                        content = {
                            "status": "error",
                            "mensaje": f"La orden número {orden_numero} no existe."
                        }
                    else:
                        ordenes_a_modificar = []
                        if aplicar_a_todas:
                            ordenes_a_modificar = list(range(len(orden_temporal['ordenes'])))
                        else:
                            ordenes_a_modificar = [orden_numero - 1]
                        
                        cambios_realizados = []
                        
                        for idx in ordenes_a_modificar:
                            orden = orden_temporal['ordenes'][idx]
                            
                            platillos_tiempo = orden['platillos'].get(tiempo, [])
                            if isinstance(platillos_tiempo, str):
                                platillos_tiempo = [platillos_tiempo] if platillos_tiempo else []
                            
                            if platillo_quitar in platillos_tiempo:
                                platillos_tiempo.remove(platillo_quitar)
                                orden['platillos'][tiempo] = platillos_tiempo
                                
                                # ✅ CAMBIO: Recalcular dinámicamente
                                tool_input_recalculo = {campo: orden['platillos'].get(campo, []) for campo in campos_platillos_validos}
                                tool_input_recalculo['desechables'] = orden.get('desechables', False)
                                
                                costo_viejo = orden['costos'].get('monto_total', 0)
                                # nuevos_costos = determinar_costo_comanda(tool_input_recalculo, config=config)
                                nuevos_costos = determinar_costo_comanda(tool_input, config=config, campos_platillos=campos_platillos_validos)
                                costo_nuevo = nuevos_costos.get('monto_total', 0)
                                
                                orden['costos'] = nuevos_costos
                                
                                orden_temporal['monto_total_general'] = orden_temporal['monto_total_general'] - costo_viejo + costo_nuevo
                                
                                cambios_realizados.append({
                                    "orden_numero": idx + 1,
                                    "costo_nuevo": costo_nuevo
                                })
                        
                        save_orden_temporal(telefono, orden_temporal)
                        
                        content = {
                            "status": "platillo_quitado",
                            "tiempo": tiempo,
                            "platillo": platillo_quitar,
                            "ordenes_modificadas": cambios_realizados,
                            "nuevo_total_general": orden_temporal['monto_total_general']
                        }
                
                # ACCIÓN NO RECONOCIDA
                else:
                    content = {
                        "status": "error",
                        "mensaje": f"Acción '{accion}' no reconocida. Usa: eliminar_orden, cambiar_platillo, agregar_platillo o quitar_platillo"
                    }
                
                tool_response = {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": str(content)
                        }
                    ]
                }
                new_messages.append(tool_response)
                print(f"✅ tool_result agregado para {tool_use.id}")

            # ========================================================================
            # TOOL: editar_pedido_confirmado
            # ========================================================================
            elif 'editar_pedido_confirmado' in tool_name.lower():
                print("✏️ EDITANDO PEDIDO CONFIRMADO", tool_input)
                
                pedido_data = obtener_pedido_reciente_usuario(telefono)
                
                if not pedido_data:
                    content = {
                        "status": "error",
                        "mensaje": "No encontré ningún pedido tuyo para editar."
                    }
                    
                    tool_response = {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use.id,
                                "content": str(content)
                            }
                        ]
                    }
                    new_messages.append(tool_response)
                    print(f"✅ tool_result agregado para {tool_use.id}")
                    continue
                
                pedido_grupo = pedido_data['pedido_grupo']
                cliente_nombre = pedido_data['cliente_nombre']
                
                print(f"📦 Pedido encontrado: {pedido_grupo} - Cliente: {cliente_nombre}")
                
                validacion = validar_pedido_editable(pedido_grupo)
                
                if not validacion['editable']:
                    content = {
                        "status": "error",
                        "mensaje": validacion['mensaje']
                    }
                    
                    tool_response = {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use.id,
                                "content": str(content)
                            }
                        ]
                    }
                    new_messages.append(tool_response)
                    print(f"✅ tool_result agregado para {tool_use.id}")
                    continue

                print(f"✅ Pedido editable - Estados: {validacion['estados']}")

                # Congelar pedido mientras se procesa la edición
                congelar_pedido(pedido_grupo)

                comandas_actuales = obtener_comandas_con_platillos(pedido_grupo)
                
                if not comandas_actuales:
                    content = {
                        "status": "error",
                        "mensaje": "No se pudieron cargar las comandas del pedido."
                    }
                    
                    tool_response = {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use.id,
                                "content": str(content)
                            }
                        ]
                    }
                    new_messages.append(tool_response)
                    print(f"✅ tool_result agregado para {tool_use.id}")
                    continue
                
                accion = tool_input.get('accion')
                orden_numero = tool_input.get('orden_numero')
                tiempo = tool_input.get('tiempo')
                platillo_quitar = tool_input.get('platillo_quitar')
                platillo_agregar = tool_input.get('platillo_agregar')
                
                if not orden_numero:
                    orden_numero = len(comandas_actuales)
                
                # ACCIÓN: ELIMINAR COMANDA COMPLETA
                if accion == 'eliminar_orden':
                    print(f"🗑️ Eliminando comanda número {orden_numero}")
                    
                    if len(comandas_actuales) == 1:
                        content = {
                            "status": "error",
                            "mensaje": "No puedes eliminar la única comanda del pedido. Si deseas cancelar todo el pedido, usa la opción de cancelar."
                        }
                    elif orden_numero < 1 or orden_numero > len(comandas_actuales):
                        content = {
                            "status": "error",
                            "mensaje": f"La comanda número {orden_numero} no existe. Tu pedido tiene {len(comandas_actuales)} comandas."
                        }
                    else:
                        comanda_eliminar = comandas_actuales[orden_numero - 1]
                        comanda_id = comanda_eliminar['comanda_id']
                        monto_eliminado = comanda_eliminar['monto_total']
                        
                        resultado = eliminar_comanda(comanda_id)
                        
                        if resultado['success']:
                            comandas_restantes = obtener_comandas_con_platillos(pedido_grupo)
                            
                            resumen_comandas = []
                            total_nuevo = 0
                            for comanda in comandas_restantes:
                                platillos_nombres = [p['platillo'] for p in comanda['platillos']]
                                resumen_comandas.append({
                                    "numero": comanda['numero'],
                                    "platillos": platillos_nombres,
                                    "costo": comanda['monto_total'],
                                    "texto": f"Comida {comanda['numero']}: {', '.join(platillos_nombres)} (${comanda['monto_total']})"
                                })
                                total_nuevo += comanda['monto_total']
                            
                            content = {
                                "status": "comanda_eliminada",
                                "comanda_eliminada": orden_numero,
                                "monto_eliminado": monto_eliminado,
                                "comandas_restantes": len(comandas_restantes),
                                "nuevo_total": total_nuevo,
                                "resumen_comandas": resumen_comandas
                            }
                        else:
                            content = {
                                "status": "error",
                                "mensaje": resultado['mensaje']
                            }
                
                # ACCIÓN: CAMBIAR PLATILLO
                elif accion == 'cambiar_platillo':
                    print(f"🔄 Cambiando platillo en comanda {orden_numero}")
                    
                    if not tiempo or not platillo_quitar or not platillo_agregar:
                        content = {
                            "status": "error",
                            "mensaje": "Para cambiar un platillo necesito: tiempo, platillo_quitar y platillo_agregar"
                        }
                    elif orden_numero < 1 or orden_numero > len(comandas_actuales):
                        content = {
                            "status": "error",
                            "mensaje": f"La comanda número {orden_numero} no existe."
                        }
                    else:
                        comanda = comandas_actuales[orden_numero - 1]
                        comanda_id = comanda['comanda_id']
                        
                        platillos_actuales = [p['platillo'] for p in comanda['platillos']]
                        
                        if platillo_quitar in platillos_actuales:
                            platillos_actuales.remove(platillo_quitar)
                        
                        platillos_actuales.append(platillo_agregar)
                        
                        platillos_ids_data = extraer_ids_platillos(platillos_actuales)
                        nuevos_platillos_ids = [p['id'] for p in platillos_ids_data]
                        
                        # Construir tool_input_recalculo con el cambio ya aplicado
                        tool_input_recalculo = {}
                        for p in comanda['platillos']:
                            if p.get('campo'):
                                # Si este es el platillo que se quitó, poner el nuevo
                                if p['platillo'] == platillo_quitar:
                                    tool_input_recalculo[p['campo']] = platillo_agregar
                                else:
                                    tool_input_recalculo[p['campo']] = p['platillo']
                        tool_input_recalculo['desechables'] = 'No'
                        
                        # nuevos_costos = determinar_costo_comanda(tool_input_recalculo, config=config)
                        nuevos_costos = determinar_costo_comanda(tool_input, config=config, campos_platillos=campos_platillos_validos)
                        
                        resultado = actualizar_platillos_comanda(comanda_id, nuevos_platillos_ids, nuevos_costos)
                        
                        if resultado['success']:
                            comandas_actualizadas = obtener_comandas_con_platillos(pedido_grupo)
                            total_nuevo = sum(c['monto_total'] for c in comandas_actualizadas)
                            
                            content = {
                                "status": "platillo_cambiado",
                                "comanda_numero": orden_numero,
                                "platillo_quitado": platillo_quitar,
                                "platillo_agregado": platillo_agregar,
                                "nuevo_costo_comanda": nuevos_costos['monto_total'],
                                "nuevo_total_pedido": total_nuevo
                            }
                        else:
                            content = {
                                "status": "error",
                                "mensaje": resultado['mensaje']
                            }
                    # else:
                    #     comanda = comandas_actuales[orden_numero - 1]
                    #     comanda_id = comanda['comanda_id']
                        
                    #     platillos_actuales = [p['platillo'] for p in comanda['platillos']]
                        
                    #     if platillo_quitar in platillos_actuales:
                    #         platillos_actuales.remove(platillo_quitar)
                        
                    #     platillos_actuales.append(platillo_agregar)
                        
                    #     platillos_ids_data = extraer_ids_platillos(platillos_actuales)
                    #     nuevos_platillos_ids = [p['id'] for p in platillos_ids_data]
                        
                    #     tool_input_recalculo = {}
                    #     for p in comanda['platillos']:
                    #         if p.get('campo'):
                    #             tool_input_recalculo[p['campo']] = p['platillo']
                    #     tool_input_recalculo['desechables'] = 'No'
                        
                    #     nuevos_costos = determinar_costo_comanda(tool_input_recalculo, config=config)
                        
                    #     resultado = actualizar_platillos_comanda(comanda_id, nuevos_platillos_ids, nuevos_costos)
                        
                    #     if resultado['success']:
                    #         comandas_actualizadas = obtener_comandas_con_platillos(pedido_grupo)
                    #         total_nuevo = sum(c['monto_total'] for c in comandas_actualizadas)
                            
                    #         content = {
                    #             "status": "platillo_cambiado",
                    #             "comanda_numero": orden_numero,
                    #             "platillo_quitado": platillo_quitar,
                    #             "platillo_agregado": platillo_agregar,
                    #             "nuevo_costo_comanda": nuevos_costos['monto_total'],
                    #             "nuevo_total_pedido": total_nuevo
                    #         }
                    #     else:
                    #         content = {
                    #             "status": "error",
                    #             "mensaje": resultado['mensaje']
                    #         }
                
                # ACCIÓN: AGREGAR PLATILLO
                elif accion == 'agregar_platillo':
                    print(f"➕ Agregando platillo a comanda {orden_numero}")
                    
                    if not tiempo or not platillo_agregar:
                        content = {
                            "status": "error",
                            "mensaje": "Para agregar un platillo necesito: tiempo y platillo_agregar"
                        }
                    elif orden_numero < 1 or orden_numero > len(comandas_actuales):
                        content = {
                            "status": "error",
                            "mensaje": f"La comanda número {orden_numero} no existe."
                        }
                    else:
                        comanda = comandas_actuales[orden_numero - 1]
                        comanda_id = comanda['comanda_id']
                        
                        platillos_actuales = [p['platillo'] for p in comanda['platillos']]
                        platillos_actuales.append(platillo_agregar)
                        
                        platillos_ids_data = extraer_ids_platillos(platillos_actuales)
                        nuevos_platillos_ids = [p['id'] for p in platillos_ids_data]
                        
                        tool_input_recalculo = {}
                        for p in comanda['platillos']:
                            if p.get('campo'):
                                tool_input_recalculo[p['campo']] = p['platillo']
                        tool_input_recalculo['desechables'] = 'No'
                        
                        # nuevos_costos = determinar_costo_comanda(tool_input_recalculo, config=config)
                        nuevos_costos = determinar_costo_comanda(tool_input, config=config, campos_platillos=campos_platillos_validos)
                        
                        resultado = actualizar_platillos_comanda(comanda_id, nuevos_platillos_ids, nuevos_costos)
                        
                        if resultado['success']:
                            comandas_actualizadas = obtener_comandas_con_platillos(pedido_grupo)
                            total_nuevo = sum(c['monto_total'] for c in comandas_actualizadas)
                            
                            content = {
                                "status": "platillo_agregado",
                                "comanda_numero": orden_numero,
                                "platillo": platillo_agregar,
                                "nuevo_costo_comanda": nuevos_costos['monto_total'],
                                "nuevo_total_pedido": total_nuevo
                            }
                        else:
                            content = {
                                "status": "error",
                                "mensaje": resultado['mensaje']
                            }
                
                # ACCIÓN: QUITAR PLATILLO
                elif accion == 'quitar_platillo':
                    print(f"➖ Quitando platillo de comanda {orden_numero}")
                    
                    if not tiempo or not platillo_quitar:
                        content = {
                            "status": "error",
                            "mensaje": "Para quitar un platillo necesito: tiempo y platillo_quitar"
                        }
                    elif orden_numero < 1 or orden_numero > len(comandas_actuales):
                        content = {
                            "status": "error",
                            "mensaje": f"La comanda número {orden_numero} no existe."
                        }
                    else:
                        comanda = comandas_actuales[orden_numero - 1]
                        comanda_id = comanda['comanda_id']
                        
                        platillos_actuales = [p['platillo'] for p in comanda['platillos']]
                        
                        if len(platillos_actuales) == 1:
                            content = {
                                "status": "error",
                                "mensaje": "No puedes quitar el único platillo de la comanda. Si deseas eliminarla, usa la opción de eliminar comanda."
                            }
                        elif platillo_quitar not in platillos_actuales:
                            content = {
                                "status": "error",
                                "mensaje": f"El platillo '{platillo_quitar}' no está en esta comanda."
                            }
                        else:
                            platillos_actuales.remove(platillo_quitar)
                            
                            platillos_ids_data = extraer_ids_platillos(platillos_actuales)
                            nuevos_platillos_ids = [p['id'] for p in platillos_ids_data]
                            
                            tool_input_recalculo = {}
                            for p in comanda['platillos']:
                                if p.get('campo'):
                                    tool_input_recalculo[p['campo']] = p['platillo']
                            tool_input_recalculo['desechables'] = 'No'
                            
                            # nuevos_costos = determinar_costo_comanda(tool_input_recalculo, config=config)
                            nuevos_costos = determinar_costo_comanda(tool_input, config=config, campos_platillos=campos_platillos_validos)
                            
                            resultado = actualizar_platillos_comanda(comanda_id, nuevos_platillos_ids, nuevos_costos)
                            
                            if resultado['success']:
                                comandas_actualizadas = obtener_comandas_con_platillos(pedido_grupo)
                                total_nuevo = sum(c['monto_total'] for c in comandas_actualizadas)
                                
                                content = {
                                    "status": "platillo_quitado",
                                    "comanda_numero": orden_numero,
                                    "platillo": platillo_quitar,
                                    "nuevo_costo_comanda": nuevos_costos['monto_total'],
                                    "nuevo_total_pedido": total_nuevo
                                }
                            else:
                                content = {
                                    "status": "error",
                                    "mensaje": resultado['mensaje']
                                }
                
                # ACCIÓN: AGREGAR COMANDA NUEVA AL GRUPO
                elif accion == 'agregar_comanda':
                    print(f"➕ Agregando comanda nueva al grupo {pedido_grupo}")
                    
                    platillos_nuevos = tool_input.get('platillos_nuevos', [])
                    
                    if not platillos_nuevos:
                        content = {
                            "status": "error",
                            "mensaje": "Para agregar una comanda necesito la lista de platillos."
                        }
                    else:
                        platillos_ids_data = extraer_ids_platillos(platillos_nuevos)
                        nuevos_platillos_ids = [p['id'] for p in platillos_ids_data]
                        
                        # Calcular costo de los platillos nuevos
                        tool_input_recalculo = {'desechables': 'No'}
                        for i, nombre in enumerate(platillos_nuevos):
                            tool_input_recalculo[f'extra_{i+1}'] = nombre
                        
                        # nuevos_costos = determinar_costo_comanda(tool_input_recalculo, config=config)
                        nuevos_costos = determinar_costo_comanda(tool_input, config=config, campos_platillos=campos_platillos_validos)
                        
                        # Crear comanda nueva en el mismo grupo
                        from fct_orden_manual import crear_orden_manual
                        from datetime import datetime, timezone
                        from fct_supabase import insert_data as _insert
                        
                        nueva_comanda = {
                            'user_id': user_id,
                            'cliente_nombre': cliente_nombre,
                            'pedido_grupo': pedido_grupo,
                            'monto_estandar': 0,
                            'monto_extras': nuevos_costos.get('monto_total', 0),
                            'monto_desechables': 0,
                            'monto_total': nuevos_costos.get('monto_total', 0),
                            'telefono_cliente': telefono,
                            'tipo_entrega': comandas_actuales[0].get('tipo_entrega', 'local') if comandas_actuales else 'local',
                            'status': 'PENDIENTE'
                        }
                        
                        # Obtener tipo_entrega y dirección de la primera comanda del grupo
                        primera = _sc.table(os.getenv('TLB_COMANDAS'))\
                            .select('tipo_entrega, direccion')\
                            .eq('pedido_grupo', pedido_grupo)\
                            .limit(1)\
                            .execute()

                        tipo_entrega_grupo = primera.data[0].get('tipo_entrega', 'local') if primera.data else 'local'
                        direccion_grupo = primera.data[0].get('direccion', '') if primera.data else ''

                        nueva_comanda = {
                            'user_id': user_id,
                            'cliente_nombre': cliente_nombre,
                            'pedido_grupo': pedido_grupo,
                            'monto_estandar': nuevos_costos.get('monto_total', 0),
                            'monto_extras': 0,
                            'monto_desechables': 0,
                            'monto_total': nuevos_costos.get('monto_total', 0),
                            'telefono_cliente': telefono,
                            'tipo_entrega': tipo_entrega_grupo,
                            'direccion': direccion_grupo,
                            'status': 'PENDIENTE',
                            'es_extra': True,
                        }

                        result = _sc.table(os.getenv('TLB_COMANDAS')).insert(nueva_comanda).execute()
                        
                        if result.data:
                            nueva_comanda_id = result.data[0]['id']
                            
                            # for platillo_id in nuevos_platillos_ids:
                            #     _sc.table(os.getenv('TLB_DESGLOSE')).insert({
                            #         'comanda_id': nueva_comanda_id,
                            #         'platillo_id': platillo_id
                            #     }).execute()
                            for platillo_id in nuevos_platillos_ids:
                                try:
                                    result_desglose = _sc.table(os.getenv('TLB_DESGLOSE')).insert({
                                        'comanda_id': nueva_comanda_id,
                                        'platillo_id': platillo_id
                                    }).execute()
                                    print(f"✅ Desglose insertado: comanda={nueva_comanda_id} platillo={platillo_id}")
                                    print(f"🔍 Result desglose: {result_desglose.data}")
                                except Exception as e:
                                    print(f"❌ Error insertando desglose: {e}")
                            
                            comandas_actualizadas = obtener_comandas_con_platillos(pedido_grupo)
                            total_nuevo = sum(c['monto_total'] for c in comandas_actualizadas)
                            
                            content = {
                                "status": "comanda_agregada",
                                "platillos": platillos_nuevos,
                                "costo": nuevos_costos.get('monto_total', 0),
                                "nuevo_total_pedido": total_nuevo
                            }
                        else:
                            content = {
                                "status": "error",
                                "mensaje": "No se pudo crear la comanda extra."
                            }
                
                # ACCIÓN NO RECONOCIDA
                else:
                    content = {
                        "status": "error",
                        "mensaje": f"Acción '{accion}' no reconocida. Usa: eliminar_orden, cambiar_platillo, agregar_platillo o quitar_platillo"
                    }
                
                # Descongelar pedido al terminar (exitoso o con error)
                descongelar_pedido(pedido_grupo)
                
                tool_response = {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": str(content)
                        }
                    ]
                }
                new_messages.append(tool_response)
                print(f"✅ tool_result agregado para {tool_use.id}")
        
            # ========================================================================
            # TOOL: confirmar_entrega
            # ========================================================================
            elif 'confirmar_entrega' in tool_name.lower():
                print("🚚 Ejecutando: confirmar_entrega", tool_input)

                tipo_entrega = tool_input.get('tipo_entrega')
                direccion = tool_input.get('direccion')
                referencia_1 = tool_input.get('referencia_1')
                referencia_2 = tool_input.get('referencia_2')

                # Validar que existe estado de entrega en Redis
                estado_entrega = get_estado_entrega(telefono)

                if not estado_entrega:
                    print("⚠️ No hay estado de entrega en Redis")
                    content = {
                        "status": "error",
                        "mensaje": "No encontré un pedido pendiente de confirmar entrega. Puede que ya haya sido procesado."
                    }
                    tool_response = {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use.id,
                                "content": str(content)
                            }
                        ]
                    }
                    new_messages.append(tool_response)
                    print(f"✅ tool_result agregado para {tool_use.id}")
                    continue

                # Validar dirección si es domicilio
                if tipo_entrega == 'domicilio':
                    if not direccion or str(direccion).strip() in ['', '<UNKNOWN>']:
                        print("⚠️ Domicilio sin dirección")
                        content = {
                            "status": "error",
                            "mensaje": "Para entrega a domicilio necesito la dirección completa del cliente (calle, número y colonia)."
                        }
                        tool_response = {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_use.id,
                                    "content": str(content)
                                }
                            ]
                        }
                        new_messages.append(tool_response)
                        print(f"✅ tool_result agregado para {tool_use.id}")
                        continue

                    if not referencia_1 or str(referencia_1).strip() in ['', '<UNKNOWN>']:
                        print("⚠️ Domicilio sin referencia_1")
                        content = {
                            "status": "error",
                            "mensaje": "Para entrega a domicilio necesito al menos una referencia para ubicar el domicilio."
                        }
                        tool_response = {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_use.id,
                                    "content": str(content)
                                }
                            ]
                        }
                        new_messages.append(tool_response)
                        print(f"✅ tool_result agregado para {tool_use.id}")
                        continue

                # Construir datos a actualizar en BD
                datos_entrega = {
                    "tipo_entrega": tipo_entrega
                }

                if tipo_entrega == 'domicilio':
                    datos_entrega["direccion"] = direccion.strip()
                    datos_entrega["referencia_1"] = referencia_1.strip() if referencia_1 else None
                    datos_entrega["referencia_2"] = referencia_2.strip() if referencia_2 else None

                # Actualizar TODAS las comandas del pedido_grupo
                comandas_ids = estado_entrega.get("comandas_ids", [])
                pedido_grupo = estado_entrega.get("pedido_grupo")
                nombre_cliente = estado_entrega.get("nombre_cliente")
                monto_total = estado_entrega.get("monto_total")

                print(f"📦 Actualizando {len(comandas_ids)} comanda(s) con datos de entrega...")

                errores = []
                for comanda_id in comandas_ids:
                    resultado = update_data(
                        table=TLB_COMANDAS,
                        data=datos_entrega,
                        filters={"id": comanda_id}
                    )
                    if not resultado:
                        errores.append(comanda_id)
                        print(f"❌ Error actualizando comanda {comanda_id}")
                    else:
                        print(f"✅ Comanda {comanda_id} actualizada con entrega: {tipo_entrega}")

                if errores:
                    content = {
                        "status": "error_parcial",
                        "mensaje": f"Hubo un problema actualizando {len(errores)} comanda(s). Intenta de nuevo.",
                        "comandas_con_error": errores
                    }
                else:
                    # Limpiar estado de entrega de Redis
                    delete_estado_entrega(telefono)
                    print("🗑️ Estado de entrega eliminado de Redis")

                    # Construir resumen final
                    if tipo_entrega == 'domicilio':
                        resumen_entrega = (
                            f"Entrega a domicilio en: {direccion}. "
                            f"Referencias: {referencia_1}"
                            + (f" / {referencia_2}" if referencia_2 else "")
                        )
                    else:
                        resumen_entrega = "El cliente pasará a recoger su pedido."

                    content = {
                        "status": "pedido_completo",
                        "nombre_cliente": nombre_cliente,
                        "pedido_grupo": pedido_grupo,
                        "total_ordenes": estado_entrega.get("total_ordenes"),
                        "monto_total": monto_total,
                        "tipo_entrega": tipo_entrega,
                        "resumen_entrega": resumen_entrega,
                        "instruccion": "Pedido completamente confirmado. Despídete amablemente del cliente con un resumen del pedido y los datos de entrega."
                    }

                tool_response = {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": str(content)
                        }
                    ]
                }
                new_messages.append(tool_response)
                print(f"✅ tool_result agregado para {tool_use.id}")
        
        # ========================================================================
        # FIN DEL FOR - Todos los tool_use procesados
        # ========================================================================
        
        # DEBUGGING ANTES DE LA SIGUIENTE LLAMADA
        print("\n" + "="*80)
        print("🔍 INSPECCIONANDO new_messages ANTES DE SIGUIENTE LLAMADA A ANTHROPIC:")
        print("="*80)

        for idx, msg in enumerate(new_messages):
            print(f"\n--- Mensaje {idx} ---")
            print(f"Role: {msg['role']}")
            
            if isinstance(msg['content'], list):
                print(f"Content (list con {len(msg['content'])} items):")
                for content_idx, content_item in enumerate(msg['content']):
                    if isinstance(content_item, dict):
                        print(f"  [{content_idx}] type: {content_item.get('type')}")
                        if content_item.get('type') == 'tool_result':
                            print(f"       tool_use_id: {content_item.get('tool_use_id')}")
                        elif content_item.get('type') == 'tool_use':
                            print(f"       tool_use_id: {content_item.get('id')}")
                            print(f"       name: {content_item.get('name')}")
            else:
                print(f"Content (string): {str(msg['content'])[:100]}...")

        print("="*80)

        # Detectar duplicados
        tool_result_ids = []
        for msg in new_messages:
            if msg['role'] == 'user' and isinstance(msg['content'], list):
                for item in msg['content']:
                    if isinstance(item, dict) and item.get('type') == 'tool_result':
                        tool_result_ids.append(item.get('tool_use_id'))

        from collections import Counter
        duplicados = {k: v for k, v in Counter(tool_result_ids).items() if v > 1}

        if duplicados:
            print("🚨 DUPLICADOS DETECTADOS:")
            for tool_id, count in duplicados.items():
                print(f"   {tool_id}: aparece {count} veces")
            print("="*80)
        
        # Hacer la siguiente llamada a Anthropic
        print("📞 Llamando a Anthropic con los tool_results...")
        anthropic_client_response = anthropic_client.messages.create(
            system=system_prompt,
            model=model_name,
            messages=new_messages,
            max_tokens=4096,
            tools=tools,
        )
        print(f"🔵 ANTHROPIC RESPONSE: stop_reason={anthropic_client_response.stop_reason}")
        
        input_tokens += anthropic_client_response.usage.input_tokens
        output_tokens += anthropic_client_response.usage.output_tokens

    # ============================================================================
    # FIN DEL WHILE LOOP
    # ============================================================================
    
    print("\n" + "="*80)
    print("✅ SALIÓ DEL WHILE LOOP")
    print(f"   stop_reason final: {anthropic_client_response.stop_reason}")
    print("="*80 + "\n")

    output = {
        "answer": anthropic_client_response.content[0].text,
        "output": anthropic_client_response.content,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        'model_name': model_name
    }

    return output

if __name__ == '__main__':

    # FLUJO PARA PROBAR EL AGENTE EN LOCAL
    messages=[]
    while True:
        query = input("\nUsuario (escribe 'salir' para terminar): ")

        if query.lower().strip() in ['salir']:
            print("¡Hasta luego!")
            break

        data = {
            'type': 'text',
            'body': query
        }

        answer = responder_usuario(
            messages=messages,
            data=data,
            telefono="5566098295"
        )

        print(
            f'Respuesta: {answer['answer']}'
            )

        messages.append({
            'role': 'assistant',
            'content': answer['answer']
            })