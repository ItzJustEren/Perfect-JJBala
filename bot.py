# ============================================
# فایل 6: bot.py
# ============================================

import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from database import init_db
from handlers import dp, auto_send_ideas

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def main():
    init_db()
    asyncio.create_task(auto_send_ideas())
    await dp.start_polling(Bot(token=TOKEN))

if __name__ == "__main__":
    asyncio.run(main())
