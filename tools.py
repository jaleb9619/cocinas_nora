# Generación de tools dinámicos basada en la configuración de la cocina de cada cliente.
def generar_tools(campos_platillos_validos):

    # Campos fijos que no son tiempos del menú
    CAMPOS_FIJOS = ['a_la_carta', 'extra_1', 'extra_2', 'extra_3', 'desechables', 'nombre_completo']

    # Generar properties dinámicas para los tiempos del menú
    properties_menu = {}
    for campo in campos_platillos_validos:
        if campo not in CAMPOS_FIJOS:
            properties_menu[campo] = {
                'type': 'string',
                'description': f'Platillo de {campo.replace("_", " ")} que el cliente desea ordenar.'
            }

    # Generar enum dinámico para el campo 'tiempo' en editar_orden y editar_pedido_confirmado
    enum_tiempos = list(properties_menu.keys()) + ['a_la_carta', 'extra_1', 'extra_2', 'extra_3']

    return [
        {
            'name': 'informacion_menu',
            'description': 'Función para ofrecer información general del menú disponible.',
            'input_schema': {
                'type': 'object',
                'properties': {
                    'consulta': {
                        'type': 'string',
                        'description': 'Consulta del cliente sobre el menú disponible.'
                    }
                },
                'required': ['consulta']
            }
        },
        {
            'name': 'ordenar',
            'description': 'Función para determinar UNA SOLA ORDEN del cliente de manera precisa. Si el cliente no menciona un platillo relacionado a la carta, no insistas el campo es NULL',
            'input_schema': {
                'type': 'object',
                'properties': {
                    'nombre_completo': {
                        'type': 'string',
                        'description': 'Nombre completo del cliente. Al menos un nombre y un apellido'
                    },
                    **properties_menu,
                    'a_la_carta': {
                        'type': 'string',
                        'description': 'Platillo a la carta que el cliente desea ordenar.'
                    },
                    'extra_1': {
                        'type': 'string',
                        'description': 'Platillo extra que el cliente desea ordenar.'
                    },
                    'extra_2': {
                        'type': 'string',
                        'description': 'Platillo extra que el cliente desea ordenar.'
                    },
                    'extra_3': {
                        'type': 'string',
                        'description': 'Platillo extra que el cliente desea ordenar.'
                    },
                    'desechables': {
                        'type': 'string',
                        'description': 'Indica si el cliente desea desechables para su pedido. Los valores posibles son "Sí" o "No"'
                    },
                },
                'required': ['nombre_completo']
            }
        },
        {
            'name': 'editar_orden',
            'description': 'Función para editar la orden temporal del cliente ANTES de confirmarla con su nombre. Permite eliminar órdenes, cambiar platillos, agregar o quitar elementos.',
            'input_schema': {
                'type': 'object',
                'properties': {
                    'accion': {
                        'type': 'string',
                        'enum': ['eliminar_orden', 'cambiar_platillo', 'agregar_platillo', 'quitar_platillo'],
                        'description': 'Tipo de edición a realizar: eliminar_orden (elimina una comida completa), cambiar_platillo (reemplaza un platillo por otro), agregar_platillo (añade un platillo a una orden), quitar_platillo (elimina un platillo de una orden)'
                    },
                    'orden_numero': {
                        'type': 'integer',
                        'description': 'Número de la orden a editar (1, 2, 3, etc). Si no se especifica y la acción lo requiere, se aplicará a la última orden.'
                    },
                    'tiempo': {
                        'type': 'string',
                        'enum': enum_tiempos,
                        'description': 'Categoría del platillo a modificar (primer_tiempo, segundo_tiempo, etc)'
                    },
                    'platillo_quitar': {
                        'type': 'string',
                        'description': 'Nombre del platillo a quitar (usado en cambiar_platillo y quitar_platillo)'
                    },
                    'platillo_agregar': {
                        'type': 'string',
                        'description': 'Nombre del platillo a agregar (usado en cambiar_platillo y agregar_platillo)'
                    },
                    'aplicar_a_todas': {
                        'type': 'boolean',
                        'description': 'Si es true, aplica el cambio a todas las órdenes (solo para agregar_platillo y quitar_platillo)'
                    }
                },
                'required': ['accion']
            }
        },
        {
            'name': 'editar_pedido_confirmado',
            'description': 'Función para editar un pedido que YA FUE CONFIRMADO con nombre, pero solo si ninguna de sus comandas está en proceso o terminada. Permite las mismas acciones que editar_orden pero trabaja sobre pedidos guardados en la base de datos.',
            'input_schema': {
                'type': 'object',
                'properties': {
                    'accion': {
                        'type': 'string',
                        'enum': ['eliminar_orden', 'cambiar_platillo', 'agregar_platillo', 'quitar_platillo', 'agregar_comanda'],
                        'description': 'Tipo de edición a realizar sobre el pedido confirmado'
                    },
                    'orden_numero': {
                        'type': 'integer',
                        'description': 'Número de la comanda dentro del pedido a editar (1, 2, 3, etc)'
                    },
                    'tiempo': {
                        'type': 'string',
                        'enum': enum_tiempos,
                        'description': 'Categoría del platillo a modificar'
                    },
                    'platillo_quitar': {
                        'type': 'string',
                        'description': 'Nombre del platillo a quitar'
                    },
                    'platillo_agregar': {
                        'type': 'string',
                        'description': 'Nombre del platillo a agregar'
                    },
                    'platillos_nuevos': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Lista de nombres de platillos para la nueva comanda (usado en agregar_comanda). Ej: ["flan napolitano"]'
                    },
                },
                'required': ['accion']
            }
        },
        {
            'name': 'confirmar_entrega',
            'description': 'Función para confirmar el tipo de entrega del pedido DESPUÉS de que el cliente ya dio su nombre y se confirmaron los platillos. Siempre se debe llamar esta función antes de cerrar el pedido.',
            'input_schema': {
                'type': 'object',
                'properties': {
                    'tipo_entrega': {
                        'type': 'string',
                        'enum': ['domicilio', 'recoger'],
                        'description': 'Indica si el cliente quiere entrega a domicilio o si va a recoger su pedido en el local.'
                    },
                    'direccion': {
                        'type': 'string',
                        'description': 'Dirección completa del cliente (calle, número, colonia). Solo requerida si tipo_entrega es domicilio.'
                    },
                    'referencia_1': {
                        'type': 'string',
                        'description': 'Primera referencia para ubicar el domicilio (ej: "entre calles Morelos y Juárez, a lado de una casa naranja"). Solo requerida si tipo_entrega es domicilio.'
                    },
                    'referencia_2': {
                        'type': 'string',
                        'description': 'Segunda referencia adicional para ubicar el domicilio (ej: "frente a la farmacia del ahorro, en la esquina de la avenida juarez"). Solo requerida si tipo_entrega es domicilio.'
                    }
                },
                'required': ['tipo_entrega']
            }
        }
    ]


