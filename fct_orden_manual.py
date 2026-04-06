# python3 fct_orden_manual.py

import os
import uuid
from datetime import datetime, timezone

from clients.supabase_client import supabase_client
from fct_supabase import read_data, insert_data
from dotenv import load_dotenv

load_dotenv()

user_id = os.getenv('USER_ID')

TLB_COMANDAS = os.getenv('TLB_COMANDAS')
TLB_DESGLOSE = os.getenv('TLB_DESGLOSE')
TLB_PLATILLOS = os.getenv('TLB_PLATILLOS')

print(f"🔍 TLB_COMANDAS={TLB_COMANDAS}, TLB_DESGLOSE={TLB_DESGLOSE}, TLB_PLATILLOS={TLB_PLATILLOS}")


def _calcular_monto_comida(
    precio_menu: float,
    descuento_por_platillo: bool,
    platillos_seleccionados: list[dict],  # [{"platillo_id": int, "platillo_nombre": str, "precio": float}]
    todos_los_platillos: list[dict],      # todos los platillos activos del menú
) -> float:
    """
    Calcula el monto de UNA comida completa.
    Si descuento_por_platillo está activo, descuenta los platillos NO seleccionados.
    """
    if not descuento_por_platillo:
        return precio_menu

    ids_seleccionados = {str(p["platillo_id"]) for p in platillos_seleccionados}

    descuento = sum(
        float(p.get("precio", 0.0))
        for p in todos_los_platillos
        if str(p["id"]) not in ids_seleccionados
    )

    return max(0.0, precio_menu - descuento)


def crear_orden_manual(
    cliente_nombre: str,
    tipo_entrega: str,
    direccion: str,
    comidas: list[dict],       # [{"platillos": [{"platillo_id": int, "platillo_nombre": str, "precio": float}]}]
    extras: list[dict],        # [{"platillo_id": int, "platillo_nombre": str, "precio": float}]
    precio_menu: float,
    descuento_por_platillo: bool,
    supabase=supabase_client,
    uid=user_id
) -> dict:
    """
    Crea comandas desde el dashboard (sin WhatsApp).

    - Una comanda por cada comida completa, con sus platillos en desglose
    - Una comanda por cada extra
    - Todas vinculadas por el mismo pedido_grupo
    """

    if not comidas and not extras:
        return {"ok": False, "error": "La orden no tiene items"}

    if not cliente_nombre or not cliente_nombre.strip():
        return {"ok": False, "error": "El nombre del cliente es obligatorio"}

    pedido_grupo = str(uuid.uuid4())
    comandas_ids = []

    try:
        # Obtener todos los platillos activos para calcular descuentos
        todos_los_platillos = read_data(
            table_name=TLB_PLATILLOS,
            variables='id, platillo, precio',
            filters={'activo': 'TRUE'},
        )

        # ── Comidas completas ──────────────────────────────────────────
        for i, comida in enumerate(comidas):
            platillos_comida = comida.get("platillos", [])

            monto = _calcular_monto_comida(
                precio_menu=precio_menu,
                descuento_por_platillo=descuento_por_platillo,
                platillos_seleccionados=platillos_comida,
                todos_los_platillos=todos_los_platillos,
            )

            comanda = {
                "user_id": uid,
                "cliente_nombre": cliente_nombre.strip(),
                "pedido_grupo": pedido_grupo,
                "telefono_cliente": "mostrador",
                "tipo_entrega": tipo_entrega or "local",
                "direccion": direccion.strip() if direccion else "",
                "monto_estandar": monto,
                "monto_extras": 0,
                "monto_desechables": 0,
                "monto_total": monto,
                "status": "PENDIENTE",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            comanda_id = insert_data(comanda, TLB_COMANDAS, return_id=True)

            if not comanda_id:
                return {"ok": False, "error": f"Error insertando comida {i + 1}"}

            comandas_ids.append(comanda_id)

            # Insertar desglose de platillos de esta comida
            for platillo in platillos_comida:
                insert_data(
                    {
                        "comanda_id": comanda_id,
                        "platillo_id": platillo["platillo_id"],
                    },
                    TLB_DESGLOSE
                )

            print(f"✅ Comida {i + 1} creada: {comanda_id} | ${monto} | {len(platillos_comida)} platillos")

        # ── Extras ────────────────────────────────────────────────────
        for extra in extras:
            platillo_id = str(extra.get("platillo_id", "")).strip('"')
            precio_extra = float(extra.get("precio", 0.0))
            nombre_extra = extra.get("platillo_nombre", "")

            comanda_extra = {
                "user_id": uid,
                "cliente_nombre": cliente_nombre.strip(),
                "pedido_grupo": pedido_grupo,
                "telefono_cliente": "mostrador",
                "tipo_entrega": tipo_entrega or "local",
                "direccion": direccion.strip() if direccion else "",
                "monto_estandar": 0,
                "monto_extras": precio_extra,
                "monto_desechables": 0,
                "monto_total": precio_extra,
                "status": "PENDIENTE",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "es_extra": True
            }

            comanda_id = insert_data(comanda_extra, TLB_COMANDAS, return_id=True)

            if not comanda_id:
                return {"ok": False, "error": f"Error insertando extra: {nombre_extra}"}

            comandas_ids.append(comanda_id)

            insert_data(
                {"comanda_id": comanda_id, "platillo_id": platillo_id},
                TLB_DESGLOSE
            )

            print(f"✅ Extra creado: {comanda_id} | {nombre_extra} | ${precio_extra}")

        print(f"📦 Orden manual completa | grupo: {pedido_grupo} | {len(comandas_ids)} comandas")

        return {
            "ok": True,
            "pedido_grupo": pedido_grupo,
            "comandas_ids": comandas_ids,
        }

    except Exception as e:
        print(f"❌ Error en crear_orden_manual: {e}")
        return {"ok": False, "error": str(e)}

def editar_comanda(
    comanda_id: str,
    platillos: list[dict],  # [{"platillo_id": str, "tiempo_id": str, ...}]
    precio_menu: float,
    descuento_por_platillo: bool,
    todos_los_platillos: list[dict],
) -> dict:
    """
    Edita una comanda individual:
    - Limpia su desglose anterior
    - Inserta el nuevo desglose
    - Recalcula y actualiza monto_total
    """
    try:
        # 1. Borrar desglose anterior
        supabase_client.table(TLB_DESGLOSE)\
            .delete()\
            .eq("comanda_id", comanda_id)\
            .execute()

        # 2. Insertar nuevo desglose
        for platillo in platillos:
            insert_data(
                {"comanda_id": comanda_id, "platillo_id": platillo["platillo_id"]},
                TLB_DESGLOSE
            )

        # 3. Recalcular monto
        monto = _calcular_monto_comida(
            precio_menu=precio_menu,
            descuento_por_platillo=descuento_por_platillo,
            platillos_seleccionados=platillos,
            todos_los_platillos=todos_los_platillos,
        )

        # 4. Actualizar comanda
        supabase_client.table(TLB_COMANDAS)\
            .update({"monto_total": monto, "monto_estandar": monto})\
            .eq("id", comanda_id)\
            .execute()

        print(f"✅ Comanda editada: {comanda_id} | ${monto}")
        return {"ok": True, "comanda_id": comanda_id, "monto": monto}

    except Exception as e:
        print(f"❌ Error en editar_comanda: {e}")
        return {"ok": False, "error": str(e)}