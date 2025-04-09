import asyncio
import psycopg2
from datetime import datetime
from db import DB_PARAMS
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes


async def save_test_result(user_id: int, test_type: str, score: int):
    await asyncio.to_thread(_sync_save_test_result, user_id, test_type, score)


def _sync_save_test_result(user_id: int, test_type: str, score: int):
    conn = None
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO tests_results (user_id, test_type, test_result, datetime) VALUES (%s, %s, %s, %s)",
            (user_id, test_type, score, datetime.now())
        )
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"[DB ERROR] {e}")
    finally:
        if conn:
            conn.close()


async def confirm_delete_tests_request(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):

    has_tests = await check_test_results_exist(user_id)
    if not has_tests:
        await update.message.reply_text("У вас нет сохранённых результатов тестов.")
        return

    keyboard = [
        [InlineKeyboardButton("✅ Да", callback_data="delete_tests_yes")],
        [InlineKeyboardButton("❌ Нет", callback_data="delete_tests_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Вы уверены, что хотите удалить все результаты тестов?",
        reply_markup=reply_markup
    )


async def handle_delete_tests_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    user_id = context.user_data.get("checked_user")

    if not user_id:
        await query.message.edit_text("⚠️ Не удалось определить пользователя.")
        return

    if data == "delete_tests_yes":
        try:
            await delete_test_results(user_id)
            await query.message.edit_text("🗑️ Все результаты тестов были удалены.")
        except Exception as e:
            await query.message.edit_text("⚠️ Ошибка при удалении тестов.")
            print(f"[DELETE TESTS ERROR] {e}")
    else:
        print(data)
        await query.message.edit_text("Удаление отменено.----")


async def check_test_results_exist(user_id: int) -> bool:
    return await asyncio.to_thread(_sync_check_test_results_exist, user_id)


def _sync_check_test_results_exist(user_id: int) -> bool:
    conn = None
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()

        cur.execute("SELECT 1 FROM tests_results WHERE user_id = %s LIMIT 1", (user_id,))
        exists = cur.fetchone() is not None

        cur.close()
        return exists
    except Exception as e:
        print(f"[DB ERROR] {e}")
        return False
    finally:
        if conn:
            conn.close()


async def delete_test_results(user_id: int):
    await asyncio.to_thread(_sync_delete_test_results, user_id)


def _sync_delete_test_results(user_id: int):
    conn = None
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()

        cur.execute("DELETE FROM tests_results WHERE user_id = %s RETURNING user_id", (user_id,))
        deleted = cur.rowcount

        if deleted > 0:
            conn.commit()
            print(f"[DELETE TESTS] Удалено {deleted} записей для user_id={user_id}")
        else:
            print(f"[DELETE TESTS] Нет записей для user_id={user_id}")

        cur.close()
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[DB ERROR] {e}")
        raise
    finally:
        if conn:
            conn.close()

