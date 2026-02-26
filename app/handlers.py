from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select

from app import db, keyboards
from app.models import SupplierResponse, SupplyRequest, User
from app.services import (
    ProcessGate,
    flush_user_queue,
    get_or_create_user,
    normalize_phone,
    notify_consumer_about_response,
    notify_supplier_about_request,
    pack_media,
    request_text_view,
    response_text_view,
    send_media_and_text,
    unpack_media,
    user_contact_view,
)
from app.states import AdminState, ConsumerRequestState, RegistrationState, SupplierResponseState

router = Router()


def _sf():
    if db.session_factory is None:
        raise RuntimeError("DB not initialized")
    return db.session_factory


async def send_main_menu(message: Message, user: User) -> None:
    await message.answer("Меню:", reply_markup=keyboards.menu_kb(user.role))


async def send_main_menu_cb(callback: CallbackQuery, user: User) -> None:
    await callback.message.answer("Меню:", reply_markup=keyboards.menu_kb(user.role))


def _require_admin(user: User, admin_ids: set[int]) -> bool:
    return user.tg_id in admin_ids or user.role == "admin"


@router.message(Command("start"))
async def start_cmd(message: Message, state: FSMContext) -> None:
    async with _sf()() as session:
        user = await get_or_create_user(session, message.from_user)
        if user.is_registered:
            await message.answer("Добро пожаловать в наш чат!")
            await send_main_menu(message, user)
            return

    await state.clear()
    await state.set_state(RegistrationState.waiting_phone)
    await message.answer(
        "Добро пожаловать в наш чат!\nУкажите свой номер телефона (введите текстом)."
    )


@router.message(Command("menu"))
async def menu_cmd(message: Message) -> None:
    async with _sf()() as session:
        user = await get_or_create_user(session, message.from_user)
        if not user.is_registered:
            await message.answer("Сначала пройдите регистрацию через /start.")
            return
        await send_main_menu(message, user)


@router.message(Command("admin"))
async def admin_cmd(message: Message, state: FSMContext, admin_ids: set[int]) -> None:
    async with _sf()() as session:
        user = await get_or_create_user(session, message.from_user)
        if not _require_admin(user, admin_ids):
            await message.answer("Нет доступа.")
            return
    await state.clear()
    await message.answer("Админ-панель:", reply_markup=keyboards.admin_menu_kb())


@router.message(RegistrationState.waiting_phone)
async def reg_phone_input(message: Message, state: FSMContext) -> None:
    phone = normalize_phone(message.text or "")
    if len(phone) < 10:
        await message.answer("Введите корректный номер телефона.")
        return
    await state.update_data(phone=phone)
    await state.set_state(RegistrationState.confirm_phone)
    await message.answer(
        f'Ваш номер "{phone}" правильно?',
        reply_markup=keyboards.start_phone_confirm_kb(),
    )


