import asyncio
import sqlite3
import logging
from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.types import InlineQueryResultCachedVoice, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Включаем логи
logging.basicConfig(level=logging.INFO)

# ===== НАСТРОЙКИ =====
TOKEN = "8838743887:AAGwl6r4X_ZlTgRcD4a0ezlky9Mawc_cGXE"  # Вставь токен от @BotFather
ADMIN_IDS = [5209929082]  # Вставь свой Telegram ID (число, например 123456789)

# ===== БАЗА ДАННЫХ =====
def init_db():
    conn = sqlite3.connect('sounds.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            file_id TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ База данных готова")

def add_sound(name, file_id):
    conn = sqlite3.connect('sounds.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO sounds (name, file_id) VALUES (?, ?)', (name, file_id))
    conn.commit()
    conn.close()
    print(f"✅ Добавлен звук: {name}")

def search_sounds(query):
    conn = sqlite3.connect('sounds.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, file_id FROM sounds WHERE LOWER(name) LIKE LOWER(?) LIMIT 50', (f'%{query}%',))
    results = cursor.fetchall()
    conn.close()
    return results

def get_all_sounds():
    conn = sqlite3.connect('sounds.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, file_id FROM sounds ORDER BY name')
    results = cursor.fetchall()
    conn.close()
    return results

def delete_sound(sound_id):
    conn = sqlite3.connect('sounds.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM sounds WHERE id = ?', (sound_id,))
    conn.commit()
    conn.close()

# ===== СОСТОЯНИЯ =====
class AddSound(StatesGroup):
    waiting_for_name = State()
    waiting_for_file = State()

# ===== РОУТЕР =====
router = Router()

# ===== КЛАВИАТУРЫ =====
def admin_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить звук", callback_data="add_sound")],
        [InlineKeyboardButton(text="📋 Все звуки", callback_data="list_sounds")],
        [InlineKeyboardButton(text="🗑 Удалить звук", callback_data="delete_sound")]
    ])
    return keyboard

# ===== КОМАНДА /start =====
@router.message(Command('start'))
async def cmd_start(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        await message.answer("👑 Админ-панель:", reply_markup=admin_keyboard())
    else:
        await message.answer(
            "🎵 Бот звуков Mellstroy!\n\n"
            "Как использовать:\n"
            "• Напиши @MellstroyMP3_bot в любом чате\n"
            "• Добавь название звука\n"
            "• Выбери из списка и отправь в чат"
        )

# ===== АДМИН-КНОПКИ =====
@router.callback_query(lambda c: c.data == "add_sound")
async def btn_add_sound(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("✏️ Напиши название звука:")
    await state.set_state(AddSound.waiting_for_name)
    await callback.answer()

@router.callback_query(lambda c: c.data == "list_sounds")
async def btn_list_sounds(callback: types.CallbackQuery):
    sounds = get_all_sounds()
    if not sounds:
        await callback.message.answer("❌ Нет звуков в базе")
    else:
        text = "📋 Все звуки:\n\n"
        for sound_id, name, _ in sounds:
            text += f"• ID: {sound_id} | {name}\n"
        await callback.message.answer(text)
    await callback.answer()

@router.callback_query(lambda c: c.data == "delete_sound")
async def btn_delete_sound(callback: types.CallbackQuery):
    sounds = get_all_sounds()
    if not sounds:
        await callback.message.answer("❌ Нечего удалять")
        await callback.answer()
        return
    
    text = "Выбери ID звука для удаления:\n\n"
    for sound_id, name, _ in sounds:
        text += f"• ID: {sound_id} | {name}\n"
    text += "\nИспользуй команду: /delete ID"
    await callback.message.answer(text)
    await callback.answer()

# ===== КОМАНДА УДАЛЕНИЯ =====
@router.message(Command('delete'))
async def cmd_delete(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет прав!")
        return
    
    try:
        sound_id = int(message.text.split()[1])
        delete_sound(sound_id)
        await message.answer(f"✅ Звук с ID {sound_id} удален!")
    except:
        await message.answer("❌ Используй: /delete ID_звука\nПример: /delete 1")

# ===== ДОБАВЛЕНИЕ ЗВУКА =====
@router.message(AddSound.waiting_for_name)
async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("📁 Теперь отправь звук (голосовое, аудио или файл)")
    await state.set_state(AddSound.waiting_for_file)

@router.message(AddSound.waiting_for_file)
async def get_file(message: types.Message, state: FSMContext):
    file_id = None
    
    if message.voice:
        file_id = message.voice.file_id
    elif message.audio:
        file_id = message.audio.file_id
    elif message.document:
        file_id = message.document.file_id
    elif message.video_note:
        file_id = message.video_note.file_id
    
    if not file_id:
        await message.answer("❌ Отправь голосовое, аудио или файл!")
        return
    
    data = await state.get_data()
    name = data['name']
    
    add_sound(name, file_id)
    await message.answer(f"✅ Звук '{name}' добавлен!\n\nПроверь: @MellstroyMP3_bot {name}")
    await state.clear()

# ===== ИНЛАЙН-ПОИСК =====
@router.inline_query()
async def inline_search(inline_query: types.InlineQuery):
    query = inline_query.query.strip()
    
    if not query:
        sounds = get_all_sounds()
    else:
        sounds = search_sounds(query)
    
    results = []
    for sound_id, name, file_id in sounds[:50]:
        results.append(
            InlineQueryResultCachedVoice(
                id=str(sound_id),
                voice_file_id=file_id,
                title=name
            )
        )
    
    await inline_query.answer(results, cache_time=1)

# ===== ЗАПУСК =====
async def main():
    print("🚀 Запускаю бота...")
    init_db()
    
    # Показываем сколько звуков в базе
    sounds = get_all_sounds()
    print(f"📊 Звуков в базе: {len(sounds)}")
    
    bot = Bot(token=TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    
    print("✅ Бот запущен! Ожидаю сообщения...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())