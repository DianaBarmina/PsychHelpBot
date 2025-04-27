import json
import psycopg2
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from db import DB_PARAMS, hash_user_id
import asyncio
from psychographic_questions import psychographic_questions


async def save_profile_to_db(user_id: int, answers: dict):
    return await asyncio.to_thread(_sync_save_profile_to_db, user_id, answers)


def _sync_save_profile_to_db(user_id: int, answers: dict):
    #encrypted_id = hash_user_id(user_id)#encrypt_user_id(user_id)

    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()

        cur.execute("SELECT 1 FROM user_profiles WHERE user_id = %s LIMIT 1", (user_id,))
        exists = cur.fetchone() is not None

        if exists:
            cur.execute("""
                UPDATE user_profiles 
                SET 
                    demography = %s,
                    lifestyle_and_values = %s,
                    character = %s,
                    hobby = %s
                WHERE user_id = %s
                AND (
                    demography IS DISTINCT FROM %s OR
                    lifestyle_and_values IS DISTINCT FROM %s OR
                    character IS DISTINCT FROM %s OR
                    hobby IS DISTINCT FROM %s
                )
                RETURNING 1;
            """, (
                json.dumps(answers['demography'], ensure_ascii=False),
                json.dumps(answers['lifestyle_and_values'], ensure_ascii=False),
                json.dumps(answers['character'], ensure_ascii=False),
                json.dumps(answers['hobby'], ensure_ascii=False),
                user_id,  # encrypted_id,
                json.dumps(answers['demography'], ensure_ascii=False),
                json.dumps(answers['lifestyle_and_values'], ensure_ascii=False),
                json.dumps(answers['character'], ensure_ascii=False),
                json.dumps(answers['hobby'], ensure_ascii=False),
            ))

            if cur.fetchone() is None:
                print("[DB INFO] Данные не изменились, обновление не требуется")
                return False
        else:
            # Вставляем новую запись
            cur.execute("""
                INSERT INTO user_profiles 
                (user_id, demography, lifestyle_and_values, character, hobby)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                user_id, # encrypted_id,
                json.dumps(answers['demography'], ensure_ascii=False),
                json.dumps(answers['lifestyle_and_values'], ensure_ascii=False),
                json.dumps(answers['character'], ensure_ascii=False),
                json.dumps(answers['hobby'], ensure_ascii=False),
                #user_id,
                #answers['demography'],
                #answers['lifestyle_and_values'],
                #answers['character'],
                #answers['hobby'],
            ))

        conn.commit()
        return True

    except Exception as e:
        conn.rollback()
        print(f"[DB ERROR] {e}")
        raise
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()


async def start_psychographic_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    context.user_data['profile'] = {
        "current_block": 0,
        "current_question": 0,
        "answers": {
            "demography": [],
            "lifestyle_and_values": [],
            "character": [],
            "hobby": []
        }
    }
    await update.message.reply_text("📋 Начинаем составление психографического портрета.\n После начала опроса его нельзя прервать - ответьте, пожалуйста, на все вопросы")
    await ask_next_profile_question(update, context, user_id)


async def ask_next_profile_question(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    profile = context.user_data.get("profile")
    if not profile:
        await update.message.reply_text("❌ Ошибка: сессия профиля не найдена.")
        return

    block_index = profile["current_block"]
    question_index = profile["current_question"]

    if block_index >= len(psychographic_questions):
        try:
            await save_profile_to_db(user_id, profile["answers"])
            await update.message.reply_text("✅ Психографический портрет сохранён.")
            context.user_data.pop("profile", None)
        except Exception as e:
            await update.message.reply_text("⚠️ Ошибка при сохранении профиля. Попробуйте позже.")
            print(f"[SAVE PROFILE ERROR] {e}")
        return

    block = psychographic_questions[block_index]
    questions = block["questions"]

    if question_index < len(questions):
        await update.message.reply_text(questions[question_index])
    else:
        profile["current_block"] += 1
        profile["current_question"] = 0
        await ask_next_profile_question(update, context, user_id)


async def handle_profile_response(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    profile = context.user_data.get("profile")
    if not profile:
        return

    block_index = profile["current_block"]
    question_index = profile["current_question"]
    block = psychographic_questions[block_index]
    key = block["key"]

    profile["answers"][key].append(update.message.text)
    profile["current_question"] += 1
    await ask_next_profile_question(update, context, user_id)


async def check_user_profile_exist(user_id: int) -> bool:
    return await asyncio.to_thread(_sync_check_user_profile_exist, user_id)


def _sync_check_user_profile_exist(user_id: int) -> bool:
    conn = None
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()

        cur.execute("SELECT 1 FROM user_profiles WHERE user_id = %s LIMIT 1", (user_id,))
        exists = cur.fetchone() is not None

        cur.close()
        return exists
    except Exception as e:
        print(f"[DB ERROR] {e}")
        return False
    finally:
        if conn:
            conn.close()


async def confirm_delete_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    has_profile = await check_user_profile_exist(user_id)
    if not has_profile:
        await update.message.reply_text("У вас нет сохраненного психографического портрета")
        return

    keyboard = [
        [InlineKeyboardButton("✅ Да", callback_data="delete_profile_yes")],
        [InlineKeyboardButton("❌ Нет", callback_data="delete_profile_no")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Вы уверены, что хотите удалить свой психографический портрет?",
        reply_markup=reply_markup
    )


async def handle_profile_delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    user_id = context.user_data.get("checked_user")

    if data == "delete_profile_yes":
        try:
            await delete_profile_from_db(user_id)
            await query.message.edit_text("🗑️ Профиль успешно удалён.")
        except Exception as e:
            await query.message.edit_text("⚠️ Ошибка при удалении профиля.")
            print(f"[DELETE ERROR] {e}")
    else:
        await query.message.edit_text("Удаление отменено.")


async def delete_profile_from_db(user_id: int):
    return await asyncio.to_thread(_sync_delete_profile_from_db, user_id)


def _sync_delete_profile_from_db(user_id: str):
    #encrypted_id = hash_user_id(user_id)#encrypt_user_id(user_id)
    conn = None
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()

        # Явная проверка существования записи
        cur.execute("SELECT 1 FROM user_profiles WHERE user_id = %s", (user_id,))
        if not cur.fetchone():
            print(f"[DELETE] Запись для user_id={user_id} не найдена")
            return False

        # Удаление с подтверждением
        cur.execute("DELETE FROM user_profiles WHERE user_id = %s RETURNING user_id", (user_id,))
        deleted_id = cur.fetchone()

        if deleted_id:
            conn.commit()  # Явный коммит перед закрытием
            print(f"[DELETE] Удалена запись: {deleted_id[0]}")
            return True
        return False

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[DELETE ERROR] {e}")
        raise
    finally:
        if conn:
            conn.close()


async def get_profile_from_db(user_id: str):
    return await asyncio.to_thread(_sync_get_profile_from_db, user_id)


def _sync_get_profile_from_db(user_id: str):
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()

        cur.execute("""
            SELECT demography, lifestyle_and_values, character, hobby
            FROM user_profiles
            WHERE user_id = %s
            LIMIT 1
        """, (user_id,))

        row = cur.fetchone()
        if row is None:
            print(f"[DB INFO] Профиль для user_id={user_id} не найден")
            return None

        # JSON поля уже десериализованы
        demography = row[0]
        lifestyle_and_values = row[1]
        character = row[2]
        hobby = row[3]

        return {
            'demography': demography,
            'lifestyle_and_values': lifestyle_and_values,
            'character': character,
            'hobby': hobby
        }

    except Exception as e:
        print(f"[DB ERROR] {e}")
        raise
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()


def format_profile_answers(answers: dict) -> str:
    result_parts = []

    demography = answers.get("demography", [])
    if demography:
        family = demography[0] if len(demography) > 0 else "не указано"
        age_range = demography[1] if len(demography) > 1 else "неизвестный возраст"

        family_template = f"Семейное положение: {family}."
        age_template = f"Возраст: {age_range}."

        result_parts.append(family_template)
        result_parts.append(age_template)

    lifestyle = answers.get("lifestyle_and_values", [])
    if lifestyle:
        occupation = lifestyle[0] if len(lifestyle) > 0 else ""
        priorities = lifestyle[1] if len(lifestyle) > 1 else ""
        routine = lifestyle[2] if len(lifestyle) > 2 else ""
        health_factors = lifestyle[3] if len(lifestyle) > 3 else ""
        balance = lifestyle[4] if len(lifestyle) > 4 else ""

        lifestyle_text = f"Занимается: {occupation}. "
        if priorities:
            lifestyle_text += f"Приоритеты: {priorities}. "
        if routine:
            lifestyle_text += f"Типичный день: {routine}. "
        if health_factors:
            lifestyle_text += f"На решения о здоровье влияют: {health_factors}. "
        if balance:
            lifestyle_text += f"Баланс между делами и отдыхом: {balance}."

        result_parts.append(lifestyle_text.strip())

    character = answers.get("character", [])
    if character:
        traits = character[0] if len(character) > 0 else ""
        intro_extro = character[1] if len(character) > 1 else ""

        char_template = f"Черты личности: {traits}."
        temper_templates = f"Тип темперамента: {intro_extro}."

        result_parts.append(char_template)
        result_parts.append(temper_templates)

    hobby = answers.get("hobby", [])
    if hobby:
        hobbies = hobby[0] if len(hobby) > 0 else ""
        sport = hobby[1] if len(hobby) > 1 else ""
        news = hobby[2] if len(hobby) > 2 else ""

        hobby_text = f"Хобби: {hobbies}. "
        hobby_text += f"Отношение к спорту: {sport}. "
        hobby_text += f"Интерес к новостям: {news}."

        result_parts.append(hobby_text.strip())

    return " ".join(result_parts)


async def get_formatted_profile_from_db(user_id: str) -> str | None:
    profile = await get_profile_from_db(user_id)
    if not profile:
        return None
    return format_profile_answers(profile)
