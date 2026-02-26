from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    role: Mapped[str] = mapped_column(String(30), default="consumer")
    is_registered: Mapped[int] = mapped_column(Integer, default=0)
    sent_requests_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    requests: Mapped[list["SupplyRequest"]] = relationship(
        back_populates="consumer", foreign_keys="SupplyRequest.consumer_id"
    )
    responses: Mapped[list["SupplierResponse"]] = relationship(
        back_populates="supplier", foreign_keys="SupplierResponse.supplier_id"
    )


class SupplyRequest(Base):
    __tablename__ = "supply_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    consumer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    photos_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(20), default="open")  # open/closed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    consumer: Mapped[User] = relationship(back_populates="requests", foreign_keys=[consumer_id])
    responses: Mapped[list["SupplierResponse"]] = relationship(back_populates="request")


class SupplierResponse(Base):
    __tablename__ = "supplier_responses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("supply_requests.id"), index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    price_text: Mapped[str] = mapped_column(String(255))
    eta_text: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    photos_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/selected
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    request: Mapped[SupplyRequest] = relationship(back_populates="responses")
    supplier: Mapped[User] = relationship(back_populates="responses", foreign_keys=[supplier_id])