# TOOLS ORIGINAL 
# tools = [
#     {
#         'name': 'informacion_menu',
#         'description': 'Función para ofrecer información general del menú disponible.',
#         'input_schema': {
#                 'type': 'object',
#                 'properties': {
#                     'consulta': {
#                         'type': 'string',
#                         'description': 'Consulta del cliente sobre el menú disponible.'
#                     }
#                 },
#             'required': ['consulta']
#         }
#     },
#     {
#         'name': 'ordenar',
#         'description': 'Función para determinar UNA SOLA ORDEN del cliente de manera precisa. Si el cliente no menciona un platillo relacionado a la carta, no insistas el campo es NULL',
#         'input_schema': {
#             'type': 'object',
#             'properties': {
#                 'nombre_completo': {
#                     'type': 'string',
#                     'description': 'Nombre completo del cliente. Al menos un nombre y un apellido'
#                 },
#                 'primer_tiempo': {
#                     'type': 'string',
#                     'description': 'Plato del primer tiempo que el cliente desea ordenar.'
#                 },
#                 'segundo_tiempo': {
#                     'type': 'string',
#                     'description': 'Plato del segundo tiempo que el cliente desea ordenar.'
#                 },
#                 'tercer_tiempo': {
#                     'type': 'string',
#                     'description': 'Plato del tercer tiempo que el cliente desea ordenar.'
#                 },
#                 'postre': {
#                     'type': 'string',
#                     'description': 'Postre que el cliente desea ordenar.'
#                 },
#                 'agua': {
#                     'type': 'string',
#                     'description': 'Agua de sabor que el cliente desea ordenar.'
#                 },
#                 'a_la_carta': {
#                     'type': 'string',
#                     'description': 'Platillo a la carta que el cliente desea ordenar.'
#                 },
#                 'extra_1': {
#                     'type': 'string',
#                     'description': 'Platillo extra que el cliente desea ordenar.'
#                 },
#                 'extra_2': {
#                     'type': 'string',
#                     'description': 'Platillo extra que el cliente desea ordenar.'
#                 },
#                 'extra_3': {
#                     'type': 'string',
#                     'description': 'Platillo extra que el cliente desea ordenar.'
#                 },
#                 'desechables': {
#                     'type': 'string',
#                     'description': 'Indica si el cliente desea desechables para su pedido. Los valores posibles son "Sí" o "No"'
#                 },
#             },
#             # 'required': ['nombre_completo', 'primer_tiempo', 'segundo_tiempo', 'tercer_tiempo', 'postre', 'agua', 'a_la_carta']
#             'required': ['nombre_completo']
#         }
#     },
#     {
#         'name': 'editar_orden',
#         'description': 'Función para editar la orden temporal del cliente ANTES de confirmarla con su nombre. Permite eliminar órdenes, cambiar platillos, agregar o quitar elementos.',
#         'input_schema': {
#             'type': 'object',
#             'properties': {
#                 'accion': {
#                     'type': 'string',
#                     'enum': ['eliminar_orden', 'cambiar_platillo', 'agregar_platillo', 'quitar_platillo'],
#                     'description': 'Tipo de edición a realizar: eliminar_orden (elimina una comida completa), cambiar_platillo (reemplaza un platillo por otro), agregar_platillo (añade un platillo a una orden), quitar_platillo (elimina un platillo de una orden)'
#                 },
#                 'orden_numero': {
#                     'type': 'integer',
#                     'description': 'Número de la orden a editar (1, 2, 3, etc). Si no se especifica y la acción lo requiere, se aplicará a la última orden.'
#                 },
#                 'tiempo': {
#                     'type': 'string',
#                     'enum': ['primer_tiempo', 'segundo_tiempo', 'tercer_tiempo', 'postre', 'agua', 'a_la_carta', 'extra_1', 'extra_2', 'extra_3'],
#                     'description': 'Categoría del platillo a modificar (primer_tiempo, segundo_tiempo, etc)'
#                 },
#                 'platillo_quitar': {
#                     'type': 'string',
#                     'description': 'Nombre del platillo a quitar (usado en cambiar_platillo y quitar_platillo)'
#                 },
#                 'platillo_agregar': {
#                     'type': 'string',
#                     'description': 'Nombre del platillo a agregar (usado en cambiar_platillo y agregar_platillo)'
#                 },
#                 'aplicar_a_todas': {
#                     'type': 'boolean',
#                     'description': 'Si es true, aplica el cambio a todas las órdenes (solo para agregar_platillo y quitar_platillo)'
#                 }
#             },
#             'required': ['accion']
#         }
#     },
#     {
#         'name': 'editar_pedido_confirmado',
#         'description': 'Función para editar un pedido que YA FUE CONFIRMADO con nombre, pero solo si ninguna de sus comandas está en proceso o terminada. Permite las mismas acciones que editar_orden pero trabaja sobre pedidos guardados en la base de datos.',
#         'input_schema': {
#             'type': 'object',
#             'properties': {
#                 'accion': {
#                     'type': 'string',
#                     'enum': ['eliminar_orden', 'cambiar_platillo', 'agregar_platillo', 'quitar_platillo', 'agregar_comanda'],
#                     'description': 'Tipo de edición a realizar sobre el pedido confirmado'
#                 },
#                 'orden_numero': {
#                     'type': 'integer',
#                     'description': 'Número de la comanda dentro del pedido a editar (1, 2, 3, etc)'
#                 },
#                 'tiempo': {
#                     'type': 'string',
#                     'enum': ['primer_tiempo', 'segundo_tiempo', 'tercer_tiempo', 'postre', 'agua', 'a_la_carta', 'extra_1', 'extra_2', 'extra_3'],
#                     'description': 'Categoría del platillo a modificar'
#                 },
#                 'platillo_quitar': {
#                     'type': 'string',
#                     'description': 'Nombre del platillo a quitar'
#                 },
#                 'platillo_agregar': {
#                     'type': 'string',
#                     'description': 'Nombre del platillo a agregar'
#                 },
#                 'platillos_nuevos': {
#                     'type': 'array',
#                     'items': {'type': 'string'},
#                     'description': 'Lista de nombres de platillos para la nueva comanda (usado en agregar_comanda). Ej: ["flan napolitano"]'
#                 },
#             },
#             'required': ['accion']
#         }
#     },
#     {
#         'name': 'confirmar_entrega',
#         'description': 'Función para confirmar el tipo de entrega del pedido DESPUÉS de que el cliente ya dio su nombre y se confirmaron los platillos. Siempre se debe llamar esta función antes de cerrar el pedido.',
#         'input_schema': {
#             'type': 'object',
#             'properties': {
#                 'tipo_entrega': {
#                     'type': 'string',
#                     'enum': ['domicilio', 'recoger'],
#                     'description': 'Indica si el cliente quiere entrega a domicilio o si va a recoger su pedido en el local.'
#                 },
#                 'direccion': {
#                     'type': 'string',
#                     'description': 'Dirección completa del cliente (calle, número, colonia). Solo requerida si tipo_entrega es domicilio.'
#                 },
#                 'referencia_1': {
#                     'type': 'string',
#                     'description': 'Primera referencia para ubicar el domicilio (ej: "entre calles Morelos y Juárez, a lado de una casa naranja"). Solo requerida si tipo_entrega es domicilio.'
#                 },
#                 'referencia_2': {
#                     'type': 'string',
#                     'description': 'Segunda referencia adicional para ubicar el domicilio (ej: "frente a la farmacia del ahorro, en la esquina de la avenida juarez"). Solo requerida si tipo_entrega es domicilio.'
#                 }
#             },
#             'required': ['tipo_entrega']
#         }
#     }
# ]