from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    full_name: Mapped[str | None] = mapped_column(String(150))
    role: Mapped[str] = mapped_column(String(30), default="citizen", server_default="citizen")
    password_hash: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    reports: Mapped[list["GarbageReport"]] = relationship(back_populates="user")
    status_changes: Mapped[list["ReportStatusHistory"]] = relationship(
        back_populates="changed_by"
    )


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = (
        CheckConstraint(
            "(address IS NOT NULL AND length(trim(address)) > 0 "
            "AND latitude IS NULL AND longitude IS NULL) OR "
            "(address IS NULL AND latitude IS NOT NULL AND longitude IS NOT NULL "
            "AND latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)",
            name="ck_locations_address_or_coordinates",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    address: Mapped[str | None] = mapped_column(String(300))
    latitude: Mapped[float | None]
    longitude: Mapped[float | None]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    report: Mapped["GarbageReport"] = relationship(back_populates="location")


class ComplaintStatus(Base):
    __tablename__ = "complaint_statuses"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    label: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    reports: Mapped[list["GarbageReport"]] = relationship(back_populates="status")
    history_entries: Mapped[list["ReportStatusHistory"]] = relationship(
        back_populates="status"
    )


class GarbageReport(Base):
    __tablename__ = "waste_reports"
    __table_args__ = (
        Index("ix_waste_reports_created_at", "created_at"),
        Index("ix_waste_reports_status_id", "status_id"),
        Index(
            "uq_waste_reports_idempotency_key",
            "idempotency_key",
            unique=True,
            sqlite_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    description: Mapped[str] = mapped_column(Text)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), unique=True
    )
    status_id: Mapped[int] = mapped_column(
        ForeignKey("complaint_statuses.id", ondelete="RESTRICT")
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    request_fingerprint: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User | None] = relationship(back_populates="reports")
    status: Mapped[ComplaintStatus] = relationship(back_populates="reports")
    location: Mapped[Location] = relationship(back_populates="report")
    image: Mapped["ImageReference"] = relationship(
        back_populates="report", cascade="all, delete-orphan", uselist=False
    )
    classification: Mapped["WasteClassification | None"] = relationship(
        back_populates="report", cascade="all, delete-orphan", uselist=False
    )
    complaint: Mapped["MunicipalComplaint | None"] = relationship(
        back_populates="report", cascade="all, delete-orphan", uselist=False
    )
    status_history: Mapped[list["ReportStatusHistory"]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="ReportStatusHistory.changed_at",
    )


class ImageReference(Base):
    __tablename__ = "image_references"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("waste_reports.id", ondelete="CASCADE"), unique=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    image_data: Mapped[bytes] = mapped_column(LargeBinary)
    file_path: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    report: Mapped[GarbageReport] = relationship(back_populates="image")


class WasteClassification(Base):
    __tablename__ = "waste_classifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("waste_reports.id", ondelete="CASCADE"), unique=True
    )
    category: Mapped[str] = mapped_column(String(100))
    confidence: Mapped[float] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(100))
    classified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    report: Mapped[GarbageReport] = relationship(back_populates="classification")


class ReportStatusHistory(Base):
    __tablename__ = "report_status_history"
    __table_args__ = (Index("ix_report_status_history_report_id", "report_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("waste_reports.id", ondelete="CASCADE")
    )
    status_id: Mapped[int] = mapped_column(
        ForeignKey("complaint_statuses.id", ondelete="RESTRICT")
    )
    changed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    note: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    report: Mapped[GarbageReport] = relationship(back_populates="status_history")
    status: Mapped[ComplaintStatus] = relationship(back_populates="history_entries")
    changed_by: Mapped[User | None] = relationship(back_populates="status_changes")


class MunicipalComplaint(Base):
    __tablename__ = "municipal_complaints"
    __table_args__ = (
        Index("ix_municipal_complaints_status", "status"),
        Index("ix_municipal_complaints_department", "assigned_department"),
        Index("ix_municipal_complaints_location", "location"),
        Index("ix_municipal_complaints_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("waste_reports.id", ondelete="CASCADE"), unique=True
    )
    waste_category: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String(500))
    assigned_department: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(40), default="New", server_default="New")
    after_cleaning_photo_path: Mapped[str | None] = mapped_column(String(500))
    after_cleaning_photo_uploaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    report: Mapped[GarbageReport] = relationship(back_populates="complaint")
    status_history: Mapped[list["ComplaintStatusHistory"]] = relationship(
        back_populates="complaint",
        cascade="all, delete-orphan",
        order_by="ComplaintStatusHistory.changed_at",
    )


class ComplaintStatusHistory(Base):
    __tablename__ = "complaint_status_history"
    __table_args__ = (Index("ix_complaint_status_history_complaint_id", "complaint_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    complaint_id: Mapped[int] = mapped_column(
        ForeignKey("municipal_complaints.id", ondelete="CASCADE")
    )
    previous_status: Mapped[str | None] = mapped_column(String(40))
    new_status: Mapped[str] = mapped_column(String(40))
    event_type: Mapped[str] = mapped_column(
        String(30), default="status", server_default="status"
    )
    changed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    staff_note: Mapped[str | None] = mapped_column(Text)

    complaint: Mapped[MunicipalComplaint] = relationship(
        back_populates="status_history"
    )
    changed_by: Mapped[User | None] = relationship()
