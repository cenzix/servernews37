import asyncio
import os
from collections import deque
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# === НАСТРОЙКИ (ничего сюда не вписывай) ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
REVIEW_GROUP_ID = int(os.getenv("REVIEW_GROUP_ID"))

# === ID чатов, откуда бот будет собирать сообщения ===
# Перечислите ID ваших исходных групп/каналов через запятую.
SOURCE_CHAT_IDS = [
    -1004476147854,
    -1004441092241,
    -1004451757944,
    -1003833659044
]

MAX_MESSAGES = 40
# ==========================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = Groq(api_key=GROQ_API_KEY)

messages_storage = deque(maxlen=MAX_MESSAGES)

@dp.message(F.chat.id.in_(SOURCE_CHAT_IDS))
async def collect_messages(message: types.Message):
    if message.text:
        text = f"{message.from_user.full_name if message.from_user else 'Канал'}: {message.text}"
        messages_storage.append(text)
        print(f"Сохранил сообщение. Всего: {len(messages_storage)}")

@dp.message(Command("generate"))
async def generate_post(message: types.Message):
    if message.chat.id != REVIEW_GROUP_ID:
        return await message.answer("Эту команду можно использовать только в группе оценки.")

    if len(messages_storage) < 3:
        return await message.answer("Пока мало сообщений для генерации. Нужно хотя бы 3.")

    await message.answer("Генерирую пост, подожди 10–20 секунд...")

    all_text = "\n".join(list(messages_storage)[-30:])

    prompt = f"""
Ты — опытный редактор новостного Telegram-канала про Minecraft-сервер.
На основе этих сообщений из чатов/каналов сделай один крутой, живой и интересный пост.

Требования к посту:
- Пиши живо, по-человечески, без канцелярита
- Длина 400–900 символов
- Можно использовать эмодзи
- Сделай так, чтобы хотелось прочитать до конца
- Не выдумывай факты, которых нет в сообщениях
- В конце можно добавить лёгкий призыв (зайти на сервер, написать в чат и т.д.)

Вот сообщения:
{all_text}
"""

    try:
        completion = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=800,
            top_p=0.95
        )
        post = completion.choices[0].message.content.strip()

        await bot.send_message(
            REVIEW_GROUP_ID,
            f"✨ **Новый пост от ИИ:**\n\n{post}\n\n---\nМожно редактировать и пересылать в основной канал."
        )
        await message.answer("Пост отправлен в группу оценки!")
    except Exception as e:
        await message.answer(f"Ошибка при генерации: {e}")

@dp.message(Command("status"))
async def status(message: types.Message):
    await message.answer(f"Сейчас в памяти {len(messages_storage)} сообщений.")

async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
