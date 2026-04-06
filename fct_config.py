# python3 fct_config.py

import os
from clients.supabase_client import supabase_client
from dotenv import load_dotenv

load_dotenv()

def obtener_config_cocina(user_id=None):
    try:
        # Obtener user_id del .env si no se proporciona
        if user_id is None:
            user_id = os.getenv('USER_ID')

        if not user_id:
            print("⚠️ USER_ID no configurado - usando valores por defecto")
            return {
                'user_id': None,
                'business_name': 'Mi Cocina',
                'agent_name': 'Lucía'
            }

        result = supabase_client.table('tbl_cocina_config')\
            .select('business_name, agent_name, precio_menu, descuento_por_platillo')\
            .eq('user_id', user_id)\
            .execute()

        if result.data and len(result.data) > 0:
            config = result.data[0]
            return {
                'user_id': user_id,
                'business_name': config['business_name'],
                'agent_name': config['agent_name'],
                'precio_menu': float(config.get('precio_menu') or 0.0),
                'descuento_por_platillo': bool(config.get('descuento_por_platillo') or False)
            }
        else:
            # No existe config, retornar valores por defecto
            print(f"⚠️ No se encontró config para user_id: {user_id} - usando defaults")
            return {
                'user_id': user_id,
                'business_name': 'Mi Cocina',
                'agent_name': 'Lucía',
                'precio_menu': 0.0,
                'descuento_por_platillo': False
            }

    except Exception as e:
        print(f"❌ Error obteniendo config de cocina: {e}")
        # Fallback al .env
        return {
            'user_id': user_id or os.getenv('USER_ID'),
            'business_name': os.getenv('BUSINESS_NAME', 'Mi Cocina'),
            'agent_name': os.getenv('AGENT_NAME', 'Lucía'),
            'precio_menu': 0.0,
            'descuento_por_platillo': False
        }

if __name__ == "__main__":
    config = obtener_config_cocina()
    print(config)