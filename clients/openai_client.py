
from openai import OpenAI
from dotenv import load_dotenv

import os

load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
openai_client = OpenAI(api_key=OPENAI_API_KEY)
print("Cliente OpenAI inicializado.")