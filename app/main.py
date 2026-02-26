import asyncio
import contextlib
import logging

from aiogram import Bot, Dispatcher

from app.config import load_settings
from app import db
from app.handlers import router
from app.services import ProcessGate, timeout_watcher


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = load_settings()

    db.init_db(settings.database_url)
    await db.create_tables()

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    gate = ProcessGate()

    watcher_task = None
    if db.session_factory is not None:
        watcher_task = asyncio.create_task(timeout_watcher(bot, gate, db.session_factory))

    try:
        await dp.start_polling(
            bot,
            gate=gate,
            admin_ids=settings.admin_ids,
        )
    finally:
        if watcher_task:
            watcher_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watcher_task


if __name__ == "__main__":
    asyncio.run(main())
