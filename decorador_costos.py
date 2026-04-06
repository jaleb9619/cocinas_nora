import functools
import csv


from datetime import datetime

# from db_costos import (
#     insert_new_interaction
# )


costos = {
    'claude-3-7-sonnet-20250219': {
        "input_tokens": 3/1000000,
        "output_tokens": 15/1000000,
    }
    # 'text-embedding-3-large': {
    #     "input_tokens": 0.13/1000000
    # },
    # 'whisper-1':{
    #     'input_tokens': 0.006/60,
    # }
}

def decorador_costo(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        value = func(*args, **kwargs)
        
        input_tokens = value.get('input_tokens', 0)
        output_tokens = value.get('output_tokens', 0)
        answer = value.get('answer', '')
        # id_conversacion=value.get('id_conversacion', '')
        model_name=value.get('model_name','')

        print(model_name)
        print(input_tokens)
        print(output_tokens)

        # breakpoint()

        try:
            if 'output_tokens' in value:
                query_cost = input_tokens * costos[model_name]['input_tokens'] + output_tokens*costos[model_name]['output_tokens']
            else:
                query_cost = input_tokens * costos[model_name]['input_tokens']
        except:
            print(f"[Chatbot] No se pudo calcular el costo para el modelo {model_name}.")
            query_cost = 0.0

        print("Costos actualizados")
        return answer
    return wrapper
