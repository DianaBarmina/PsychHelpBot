from datetime import date, timedelta
import psycopg2
import asyncpg
import os
import hashlib
from dotenv import load_dotenv
import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from db import DB_PARAMS
import matplotlib.pyplot as plt
from io import BytesIO


load_dotenv()
DB_PARAMS1 = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}


def hash_user_id(user_id: int) -> bytes:
    return hashlib.sha256(str(user_id).encode()).digest()


async def save_emotions_to_db(user_id: int, text_emotions: list[str], voice_emotions: list[str]):
    today = date.today()

    try:
        conn = await asyncpg.connect(**DB_PARAMS1)
        exists = await conn.fetchval(
            """
            SELECT 1 FROM user_emotions 
            WHERE user_id = $1 AND date_added = $2
            """,
            user_id, today
        )

        if exists:
            await conn.execute(
                """
                UPDATE user_emotions
                SET 
                    text_emotions = array_cat(text_emotions, $1),
                    voice_emotions = array_cat(voice_emotions, $2)
                WHERE user_id = $3 AND date_added = $4
                """,
                text_emotions, voice_emotions, user_id, today
            )
        else:
            await conn.execute(
                """
                INSERT INTO user_emotions 
                (user_id, date_added, text_emotions, voice_emotions)
                VALUES ($1, $2, $3, $4)
                """,
                user_id, today, text_emotions, voice_emotions
            )

    except Exception as e:
        print(f"Ошибка при сохранении эмоций: {e}")
        raise
    finally:
        if 'conn' in locals():
            await conn.close()


async def check_emotions_exist(user_id: int) -> bool:
    return await asyncio.to_thread(_sync_check_emotions_exist, user_id)


def _sync_check_emotions_exist(user_id: int) -> bool:
    conn = None
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()

        cur.execute("SELECT 1 FROM user_emotions WHERE user_id = %s LIMIT 1", (user_id,))
        exists = cur.fetchone() is not None

        cur.close()
        return exists
    except Exception as e:
        print(f"[DB ERROR] {e}")
        return False
    finally:
        if conn:
            conn.close()


async def confirm_delete_emotions_request(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    has_emotions = await check_emotions_exist(user_id)
    if not has_emotions:
        await update.message.reply_text("У вас нет сохранённых эмоций.")
        return

    context.user_data["checked_user"] = user_id

    keyboard = [
        [InlineKeyboardButton("✅ Да", callback_data="delete_emotions_yes")],
        [InlineKeyboardButton("❌ Нет", callback_data="delete_emotions_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Вы уверены, что хотите удалить все сохранённые эмоции?",
        reply_markup=reply_markup
    )


async def handle_delete_emotions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    user_id = context.user_data.get("checked_user")

    if not user_id:
        await query.message.edit_text("⚠️ Не удалось определить пользователя.")
        return

    if data == "delete_emotions_yes":
        try:
            await delete_user_emotions(user_id)
            await query.message.edit_text("🗑️ Все эмоции были удалены.")
        except Exception as e:
            await query.message.edit_text("⚠️ Ошибка при удалении эмоций.")
            print(f"[DELETE EMOTIONS ERROR] {e}")
    else:
        await query.message.edit_text("Удаление отменено.")


async def delete_user_emotions(user_id: int):
    await asyncio.to_thread(_sync_delete_user_emotions, user_id)


def _sync_delete_user_emotions(user_id: int):
    conn = None
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()

        cur.execute("DELETE FROM user_emotions WHERE user_id = %s", (user_id,))
        conn.commit()
        cur.close()
        print(f"[DELETE EMOTIONS] Эмоции пользователя {user_id} удалены.")
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[DB ERROR] {e}")
        raise
    finally:
        if conn:
            conn.close()


async def get_emotions_stats1(user_id: int, period_days: int) -> dict:
    end_date = date.today()
    start_date = end_date - timedelta(days=period_days)

    conn = await asyncpg.connect(**DB_PARAMS1)
    try:
        records = await conn.fetch(
            """
            SELECT unnest(text_emotions) as emotion, count(*) as count
            FROM user_emotions
            WHERE user_id = $1 AND date_added BETWEEN $2 AND $3
            GROUP BY emotion
            ORDER BY count DESC
            """,
            user_id, start_date, end_date
        )
        return {record['emotion']: record['count'] for record in records}
    finally:
        await conn.close()


async def create_emotions_chart1(emotions_data: dict, period: str) -> BytesIO:
    if not emotions_data:
        return None

    emotions = list(emotions_data.keys())
    counts = list(emotions_data.values())

    plt.figure(figsize=(10, 6))
    bars = plt.bar(emotions, counts, color='skyblue')

    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2., height,
                 f'{int(height)}', ha='center', va='bottom')

    plt.title(f'Статистика эмоций за {period}')
    plt.xlabel('Эмоции')
    plt.ylabel('Количество')
    plt.xticks(rotation=45)
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    buf.seek(0)
    plt.close()
    return buf


async def get_emotions_stats(user_id: int, period_days: int, emotions_type: str) -> dict:
    end_date = date.today()
    start_date = end_date - timedelta(days=period_days)

    conn = None
    try:
        conn = await asyncpg.connect(**DB_PARAMS1)
        print(emotions_type)

        column = 'text_emotions' if emotions_type == 'text' else 'voice_emotions'

        records = await conn.fetch(
            f"""
            SELECT unnest({column}) as emotion, count(*) as count
            FROM user_emotions
            WHERE user_id = $1 AND date_added BETWEEN $2 AND $3
            GROUP BY emotion
            ORDER BY count DESC
            """,
            user_id, start_date, end_date
        )
        return {record['emotion']: record['count'] for record in records}

    except Exception as e:
        print(f"[DB ERROR] {e}")
        return None
    finally:
        if conn:
            await conn.close()


async def create_emotions_chart(emotions_data: dict, period: str, emotions_type: str) -> BytesIO:
    """Создаем столбчатую диаграмму"""
    if not emotions_data:
        return None

    emotions = list(emotions_data.keys())
    counts = list(emotions_data.values())

    plt.figure(figsize=(10, 6))
    color = '#4CAF50' if emotions_type == 'text' else '#2196F3'
    bars = plt.bar(emotions, counts, color=color)

    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2., height,
                 f'{int(height)}', ha='center', va='bottom')

    title_type = 'Текстовые' if emotions_type == 'text' else 'Голосовые'
    plt.title(f'{title_type} эмоции за {period}')
    plt.xlabel('Эмоции')
    plt.ylabel('Количество')
    plt.xticks(rotation=45)
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=100)
    buf.seek(0)
    plt.close()
    return buf
