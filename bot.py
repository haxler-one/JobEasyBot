import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ========== НАСТРОЙКИ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ RAILWAY ==========
TOKEN = os.environ.get("TOKEN", "8556395320:AAHP5utdJlFvyZQDRiFBOvC_vpVCYJAkVU0")
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "@jobeasyco")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", -1003772994069))

# ========== ИНИЦИАЛИЗАЦИЯ ==========
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ========== ХРАНЕНИЕ ПОПЫТОК (в памяти) ==========
user_attempts = {}  # {user_id: {"count": 1, "last_time": timestamp}}

# ========== МАШИНА СОСТОЯНИЙ ==========
class Form(StatesGroup):
    vacancy = State()    # Новаяп: на какую вакансию откликнулись
    name = State()
    city = State()
    experience = State()

# ========== КЛАВИАТУРЫ ==========
def sub_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Я подписался", callback_data="check_sub")
    return builder.as_markup()

# ========== ПРОВЕРКА ЛИМИТА ПОПЫТОК ==========
def check_attempts_limit(user_id: int) -> bool:
    """Проверяет, не превысил ли пользователь лимит попыток (2 заявки)"""
    if user_id not in user_attempts:
        return True  # Нет попыток - можно отправлять
    
    user_data = user_attempts[user_id]
    
    # Сбрасываем счётчик, если прошло больше 24 часов
    if datetime.now() - user_data["last_time"] > timedelta(hours=24):
        user_attempts[user_id] = {"count": 0, "last_time": datetime.now()}
        return True
    
    # Проверяем лимит
    if user_data["count"] >= 2:
        return False  # Лимит исчерпан
    return True  # Можно отправить

# ========== УВЕЛИЧЕНИЕ СЧЁТЧИКА ПОПЫТОК ==========
def increment_attempts(user_id: int):
    """Увеличивает счётчик попыток для пользователя"""
    if user_id not in user_attempts:
        user_attempts[user_id] = {"count": 1, "last_time": datetime.now()}
    else:
        user_attempts[user_id]["count"] += 1
        user_attempts[user_id]["last_time"] = datetime.now()

# ========== КОМАНДА /START ==========
@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    # Проверяем лимит попыток
    if not check_attempts_limit(message.from_user.id):
        await message.answer(
            "⚠️ <b>Вы исчерпали лимит заявок</b>\n\n"
            "Вы можете отправить не более 2 заявок в сутки.\n"
            "Попробуйте завтра или обратитесь к администратору.",
            parse_mode="HTML"
        )
        return
    
    await state.clear()
    await message.answer(
        "👋 <b>Добро пожаловать в JobEasy!</b>\n\n"
        f"📌 Для продолжения подпишитесь на наш канал: {CHANNEL_USERNAME}\n\n"
        "<i>После подписки нажмите кнопку ниже:</i>",
        reply_markup=sub_keyboard(),
        parse_mode="HTML"
    )
    logging.info(f"Пользователь {message.from_user.id} запустил бота")

