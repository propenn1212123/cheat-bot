# main.py
import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import TOKEN
from database import db
from handlers import router

logging.basicConfig(level=logging.INFO)

async def main():
    # Инициализация БД
    await db.init()
    print("✅ База данных готова")
    
    # Запуск бота
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    
    print("🚀 Бот запущен!")
    print("📱 Админ-панель: /admin")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())