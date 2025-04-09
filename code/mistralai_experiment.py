from mistralai import Mistral
import os
from dotenv import load_dotenv
import time

load_dotenv()

# Получение переменных
MISTRALAI_API_KEY = os.getenv("MISTRALAI_API_KEY")


def generate_response(prompt):
    time.sleep(1)
    client = Mistral(api_key=MISTRALAI_API_KEY)

    system_prompt = (
        "Ты психолог. "
        "Ты умеешь хорошо помогать людям, не не забывай, что твой ответ будет ограничен сотней токенов"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]

    completion = client.chat.complete(
        # model="open-codestral-mamba",
        model="open-mistral-nemo",
        messages=messages,
        # max_tokens=100
    )

    response = completion.choices[0].message.content.strip()
    return response


def generate_response_for_emotion(prompt=None,
                                  text_emotions=None,
                                  voice_emotion=None,
                                  profile=None,
                                  phq_results=None,
                                  gad_results=None,
                                  ):
    time.sleep(1)
    client = Mistral(api_key=MISTRALAI_API_KEY)

    system_prompt = (
        "Ты психолог и эмпат. "
        "Ты умеешь хорошо понимать эмоции людей, помогать людям и показывать свою эмпатию."
    )
    if text_emotions is not None:
        system_prompt += f"Пользователь испытывает эмоции {text_emotions}."

    if voice_emotion is not None:
        system_prompt += f"Пользователь говорил с интонацией {voice_emotion}."

    if phq_results is not None:
        system_prompt += f"Пользователь прошел тест на депрессию PHQ с результатом: {phq_results}."

    if gad_results is not None:
        system_prompt += f"Пользователь прошел тест на тревожность GAD с результатом: {gad_results}."

    if profile is not None:
        system_prompt += f"Дай пользователю совет и поддержку на основе его психографического портрета: {profile}"
    else:
        system_prompt += "Дай пользователю совет и поддержку."

    if prompt is None:
        prompt = "Окажи мне психологическую поддержку или дай рекоендации к кому обратиться"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]

    completion = client.chat.complete(
        # model="open-codestral-mamba",
        model="open-mistral-nemo",
        messages=messages,
        # max_tokens=100
    )

    response = completion.choices[0].message.content.strip()
    return response


def classificate_emotions(prompt):
    time.sleep(1)
    client = Mistral(api_key=MISTRALAI_API_KEY)

    system_prompt = (
        "ты эмпат, ты хорошо разбираешься в эмоциях "
        """ты можешь определить три наиболее вероятные эмоции текстового сообщения, такие как:
        admiration: восхищение
        amusement: веселье
        anger: злость
        annoyance: раздражение
        approval: одобрение
        caring: забота
        confusion: непонимание
        curiosity: любопытство
        desire: желание
        disappointment: разочарование
        disapproval: неодобрение
        disgust: отвращение
        embarrassment: смущение
        excitement: возбуждение
        fear: страх
        gratitude: признательность
        grief: горе
        joy: радость
        love: любовь
        nervousness: нервозность
        optimism: оптимизм
        pride: гордость
        realization: осознание
        relief: облегчение
        remorse: раскаяние
        sadness: грусть
        surprise: удивление
        neutral: нейтральность
        """
        "выведи в ответ только три слова - три эмоции на русском языке"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]

    completion = client.chat.complete(
        # model="open-codestral-mamba",
        model="open-mistral-nemo",
        messages=messages,
        max_tokens=100
    )

    response = completion.choices[0].message.content.strip()
    return response


# Предположим, api_key и lang уже определены
if __name__ == "__main__":
    client = Mistral(api_key="c7Py7BhqBgXT1rfy1ceTQsA2nY6ssirn")

    system_prompt = (
        "Ты психолог. "
        "Ты умеешь хорошо помогать людям"
    )
    # Убедитесь, что lang определён
    prompt = 'мне грустно'

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]

    completion = client.chat.complete(
        # model="open-codestral-mamba",
        model="open-mistral-nemo",
        messages=messages
    )

    response = completion.choices[0].message.content.strip()
    print(response)