@router.callback_query(F.data == "reg:edit")
async def reg_edit(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(RegistrationState.waiting_phone)
    await callback.message.answer("Введите номер телефона еще раз.")


@router.callback_query(F.data == "reg:confirm")
async def reg_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    phone = data.get("phone")
    if not phone:
        await callback.message.answer("Телефон не найден. Повторите /start.")
        await state.clear()
        return

    async with _sf()() as session:
        user = await get_or_create_user(session, callback.from_user)
        user.phone = phone
        user.is_registered = 1
        if not user.role:
            user.role = "consumer"
        await session.commit()
        await callback.message.answer("Регистрация пройдена.")
        await callback.message.answer("Меню:", reply_markup=keyboards.menu_kb(user.role))
    await state.clear()


@router.callback_query(F.data == "menu:refresh")
async def menu_refresh(callback: CallbackQuery) -> None:
    await callback.answer()
    async with _sf()() as session:
        user = await get_or_create_user(session, callback.from_user)
        if user.is_registered:
            await send_main_menu_cb(callback, user)


@router.callback_query(F.data == "menu:create_req")
async def menu_create_request(callback: CallbackQuery, state: FSMContext, gate: ProcessGate) -> None:
    await callback.answer()
    async with _sf()() as session:
        user = await get_or_create_user(session, callback.from_user)
        if user.role != "consumer":
            await callback.message.answer("Действие доступно только потребителю.")
            return

    await gate.set_busy(callback.from_user.id, "consumer_create_request", 300)
    await state.clear()
    await state.set_state(ConsumerRequestState.waiting_text)
    await state.update_data(request_photos=[])
    await callback.message.answer("Что нужно вам? Введите текст заявки.")


@router.message(ConsumerRequestState.waiting_text)
async def consumer_request_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите текст заявки.")
        return
    await state.update_data(request_text=text, request_photos=[])
    await state.set_state(ConsumerRequestState.waiting_photos)
    await message.answer(
        "Прикрепите фотографию/фотографии (можно несколько), затем нажмите Готово.",
        reply_markup=keyboards.done_kb("req:photos_done"),
    )


@router.message(ConsumerRequestState.waiting_photos, F.photo)
async def consumer_request_add_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    items = data.get("request_photos", [])
    items.append({"type": "photo", "file_id": message.photo[-1].file_id})
    await state.update_data(request_photos=items)
    await message.answer("Фото добавлено. Можно отправить еще или нажать Готово.")


@router.message(ConsumerRequestState.waiting_photos, F.document)
async def consumer_request_add_doc(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    items = data.get("request_photos", [])
    items.append({"type": "document", "file_id": message.document.file_id})
    await state.update_data(request_photos=items)
    await message.answer("Файл добавлен. Можно отправить еще или нажать Готово.")


@router.callback_query(F.data == "req:photos_done")
async def consumer_request_preview(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    text = data.get("request_text")
    if not text:
        await callback.message.answer("Не найден текст заявки, начните заново.")
        await state.clear()
        return

    photos = data.get("request_photos", [])
    preview_text = f"Правильно ли все введено?\n\nЧто нужно:\n{text}"
    await send_media_and_text(
        bot=callback.bot,
        chat_id=callback.from_user.id,
        text=preview_text,
        media_items=photos,
        reply_markup=keyboards.request_preview_kb(),
    )
    await state.set_state(ConsumerRequestState.preview)


@router.callback_query(F.data == "req:preview:edit")
async def consumer_request_edit(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(ConsumerRequestState.waiting_text)
    await state.update_data(request_photos=[])
    await callback.message.answer("Введите текст заявки заново.")


@router.callback_query(F.data == "req:preview:cancel")
async def consumer_request_cancel(callback: CallbackQuery, state: FSMContext, gate: ProcessGate) -> None:
    await callback.answer()
    await state.clear()
    async with _sf()() as session:
        await callback.message.answer("Создание заявки отменено.")
        await flush_user_queue(callback.bot, gate, session, callback.from_user.id)


@router.callback_query(F.data == "req:preview:confirm")
async def consumer_request_confirm(callback: CallbackQuery, state: FSMContext, gate: ProcessGate) -> None:
    await callback.answer()
    data = await state.get_data()
    text = data.get("request_text")
    photos = data.get("request_photos", [])
    if not text:
        await callback.message.answer("Нет текста заявки, начните заново.")
        await state.clear()
        return

    async with _sf()() as session:
        user = await get_or_create_user(session, callback.from_user)
        request = SupplyRequest(
            consumer_id=user.id,
            text=text,
            photos_json=pack_media(photos),
            status="open",
        )
        session.add(request)
        user.sent_requests_count += 1
        await session.commit()
        await session.refresh(request)

        stmt = select(User).where(User.role == "supplier", User.is_registered == 1)
        suppliers = (await session.execute(stmt)).scalars().all()

        await callback.message.answer("Заявка отправлена.")
        await send_main_menu_cb(callback, user)

        for supplier in suppliers:
            await notify_supplier_about_request(callback.bot, gate, supplier.tg_id, request)

        await flush_user_queue(callback.bot, gate, session, callback.from_user.id)
    await state.clear()


@router.callback_query(F.data == "menu:my_req")
async def consumer_my_requests(callback: CallbackQuery, gate: ProcessGate) -> None:
    await callback.answer()

    async with _sf()() as session:
        user = await get_or_create_user(session, callback.from_user)
        if user.role != "consumer":
            await callback.message.answer("Действие доступно только потребителю.")
            return
        await gate.set_busy(callback.from_user.id, "consumer_view_requests", 300)
        stmt = (
            select(SupplyRequest)
            .where(SupplyRequest.consumer_id == user.id, SupplyRequest.status == "open")
            .order_by(SupplyRequest.id.desc())
        )
        requests = (await session.execute(stmt)).scalars().all()
        if not requests:
            await callback.message.answer("Открытых заявок нет.")
        for req in requests:
            await send_media_and_text(
                callback.bot,
                callback.from_user.id,
                request_text_view(req),
                unpack_media(req.photos_json),
                keyboards.my_request_item_kb(req.id),
            )
        await callback.message.answer(
            "Вы просматриваете заявки. Нажмите Выйти для возврата в обычный режим.",
            reply_markup=keyboards.exit_process_kb(),
        )


@router.callback_query(F.data.startswith("req:view:"))
async def consumer_view_responses(callback: CallbackQuery) -> None:
    await callback.answer()
    req_id = int(callback.data.split(":")[2])
    async with _sf()() as session:
        user = await get_or_create_user(session, callback.from_user)
        req = await session.get(SupplyRequest, req_id)
        if not req or req.consumer_id != user.id:
            await callback.message.answer("Заявка не найдена.")
            return
        stmt = (
            select(SupplierResponse)
            .where(SupplierResponse.request_id == req_id)
            .order_by(SupplierResponse.id.desc())
        )
        responses = (await session.execute(stmt)).scalars().all()
        if not responses:
            await callback.message.answer("Откликов пока нет.")
            return
        for resp in responses:
            await send_media_and_text(
                callback.bot,
                callback.from_user.id,
                response_text_view(resp),
                unpack_media(resp.photos_json),
                keyboards.response_item_kb(resp.id, req_id),
            )


@router.callback_query(F.data.startswith("req:close:"))
async def consumer_close_request(callback: CallbackQuery) -> None:
    await callback.answer()
    req_id = int(callback.data.split(":")[2])
    async with _sf()() as session:
        user = await get_or_create_user(session, callback.from_user)
        req = await session.get(SupplyRequest, req_id)
        if not req or req.consumer_id != user.id:
            await callback.message.answer("Заявка не найдена.")
            return
        req.status = "closed"
        await session.commit()
        await callback.message.answer("Заявка закрыта, прием откликов остановлен.")


@router.callback_query(F.data.startswith("resp:stop:"))
async def consumer_stop_responses(callback: CallbackQuery) -> None:
    await callback.answer()
    req_id = int(callback.data.split(":")[2])
    async with _sf()() as session:
        user = await get_or_create_user(session, callback.from_user)
        req = await session.get(SupplyRequest, req_id)
        if not req or req.consumer_id != user.id:
            await callback.message.answer("Заявка не найдена.")
            return
        req.status = "closed"
        await session.commit()
        await callback.message.answer("Заявка закрыта и удалена из приема откликов.")


@router.callback_query(F.data.startswith("resp:contact:"))
async def consumer_contact_supplier(callback: CallbackQuery) -> None:
    await callback.answer()
    response_id = int(callback.data.split(":")[2])
    async with _sf()() as session:
        user = await get_or_create_user(session, callback.from_user)
        response = await session.get(SupplierResponse, response_id)
        if not response:
            await callback.message.answer("Отклик не найден.")
            return
        req = await session.get(SupplyRequest, response.request_id)
        if not req or req.consumer_id != user.id:
            await callback.message.answer("Нет доступа к этому отклику.")
            return
        supplier = await session.get(User, response.supplier_id)
        if not supplier:
            await callback.message.answer("Поставщик не найден.")
            return

        response.status = "selected"
        await session.commit()

        contact = user_contact_view(supplier)
        await callback.message.answer(
            f"Контакт поставщика:\n{contact}\n\nОтклик:\n{response_text_view(response)}"
        )

        consumer_contact = user_contact_view(user)
        await callback.bot.send_message(
            chat_id=supplier.tg_id,
            text=(
                "Ваш отклик выбрали!\n\n"
                f"{request_text_view(req)}\n\n{response_text_view(response)}\n\n"
                f"Контакт потребителя: {consumer_contact}"
            ),
        )


@router.callback_query(F.data == "menu:open_req")
async def supplier_open_requests(callback: CallbackQuery, gate: ProcessGate) -> None:
    await callback.answer()
    async with _sf()() as session:
        user = await get_or_create_user(session, callback.from_user)
        if user.role != "supplier":
            await callback.message.answer("Действие доступно только поставщику.")
            return
        stmt = (
            select(SupplyRequest)
            .where(SupplyRequest.status == "open")
            .order_by(SupplyRequest.id.desc())
        )
        requests = (await session.execute(stmt)).scalars().all()
        if not requests:
            await callback.message.answer("Открытых заявок нет.")
            return
        await gate.set_busy(callback.from_user.id, "supplier_view_open", 600)
        for req in requests:
            await send_media_and_text(
                callback.bot,
                callback.from_user.id,
                request_text_view(req),
                unpack_media(req.photos_json),
                keyboards.supplier_request_kb(req.id),
            )
        await callback.message.answer(
            "Вы просматриваете открытые заявки. Нажмите Выйти для возврата в режим приема.",
            reply_markup=keyboards.exit_process_kb(),
        )


@router.callback_query(F.data == "menu:my_resp")
async def supplier_my_responses(callback: CallbackQuery, gate: ProcessGate) -> None:
    await callback.answer()
    async with _sf()() as session:
        user = await get_or_create_user(session, callback.from_user)
        if user.role != "supplier":
            await callback.message.answer("Действие доступно только поставщику.")
            return
        await gate.set_busy(callback.from_user.id, "supplier_view_my_responses", 600)
        stmt = (
            select(SupplierResponse)
            .where(SupplierResponse.supplier_id == user.id)
            .order_by(SupplierResponse.id.desc())
        )
        responses = (await session.execute(stmt)).scalars().all()
        if not responses:
            await callback.message.answer("Откликов пока нет.")
        for resp in responses:
            req = await session.get(SupplyRequest, resp.request_id)
            req_part = request_text_view(req) if req else "Заявка не найдена"
            text = f"{req_part}\n\n{response_text_view(resp)}"
            await send_media_and_text(
                callback.bot,
                callback.from_user.id,
                text,
                unpack_media(resp.photos_json),
                None,
            )
        await callback.message.answer(
            "Просмотр завершен. Нажмите Выйти для возврата в обычный режим.",
            reply_markup=keyboards.exit_process_kb(),
        )


@router.callback_query(F.data.startswith("sup:reply:"))
async def supplier_start_response(
    callback: CallbackQuery,
    state: FSMContext,
    gate: ProcessGate,
) -> None:
    await callback.answer()
    request_id = int(callback.data.split(":")[2])
    async with _sf()() as session:
        user = await get_or_create_user(session, callback.from_user)
        if user.role != "supplier":
            await callback.message.answer("Только поставщик может откликнуться.")
            return
        req = await session.get(SupplyRequest, request_id)
        if not req or req.status != "open":
            await callback.message.answer("Эта заявка уже закрыта.")
            return
    await gate.set_busy(callback.from_user.id, "supplier_make_response", 600)
    await state.clear()
    await state.set_state(SupplierResponseState.waiting_price)
    await state.update_data(response_request_id=request_id, response_photos=[])
    await callback.message.answer(
        "Укажите цену в цифрах (тенге).",
        reply_markup=keyboards.supplier_price_kb(),
    )


@router.callback_query(F.data == "sup:price_tbd")
async def supplier_price_tbd(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    current = await state.get_state()
    if current != SupplierResponseState.waiting_price.state:
        return
    await state.update_data(response_price="Цена уточняется")
    await state.set_state(SupplierResponseState.waiting_eta)
    await callback.message.answer("Укажите ориентировочный срок поставки (текстом).")


@router.message(SupplierResponseState.waiting_price)
async def supplier_price_input(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if not value:
        await message.answer("Введите цену или используйте кнопку 'цена уточняется'.")
        return
    await state.update_data(response_price=value)
    await state.set_state(SupplierResponseState.waiting_eta)
    await message.answer("Укажите ориентировочный срок поставки (текстом).")


@router.message(SupplierResponseState.waiting_eta)
async def supplier_eta_input(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if not value:
        await message.answer("Введите срок поставки.")
        return
    await state.update_data(response_eta=value)
    await state.set_state(SupplierResponseState.waiting_description)
    await message.answer("Укажите описание отклика.")


@router.message(SupplierResponseState.waiting_description)
async def supplier_description_input(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if not value:
        await message.answer("Введите описание отклика.")
        return
    await state.update_data(response_description=value, response_photos=[])
    await state.set_state(SupplierResponseState.waiting_photos)
    await message.answer(
        "Прикрепите фото/файлы для отклика, затем нажмите Готово.",
        reply_markup=keyboards.done_kb("sup:photos_done"),
    )


@router.message(SupplierResponseState.waiting_photos, F.photo)
async def supplier_add_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    photos = data.get("response_photos", [])
    photos.append({"type": "photo", "file_id": message.photo[-1].file_id})
    await state.update_data(response_photos=photos)
    await message.answer("Фото добавлено. Можно отправить еще или нажать Готово.")


@router.message(SupplierResponseState.waiting_photos, F.document)
async def supplier_add_document(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    photos = data.get("response_photos", [])
    photos.append({"type": "document", "file_id": message.document.file_id})
    await state.update_data(response_photos=photos)
    await message.answer("Файл добавлен. Можно отправить еще или нажать Готово.")


@router.callback_query(F.data == "sup:photos_done")
async def supplier_response_preview(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    price = data.get("response_price")
    eta = data.get("response_eta")
    desc = data.get("response_description")
    if not all([price, eta, desc]):
        await callback.message.answer("Не хватает данных. Заполните форму заново.")
        await state.clear()
        return
    text = f"Проверьте отклик:\n\nЦена: {price}\nСрок: {eta}\n\nОписание:\n{desc}"
    await send_media_and_text(
        callback.bot,
        callback.from_user.id,
        text,
        data.get("response_photos", []),
        keyboards.supplier_preview_kb(),
    )
    await state.set_state(SupplierResponseState.preview)


@router.callback_query(F.data == "sup:preview:edit")
async def supplier_response_edit(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(SupplierResponseState.waiting_price)
    await state.update_data(response_photos=[])
    await callback.message.answer(
        "Начинаем заново. Укажите цену в тенге.",
        reply_markup=keyboards.supplier_price_kb(),
    )


@router.callback_query(F.data == "sup:preview:cancel")
async def supplier_response_cancel(callback: CallbackQuery, state: FSMContext, gate: ProcessGate) -> None:
    await callback.answer()
    await state.clear()
    async with _sf()() as session:
        await callback.message.answer("Формирование отклика отменено.")
        await flush_user_queue(callback.bot, gate, session, callback.from_user.id)


@router.callback_query(F.data == "sup:preview:confirm")
async def supplier_response_confirm(callback: CallbackQuery, state: FSMContext, gate: ProcessGate) -> None:
    await callback.answer()
    data = await state.get_data()
    request_id = data.get("response_request_id")
    price = data.get("response_price")
    eta = data.get("response_eta")
    desc = data.get("response_description")
    photos = data.get("response_photos", [])
    if not all([request_id, price, eta, desc]):
        await callback.message.answer("Нет всех данных для отправки.")
        await state.clear()
        return

    async with _sf()() as session:
        user = await get_or_create_user(session, callback.from_user)
        req = await session.get(SupplyRequest, int(request_id))
        if not req or req.status != "open":
            await callback.message.answer("Заявка уже закрыта.")
            await flush_user_queue(callback.bot, gate, session, callback.from_user.id)
            await state.clear()
            return

        response = SupplierResponse(
            request_id=req.id,
            supplier_id=user.id,
            price_text=price,
            eta_text=eta,
            description=desc,
            photos_json=pack_media(photos),
            status="pending",
        )
        session.add(response)
        await session.commit()
        await session.refresh(response)

        consumer = await session.get(User, req.consumer_id)
        if consumer:
            await notify_consumer_about_response(
                callback.bot,
                gate,
                consumer.tg_id,
                req,
                response,
            )
        await callback.message.answer("Отклик отправлен.")
        await send_main_menu_cb(callback, user)
        await flush_user_queue(callback.bot, gate, session, callback.from_user.id)
    await state.clear()


@router.callback_query(F.data == "menu:exit_process")
async def exit_process(callback: CallbackQuery, state: FSMContext, gate: ProcessGate) -> None:
    await callback.answer()
    await state.clear()
    async with _sf()() as session:
        await flush_user_queue(callback.bot, gate, session, callback.from_user.id)
    await callback.message.answer("Вы вернулись в обычный режим.")


@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery, admin_ids: set[int]) -> None:
    await callback.answer()
    async with _sf()() as session:
        user = await get_or_create_user(session, callback.from_user)
        if not _require_admin(user, admin_ids):
            await callback.message.answer("Нет доступа.")
            return

        users_total = (
            await session.execute(select(func.count()).select_from(User))
        ).scalar_one()
        consumers = (
            await session.execute(select(func.count()).select_from(User).where(User.role == "consumer"))
        ).scalar_one()
        suppliers = (
            await session.execute(select(func.count()).select_from(User).where(User.role == "supplier"))
        ).scalar_one()
        requests_total = (
            await session.execute(select(func.count()).select_from(SupplyRequest))
        ).scalar_one()
        responses_total = (
            await session.execute(select(func.count()).select_from(SupplierResponse))
        ).scalar_one()

    await callback.message.answer(
        "Статистика:\n"
        f"- Пользователей: {users_total}\n"
        f"- Потребителей: {consumers}\n"
        f"- Поставщиков: {suppliers}\n"
        f"- Заявок: {requests_total}\n"
        f"- Откликов: {responses_total}\n\n"
        "Количество заявок по каждому пользователю хранится в users.sent_requests_count."
    )


@router.callback_query(F.data == "admin:set_role")
async def admin_set_role_start(callback: CallbackQuery, state: FSMContext, admin_ids: set[int]) -> None:
    await callback.answer()
    async with _sf()() as session:
        user = await get_or_create_user(session, callback.from_user)
        if not _require_admin(user, admin_ids):
            await callback.message.answer("Нет доступа.")
            return
    await state.set_state(AdminState.waiting_set_role_tg)
    await callback.message.answer("Введите Telegram ID пользователя для смены роли.")


@router.message(AdminState.waiting_set_role_tg)
async def admin_set_role_tg_input(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("Введите числовой Telegram ID.")
        return
    await state.update_data(target_tg_id=int(raw))
    await state.set_state(AdminState.waiting_set_role_name)
    await message.answer("Введите роль: consumer / supplier / admin")


@router.message(AdminState.waiting_set_role_name)
async def admin_set_role_name_input(message: Message, state: FSMContext, admin_ids: set[int]) -> None:
    role = (message.text or "").strip().lower()
    if role not in {"consumer", "supplier", "admin"}:
        await message.answer("Допустимые роли: consumer / supplier / admin")
        return

    data = await state.get_data()
    target_tg_id = data.get("target_tg_id")
    if not target_tg_id:
        await message.answer("Не найден target_tg_id, начните заново /admin.")
        await state.clear()
        return

    async with _sf()() as session:
        admin_user = await get_or_create_user(session, message.from_user)
        if not _require_admin(admin_user, admin_ids):
            await message.answer("Нет доступа.")
            await state.clear()
            return
        stmt = select(User).where(User.tg_id == target_tg_id)
        target = (await session.execute(stmt)).scalar_one_or_none()
        if not target:
            await message.answer("Пользователь не найден в базе.")
            await state.clear()
            return
        target.role = role
        await session.commit()

    await message.answer(f"Роль пользователя {target_tg_id} изменена на {role}.")
    await state.clear()


@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext, admin_ids: set[int]) -> None:
    await callback.answer()
    async with _sf()() as session:
        user = await get_or_create_user(session, callback.from_user)
        if not _require_admin(user, admin_ids):
            await callback.message.answer("Нет доступа.")
            return
    await state.set_state(AdminState.waiting_broadcast)
    await callback.message.answer("Введите текст рассылки всем зарегистрированным пользователям.")


@router.message(AdminState.waiting_broadcast)
async def admin_broadcast_input(message: Message, state: FSMContext, admin_ids: set[int]) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите непустой текст.")
        return

    async with _sf()() as session:
        admin_user = await get_or_create_user(session, message.from_user)
        if not _require_admin(admin_user, admin_ids):
            await message.answer("Нет доступа.")
            await state.clear()
            return

        stmt = select(User).where(User.is_registered == 1)
        users = (await session.execute(stmt)).scalars().all()

    sent = 0
    for user in users:
        try:
            await message.bot.send_message(chat_id=user.tg_id, text=f"Рассылка:\n\n{text}")
            sent += 1
        except Exception:
            continue
    await message.answer(f"Рассылка завершена. Отправлено: {sent}")
    await state.clear()


@router.message()
async def fallback(message: Message) -> None:
    await message.answer("Используйте /start для начала или /menu для меню.")
