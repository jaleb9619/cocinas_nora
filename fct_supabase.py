
from clients.supabase_client import supabase_client
from typing import Union, Dict, List, Any


def insert_data(
        data: Union[Dict[str, Any], List[Dict[str, Any]]], 
        table,
        supabase_client=supabase_client,
        return_id: bool = False
        ) -> Union[bool, str, List[str]]:
    if not data:
        print("No se proporcionaron datos para insertar.")
        return False
    try:
        response = supabase_client.table(table).insert(data).execute()
        if response.data:
            print(f"Datos insertados en la tabla '{table}'.")
            if return_id:
                ids = [item["id"] for item in response.data if "id" in item]
                return ids[0] if len(ids) == 1 else ids
            return True

        else:
            print(f"Error al insertar datos en '{table}': {response.error}")
            return False

    except Exception as e:
        print(f"Excepción al insertar en '{table}': {e}")
        return False
    
def read_data(
        table_name:str,
        variables:str='*',
        filters:dict=None,
        supabase_client=supabase_client,
        ):
    try:
        query=supabase_client.table(table_name).select(variables)
        if filters:
            for var, value in filters.items():
                if isinstance(value, list):
                    query=query.in_(var, value)

                else:
                    query=query.eq(var, value)
        supabase_client_response=query.execute()
        data = supabase_client_response.data or []
        if data:
            return data

        else:
            print(f"No se encontraron registros en '{table_name}' con los filtros {filters}.")
            return []

    except Exception as error:
            print(f"Error al consultar '{table_name}': {error}")
            return []
    
def update_data(
        table: str,
        data: Dict[str, Any],
        filters: Dict[str, Any],
        supabase_client=supabase_client
        ) -> bool:
    """
    Actualiza registros en una tabla de Supabase.

    Args:
        table: nombre de la tabla
        data: diccionario con los campos a actualizar
        filters: diccionario con las condiciones (ej: {'id': '123'})
        supabase_client: cliente de Supabase

    Returns:
        bool: True si se actualizó exitosamente
    """
    if not data:
        print("No se proporcionaron datos para actualizar.")
        return False

    if not filters:
        print("No se proporcionaron filtros para el update. Operación cancelada por seguridad.")
        return False

    try:
        query = supabase_client.table(table).update(data)

        for var, value in filters.items():
            query = query.eq(var, value)

        response = query.execute()

        if response.data:
            print(f"✅ Datos actualizados en '{table}': {len(response.data)} registro(s).")
            return True
        else:
            print(f"⚠️ Update ejecutado en '{table}' pero sin registros afectados. Filters: {filters}")
            return False

    except Exception as e:
        print(f"❌ Excepción al actualizar en '{table}': {e}")
        return False

if __name__=='__main__':
    data={
        'platillo':'Sopa de verduras',
        'precio':35.0,
        'tiempo':1
    }
    # insert_data(
    #     data,
    #     supabase_client=supabase_client, 
    #     table='tbl_cocina_platillos')

    # breakpoint()
    # hola=read_data(
    #     table_name='tbl_cocina_platillos',
    #     variables='platillo, precio',
    #     filters={'status':'TRUE'}, 
    #     supabase_client=supabase_client)