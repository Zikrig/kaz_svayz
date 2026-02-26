import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.types import InputMediaDocument, InputMediaPhoto
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import keyboards
from app.models import SupplierResponse, SupplyRequest, User


def normalize_phone(raw: str) -> str:
    digits = "".join(ch for ch in raw if ch.isdigit())
    return digits


def pack_media(items: list[dict]) -> str:
    return json.dumps(items, ensure_ascii=False)


def unpack_media(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def request_text_view(request: SupplyRequest) -> str:
    return (
        f"Заявка #{request.id}\n"
        f"Статус: {request.status}\n\n"
        f"Что нужно:\n{request.text}"
    )


def response_text_view(response: SupplierResponse) -> str:
    return (
        f"Отклик #{response.id}\n"
        f"Цена: {response.price_text}\n"
        f"Срок: {response.eta_text}\n\n"
        f"Описание:\n{response.description}\n\n"
        f"Статус отклика: {response.status}"
    )


def user_contact_view(user: User) -> str:
    if user.username:
        return f"https://t.me/{user.username}"
    if user.phone:
        return user.phone
    return f"tg://user?id={user.tg_id}"


async def send_media_and_text(
    bot: Bot,
    chat_id: int,
    text: str,
    media_items: list[dict] | None = None,
    reply_markup=None,
) -> None:
    media_items = media_items or []
    if media_items:
        media_group = []
        for idx, item in enumerate(media_items):
            caption = text if idx == 0 else None
            if item.get("type") == "document":
                media_group.append(InputMediaDocument(media=item["file_id"], caption=caption))
            else:
                media_group.append(InputMediaPhoto(media=item["file_id"], caption=caption))
        await bot.send_media_group(chat_id=chat_id, media=media_group)
        if reply_markup:
            await bot.send_message(chat_id=chat_id, text="Действия:", reply_markup=reply_markup)
    else:
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)


@dataclass
class QueuedEvent:
    kind: str
    payload: dict


class ProcessGate:
    def __init__(self) -> None:
        self.busy_until: dict[int, datetime] = {}
        self.busy_reason: dict[int, str] = {}
        self.pending: dict[int, list[QueuedEvent]] = {}
        self._lock = asyncio.Lock()

    async def set_busy(self, tg_id: int, reason: str, timeout_seconds: int) -> None:
        async with self._lock:
            self.busy_until[tg_id] = datetime.utcnow() + timedelta(seconds=timeout_seconds)
            self.busy_reason[tg_id] = reason

    async def is_busy(self, tg_id: int) -> bool:
        async with self._lock:
            expires = self.busy_until.get(tg_id)
            if not expires:
                return False
            if expires < datetime.utcnow():
                self.busy_until.pop(tg_id, None)
                self.busy_reason.pop(tg_id, None)
                return False
            return True

    async def clear_busy(self, tg_id: int) -> list[QueuedEvent]:
        async with self._lock:
            self.busy_until.pop(tg_id, None)
            self.busy_reason.pop(tg_id, None)
            queued = self.pending.pop(tg_id, [])
        return queued

    async def queue(self, tg_id: int, event: QueuedEvent) -> None:
        async with self._lock:
            self.pending.setdefault(tg_id, []).append(event)

    async def expired_ids(self) -> list[int]:
        now = datetime.utcnow()
        async with self._lock:
            items = [(uid, dt) for uid, dt in self.busy_until.items() if dt < now]
            ids = [uid for uid, _ in items]
            for uid in ids:
                self.busy_until.pop(uid, None)
                self.busy_reason.pop(uid, None)
        return ids


async def notify_supplier_about_request(
    bot: Bot,
    gate: ProcessGate,
    supplier_tg_id: int,
    request: SupplyRequest,
) -> None:
    event = QueuedEvent(kind="new_request", payload={"request_id": request.id})
    if await gate.is_busy(supplier_tg_id):
        await gate.queue(supplier_tg_id, event)
        return
    await send_media_and_text(
        bot=bot,
        chat_id=supplier_tg_id,
        text=f"Новая заявка!\n\n{request_text_view(request)}",
        media_items=unpack_media(request.photos_json),
        reply_markup=keyboards.supplier_request_kb(request.id),
    )


async def notify_consumer_about_response(
    bot: Bot,
    gate: ProcessGate,
    consumer_tg_id: int,
    request: SupplyRequest,
    response: SupplierResponse,
) -> None:
    event = QueuedEvent(
        kind="new_response",
        payload={"request_id": request.id, "response_id": response.id},
    )
    if await gate.is_busy(consumer_tg_id):
        await gate.queue(consumer_tg_id, event)
        return
    text = (
        f"По вашей заявке пришел отклик.\n\n{request_text_view(request)}\n\n"
        f"{response_text_view(response)}"
    )
    await send_media_and_text(
        bot=bot,
        chat_id=consumer_tg_id,
        text=text,
        media_items=unpack_media(response.photos_json),
        reply_markup=keyboards.response_item_kb(response.id, request.id),
    )


async def flush_user_queue(
    bot: Bot,
    gate: ProcessGate,
    session: AsyncSession,
    tg_id: int,
) -> None:
    events = await gate.clear_busy(tg_id)
    if not events:
        return

    for event in events:
        if event.kind == "new_request":
            req = await session.get(SupplyRequest, event.payload["request_id"])
            if req and req.status == "open":
                await send_media_and_text(
                    bot=bot,
                    chat_id=tg_id,
                    text=f"Новая заявка!\n\n{request_text_view(req)}",
                    media_items=unpack_media(req.photos_json),
                    reply_markup=keyboards.supplier_request_kb(req.id),
                )
        elif event.kind == "new_response":
            req = await session.get(SupplyRequest, event.payload["request_id"])
            resp = await session.get(SupplierResponse, event.payload["response_id"])
            if req and resp and req.status == "open":
                await send_media_and_text(
                    bot=bot,
                    chat_id=tg_id,
                    text=(
                        f"По вашей заявке пришел отклик.\n\n"
                        f"{request_text_view(req)}\n\n{response_text_view(resp)}"
                    ),
                    media_items=unpack_media(resp.photos_json),
                    reply_markup=keyboards.response_item_kb(resp.id, req.id),
                )


async def timeout_watcher(
    bot: Bot,
    gate: ProcessGate,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    while True:
        await asyncio.sleep(5)
        expired = await gate.expired_ids()
        for tg_id in expired:
            async with session_factory() as session:
                await bot.send_message(
                    chat_id=tg_id,
                    text="Ошибка, повторите действие позже. Вы возвращены в обычный режим.",
                )
                await flush_user_queue(bot, gate, session, tg_id)


async def get_or_create_user(session: AsyncSession, tg_user) -> User:
    stmt = select(User).where(User.tg_id == tg_user.id)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user:
        user.username = tg_user.username
        user.full_name = tg_user.full_name
        await session.commit()
        return user

    role = "consumer"
    user = User(
        tg_id=tg_user.id,
        username=tg_user.username,
        full_name=tg_user.full_name,
        role=role,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
