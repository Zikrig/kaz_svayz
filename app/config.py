from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass
class Settings:
    bot_token: str | None
    admin_ids: set[int]
    database_url: str
    api_token: str | None


def load_settings() -> Settings:
    load_dotenv()

    token = os.getenv("BOT_TOKEN", "").strip() or None

    raw_admin_ids = os.getenv("ADMIN_IDS", "")
    admin_ids: set[int] = set()
    for value in raw_admin_ids.split(","):
        value = value.strip()
        if value.isdigit():
            admin_ids.add(int(value))

    database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/bot.db")
    api_token = os.getenv("API_TOKEN", "").strip() or None
    return Settings(
        bot_token=token,
        admin_ids=admin_ids,
        database_url=database_url,
        api_token=api_token,
    )
