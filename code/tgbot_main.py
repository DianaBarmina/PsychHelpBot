import os
import torch
from transformers import Wav2Vec2FeatureExtractor, HubertForSequenceClassification
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from pydub import AudioSegment
from dotenv import load_dotenv
import soundfile as sf
import whisper
from mistralai_experiment import generate_response_for_emotion, classificate_emotions, generate_empathic_response
from tests_questionare import PHQ9_QUESTIONS, GAD7_QUESTIONS, Questionnaire, interpret_phq9, \
    interpret_gad7
from test_result import save_test_result, confirm_delete_tests_request, delete_test_results, \
    handle_delete_tests_callback, check_test_results_exist, create_tests_chart
from psychograph_profile import start_psychographic_profile, handle_profile_response, confirm_delete_profile,\
    handle_profile_delete_callback, get_formatted_profile_from_db, delete_profile_from_db, check_user_profile_exist
from save_emotions import save_emotions_to_db, handle_delete_emotions_callback, confirm_delete_emotions_request, \
    delete_user_emotions, check_emotions_exist, get_emotions_stats, create_emotions_chart
from voice_convert import convert_ogg_to_wav
from confidential import save_user_consent, check_user_consent, consent_text, delete_user_consent


AudioSegment.converter = "C:\\ffmpeg\\ffmpeg-7.1.1-essentials_build\\bin\\ffmpeg.exe"
AudioSegment.ffprobe = "C:\\ffmpeg\\ffmpeg-7.1.1-essentials_build\\bin\\ffprobe.exe"
os.environ["PATH"] += os.pathsep + r"C:\ffmpeg\ffmpeg-7.1.1-essentials_build\bin"

load_dotenv()
TELEBOT_API_TOKEN = os.getenv("TELEBOT_API_TOKEN")

# Загрузка модели классификации эмоций голосовых сообщений
feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained("xbgoose/hubert-large-speech-emotion-recognition-russian-dusha-finetuned")
model = HubertForSequenceClassification.from_pretrained("xbgoose/hubert-large-speech-emotion-recognition-russian-dusha-finetuned")

# Загрузка модели speech-to-text
asr_model = whisper.load_model("tiny")

PHQ9 = Questionnaire("PHQ-9 (Депрессия)", PHQ9_QUESTIONS, interpret_phq9)
GAD7 = Questionnaire("GAD-7 (Тревожность)", GAD7_QUESTIONS, interpret_gad7)

'''main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("Пройти тест на депрессию")],
        [KeyboardButton("Пройти тест на тревожность")],
        [KeyboardButton("📋 Пройти психографический опрос")],
        [KeyboardButton("🗑️ Удалить психографический профиль")],
        [KeyboardButton("/edit_privacy")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)'''

consent_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("✅ Я соглашаюсь", callback_data="consent_yes")]
])

revoke_consent_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("❌ Отозвать согласие", callback_data="consent_revoke")]
])


def send_personalized_keyboard(is_checked):

    keyboard = [
        [KeyboardButton("Пройти тест на депрессию")],
        [KeyboardButton("Пройти тест на тревожность")],
    ]

    if is_checked:
        keyboard.extend([
            [KeyboardButton("📋 Пройти психографический опрос")],
            [KeyboardButton("🗑️ Удалить психографический профиль")],
            [KeyboardButton("🗑️ Удалить результаты тестов")],
            [KeyboardButton("🗑️ Удалить историю эмоций")],
            [KeyboardButton("Мои эмоции: история")],
            [KeyboardButton("Мои тесты: история")]
        ])

    keyboard.append([KeyboardButton("/edit_privacy")])
    reply_markup = ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )

    return reply_markup


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    checked_user = await check_user_consent(user_id)
    print(checked_user)

    if checked_user:
        reply_keyboard = send_personalized_keyboard(is_checked=True)
        await update.message.reply_text(
            "Добро пожаловать обратно! 😊\nТы можешь поделиться своими мыслями или пройти тест.",
            reply_markup=reply_keyboard
        )
        return
    else:
        reply_keyboard = send_personalized_keyboard(is_checked=False)
        await update.message.reply_text(
            "Привет! Я окажу тебе психологическую поддержку",
            reply_markup=reply_keyboard
        )

    await update.message.reply_text(
        consent_text,
        parse_mode="Markdown",
        reply_markup=consent_keyboard
    )


