from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import db
from app.config import load_settings
from app.models import SupplierResponse, SupplyRequest, User


app = FastAPI(title="Aggregator CRUD API", version="1.0.0")
settings = load_settings()
db.init_db(settings.database_url)


class UserBase(BaseModel):
    tg_id: int
    username: str | None = None
    full_name: str | None = None
    phone: str | None = None
    role: str = "consumer"
    is_registered: int = 0
    sent_requests_count: int = 0


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    tg_id: int | None = None
    username: str | None = None
    full_name: str | None = None
    phone: str | None = None
    role: str | None = None
    is_registered: int | None = None
    sent_requests_count: int | None = None


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class RequestBase(BaseModel):
    consumer_id: int
    text: str
    photos_json: str = "[]"
    status: str = "open"


class RequestCreate(RequestBase):
    pass


class RequestUpdate(BaseModel):
    consumer_id: int | None = None
    text: str | None = None
    photos_json: str | None = None
    status: str | None = None


class RequestOut(RequestBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class ResponseBase(BaseModel):
    request_id: int
    supplier_id: int
    price_text: str
    eta_text: str
    description: str
    photos_json: str = "[]"
    status: str = "pending"


class ResponseCreate(ResponseBase):
    pass


class ResponseUpdate(BaseModel):
    request_id: int | None = None
    supplier_id: int | None = None
    price_text: str | None = None
    eta_text: str | None = None
    description: str | None = None
    photos_json: str | None = None
    status: str | None = None


class ResponseOut(ResponseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


async def get_db() -> AsyncSession:
    if db.session_factory is None:
        raise RuntimeError("Session factory is not initialized.")
    async with db.session_factory() as session:
        yield session


async def check_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    expected = settings.api_token
    if expected and x_api_key != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


@app.on_event("startup")
async def on_startup() -> None:
    await db.create_tables()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/users", response_model=list[UserOut], dependencies=[Depends(check_api_key)])
async def list_users(
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[User]:
    stmt = select(User).order_by(User.id).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


@app.get("/users/{item_id}", response_model=UserOut, dependencies=[Depends(check_api_key)])
async def get_user(item_id: int, session: Annotated[AsyncSession, Depends(get_db)]) -> User:
    item = await session.get(User, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="User not found")
    return item


@app.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_api_key)],
)
async def create_user(payload: UserCreate, session: Annotated[AsyncSession, Depends(get_db)]) -> User:
    item = User(**payload.model_dump())
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


@app.put("/users/{item_id}", response_model=UserOut, dependencies=[Depends(check_api_key)])
async def replace_user(
    item_id: int,
    payload: UserCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    item = await session.get(User, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="User not found")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    await session.commit()
    await session.refresh(item)
    return item


@app.patch("/users/{item_id}", response_model=UserOut, dependencies=[Depends(check_api_key)])
async def update_user(
    item_id: int,
    payload: UserUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    item = await session.get(User, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="User not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    await session.commit()
    await session.refresh(item)
    return item


@app.delete(
    "/users/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(check_api_key)],
)
async def delete_user(item_id: int, session: Annotated[AsyncSession, Depends(get_db)]) -> Response:
    item = await session.get(User, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="User not found")
    await session.delete(item)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/requests", response_model=list[RequestOut], dependencies=[Depends(check_api_key)])
async def list_requests(
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[SupplyRequest]:
    stmt = select(SupplyRequest).order_by(SupplyRequest.id).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


@app.get("/requests/{item_id}", response_model=RequestOut, dependencies=[Depends(check_api_key)])
async def get_request(item_id: int, session: Annotated[AsyncSession, Depends(get_db)]) -> SupplyRequest:
    item = await session.get(SupplyRequest, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Request not found")
    return item


@app.post(
    "/requests",
    response_model=RequestOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_api_key)],
)
async def create_request(
    payload: RequestCreate, session: Annotated[AsyncSession, Depends(get_db)]
) -> SupplyRequest:
    item = SupplyRequest(**payload.model_dump())
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


@app.put("/requests/{item_id}", response_model=RequestOut, dependencies=[Depends(check_api_key)])
async def replace_request(
    item_id: int,
    payload: RequestCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SupplyRequest:
    item = await session.get(SupplyRequest, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Request not found")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    await session.commit()
    await session.refresh(item)
    return item


@app.patch("/requests/{item_id}", response_model=RequestOut, dependencies=[Depends(check_api_key)])
async def update_request(
    item_id: int,
    payload: RequestUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SupplyRequest:
    item = await session.get(SupplyRequest, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Request not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    await session.commit()
    await session.refresh(item)
    return item


@app.delete(
    "/requests/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(check_api_key)],
)
async def delete_request(item_id: int, session: Annotated[AsyncSession, Depends(get_db)]) -> Response:
    item = await session.get(SupplyRequest, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Request not found")
    await session.delete(item)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/responses", response_model=list[ResponseOut], dependencies=[Depends(check_api_key)])
async def list_responses(
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[SupplierResponse]:
    stmt = select(SupplierResponse).order_by(SupplierResponse.id).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


@app.get("/responses/{item_id}", response_model=ResponseOut, dependencies=[Depends(check_api_key)])
async def get_response(item_id: int, session: Annotated[AsyncSession, Depends(get_db)]) -> SupplierResponse:
    item = await session.get(SupplierResponse, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Response not found")
    return item


@app.post(
    "/responses",
    response_model=ResponseOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_api_key)],
)
async def create_response(
    payload: ResponseCreate, session: Annotated[AsyncSession, Depends(get_db)]
) -> SupplierResponse:
    item = SupplierResponse(**payload.model_dump())
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


@app.put("/responses/{item_id}", response_model=ResponseOut, dependencies=[Depends(check_api_key)])
async def replace_response(
    item_id: int,
    payload: ResponseCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SupplierResponse:
    item = await session.get(SupplierResponse, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Response not found")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    await session.commit()
    await session.refresh(item)
    return item


@app.patch("/responses/{item_id}", response_model=ResponseOut, dependencies=[Depends(check_api_key)])
async def update_response(
    item_id: int,
    payload: ResponseUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SupplierResponse:
    item = await session.get(SupplierResponse, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Response not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    await session.commit()
    await session.refresh(item)
    return item


@app.delete(
    "/responses/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(check_api_key)],
)
async def delete_response(item_id: int, session: Annotated[AsyncSession, Depends(get_db)]) -> Response:
    item = await session.get(SupplierResponse, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Response not found")
    await session.delete(item)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
