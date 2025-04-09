import datetime
import psycopg2
from db import hash_user_id
import os
from dotenv import load_dotenv


load_dotenv()
DB_PARAMS = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
    "dbname": os.getenv("DB_NAME2"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}


consent_text = (
    "🛡️ Перед началом, пожалуйста, ознакомься с условиями использования данных и подтверди согласие:\n\n"
    "🔐 *Какие данные сохраняются:*\n"
    "• Идентификатор пользователя (в зашифрованном виде)\n"
    "• Результаты психологических тестов и эмоции (сохраняются автоматически при прохождении тестов и отправке сообщений)\n"
    "• Психографический портрет (опционально - ты можешь самостоятельно выбрать, проходить опрос или нет в любое время\n\n"
    "📊 *Как используются данные:*\n"
    "• Для формирования персонализированных рекомендаций\n"
    "• Для отслеживания изменений психологического и эмоционального состояния\n\n"
    "🧾 *Как можно контролировать данные:*\n"
    "• Вы можете удалить все данные в любой момент\n\n"
    "👨‍💻 *Кто имеет доступ:* Только разработчики для технической поддержки\n\n"
    "Если вы согласны с этими условиями, нажмите кнопку ниже 👇"
)


async def save_user_consent(user_id):
    hashed_id = hash_user_id(user_id)

    conn = psycopg2.connect(**DB_PARAMS)
    cursor = conn.cursor()

    cursor.execute("""
            SELECT consent_given FROM user_consents
            WHERE user_id = %s AND consent_given = TRUE
        """, (hashed_id,))

    cursor.execute("SELECT 1 FROM user_consents WHERE user_id = %s LIMIT 1", (hashed_id,))
    exists = cursor.fetchone() is not None

    if not exists:

        cursor.execute("""
            INSERT INTO user_consents (user_id, consent_given, consent_date)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET consent_given = TRUE, consent_date = EXCLUDED.consent_date
        """, (hashed_id, True, datetime.datetime.utcnow()))

        conn.commit()
        cursor.close()
        conn.close()


async def check_user_consent(user_id):
    hashed_id = hash_user_id(user_id)

    conn = psycopg2.connect(**DB_PARAMS)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id FROM user_consents
        WHERE user_id = %s AND consent_given = TRUE
    """, (hashed_id,))

    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if result:
        return result[0]  # Возвращаем id записи
    return None


async def delete_user_consent(user_id):
    hashed_id = hash_user_id(user_id)

    conn = psycopg2.connect(**DB_PARAMS)
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM user_consents WHERE user_id = %s
    """, (hashed_id,))

    conn.commit()
    cursor.close()
    conn.close()
