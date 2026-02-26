from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass
class Settings:
    bot_token: str
    admin_ids: set[int]
    database_url: str


def load_settings() -> Settings:
    load_dotenv()

    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is required in .env")

    raw_admin_ids = os.getenv("ADMIN_IDS", "")
    admin_ids: set[int] = set()
    for value in raw_admin_ids.split(","):
        value = value.strip()
        if value.isdigit():
            admin_ids.add(int(value))

    database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/bot.db")
    return Settings(bot_token=token, admin_ids=admin_ids, database_url=database_url)
