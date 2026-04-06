# 🍽️ Sistema de Agente de Cocinas - Backend

Sistema de automatización de pedidos para cocinas económicas mediante WhatsApp, utilizando IA conversacional (Claude de Anthropic) para gestionar menús, tomar órdenes, editar pedidos y procesar mensajes multimedia.

## 📋 Tabla de Contenidos

- [Descripción General](#-descripción-general)
- [Arquitectura del Sistema](#-arquitectura-del-sistema)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Tecnologías Utilizadas](#-tecnologías-utilizadas)
- [Variables de Entorno](#-variables-de-entorno)
- [Instalación y Configuración](#-instalación-y-configuración)
- [Flujo de Conversación](#-flujo-de-conversación)
- [Componentes Principales](#-componentes-principales)
- [Base de Datos](#-base-de-datos)
- [Procesamiento de Mensajes](#-procesamiento-de-mensajes)
- [Gestión de Órdenes](#-gestión-de-órdenes)
- [Procesamiento Multimedia](#-procesamiento-multimedia)
- [Deployment](#-deployment)

---

## 🎯 Descripción General

Este sistema automatiza completamente el proceso de toma de pedidos para cocinas económicas a través de WhatsApp. Los clientes pueden:

- 📱 Consultar el menú del día
- 🛒 Realizar múltiples pedidos en una sola conversación
- ✏️ Editar pedidos antes de confirmar (órdenes temporales)
- 🔄 Modificar pedidos ya confirmados (si están en estado PENDIENTE)
- 🎤 Enviar pedidos por audio (transcripción automática)
- 📸 Enviar imágenes (procesamiento con vision AI)

El sistema mantiene conversaciones naturales en español usando Claude Sonnet 4 de Anthropic, gestiona estado en Redis, y persiste datos en Supabase (PostgreSQL).

---

## 🏗️ Arquitectura del Sistema

```
┌─────────────────┐
│   WhatsApp      │
│   (WASender)    │
└────────┬────────┘
         │ Webhook
         ▼
┌─────────────────────────────────────────────┐
│          FastAPI (app.py)                   │
│  • Endpoint: /api/v1/webhook                │
│  • Timeout: 2s keep-alive                   │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│    procesa_mensajes.py                      │
│  • Deduplicación (Redis)                    │
│  • Enrutamiento por tipo de mensaje        │
│  • Filtrado de mensajes propios/grupos     │
└────────┬────────────────────────────────────┘
         │
         ├─────────────┬──────────────┬────────────────┐
         │             │              │                │
         ▼             ▼              ▼                ▼
    ┌────────┐   ┌──────────┐   ┌─────────┐    ┌──────────┐
    │ Texto  │   │  Audio   │   │ Imagen  │    │ Comando  │
    │        │   │  (async) │   │ (sync)  │    │ (borrar) │
    └───┬────┘   └────┬─────┘   └────┬────┘    └────┬─────┘
        │             │              │              │
        │             ▼              │              │
        │      ┌──────────────┐     │              │
        │      │ audio_queue  │     │              │
        │      │   (Redis)    │     │              │
        │      └──────┬───────┘     │              │
        │             │              │              │
        │             ▼              │              │
        │      ┌──────────────┐     │              │
        │      │worker_audio  │     │              │
        │      │  (Whisper)   │     │              │
        │      └──────┬───────┘     │              │
        │             │              │              │
        ▼             ▼              ▼              ▼
    ┌─────────────────────────────────────────────────┐
    │              agente.py                          │
    │  • Claude API (Anthropic)                       │
    │  • Tool calling (4 funciones)                   │
    │  • Gestión de órdenes temporales                │
    │  • Confirmación y persistencia                  │
    └────────┬────────────────────────────────────────┘
             │
             ├──────────────┬─────────────────┐
             │              │                 │
             ▼              ▼                 ▼
        ┌────────┐    ┌─────────┐      ┌──────────┐
        │ Redis  │    │Supabase │      │WASender  │
        │        │    │         │      │   API    │
        │ • Chat │    │ • Orden │      │          │
        │   hist │    │ • Client│      │ Envío msg│
        │ • Temp │    │ • Platil│      └──────────┘
        │   order│    │ • Desgl │
        └────────┘    └─────────┘
```

### Flujo de Datos

1. **Webhook de WASender** → Recibe mensaje de WhatsApp
2. **Procesamiento** → Deduplicación, filtrado, enrutamiento
3. **Agente IA** → Claude procesa con herramientas (tools)
4. **Persistencia** → Redis (temporal) y Supabase (permanente)
5. **Respuesta** → Envío a WhatsApp vía WASender API

---

## 📁 Estructura del Proyecto

```
cocinas_beta/
│
├── app.py                      # Punto de entrada FastAPI
├── procesa_mensajes.py         # Procesador principal de mensajes
├── agente.py                   # Lógica del agente conversacional
├── worker_audio.py             # Worker asíncrono para audios
│
├── clients/                    # Clientes de servicios externos
│   ├── anthropic_client.py     # Cliente de Anthropic Claude
│   ├── openai_client.py        # Cliente de OpenAI (Whisper)
│   ├── redis_client.py         # Cliente de Redis
│   └── supabase_client.py      # Cliente de Supabase
│
├── system_prompts.py           # Prompts del sistema para Claude
├── tools.py                    # Definición de herramientas (function calling)
├── chat_history.py             # Gestión del historial en Redis
│
├── fct_tools_infomenu.py       # Función: consultar menú
├── fct_tools_ordenar.py        # Función: extraer IDs, calcular costos
├── fct_editar_pedido.py        # Función: editar pedidos confirmados
├── fct_supabase.py             # Operaciones genéricas de BD
│
├── image_processor.py          # Procesamiento de imágenes (Vision AI)
├── whisper.py                  # Transcripción de audios
├── utils.py                    # Utilidades (extract phone, tokens)
│
├── decorador_costos.py         # Decorador para tracking de costos
├── requirements.txt            # Dependencias
├── Procfile                    # Configuración Heroku/Railway
└── .env                        # Variables de entorno
```

---

## 🛠️ Tecnologías Utilizadas

### Backend
- **FastAPI** - Framework web asíncrono
- **Uvicorn** - Servidor ASGI
- **Python 3.13+** - Lenguaje base

### IA & Machine Learning
- **Anthropic Claude Sonnet 4** - Agente conversacional
- **OpenAI Whisper** - Transcripción de audio
- **Claude Vision API** - Análisis de imágenes

### Base de Datos & Caché
- **Supabase (PostgreSQL)** - BD relacional
- **Redis Cloud** - Caché y gestión de estado

### Servicios Externos
- **WASender API** - Integración con WhatsApp

### Librerías Principales
```
anthropic
supabase
redis
openai
fastapi
uvicorn
tiktoken
python-dotenv
```

---

## 🔐 Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto:

```bash
# ============================================
# ANTHROPIC (Claude API)
# ============================================
ANTHROPIC_API_KEY=sk-ant-api03-...
MODEL_NAME=claude-sonnet-4-20250514

# ============================================
# OPENAI (Whisper para transcripción)
# ============================================
OPENAI_API_KEY=sk-...

# ============================================
# SUPABASE (Base de Datos)
# ============================================
SUPABASE_URL=https://xxxxx.supabase.co/
SUPABASE_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# ============================================
# TABLAS DE SUPABASE
# ============================================
TBL_COMANDAS=tbl_cocina_comandas
TBL_DESGLOSE=tbl_cocina_desglose
TBL_PLATILLOS=tbl_cocina_platillos
TBL_TIEMPOS=tbl_cocina_tiempos
TBL_CLIENTES=tbl_cocina_clientes

# ============================================
# REDIS (Caché y Estado)
# ============================================
REDIS_HOST=redis-xxxxx.c245.us-east-1-3.ec2.cloud.redislabs.com
REDIS_PORT=10481
REDIS_PASSWORD=xxxxxxxxxxxxx

# ============================================
# WASENDER (WhatsApp API)
# ============================================
WASENDER_PERSONAL_ACCESS_TOKEN=xxxxx
WASENDER_API_KEY=xxxxx

# ============================================
# CONFIGURACIÓN DEL NEGOCIO
# ============================================
USER_ID=45c1bd6a-1a5c-4dce-a0cb-2a8e2caf8943
BUSINESS_NAME=Cocinas Beta
AGENT_NAME=Lucía

# ============================================
# OPCIONAL
# ============================================
PORT=5001
TIEMPO_NUEVO=28800  # TTL de chat history en segundos (8 horas)
```

### Descripción de Variables Clave

| Variable | Descripción |
|----------|-------------|
| `USER_ID` | Identificador del usuario/negocio en el sistema. Se usa para filtrar datos en todas las consultas a Supabase |
| `MODEL_NAME` | Modelo de Claude a utilizar (debe coincidir con la API key) |
| `TIEMPO_NUEVO` | Tiempo de expiración del historial en Redis (default: 8 horas) |
| `BUSINESS_NAME` | Nombre del negocio (usado en prompts) |
| `AGENT_NAME` | Nombre del asistente virtual (usado en prompts) |

---

## 🚀 Instalación y Configuración

### 1. Clonar el Repositorio

```bash
git clone <repository-url>
cd cocinas_beta
```

### 2. Crear Entorno Virtual

```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

### 3. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar Variables de Entorno

```bash
cp .env.example .env
# Edita .env con tus credenciales
```

### 5. Verificar Conexiones

Los clientes se inicializan en `clients/`:
- `redis_client.py` - Conexión a Redis
- `supabase_client.py` - Conexión a Supabase
- `anthropic_client.py` - Cliente de Anthropic
- `openai_client.py` - Cliente de OpenAI

Cada archivo exporta un cliente singleton que se importa en los demás módulos.

### 6. Ejecutar el Sistema

#### Modo Desarrollo (con reload)
```bash
uvicorn app:app --host 0.0.0.0 --port 5001 --reload
```

#### Modo Producción (2 procesos)
```bash
# Terminal 1 - API Principal
python app.py

# Terminal 2 - Worker de Audios
python worker_audio.py
```

#### Con Heroku/Railway (usando Procfile)
```bash
# El Procfile define:
web: python app.py
worker: python worker_audio.py
```

---

## 💬 Flujo de Conversación

### Identificador de Sesión

El sistema usa un identificador único por usuario basado en teléfono + hora:

```python
id_conversacion = f"fp-idPhone:{phone_number}_{YYYY-MM-DD_HH}"
# Ejemplo: fp-idPhone:5215512345678_2025-02-16_14
```

**Características:**
- Se renueva cada hora automáticamente
- Agrupa todas las órdenes de una sesión horaria
- Usado como `pedido_grupo` en la BD

### Flujo Completo de una Conversación

```
1. Usuario envía saludo
   ↓
2. Sistema responde con presentación y pregunta por menú
   ↓
3. Usuario solicita menú
   ↓
4. Sistema llama tool "informacion_menu" → Consulta BD
   ↓
5. Usuario ordena platillos (sin nombre)
   ↓
6. Sistema llama tool "ordenar" SIN nombre_completo
   ↓
7. Redis guarda ORDEN TEMPORAL con estructura:
   {
     "pedido_grupo": "fp-idPhone:521..._2025-02-16_14",
     "ordenes": [
       {
         "orden_numero": 1,
         "platillos": {...},
         "costos": {...}
       }
     ],
     "total_ordenes": 1,
     "monto_total_general": 200
   }
   ↓
8. Usuario puede:
   a) Agregar más comidas → Repite paso 6
   b) Editar comidas → Tool "editar_orden"
   c) Confirmar → Proporciona nombre
   ↓
9. Usuario da nombre completo
   ↓
10. Sistema llama tool "ordenar" CON nombre_completo
    ↓
11. Sistema persiste TODAS las órdenes en Supabase:
    - Tabla tbl_cocina_comandas (una fila por comida)
    - Tabla tbl_cocina_desglose (platillos de cada comida)
    ↓
12. Redis elimina orden temporal
    ↓
13. Sistema confirma pedido con detalles
```

---

## 🧩 Componentes Principales

### 1. `app.py` - Servidor FastAPI

**Endpoints:**
```python
GET  /              # Health check simple
GET  /health        # Health check con JSON
GET  /api/v1/webhook    # Recepción de mensajes (webhook)
POST /api/v1/webhook    # Recepción de mensajes (webhook)
```

**Configuración:**
- CORS habilitado para todos los orígenes
- Timeout de 2 segundos (keep-alive bajo)
- Puerto configurable vía env var (default: 5001)

### 2. `procesa_mensajes.py` - Procesador Central

**Responsabilidades:**
1. **Validación de eventos** - Solo procesa eventos válidos de WASender
2. **Deduplicación** - Evita procesar el mismo mensaje dos veces
3. **Filtrado** - Ignora mensajes de grupos y mensajes propios
4. **Enrutamiento por tipo:**
   - `text` → Procesamiento síncrono
   - `audio/ptt` → Encola para worker asíncrono
   - `image` → Procesamiento síncrono (3-6s)
   - Comando especial: "borrar memoria"

**Deduplicación:**
```python
dedup_key = f"msg:{phone_number}:{timestamp}"
# TTL: 600 segundos (10 minutos)
```

**Eventos válidos:**
```python
eventos_validos = [
    'messages.received',
    'chats.update',
    'messages-personal.received'
]
```

### 3. `agente.py` - Lógica del Agente

**Flujo principal:**
```python
def responder_usuario(messages, data, telefono, id_conversacion, ...):
    1. Si es nuevo usuario → Usa prompt_saludo
    2. Si usuario existente → Usa prompt_first_response
    3. Llama a Claude con tool_choice={"type": "any"}
    4. Loop mientras stop_reason == 'tool_use':
       - Ejecuta herramienta solicitada
       - Prepara tool_result
       - Vuelve a llamar a Claude
    5. Retorna respuesta final
```

**Herramientas disponibles (tools):**
1. `informacion_menu` - Consulta menú del día
2. `ordenar` - Registra orden (temporal o confirmada)
3. `editar_orden` - Modifica orden temporal
4. `editar_pedido_confirmado` - Modifica pedido en BD

### 4. `tools.py` - Definición de Herramientas

Cada tool define:
- `name` - Nombre de la función
- `description` - Cuándo usarla
- `input_schema` - Parámetros esperados (JSON Schema)
- `required` - Campos obligatorios

**Ejemplo de tool:**
```python
{
    'name': 'ordenar',
    'description': 'Función para determinar UNA SOLA ORDEN del cliente...',
    'input_schema': {
        'type': 'object',
        'properties': {
            'nombre_completo': {'type': 'string', ...},
            'primer_tiempo': {'type': 'string', ...},
            'segundo_tiempo': {'type': 'string', ...},
            ...
        },
        'required': ['nombre_completo']
    }
}
```

### 5. `system_prompts.py` - Prompts del Sistema

**Dos prompts principales:**

1. **`prompt_saludo`** - Para nuevos usuarios
   - Detecta tipo de saludo
   - Responde apropiadamente
   - Se presenta como {AGENT_NAME} de {BUSINESS_NAME}

2. **`prompt_first_response`** - Para conversación principal
   - Objetivos claros (consulta menú, tomar orden, editar, confirmar)
   - Reglas de uso de herramientas
   - Flujo completo de orden temporal → confirmada
   - Instrucciones para edición pre/post confirmación

### 6. `chat_history.py` - Gestión de Historial

**Funciones principales:**

```python
get_chat_history(chat_history_id, telefono)
# Recupera historial desde Redis

add_to_chat_history(chat_history_id, mensaje, rol, telefono)
# Agrega mensaje con gestión de token budget (30k tokens)

reset_chat_history(chat_history_id)
# Elimina historial (comando "borrar memoria")

# === Gestión de Órdenes Temporales ===
get_orden_temporal(telefono)
# Recupera orden temporal desde Redis

save_orden_temporal(telefono, orden_data, ttl=1800)
# Guarda/actualiza orden temporal (TTL: 30 min)

delete_orden_temporal(telefono)
# Elimina orden temporal al confirmar
```

**Keys en Redis:**
```
fp-chatHistory:{phone_with_jid}     # Historial de chat
fp-idPhone:{phone_number}           # Datos del usuario
orden_temporal:{phone_number}       # Orden en proceso
msg:{phone}:{timestamp}             # Deduplicación
audio_processed:{phone}:{timestamp} # Dedup audio
audio_queued:{phone}:{timestamp}    # Dedup encolar audio
```

---

## 🗄️ Base de Datos

### Esquema de Supabase

#### Tabla: `tbl_cocina_platillos`
Catálogo de platillos disponibles.

```sql
CREATE TABLE tbl_cocina_platillos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    platillo VARCHAR(255) NOT NULL,
    precio DECIMAL(10,2) NOT NULL,
    tiempo_id INTEGER NOT NULL,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Campos clave:**
- `tiempo_id` - Categoría: 1=primer tiempo, 2=segundo, 3=tercer, 4=agua, 5=postre, 6=a la carta, 7=extras

#### Tabla: `tbl_cocina_tiempos`
Catálogo de categorías/tiempos.

```sql
CREATE TABLE tbl_cocina_tiempos (
    id INTEGER PRIMARY KEY,
    user_id UUID NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    orden INTEGER NOT NULL
);
```

**Ejemplo de datos:**
```
id | nombre          | orden
1  | Primer Tiempo   | 1
2  | Segundo Tiempo  | 2
3  | Tercer Tiempo   | 3
4  | Aguas           | 4
5  | Postres         | 5
```

#### Tabla: `tbl_cocina_comandas`
Registro de comandas (cada comida es una comanda).

```sql
CREATE TABLE tbl_cocina_comandas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    cliente_nombre VARCHAR(255) NOT NULL,
    pedido_grupo VARCHAR(255) NOT NULL,  -- id_conversacion
    monto_estandar DECIMAL(10,2) DEFAULT 0,
    monto_extras DECIMAL(10,2) DEFAULT 0,
    monto_desechables DECIMAL(10,2) DEFAULT 0,
    monto_total DECIMAL(10,2) NOT NULL,
    status VARCHAR(50) DEFAULT 'PENDIENTE',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Índices importantes
CREATE INDEX idx_pedido_grupo ON tbl_cocina_comandas(pedido_grupo);
CREATE INDEX idx_status ON tbl_cocina_comandas(status);
```

**Estados posibles:**
- `PENDIENTE` - Recién creada, editable
- `EN_PROCESO` - En cocina, no editable
- `LISTO_COCINA` - Terminada en cocina
- `ENTREGADO` - Entregada al cliente
- `CANCELADO` - Cancelada

#### Tabla: `tbl_cocina_desglose`
Detalle de platillos por comanda (relación N:M).

```sql
CREATE TABLE tbl_cocina_desglose (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    comanda_id UUID NOT NULL REFERENCES tbl_cocina_comandas(id) ON DELETE CASCADE,
    platillo_id UUID NOT NULL REFERENCES tbl_cocina_platillos(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_comanda_id ON tbl_cocina_desglose(comanda_id);
CREATE INDEX idx_platillo_id ON tbl_cocina_desglose(platillo_id);
```

#### Tabla: `tbl_cocina_clientes`
Información de clientes (para búsqueda por teléfono).

```sql
CREATE TABLE tbl_cocina_clientes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    telefono VARCHAR(20) UNIQUE NOT NULL,
    nombre VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_telefono ON tbl_cocina_clientes(telefono);
```

### Relaciones

```
tbl_cocina_platillos
    ↓ (1:N)
tbl_cocina_desglose
    ↓ (N:1)
tbl_cocina_comandas
    ↓ (agrupadas por)
pedido_grupo (id_conversacion)
```

---

## 📨 Procesamiento de Mensajes

### Tipos de Mensajes Soportados

#### 1. Mensajes de Texto
**Procesamiento:** Síncrono (inmediato)

```python
# Flujo
1. Validación y deduplicación
2. Extracción de teléfono
3. Verificación en Redis (user_data)
4. Obtención de historial
5. Llamada a agente.responder_usuario()
6. Envío de respuesta
7. Guardado en historial
```

#### 2. Mensajes de Audio/PTT
**Procesamiento:** Asíncrono (worker)

```python
# Flujo
1. Deduplicación especial (audio_queued)
2. Creación de job con metadata
3. Encolar en Redis (audio_queue)
4. Responder "AudioQueued" inmediatamente
5. Worker procesa:
   - Descarga audio
   - Transcribe con Whisper
   - Procesa como texto
   - Envía respuesta
```

**Ventaja:** No bloquea el webhook (WASender tiene timeout de ~30s)

#### 3. Mensajes de Imagen
**Procesamiento:** Síncrono (3-6 segundos)

```python
# Flujo
1. Extracción de datos de imagen
2. Descifrado con WASender API
3. Conversión a base64
4. Envío a Claude Vision API
5. Generación de respuesta
6. Envío al usuario
```

**System prompt para imágenes:**
```
Eres un asistente experto en análisis de imágenes de vehículos.
Para imágenes de vehículos o accidentes:
- Identifica marca, modelo y color
- Describe daños en detalle
- Indica ubicación de daños
- Evalúa severidad
Sé claro y profesional.
```

#### 4. Comando Especial: "Borrar Memoria"

```python
if 'borrar memoria' in data['body'].lower():
    reset_chat_history(f"521{phone_number}")
    enviar_mensaje(data["from"], "✅ Tu memoria ha sido borrada.")
    return resultado
```

### Deduplicación Multinivel

```python
# Nivel 1: Mensaje general
msg:{phone}:{timestamp}

# Nivel 2: Audio encolado
audio_queued:{phone}:{timestamp}

# Nivel 3: Audio procesado
audio_processed:{phone}:{timestamp}
```

Todos con TTL de 600 segundos (10 minutos).

### Filtrado de Mensajes No Válidos

```python
# Ignorar grupos
is_group_from = data['from'].find('@g.us') != -1
is_group_to = data['to'].find('@g.us') != -1

# Ignorar mensajes propios
is_from_me = data.get('fromMe', False)

# Ignorar eventos no válidos
evento_invalido = json_data.get('event') not in eventos_validos
```

---

## 🛒 Gestión de Órdenes

### Orden Temporal (Redis)

**Estructura:**
```python
{
    "pedido_grupo": "fp-idPhone:521..._2025-02-16_14",
    "ordenes": [
        {
            "orden_numero": 1,
            "platillos": {
                "primer_tiempo": "Sopa de lentejas",
                "segundo_tiempo": "Pollo en mole",
                "tercer_tiempo": "Arroz rojo",
                "postre": "Flan napolitano",
                "agua": "Jamaica",
                "a_la_carta": [],
                "extra_1": "",
                "extra_2": ""
            },
            "desechables": False,
            "costos": {
                "monto_estandar": 200,
                "monto_extras": 0,
                "monto_desechables": 0,
                "monto_total": 200
            }
        }
    ],
    "total_ordenes": 1,
    "monto_total_general": 200,
    "nombre_cliente": None  # Null hasta que confirma
}
```

**TTL:** 1800 segundos (30 minutos)

### Cálculo de Costos

**Lógica en `fct_tools_ordenar.py`:**

```python
def determinar_costo_comanda(tool_input):
    # CASO 1: Comida completa (3 tiempos)
    if tiene_3_tiempos:
        monto_estandar = 200
        monto_extras = suma_de_extras
    
    # CASO 2: Comida parcial
    else:
        monto_estandar = suma_de_precios_individuales
    
    # CASO 3: Desechables
    if desechables == "Sí":
        monto_desechables = cantidad_platillos * 5
    
    monto_total = monto_estandar + monto_extras + monto_desechables
```

### Edición de Órdenes

#### Editar ANTES de Confirmar (Redis)

**Tool:** `editar_orden`

**Acciones disponibles:**
```python
'eliminar_orden'     # Elimina una comida completa
'cambiar_platillo'   # Reemplaza un platillo por otro
'agregar_platillo'   # Añade un platillo
'quitar_platillo'    # Elimina un platillo
```

**Parámetros:**
```python
{
    'accion': 'cambiar_platillo',
    'orden_numero': 2,  # Opcional, default: última
    'tiempo': 'segundo_tiempo',
    'platillo_quitar': 'Pollo en mole',
    'platillo_agregar': 'Bistec encebollado',
    'aplicar_a_todas': False  # Para agregar/quitar
}
```

**Proceso:**
1. Lee orden temporal de Redis
2. Aplica modificación
3. Recalcula costos
4. Actualiza total general
5. Guarda en Redis
6. Responde con resumen actualizado

#### Editar DESPUÉS de Confirmar (BD)

**Tool:** `editar_pedido_confirmado`

**Validaciones:**
1. Buscar pedido más reciente del usuario (por teléfono)
2. Verificar que TODAS las comandas estén en estado `PENDIENTE`
3. Si alguna está `EN_PROCESO` o posterior → No editable

**Proceso:**
1. Obtiene comandas del pedido_grupo
2. Aplica modificación (igual que orden temporal)
3. Actualiza BD:
   - DELETE en tbl_cocina_desglose
   - INSERT de nuevos platillos
   - UPDATE de costos en tbl_cocina_comandas
4. Responde con confirmación

**Funciones auxiliares en `fct_editar_pedido.py`:**
```python
obtener_pedido_reciente_usuario(telefono)
validar_pedido_editable(pedido_grupo)
obtener_comandas_con_platillos(pedido_grupo)
eliminar_comanda(comanda_id)
actualizar_platillos_comanda(comanda_id, nuevos_platillos_ids, nuevos_costos)
```

---

## 🎤 Procesamiento Multimedia

### Audio Processing (Asíncrono)

**Worker:** `worker_audio.py`

**Arquitectura:**
```
Message arrives → Queue in Redis → Worker picks up → Process → Respond
   (instant)         (background)        (30-60s)
```

**Ventajas:**
- No bloquea webhook
- Permite reintentos
- Escala horizontalmente

**Código del worker:**
```python
def run_worker():
    while True:
        # Bloquea hasta que haya un job
        result = r.brpop('audio_queue', timeout=1)
        
        if result:
            _, job_json = result
            job_data = json.loads(job_json)
            procesar_audio_job(job_data)
```

**Procesamiento:**
```python
def procesar_audio_job(job_data):
    1. Deduplicación (audio_processed)
    2. Transcripción con Whisper (30-60s)
    3. Procesamiento como mensaje de texto
    4. Respuesta del agente
    5. Envío a usuario
    6. Guardado en historial
```

### Image Processing (Síncrono)

**Limitación:** 3-6 segundos (aceptable para webhook)

**Flujo completo:**
```python
1. extraer_datos_imagen_wasender(json_data)
   → Obtiene: url, mimetype, mediaKey, caption
   
2. Descifrar con WASender API
   POST https://wasenderapi.com/api/decrypt-media
   Body: {url, mediaKey, mimetype}
   → Retorna: publicUrl
   
3. Descargar imagen descifrada
   GET publicUrl
   
4. Convertir a base64
   
5. Llamar a Claude Vision API
   anthropic_client.messages.create(
       model="claude-sonnet-4-20250514",
       messages=[{
           "role": "user",
           "content": [
               {"type": "image", "source": {...}},
               {"type": "text", "text": user_message}
           ]
       }]
   )
   
6. Responder al usuario
```

**System prompt para imágenes:**
Se enfoca en análisis de vehículos/accidentes (herencia del proyecto anterior).

---

## 📤 Deployment

### Heroku / Railway

**Procfile:**
```
web: python app.py
worker: python worker_audio.py
```

**Configuración:**
1. Crear aplicación en plataforma
2. Conectar repositorio
3. Agregar variables de entorno
4. Configurar 2 dynos/servicios:
   - `web` - API principal
   - `worker` - Procesador de audios
5. Deploy

### Variables de Entorno en Producción

Asegúrate de configurar TODAS las variables del archivo `.env` en el panel de configuración de la plataforma.

### Health Checks

```bash
# Verificar que la API esté viva
curl https://tu-app.herokuapp.com/health

# Respuesta esperada:
{"status": "ok"}
```

### Logs y Debugging

```bash
# Heroku
heroku logs --tail --app tu-app

# Railway
# Ver logs en el dashboard
```

---

## 🔧 Troubleshooting

### Mensajes Duplicados
**Problema:** El mismo mensaje se procesa dos veces.

**Solución:** Verificar que la deduplicación esté activa:
```python
dedup_key = f"msg:{phone_number}:{timestamp}"
if redis_client.exists(dedup_key):
    return 'NoCommand'
```

### Audios No Procesan
**Problema:** Los audios se encolan pero no se procesan.

**Solución:**
1. Verificar que el worker esté corriendo
2. Revisar logs del worker
3. Verificar conexión a Redis

```bash
# Ver cola de audios
redis-cli LLEN audio_queue
```

### Órdenes No Se Guardan en BD
**Problema:** La orden temporal existe pero no se persiste.

**Solución:**
1. Verificar que el tool `ordenar` reciba `nombre_completo`
2. Revisar logs de Supabase
3. Verificar permisos de la API key

### Chat History Se Pierde
**Problema:** El historial desaparece antes de tiempo.

**Solución:**
1. Verificar TTL en Redis (TIEMPO_NUEVO)
2. Revisar que la key sea correcta:
```python
id_chat_history = f'fp-chatHistory:{data["from"]}'
```

---

## 📚 Recursos Adicionales

### Documentación Externa
- [Anthropic Claude API](https://docs.anthropic.com/)
- [WASender API Docs](https://wasenderapi.com/docs)
- [Supabase Docs](https://supabase.com/docs)
- [Redis Commands](https://redis.io/commands/)

### Contacto y Soporte
Para preguntas sobre este proyecto, contacta al equipo de desarrollo.

---

## 🎯 Próximos Pasos para el Nuevo Desarrollador

1. **Configurar entorno local**
   - Instalar dependencias
   - Configurar `.env`
   - Verificar conexiones

2. **Familiarizarse con el flujo**
   - Leer este README completo
   - Revisar `procesa_mensajes.py`
   - Entender `agente.py`

3. **Probar el sistema**
   - Enviar mensajes de texto
   - Enviar audios
   - Enviar imágenes
   - Probar edición de órdenes

4. **Explorar mejoras**
   - Optimizar prompts
   - Agregar nuevas funcionalidades
   - Mejorar manejo de errores

---

## ✨ Características Destacadas

- ✅ **Conversaciones naturales** - Claude Sonnet 4 entiende contexto
- ✅ **Órdenes múltiples** - Varios pedidos en una conversación
- ✅ **Edición flexible** - Antes y después de confirmar
- ✅ **Multimedia** - Texto, audio e imágenes
- ✅ **Persistencia dual** - Redis (temporal) + Supabase (permanente)
- ✅ **Escalable** - Worker asíncrono para tareas pesadas
- ✅ **Robusto** - Deduplicación, reintentos, manejo de errores

---

**Última actualización:** Febrero 2025
**Versión del sistema:** 1.0
**Modelo de IA:** Claude Sonnet 4 (claude-sonnet-4-20250514)