import os
import logging
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.fsm.strategy import FSMStrategy
from dotenv import load_dotenv

from handlers.user_handlers import router
from bd.db import create_table, init_ratings_table
from handlers.admin_handlers import admin
from middleware.absolut_middleware import AbsolutMiddleware

admin.message.middleware(AbsolutMiddleware())


async def main():
    print('Бот запущен!')
    load_dotenv()
    create_table()
    init_ratings_table()
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=os.getenv('BOT_API'))
    dp = Dispatcher(maintenance_mode=False, fsm_strategy=FSMStrategy.CHAT)
    dp.include_routers(router, admin)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())