async def edit_privacy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if await check_user_consent(user_id):
        await update.message.reply_text(
            f"✅ Вы ранее уже дали согласие на обработку данных:\n\n{consent_text}",
            parse_mode="Markdown",
            reply_markup=revoke_consent_keyboard
        )
    else:
        await update.message.reply_text(
            f"Вы ещё не дали согласие на обработку данных.\n\n{consent_text}",
            parse_mode="Markdown",
            reply_markup=consent_keyboard
        )


def transcribe_speech(audio_path):
    result = asr_model.transcribe(audio_path, language="ru")
    return result["text"]


def predict_emotion(audio_path):
    waveform, sr = sf.read(audio_path)
    waveform = torch.tensor(waveform).float()

    # Если несколько каналов (стерео), оставим только один
    if waveform.ndim > 1:
        waveform = waveform.mean(dim=1)

    # Приведение к нужной форме
    inputs = feature_extractor(waveform, sampling_rate=sr, return_tensors="pt", padding=True)

    with torch.no_grad():
        logits = model(**inputs).logits

    predicted_class_id = int(torch.argmax(logits, dim=-1))
    predicted_label = model.config.id2label[predicted_class_id]
    return predicted_label


async def send_questionnaire_question1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    questionnaire = context.user_data['test']
    idx = context.user_data['question_index']
    question = questionnaire.get_question(idx)

    keyboard = [
        [InlineKeyboardButton(text, callback_data=f"answer_{value}")]
        for text, value in questionnaire.get_options()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.message.edit_text(question, reply_markup=reply_markup)
    else:
        await update.message.reply_text(question, reply_markup=reply_markup)


async def send_questionnaire_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    questionnaire = context.user_data['test']
    idx = context.user_data['question_index']

    # Проверяем, нужно ли отправить вступительное сообщение
    if idx == 0:
        intro_text = "Как часто вас беспокоили следующие проблемы за последние 2 недели?"
        keyboard = [
            [InlineKeyboardButton("Начать тест", callback_data="start_questions")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.callback_query:
            await update.callback_query.message.edit_text(intro_text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(intro_text, reply_markup=reply_markup)
        return

    # Отправка обычного вопроса теста
    question = questionnaire.get_question(idx - 1)  # -1 потому что первый индекс теперь для вступления

    keyboard = [
        [InlineKeyboardButton(text, callback_data=f"answer_{value}")]
        for text, value in questionnaire.get_options()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.message.edit_text(question, reply_markup=reply_markup)
    else:
        await update.message.reply_text(question, reply_markup=reply_markup)


async def emotions_period_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    checked_user = await check_user_consent(user_id)

    emotions_type = context.user_data.get('emotions_type')

    period_map = {
        "emotions_week": 7,
        "emotions_month": 30,
        "emotions_3months": 90,
        "emotions_year": 365
    }

    period_days = period_map.get(query.data, 7)
    period_name = query.data.replace("emotions_", "").replace("3months", "3 месяца")

    try:
        # Получаем данные из БД
        #stats = await get_emotions_stats(checked_user, period_days)
        stats = await get_emotions_stats(checked_user, period_days, emotions_type)  # Передаем тип эмоций

        if not stats:
            await query.edit_message_text(f"Нет данных об эмоциях за {period_name}")
            return

        # Создаем диаграмму
        #chart = await create_emotions_chart(stats, period_name)
        chart = await create_emotions_chart(stats, period_name, emotions_type)  # Передаем тип для стилизации

        # Отправляем изображение
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=chart,
            caption=f"Статистика {'текстовых' if emotions_type == 'text' else 'голосовых'} эмоций за {period_name}"
        )

        # Удаляем сообщение с кнопками
        await query.message.delete()

    except Exception as e:
        print(f"Error generating emotions chart: {e}")
        await query.edit_message_text("Произошла ошибка при генерации статистики")


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    user_id = query.from_user.id
    checked_user = await check_user_consent(user_id)
    #new
    if data == "start_questions":
        context.user_data['question_index'] = 1  # Начинаем с первого вопроса
        await send_questionnaire_question(update, context)
        return

    if data.startswith("start_"):
        test_name = data.split("_")[1]
        questionnaire = PHQ9 if test_name == "PHQ9" else GAD7

        context.user_data['test'] = questionnaire
        context.user_data['score'] = 0
        context.user_data['question_index'] = 0
        context.user_data['phq9_short_check_done'] = False

        await send_questionnaire_question(update, context)

    elif data.startswith("answer_"):
        score = int(data.split("_")[1])
        context.user_data['score'] += score
        context.user_data['question_index'] += 1
        questionnaire = context.user_data['test']
        index = context.user_data['question_index']

        # Раннее завершение PHQ-9
        if questionnaire.name.startswith("PHQ") and not context.user_data.get("phq9_short_check_done"):
            if index == 3:
                context.user_data['phq9_short_check_done'] = True
                total = context.user_data['score']

                if total < 2 or total >= 4:

                    interpretation = "Депрессия маловероятна." if total < 2 else "Возможна выраженная депрессия"

                    await query.message.edit_text(
                        f"✅ Тест *{questionnaire.name}* завершён.\n"
                        f"Ваш балл: *{total}*\n\n"
                        f"{interpretation}",
                        parse_mode="Markdown"
                    )

                    phq_results = f"Результат теста PHQ-2: {total} балла" + interpretation

                    if checked_user:
                        await save_test_result(checked_user, "phq_2", total)
                        full_profile = await get_formatted_profile_from_db(checked_user)
                    else:
                        full_profile = None

                    #response = generate_response_for_emotion(phq_results=phq_results, profile=full_profile)

                    response, emotions = generate_empathic_response(phq_results=phq_results, profile=full_profile)

                    await query.message.reply_text(response)
                return

        if index < len(questionnaire.questions)+1:
            await send_questionnaire_question(update, context)
        else:
            total = context.user_data['score']
            interpretation = questionnaire.interpret_result(total)

            test_type = "phq_9" if questionnaire == PHQ9 else "gad_7"

            await query.message.edit_text(
                f"✅ Тест *{questionnaire.name}* завершён.\n"
                f"Ваш балл: *{total}*\n\n"
                f"{interpretation}",
                parse_mode="Markdown"
                # reply_markup=main_keyboard
            )
            results = f"Результат теста {questionnaire.name}: {total} балла" + interpretation
            if checked_user:
                await save_test_result(checked_user, test_type, total)
                full_profile = await get_formatted_profile_from_db(checked_user)
            else:
                full_profile = None

            if questionnaire == PHQ9:
                #response = generate_response_for_emotion(phq_results=results,
                #                                         profile=full_profile
                #                                         )
                response, emotions = generate_empathic_response(phq_results=results, profile=full_profile)
            else:
                #response = generate_response_for_emotion(gad_results=results,
                #                                         profile=full_profile
                #                                         )
                response, emotions = generate_empathic_response(gad_results=results, profile=full_profile)

            await query.message.reply_text(response)

            # await query.message.reply_text(
            #    "Вы можете пройти другой тест или отправить голосовое сообщение.",
            #    reply_markup=main_keyboard
            # )
    elif data == "consent_yes":
        user_id = update.effective_user.id
        await save_user_consent(user_id)
        reply_markup = send_personalized_keyboard(is_checked=True)
        await query.message.edit_text(
            "✅ Спасибо за согласие!",
            parse_mode="Markdown",
        )
        await query.message.reply_text(
            "Теперь тебе доступно составление психографического портрета",
            reply_markup=reply_markup
        )
    elif data == "consent_revoke":
        user_id = update.effective_user.id
        await delete_user_consent(user_id)

        checked_user = await check_user_consent(user_id)

        # Удаляем все связанные записи
        tests_exists = await check_test_results_exist(checked_user)
        if tests_exists:
            await delete_test_results(checked_user)
        emotions_exists = await check_emotions_exist(checked_user)
        if emotions_exists:
            await delete_user_emotions(checked_user)
        profile_exists = await check_user_profile_exist(checked_user)
        if profile_exists:
            await delete_profile_from_db(checked_user)

        # await confirm_delete_profile(update, context)
        reply_markup = send_personalized_keyboard(is_checked=False)
        await query.message.edit_text(
            "❌ Вы отозвали своё согласие. Данные больше не будут сохраняться.",
            parse_mode="Markdown",
        )
        await query.message.reply_text(
            "Ваш доступный функционал также стал ограничен: нельзя составить психографический портрет",
            reply_markup=reply_markup
        )


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.message.from_user.id
    checked_user = await check_user_consent(user_id)

    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)

    ogg_path = os.path.abspath(f"voice_{voice.file_id}.ogg")
    wav_path = os.path.abspath(f"voice_{voice.file_id}.wav")

    await file.download_to_drive(ogg_path)

    if not os.path.exists(ogg_path):
        await update.message.reply_text("Ошибка: голосовой файл не был загружен.")
        return

    try:
        if not os.path.exists(ogg_path):
            await update.message.reply_text("Файл не найден. Возможно, ошибка при загрузке.")
            return
        convert_ogg_to_wav(ogg_path, wav_path)
    except Exception as e:
        await update.message.reply_text(f"Ошибка при конвертации: {e}")
        return

    try:
        voice_emotion = predict_emotion(wav_path)

        if not os.path.exists(wav_path):
            await update.message.reply_text("Файл WAV не найден после конвертации.")
            return
        else:
            print("Файл WAV найден после конвертации.")
        transcription = transcribe_speech(wav_path)

        await update.message.reply_text(
            f"*Распознанная эмоция (интонация):* {voice_emotion}\n*Распознанный текст:* {transcription}",
            parse_mode="Markdown"
        )

        '''text_emotions = classificate_emotions(transcription)
        await update.message.reply_text(
            f"*Распознанные эмоции (смысл сообщения):* {text_emotions}",
            parse_mode="Markdown"
        )

        # user_id = update.message.from_user.id

        text_emotions = text_emotions.split(", ")
        text_emotions_lower = [em.lower() for em in text_emotions]'''

        if checked_user:
            '''await save_emotions_to_db(
                user_id=checked_user,
                text_emotions=text_emotions_lower,
                voice_emotions=[voice_emotion]
            )'''
            full_profile = await get_formatted_profile_from_db(checked_user)
        else:
            full_profile = None

        if full_profile is not None:
            await update.message.reply_text(
                f"*Профиль:* {full_profile}",
                parse_mode="Markdown"
            )

        '''response = generate_response_for_emotion(transcription,
                                                 text_emotions=text_emotions,
                                                 voice_emotion=voice_emotion,
                                                 profile=full_profile
                                                 )'''
        response, emotions = generate_empathic_response(transcription,
                                                        #text_emotions=text_emotions,
                                                        voice_emotion=voice_emotion,
                                                        profile=full_profile)
        if checked_user:
            await save_emotions_to_db(
                user_id=checked_user,
                text_emotions=emotions,
                voice_emotions=[voice_emotion]
            )

        await update.message.reply_text(response)

    except Exception as e:
        await update.message.reply_text(f"Ошибка при распознавании: {e}")
    finally:
        if os.path.exists(ogg_path):
            os.remove(ogg_path)
        if os.path.exists(wav_path):
            os.remove(wav_path)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.message.from_user.id
    checked_user = await check_user_consent(user_id)

    if 'profile' in context.user_data:
        if checked_user:
            await handle_profile_response(update, context, checked_user)
            return
        else:
            await update.message.reply_text(
                f"""У вас нет согласия для составления портрета""",
                parse_mode="Markdown"
            )

    if text == "📋 Пройти психографический опрос":
        if checked_user:
            await start_psychographic_profile(update, context, checked_user)
            return
        else:
            await update.message.reply_text(
                f"""Вы не можете составить свой психографический портрет, 
                так как не дали согласие на обработку и сохранение ваших данных""",
                parse_mode="Markdown"
            )
            return

    if text == "🗑️ Удалить психографический профиль":
        if checked_user:
            context.user_data["checked_user"] = checked_user
            await confirm_delete_profile(update, context, user_id=checked_user)
            return
        else:
            await update.message.reply_text(
                f"""Вы не можете удалить свой психографический портрет, 
                так как вы его не составляли""",
                parse_mode="Markdown"
            )
            return

    if text == "🗑️ Удалить результаты тестов":
        if checked_user:
            context.user_data["checked_user"] = checked_user
            await confirm_delete_tests_request(update, context, user_id=checked_user)
            return
        else:
            await update.message.reply_text(
                f"""Вы не можете удалить результаты тестов, 
                так как вы не дали согласие на их сохранение""",
                parse_mode="Markdown"
            )
            return

    if text == "🗑️ Удалить историю эмоций":
        if checked_user:
            context.user_data["checked_user"] = checked_user
            await confirm_delete_emotions_request(update, context, user_id=checked_user)
            return
        else:
            await update.message.reply_text(
                f"""Вы не можете удалить историю эмоций, 
                так как вы не дали согласие на их сохранение""",
                parse_mode="Markdown"
            )
            return

    if text == "Мои эмоции: история":
        if not checked_user:
            await update.message.reply_text(
                "Вы не можете просмотреть историю эмоций, так как не дали согласие на обработку данных",
                parse_mode="Markdown"
            )
            return

        context.user_data["checked_user"] = checked_user
        if not await check_emotions_exist(checked_user):
            await update.message.reply_text(
                "У вас пока нет сохраненных эмоций в истории",
                parse_mode="Markdown"
            )
            return

        keyboard = [
            [InlineKeyboardButton("📝 Текстовые эмоции", callback_data="emotions_type_text")],
            [InlineKeyboardButton("🎤 Голосовые эмоции", callback_data="emotions_type_voice")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Какие эмоции вы хотите проанализировать?",
            reply_markup=reply_markup
        )
        return

    if text == "Мои тесты: история":
        await handle_tests_history(update, context)
        '''if not checked_user:
            await update.message.reply_text(
                "Вы не можете просмотреть историю тестов, так как не дали согласие на обработку данных",
                parse_mode="Markdown"
            )
            return

        context.user_data["checked_user"] = checked_user
        if not await check_emotions_exist(checked_user):
            await update.message.reply_text(
                "У вас пока нет пройденных тестов",
                parse_mode="Markdown"
            )
            return

        keyboard = [
            [InlineKeyboardButton("За неделю", callback_data="tests_period_week")],
            [InlineKeyboardButton("За месяц", callback_data="tests_period_month")],
            [InlineKeyboardButton("За 3 месяца", callback_data="tests_period_3months")],
            [InlineKeyboardButton("За год", callback_data="tests_period_year")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Выберите период для просмотра результатов тестов:",
            reply_markup=reply_markup
        )'''
        return

    if text == "Пройти тест на депрессию":
        questionnaire = PHQ9
    elif text == "Пройти тест на тревожность":
        questionnaire = GAD7
    else:
        '''text_emotions = classificate_emotions(text)

        await update.message.reply_text(
            f"*Распознанные эмоции (смысл сообщения):* {text_emotions}",
            parse_mode="Markdown"
        )

        text_emotions = text_emotions.split(", ")
        text_emotions_lower = [emotion.lower() for emotion in text_emotions]

        if checked_user:
            await save_emotions_to_db(
                user_id=checked_user,
                text_emotions=text_emotions_lower,
                voice_emotions=[]
            )
            full_profile = await get_formatted_profile_from_db(checked_user)
        else:
            full_profile = None

        if full_profile is not None:
            await update.message.reply_text(
                f"*Профиль:* {full_profile}",
                parse_mode="Markdown"
            )

        response = generate_response_for_emotion(text, text_emotions=text_emotions, profile=full_profile)'''
        if checked_user:
            full_profile = await get_formatted_profile_from_db(checked_user)
        else:
            full_profile = None
        response, emotions = generate_empathic_response(text, profile=full_profile)
        print(emotions)
        if checked_user:
            await save_emotions_to_db(
                user_id=checked_user,
                text_emotions=emotions,
                voice_emotions=[]
            )
        await update.message.reply_text(response)

    context.user_data['test'] = questionnaire
    context.user_data['score'] = 0
    context.user_data['question_index'] = 0
    context.user_data['phq9_short_check_done'] = False

    reply_keyboard = send_personalized_keyboard(is_checked=False)
    await update.message.reply_text(f"Начинаем тест *{questionnaire.name}*", parse_mode="Markdown",
                                    reply_markup=reply_keyboard)
    await send_questionnaire_question(update, context)


async def emotions_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора типа эмоций"""
    query = update.callback_query
    await query.answer()
    print(query.data.split('_')[-1])

    context.user_data['emotions_type'] = query.data.split('_')[-1]

    keyboard = [
        [InlineKeyboardButton("За неделю", callback_data="emotions_period_week")],
        [InlineKeyboardButton("За месяц", callback_data="emotions_period_month")],
        [InlineKeyboardButton("За 3 месяца", callback_data="emotions_period_3months")],
        [InlineKeyboardButton("За год", callback_data="emotions_period_year")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text="Выберите период для анализа:",
        reply_markup=reply_markup
    )


async def handle_tests_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик просмотра истории тестов"""
    user_id = update.message.from_user.id
    checked_user = await check_user_consent(user_id)

    if not checked_user:
        await update.message.reply_text(
            "Вы не можете просмотреть историю тестов, так как не дали согласие на обработку данных",
            parse_mode="Markdown"
        )
        return

    if not await check_test_results_exist(checked_user):
        await update.message.reply_text(
            "У вас пока нет пройденных тестов",
            parse_mode="Markdown"
        )
        return

    keyboard = [
        [InlineKeyboardButton("За неделю", callback_data="tests_period_week")],
        [InlineKeyboardButton("За месяц", callback_data="tests_period_month")],
        [InlineKeyboardButton("За 3 месяца", callback_data="tests_period_3months")],
        [InlineKeyboardButton("За год", callback_data="tests_period_year")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Выберите период для просмотра результатов тестов:",
        reply_markup=reply_markup
    )


async def tests_period_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора периода для тестов"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    checked_user = await check_user_consent(user_id)

    period_map = {
        "tests_week": 7,
        "tests_month": 30,
        "tests_3months": 90,
        "tests_year": 365
    }

    period_days = period_map.get(query.data, 30)
    period_name = query.data.replace("tests_period", "").replace("3months", "3 месяца")

    try:
        chart = await create_tests_chart(checked_user, period_days)

        if not chart:
            await query.edit_message_text(f"Нет данных о тестах за {period_name}")
            return

        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=chart,
            caption=f"Динамика результатов тестов за {period_name}"
        )

        await query.message.delete()

    except Exception as e:
        print(f"Error generating tests chart: {e}")
        await query.edit_message_text("Произошла ошибка при генерации графика")


def main():

    application = ApplicationBuilder().token(TELEBOT_API_TOKEN).build()

    application.add_handler(CommandHandler("start", start))

    application.add_handler(CallbackQueryHandler(handle_profile_delete_callback, pattern="^delete_profile_"))
    application.add_handler(CallbackQueryHandler(handle_delete_tests_callback, pattern="^delete_tests_"))
    application.add_handler(CallbackQueryHandler(handle_delete_emotions_callback, pattern="^delete_emotions_"))
    application.add_handler(CallbackQueryHandler(emotions_type_callback, pattern="^emotions_type_"))
    application.add_handler(CallbackQueryHandler(emotions_period_callback, pattern="^emotions_period_"))
    application.add_handler(CallbackQueryHandler(tests_period_callback, pattern="^tests_period_"))
    application.add_handler(CallbackQueryHandler(handle_callback_query))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_profile_response))
    application.add_handler(MessageHandler(filters.Text("Мои эмоции: история"), handle_message))
    application.add_handler(MessageHandler(filters.Text("Мои тесты: история"), handle_tests_history))

    application.add_handler(CommandHandler("profile", start_psychographic_profile))
    application.add_handler(CommandHandler("delete_profile", confirm_delete_profile))
    application.add_handler(CommandHandler("edit_privacy", edit_privacy))
    application.add_handler(CommandHandler("delete_user_tests", confirm_delete_tests_request))
    application.add_handler(CommandHandler("delete_emotions", confirm_delete_emotions_request))

    application.run_polling()


if __name__ == "__main__":
    main()