# ========== ПРОВЕРКА ПОДПИСКИ ==========
@dp.callback_query(F.data == "check_sub")
async def check_subscription(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    # Ещё раз проверяем лимит
    if not check_attempts_limit(user_id):
        await callback.message.edit_text(
            "⚠️ <b>Вы исчерпали лимит заявок</b>\n\n"
            "Вы можете отправить не более 2 заявок в сутки.\n"
            "Попробуйте, пожалуйста, завтра.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    try:
        # Проверяем подписку
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            await callback.message.edit_text(
                "✅ <b>Отлично! Теперь заполните форму.</b>\n\n"
                "1. <b>На какую вакансию вы откликнулись?</b>\n"
                "<i>Напишите название вакансии полностью</i>\n"
                "<i>Пример: Помощник менеджера по продажам</i>",
                parse_mode="HTML"
            )
            await state.set_state(Form.vacancy)  # Первый шаг - вакансия
            await callback.answer()
        else:
            await callback.answer("❌ Вы не подписались на канал", show_alert=True)
    except Exception as e:
        logging.error(f"Ошибка проверки подписки: {e}")
        await callback.answer("⚠️ Ошибка проверки. Попробуйте позже.", show_alert=True)

# ========== ШАГ 1: ВАКАНСИЯ ==========
@dp.message(Form.vacancy)
async def process_vacancy(message: types.Message, state: FSMContext):
    await state.update_data(vacancy=message.text)
    await message.answer(
        "2. <b>Ваше имя и возраст?</b>\n"
        "<i>Пример: Алексей, 24 года</i>",
        parse_mode="HTML"
    )
    await state.set_state(Form.name)

# ========== ШАГ 2: ИМЯ ==========
@dp.message(Form.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("3. <b>Ваш город проживания?</b>", parse_mode="HTML")
    await state.set_state(Form.city)

# ========== ШАГ 3: ГОРОД ==========
@dp.message(Form.city)
async def process_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text)
    await message.answer(
        "4. <b>Почему вы хотите эту позицию?</b>\n"
        "<i>Кратко опишите ваш опыт или мотивацию (3-4 предложения):</i>",
        parse_mode="HTML"
    )
    await state.set_state(Form.experience)

# ========== ШАГ 4: ОПЫТ И ОТПРАВКА ==========
@dp.message(Form.experience)
async def process_experience(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    
    # Формируем сообщение для админа
    admin_text = (
        "🎯 <b>НОВЫЙ ОТКЛИК</b>\n\n"
        f"👤 @{message.from_user.username or 'без username'}\n"
        f"🆔 ID: {message.from_user.id}\n"
        f"📌 Вакансия: {user_data['vacancy']}\n"
        f"📛 Имя: {user_data['name']}\n"
        f"🏙️ Город: {user_data['city']}\n"
        f"📝 Опыт/мотивация:\n{message.text}\n\n"
        f"⏰ {message.date.strftime('%d.%m.%Y %H:%M')}"
    )
    
    # Отправляем заявку в админ-чат
    try:
        await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=admin_text,
            parse_mode="HTML"
        )
        logging.info(f"Заявка отправлена в чат {ADMIN_CHAT_ID}")
        
        # Увеличиваем счётчик попыток ТОЛЬКО при успешной отправке
        increment_attempts(message.from_user.id)
        
        # Ответ пользователю об успехе
        attempts_left = 2 - user_attempts.get(message.from_user.id, {}).get("count", 0)
        await message.answer(
            "✅ <b>Спасибо! Ваша заявка успешно отправлена.</b>\n\n"
            f"📌 <b>Вакансия:</b> {user_data['vacancy']}\n"
            f"👤 <b>Вы:</b> {user_data['name']}\n"
            f"🏙️ <b>Город:</b> {user_data['city']}\n\n"
            f"📊 <i>Осталось попыток на сегодня: {attempts_left}</i>\n\n"
            "Наша команда рассмотрит вашу кандидатуру в течение 1-3 рабочих дней.\n"
            f"✅ Вы подписаны на канал {CHANNEL_USERNAME}",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logging.error(f"Не удалось отправить заявку: {e}")
        
        # Предлагаем попробовать снова (не считаем как попытку)
        await message.answer(
            "❌ <b>Не удалось отправить заявку</b>\n\n"
            "Попробуйте ещё раз через несколько минут.\n\n"
            "<i>Эта ошибка не засчитана как попытка.</i>",
            parse_mode="HTML"
        )
        # Не очищаем состояние, чтобы пользователь мог попробовать снова
        return
    
    logging.info(f"Новая заявка от {message.from_user.username} ({message.from_user.id})")
    await state.clear()

# ========== КОМАНДА /ATTEMPTS - ПРОВЕРИТЬ ПОПЫТКИ ==========
@dp.message(Command("attempts"))
async def check_attempts_cmd(message: types.Message):
    """Показывает сколько попыток осталось"""
    user_id = message.from_user.id
    
    if user_id in user_attempts:
        user_data = user_attempts[user_id]
        attempts_left = 2 - user_data["count"]
        last_time = user_data["last_time"].strftime("%H:%M")
        
        await message.answer(
            f"📊 <b>Ваши попытки:</b>\n\n"
            f"• Использовано: {user_data['count']}/2\n"
            f"• Осталось: {attempts_left}\n"
            f"• Последняя попытка: {last_time}\n\n"
            f"<i>Лимит сбрасывается через 24 часа после первой попытки</i>",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "📊 <b>Ваши попытки:</b>\n\n"
            "• Использовано: 0/2\n"
            "• Осталось: 2\n\n"
            "<i>Вы ещё не отправляли заявок сегодня</i>",
            parse_mode="HTML"
        )

# ========== КОМАНДА ДЛЯ ПОЛУЧЕНИЯ ID ==========
@dp.message(Command("id"))
async def get_chat_id(message: types.Message):
    chat_id = message.chat.id
    await message.answer(f"<code>{chat_id}</code>", parse_mode="HTML")

# ========== КОМАНДА ДЛЯ ПРОВЕРКИ ==========
@dp.message(Command("ping"))
async def ping(message: types.Message):
    await message.answer("✅ Бот работает!")

# ========== ЗАПУСК БОТА ==========
async def main():
    logging.info("=== JobEasy Bot запускается ===")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
