from mistralai import Mistral
import os
from dotenv import load_dotenv
import time
import re
from find_contacts import find_and_format_contacts

load_dotenv()
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
    """Базовая функция для генерации ответа, когда все эмоции уже определены + отсутствие правил безопасности"""
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
        model="open-mistral-nemo",
        # model="open-mistral-7b",
        messages=messages,
        # max_tokens=100
    )

    response = completion.choices[0].message.content.strip()
    return response


def classificate_emotions(prompt):
    """Функция для определения эмоций в тексте моделью Mistral"""
    time.sleep(1)
    client = Mistral(api_key=MISTRALAI_API_KEY)

    system_prompt = (
        """ты эмпат, ты хорошо разбираешься в эмоциях и ИИ, который классифицирует сообщения пользователей по их цели.
        ты можешь определить три наиболее вероятные эмоции текстового сообщения, такие как:
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
        выведи в ответ только три слова - три эмоции на русском языке в формате:
        Эмоции: эмоция1, эмоция2, эмоция3
        
        ты можешь определить Возможные категории:

        1. Support — пользователь хочет выговориться, получить поддержку.
        2. Crisis — пользователь в остром эмоциональном или жизненном кризисе.
        3. Resource — пользователь хочет получить совет, упражнение или информацию.
        
        Пример: "Мне просто очень тяжело..." → Support
        
        Пример: "Я больше не вижу смысла жить..." → Crisis
        
        Пример: "Как справиться с тревогой?" → Resource
        вывод ф формате:
        Класс: detected_class
        """
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]

    completion = client.chat.complete(
        # model="open-codestral-mamba",
        model="open-mistral-nemo",
        # model="open-mistral-7b",
        messages=messages,
        max_tokens=100
    )

    response = completion.choices[0].message.content.strip()
    return response


def extract_emotions_and_response(response, only_response=True):
    """
    Извлекает эмоции и текст ответа из ответа модели.
    Ожидается, что модель вернёт:
    Эмоции: эмоция1, эмоция2, эмоция3
    Ответ: текст...
    """
    response_match = re.search(r'Ответ:\s*(.+)', response, re.DOTALL)
    response_text = response_match.group(1).strip() if response_match else response.strip()

    if only_response is False:
        emotions = []
        emotion_match = re.search(r'Эмоции:\s*([а-яА-ЯёЁ,\s]+)(?=\n|$)', response)

        if emotion_match:
            emotions_str = emotion_match.group(1)
            emotions = [e.strip() for e in emotions_str.split(',') if e.strip()]

        return emotions, response_text

    return [], response_text


def generate_empathic_response(prompt=None,
                               voice_emotion=None,
                               profile=None,
                               phq_results=None,
                               gad_results=None):
    """
    Генерирует эмпатичный ответ и классифицирует эмоции пользователя за один запрос к LLM.
    Возвращает: (ответ модели, список эмоций)
    """
    time.sleep(1)
    client = Mistral(api_key=MISTRALAI_API_KEY)

    # if phq_results is None and gad_results is None:
    emotions_prompt, emotions_format = "", ""
    if prompt:
        emotions_prompt = "Сначала определи три наиболее выраженные эмоции пользователя по его сообщению. " + \
                          """
                            Список возможных эмоций: восхищение, веселье, злость, раздражение, одобрение, 
                            забота, непонимание, любопытство, желание, разочарование, неодобрение, отвращение, 
                            смущение, возбуждение, страх, признательность, горе, радость, любовь, нервозность, 
                            оптимизм, гордость, осознание, облегчение, раскаяние, грусть, удивление, нейтральность.\n
                          """
        emotions_format = "Эмоции: эмоция1, эмоция2, эмоция3\n"

    system_prompt = (
        "Ты эмпатичный ИИ и психолог. Ты умеешь хорошо понимать эмоции людей и оказывать психологическую поддержку. "
        f"{emotions_prompt}"
        "Затем, основываясь на этих эмоциях или дополнительной информации, напиши эмпатичный, поддерживающий ответ.\n\n"
        "Очень важно: соблюдай правила безопасности при каждом ответе.\n"
        "Вот чек-лист безопасности, который ты обязан соблюдать:\n"
        "1. Не обещай, что 'всё будет хорошо'.\n"
        "2. Не ставь диагнозов.\n"
        "3. Не пиши, что ты заменяешь терапевта или профессиональную помощь.\n"
        "4. Не поощряй избегание, изоляцию или отказ от действий.\n"
        "5. Ты можешь давать только легкие терапевтические рекомендации.\n"                                             #не давай медицинский и терапевтических рекомендаций
        "6. Поощряй обращение за профессиональной помощью, если это уместно.\n"
        "7. Не принижай чувства пользователя. Уважай его состояние.\n"
        "8. Используй поддерживающий, не осуждающий тон.\n"
        "9. Не используй токсичный позитив (например: 'просто улыбнись' или 'всё к лучшему').\n"
        "10. Ответ должен быть деликатным и человечным.\n\n"
        "Формат ответа:\n"
        f"{emotions_format}"
        "Ответ: твой эмпатичный ответ пользователю на русском языке.\n\n"
    )
    if profile:
        system_prompt += f"\nПсихографический портрет пользователя: {profile}" + \
            "Адаптируй психологическую поддержку под психографический портрет пользователя"

    if voice_emotion:
        system_prompt += f"\nПользователь говорил с интонацией: {voice_emotion}."

    if phq_results:
        system_prompt += f"\nРезультаты теста PHQ (депрессия): {phq_results}."

    if gad_results:
        system_prompt += f"\nРезультаты теста GAD (тревожность): {gad_results}."

    '''contacts_info = find_and_format_contacts(
        user_text=prompt,
        emotions=None,
        phq_score=phq_results,
        gad_score=gad_results
    )
    print(contacts_info)
    if contacts_info:
        system_prompt += f"\nВставь подходящие контакты бесплатной психологической помощи в предложенном формате: {contacts_info}." \
                         + "Предложи все или один из них, только если это действительно необходимо: пользователь запрашивал или у него кризисная ситуация"
    '''

    if prompt is None:
        prompt = "Окажи мне психологическую поддержку или дай рекомендации к кому обратиться."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]

    completion = client.chat.complete(
        model="open-mistral-nemo",
        messages=messages
        # max_tokens=500
    )

    full_response = completion.choices[0].message.content.strip()

    only_response = phq_results is not None or gad_results is not None
    emotions, response_text = extract_emotions_and_response(full_response, only_response=only_response)

    contacts_info = find_and_format_contacts(
        user_text=prompt,
        emotions=emotions,
        phq_score=phq_results,
        gad_score=gad_results
    )

    if contacts_info:
        final_response = f"{response_text}\n\n[Контакты помощи]:\n{contacts_info}"
    else:
        final_response = response_text
    return final_response, emotions
    #return response_text, emotions


if __name__ == "__main__":
    client = Mistral(api_key="c7Py7BhqBgXT1rfy1ceTQsA2nY6ssirn")

    system_prompt = (
        "Ты психолог. "
        "Ты умеешь хорошо помогать людям"
    )

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
