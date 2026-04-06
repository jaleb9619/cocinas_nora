# python3 clean_db.py

import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# IMPORTANTE: Usa el service_role_key, NO el anon key
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def limpiar_tablas_testing():
    print("🚨 ADVERTENCIA: Esto borrará TODOS los datos de testing")
    confirmacion = input("¿Estás seguro? Escribe 'BORRAR TODO' para continuar: ")

    if "borrar todo" not in confirmacion.lower():
        print("❌ Operación cancelada")
        return

    try:
        print("\n1️⃣ Borrando desglose de comandas...")
        result = supabase.table('tbl_cocina_desglose').delete().gte('id', '00000000-0000-0000-0000-000000000000').execute()
        print(f"   ✅ Registros eliminados: {len(result.data) if result.data else 0}")

        print("\n2️⃣ Borrando comandas...")
        result = supabase.table('tbl_cocina_comandas').delete().gte('id', '00000000-0000-0000-0000-000000000000').execute()
        print(f"   ✅ Registros eliminados: {len(result.data) if result.data else 0}")

        print("\n3️⃣ Borrando platillos...")
        result = supabase.table('tbl_cocina_platillos').delete().gte('id', '00000000-0000-0000-0000-000000000000').execute()
        print(f"   ✅ Registros eliminados: {len(result.data) if result.data else 0}")

        print("\n4️⃣ Borrando tiempos de cocina...")
        result = supabase.table('tbl_cocina_tiempos').delete().gte('id', 0).execute()
        print(f"   ✅ Registros eliminados: {len(result.data) if result.data else 0}")

        print("\n5️⃣ Borrando clientes...")
        result = supabase.table('tbl_clientes').delete().gte('id', '00000000-0000-0000-0000-000000000000').execute()
        print(f"   ✅ Registros eliminados: {len(result.data) if result.data else 0}")

        print("\n6️⃣ Borrando usuarios de auth.users...")

        try:
            response = supabase.auth.admin.list_users()

            if hasattr(response, 'users'):
                usuarios = response.users
            elif isinstance(response, list):
                usuarios = response
            else:
                usuarios = []

            count = 0
            for usuario in usuarios:
                user_id = usuario.id
                supabase.auth.admin.delete_user(user_id)
                email = getattr(usuario, 'email', 'sin email')
                print(f"   🗑️  Usuario eliminado: {email}")
                count += 1

            print(f"\n✅ Total usuarios eliminados: {count}")
        except Exception as e:
            print(f"⚠️  No se pudieron borrar usuarios de auth: {str(e)}")
            print("   Puedes borrarlos manualmente desde Authentication > Users en el dashboard")

        print("\n🎉 LIMPIEZA COMPLETADA - Todas las tablas vaciadas")

    except Exception as e:
        print(f"\n❌ Error durante la limpieza: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    limpiar_tablas_testing()