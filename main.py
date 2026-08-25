import asyncio
import os
import base64
from collections import deque
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
REVIEW_GROUP_ID = int(os.getenv("REVIEW_GROUP_ID"))

SOURCE_CHAT_IDS = [
    -1004476147854,
    -1004441092241,
    -1004451757944,
    -1003833659044
]

MAX_MESSAGES = 40

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
client = Groq(api_key=GROQ_API_KEY)

messages_storage = deque(maxlen=MAX_MESSAGES)


async def describe_photo(file_id: str) -> str:
    """Скачивает фото и просит ИИ описать его"""
    try:
        file = await bot.get_file(file_id)
        file_path = file.file_path
        
        # Скачиваем файл
        file_bytes = await bot.download_file(file_path)
        image_data = file_bytes.read()
        
        # Кодируем в base64
        base64_image = base64.b64encode(image_data).decode("utf-8")
        
        # Отправляем на vision-модель
        completion = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Кратко опиши, что изображено на этом фото. Ответь на русском, 1-2 предложения."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=200
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"Ошибка при описании фото: {e}")
        return "фото (не удалось описать)"


@dp.message(F.chat.id.in_(SOURCE_CHAT_IDS))
async def collect_messages(message: types.Message):
    text_to_save = None
    user_name = message.from_user.full_name if message.from_user else "Канал"

    if message.text:
        text_to_save = f"{user_name}: {message.text}"
    
    elif message.photo:
        # Берём самое большое фото
        photo = message.photo[-1]
        caption = message.caption or ""
        
        description = await describe_photo(photo.file_id)
        
        if caption:
            text_to_save = f"{user_name}: [ФОТО] {description} | Подпись: {caption}"
        else:
            text_to_save = f"{user_name}: [ФОТО] {description}"
    
    elif message.caption:
        text_to_save = f"{user_name}: [МЕДИА] {message.caption}"

    if text_to_save:
        messages_storage.append(text_to_save)
        print(f"Сохранил: {text_to_save[:80]}... | Всего: {len(messages_storage)}")


@dp.message(Command("generate"))
async def generate_post(message: types.Message):
    if message.chat.id != REVIEW_GROUP_ID:
        return await message.answer("Эту команду можно использовать только в группе оценки.")

    if len(messages_storage) < 3:
        return await message.answer("Пока мало сообщений для генерации. Нужно хотя бы 3.")

    await message.answer("Генерирую пост, подожди 15–30 секунд...")

    all_text = "\n".join(list(messages_storage)[-25:])

    prompt = f"""
Ты — опытный редактор новостного Telegram-канала про Minecraft-сервер.
На основе этих сообщений (включая описания фото) сделай один крутой, живой пост.

Требования:
- Пиши живо и по-человечески
- Длина 350–800 символов
- Можно использовать эмодзи
- Не выдумывай факты
- Если были фото — учти, что на них было изображено
- В конце лёгкий призыв

Сообщения:
{all_text}

Напиши только готовый пост, без пояснений.
"""

    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=800
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
    if message.chat.id != REVIEW_GROUP_ID:
        return await message.answer("Эту команду можно использовать только в группе оценки.")

    count = len(messages_storage)
    if count == 0:
        return await message.answer("Сейчас в памяти 0 сообщений.")

    last_messages = list(messages_storage)[-10:]
    text = f"Сейчас в памяти {count} сообщений:\n\n"
    for i, msg in enumerate(last_messages, 1):
        short = msg[:180] + ("..." if len(msg) > 180 else "")
        text += f"{i}. {short}\n\n"

    await message.answer(text)


@dp.message(Command("clear"))
async def clear_messages(message: types.Message):
    if message.chat.id != REVIEW_GROUP_ID:
        return await message.answer("Эту команду можно использовать только в группе оценки.")

    messages_storage.clear()
    await message.answer("Память очищена. Бот забыл все предыдущие сообщения.")


async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
