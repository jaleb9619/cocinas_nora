# python3 atencion_clientes.py

import os

from clients.anthropic_client import anthropic_client
from dotenv import load_dotenv
from clients.supabase_client import supabase_client as _sc
from system_prompts import prompt_atencion_clientes
from typing import List

load_dotenv()

# Anthropic
ANTHROPIC_MODEL_NAME = os.getenv('MODEL_NAME')

def responder_pregunta(pregunta: str, prompt_atencion_clientes: str=prompt_atencion_clientes, new_messages: List[dict]=[], anthropic_client=anthropic_client) -> str:
    """
    Responde a una pregunta común de atención al cliente.
    """

    new_messages = new_messages + [{"role": "user", "content": pregunta}]

    anthropic_client_response = anthropic_client.messages.create(
        system=prompt_atencion_clientes,
        model=ANTHROPIC_MODEL_NAME,
        messages=new_messages,
        max_tokens=8000,
        temperature=0.1,
        )

    return {
            "answer": anthropic_client_response.content[0].text,
            "output": anthropic_client_response.content,
            "input_tokens": anthropic_client_response.usage.input_tokens,
            "output_tokens": anthropic_client_response.usage.output_tokens,
            'model_name': ANTHROPIC_MODEL_NAME
        }

if __name__ == "__main__":

    pregunta = "¿Cómo puedo cambiar mi contraseña?"
    respuesta = responder_pregunta(pregunta, prompt_atencion_clientes="responde", new_messages=[])
    print(respuesta)