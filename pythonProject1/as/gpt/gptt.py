import openai
import os
import dotenv
from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.getenv('OPENAI_API_KEY')

async def ask_gpt(mood: str, time: str, company: str, weather: str) -> str:
    prompt = (
        f"Пользователь описал:\n"
        f"- Настроение: {mood}\n"
        f"- Время: {time}\n"
        f"- Предпочитает проводить время: {company}\n\n"
        f"Предложи, как ему лучше всего провести досуг в такой ситуации. пришли 3-5 очень коротких ответов"
    )

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        max_tokens=200,
    )
    return response.choices[0].message.content.strip()