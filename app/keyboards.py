from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def start_phone_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Подтвердить", callback_data="reg:confirm"),
                InlineKeyboardButton(text="Изменить", callback_data="reg:edit"),
            ]
        ]
    )


def menu_kb(role: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if role == "consumer":
        rows.extend(
            [
                [InlineKeyboardButton(text="Создать заявку", callback_data="menu:create_req")],
                [InlineKeyboardButton(text="Мои заявки", callback_data="menu:my_req")],
            ]
        )
    elif role == "supplier":
        rows.extend(
            [
                [InlineKeyboardButton(text="Открытые заявки", callback_data="menu:open_req")],
                [InlineKeyboardButton(text="Мои отклики", callback_data="menu:my_resp")],
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def done_kb(callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Готово", callback_data=callback)]]
    )


def request_preview_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Подтвердить", callback_data="req:preview:confirm")],
            [InlineKeyboardButton(text="Изменить", callback_data="req:preview:edit")],
            [InlineKeyboardButton(text="Отменить", callback_data="req:preview:cancel")],
        ]
    )


def my_request_item_kb(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Просмотреть отклики", callback_data=f"req:view:{request_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Закрыть заявку", callback_data=f"req:close:{request_id}"
                )
            ],
        ]
    )


def response_item_kb(response_id: int, request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Связаться с поставщиком",
                    callback_data=f"resp:contact:{response_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Приостановить отклики по этой заявке",
                    callback_data=f"resp:stop:{request_id}",
                )
            ],
        ]
    )


def supplier_request_kb(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Откликнуться", callback_data=f"sup:reply:{request_id}")]
        ]
    )


def supplier_price_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Указать, что цена уточняется",
                    callback_data="sup:price_tbd",
                )
            ]
        ]
    )


def supplier_preview_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Подтвердить и отправить", callback_data="sup:preview:confirm")],
            [InlineKeyboardButton(text="Изменить", callback_data="sup:preview:edit")],
            [InlineKeyboardButton(text="Отменить", callback_data="sup:preview:cancel")],
        ]
    )


def exit_process_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Выйти", callback_data="menu:exit_process")]]
    )


def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Статистика", callback_data="admin:stats")],
            [InlineKeyboardButton(text="Назначить роль", callback_data="admin:set_role")],
            [InlineKeyboardButton(text="Рассылка", callback_data="admin:broadcast")],
        ]
    )


def admin_set_role_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Потребитель", callback_data="admin:set_role:consumer")],
            [InlineKeyboardButton(text="Поставщик", callback_data="admin:set_role:supplier")],
            [InlineKeyboardButton(text="Админ", callback_data="admin:set_role:admin")],
            [InlineKeyboardButton(text="Отмена", callback_data="admin:set_role:cancel")],
        ]
    )
