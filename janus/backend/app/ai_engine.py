import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None


def ask_juno_ai(question, context=""):
    if not client:
        return "Modo Demo: API Key da OpenAI não configurada. Configure a variável OPENAI_API_KEY para habilitar a inteligência operacional."
    try:
        prompt = f"""Você é o motor do Juno, especialista em decisões empresariais industriais.
        Contexto atual: {context}
        
        Pergunta do usuário: {question}
        
        Responda de forma executiva, baseada em dados e aponte ações claras."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Motor Juno v0.1"},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Erro na IA Juno: {str(e)}"
