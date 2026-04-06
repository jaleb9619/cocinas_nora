
from anthropic import Anthropic
from dotenv import load_dotenv

import os

load_dotenv()

ANTHROPIC_API_KEY: str = os.getenv('ANTHROPIC_API_KEY')
ANTHROPIC_MODEL_NAME = os.getenv('MODEL_NAME')
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
print("Cliente Anthropic inicializado.")