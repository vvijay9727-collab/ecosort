import logging
import hashlib
import json
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Header,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, selectinload
from app.complaint_routing import load_complaint_routing, route_complaint
from app.auth import (
    SESSION_COOKIE,
    SESSION_TTL_SECONDS,
    create_session_token,
    get_current_user,
    hash_password,
    require_authority,
    require_citizen,
    verify_password,
)

from app.database import SessionLocal, engine, get_db
from app.models import (
    Base,
    ComplaintStatus,
    ComplaintStatusHistory,
    GarbageReport as GarbageReportModel,
    ImageReference,
    Location,
    MunicipalComplaint,
    ReportStatusHistory,
    User,
    WasteClassification,
)
from app.ml.inference import (
    InvalidImageError,
    InferenceError,
    ModelArtifactError,
    WasteImageClassifier,
    load_classifier,
)

logger = logging.getLogger(__name__)
BACKEND_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BACKEND_DIR.parent / "frontend" / "dist"
UPLOAD_DIR = BACKEND_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_IMAGE_SIZE = 10 * 1024 * 1024
MODEL_PATH = BACKEND_DIR / "app" / "ml" / "models" / "waste_classifier.joblib"
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
INITIAL_STATUSES = (
    ("new", "New", "Report received and awaiting review."),
    ("assigned", "Assigned", "Assigned to a sanitation worker."),
    ("in_progress", "In progress", "Cleanup work is in progress."),
    ("pending_verification", "Pending verification", "Cleanup evidence awaits review."),
    ("resolved", "Resolved", "Cleanup was verified and the report was closed."),
    ("rejected", "Rejected", "The report was reviewed and rejected."),
)
COMPLAINT_STATUSES = ("New", "Assigned", "In Progress", "Resolved", "Closed")
COMPLAINT_STATUS_TRANSITIONS = {
    "New": {"Assigned"},
    "Assigned": {"In Progress"},
    "In Progress": {"Resolved"},
    "Resolved": {"Closed"},
    "Closed": set(),
}


class GarbageReport(BaseModel):
    id: int
    description: str
    location: str | None
    latitude: float | None
    longitude: float | None
    photo_filename: str
    photo_content_type: str
    photo_size_bytes: int
    photo_path: str | None
    image_id: int
    status: str
    created_at: datetime
    updated_at: datetime
    predicted_category: Literal["Wet Waste", "Dry Waste"] | None
    prediction_confidence: float | None
    model_version: str | None
    classified_at: datetime | None
    complaint_id: int | None
    assigned_department: str | None
    complaint_status: str | None


class ComplaintHistoryEntry(BaseModel):
    previous_status: str | None
    new_status: str
    event_type: str
    changed_at: datetime
    staff_note: str | None
    changed_by: str | None


class MunicipalComplaintResponse(BaseModel):
    id: int
    report_id: int
    waste_category: Literal["Wet Waste", "Dry Waste"]
    description: str
    location: str
    assigned_department: str
    status: Literal["New", "Assigned", "In Progress", "Resolved", "Closed"]
    prediction_confidence: float | None
    model_version: str | None
    created_at: datetime
    updated_at: datetime
    before_cleaning_photo_path: str | None
    after_cleaning_photo_path: str | None
    after_cleaning_photo_uploaded_at: datetime | None
    status_history: list[ComplaintHistoryEntry]


class ComplaintStatusUpdate(BaseModel):
    status: Literal["New", "Assigned", "In Progress", "Resolved", "Closed"]
    staff_note: Annotated[str | None, Field(max_length=1000)] = None


class ComplaintAssignmentUpdate(BaseModel):
    assigned_department: Annotated[str, Field(min_length=1, max_length=200)]
    staff_note: Annotated[str | None, Field(max_length=1000)] = None


class RegistrationRequest(BaseModel):
    full_name: Annotated[str, Field(min_length=1, max_length=150)]
    email: Annotated[str, Field(min_length=3, max_length=320)]
    password: Annotated[str, Field(min_length=12, max_length=128)]


class ProfileUpdateRequest(BaseModel):
    full_name: Annotated[str, Field(min_length=1, max_length=150)]
    email: Annotated[str, Field(min_length=3, max_length=320)]


class LoginRequest(BaseModel):
    email: Annotated[str, Field(min_length=3, max_length=320)]
    password: Annotated[str, Field(min_length=1, max_length=128)]
    role: Literal["citizen", "authority"]


class UserProfile(BaseModel):
    id: int
    email: str
    full_name: str
    role: Literal["citizen", "authority"]


class WastePrediction(BaseModel):
    category: Literal["Wet Waste", "Dry Waste"]
    confidence: float
    model_version: str


@asynccontextmanager
async def lifespan(application: FastAPI):
    configured_secret = os.getenv("ECOSORT_AUTH_SECRET")
    if configured_secret:
        if len(configured_secret.encode("utf-8")) < 32:
            raise RuntimeError("ECOSORT_AUTH_SECRET must be at least 32 bytes.")
        application.state.auth_secret = configured_secret.encode("utf-8")
    else:
        application.state.auth_secret = secrets.token_bytes(32)
        logger.warning(
            "ECOSORT_AUTH_SECRET is unset; sessions will be invalidated when the API restarts."
        )

    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        user_columns = {
            column["name"] for column in inspect(connection).get_columns("users")
        }
        if "password_hash" not in user_columns:
            connection.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN password_hash VARCHAR(256)"
            )
        image_columns = {
            column["name"]
            for column in inspect(connection).get_columns("image_references")
        }
        if "file_path" not in image_columns:
            connection.exec_driver_sql(
                "ALTER TABLE image_references ADD COLUMN file_path VARCHAR(500)"
            )
        report_columns = {
            column["name"]
            for column in inspect(connection).get_columns("waste_reports")
        }
        if "idempotency_key" not in report_columns:
            connection.exec_driver_sql(
                "ALTER TABLE waste_reports ADD COLUMN idempotency_key VARCHAR(128)"
            )
        if "request_fingerprint" not in report_columns:
            connection.exec_driver_sql(
                "ALTER TABLE waste_reports ADD COLUMN request_fingerprint VARCHAR(64)"
            )
        complaint_columns = {
            column["name"]
            for column in inspect(connection).get_columns("municipal_complaints")
        }
        if "after_cleaning_photo_path" not in complaint_columns:
            connection.exec_driver_sql(
                "ALTER TABLE municipal_complaints "
                "ADD COLUMN after_cleaning_photo_path VARCHAR(500)"
            )
        if "after_cleaning_photo_uploaded_at" not in complaint_columns:
            connection.exec_driver_sql(
                "ALTER TABLE municipal_complaints "
                "ADD COLUMN after_cleaning_photo_uploaded_at DATETIME"
            )
        history_columns = {
            column["name"]
            for column in inspect(connection).get_columns("complaint_status_history")
        }
        if "event_type" not in history_columns:
            connection.exec_driver_sql(
                "ALTER TABLE complaint_status_history "
                "ADD COLUMN event_type VARCHAR(30) NOT NULL DEFAULT 'status'"
            )
        if "changed_by_user_id" not in history_columns:
            connection.exec_driver_sql(
                "ALTER TABLE complaint_status_history "
                "ADD COLUMN changed_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL"
            )
        connection.exec_driver_sql(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_waste_reports_idempotency_key
            ON waste_reports (idempotency_key)
            WHERE idempotency_key IS NOT NULL
            """
        )
        connection.exec_driver_sql(
            """
            UPDATE waste_classifications
            SET category = CASE category
                WHEN 'O' THEN 'Wet Waste'
                WHEN 'R' THEN 'Dry Waste'
            END
            WHERE category IN ('O', 'R')
            """
        )

    with SessionLocal.begin() as db:
        known_statuses = set(db.scalars(select(ComplaintStatus.code)).all())
        for code, label, description in INITIAL_STATUSES:
            if code not in known_statuses:
                db.add(
                    ComplaintStatus(
                        code=code,
                        label=label,
                        description=description,
                    )
                )
    application.state.complaint_routing = load_complaint_routing()
    with SessionLocal.begin() as db:
        legacy_reports = db.scalars(
            select(GarbageReportModel)
            .options(
                joinedload(GarbageReportModel.location),
                joinedload(GarbageReportModel.classification),
                selectinload(GarbageReportModel.complaint),
            )
        ).all()
        for report in legacy_reports:
            if report.complaint is not None:
                continue
            if report.classification is None:
                logger.warning(
                    "Skipping complaint backfill for report %s without a saved waste category",
                    report.id,
                )
                continue
            if report.classification.category not in {"Wet Waste", "Dry Waste"}:
                logger.error(
                    "Skipping complaint backfill for report %s with unsupported category %r",
                    report.id,
                    report.classification.category,
                )
                continue
            report_location = display_location(
                report.location.address,
                report.location.latitude,
                report.location.longitude,
            )
            complaint = MunicipalComplaint(
                waste_category=report.classification.category,
                description=report.description,
                location=report_location,
                assigned_department=route_complaint(
                    application.state.complaint_routing,
                    report_location,
                    report.classification.category,
                ),
                status="New",
            )
            complaint.status_history.append(
                ComplaintStatusHistory(
                    previous_status=None,
                    new_status="New",
                    staff_note="Complaint created for an existing report.",
                )
            )
            report.complaint = complaint
    try:
        application.state.classifier = load_classifier(MODEL_PATH)
    except FileNotFoundError:
        application.state.classifier = None
        logger.warning("Waste classifier model is not installed at %s", MODEL_PATH)
    except ModelArtifactError:
        application.state.classifier = None
        logger.exception("Waste classifier model could not be loaded from %s", MODEL_PATH)
    yield


app = FastAPI(
    title="Intelligent Waste Segregation and Management System",
    version="0.2.0",
    lifespan=lifespan,
)

ALLOWED_ORIGINS = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
}
if render_external_url := os.getenv("RENDER_EXTERNAL_URL"):
    ALLOWED_ORIGINS.add(render_external_url.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ALLOWED_ORIGINS),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def enforce_same_origin_mutations(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if origin and origin not in ALLOWED_ORIGINS:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Requests from this origin are not allowed."},
            )
    return await call_next(request)


def serialize_report(report: GarbageReportModel) -> GarbageReport:
    return GarbageReport(
        id=report.id,
        description=report.description,
        location=report.location.address,
        latitude=report.location.latitude,
        longitude=report.location.longitude,
        photo_filename=report.image.filename,
        photo_content_type=report.image.content_type,
        photo_size_bytes=report.image.size_bytes,
        photo_path=report.image.file_path,
        image_id=report.image.id,
        status=report.status.code,
        created_at=report.created_at,
        updated_at=report.updated_at,
        predicted_category=(
            report.classification.category if report.classification else None
        ),
        prediction_confidence=(
            report.classification.confidence if report.classification else None
        ),
        model_version=(
            report.classification.model_version if report.classification else None
        ),
        classified_at=(
            report.classification.classified_at if report.classification else None
        ),
        complaint_id=report.complaint.id if report.complaint else None,
        assigned_department=(
            report.complaint.assigned_department if report.complaint else None
        ),
        complaint_status=report.complaint.status if report.complaint else None,
    )


def display_location(
    address: str | None, latitude: float | None, longitude: float | None
) -> str:
    if address:
        return address
    if latitude is not None and longitude is not None:
        return f"{latitude}, {longitude}"
    raise ValueError("A report must have an address or coordinate location.")


def serialize_complaint(
    complaint: MunicipalComplaint,
) -> MunicipalComplaintResponse:
    photo_uploaded_at = complaint.after_cleaning_photo_uploaded_at
    if photo_uploaded_at is not None and photo_uploaded_at.tzinfo is None:
        photo_uploaded_at = photo_uploaded_at.replace(tzinfo=timezone.utc)
    return MunicipalComplaintResponse(
        id=complaint.id,
        report_id=complaint.report_id,
        waste_category=complaint.waste_category,
        description=complaint.description,
        location=complaint.location,
        assigned_department=complaint.assigned_department,
        status=complaint.status,
        prediction_confidence=(
            complaint.report.classification.confidence
            if complaint.report and complaint.report.classification
            else None
        ),
        model_version=(
            complaint.report.classification.model_version
            if complaint.report and complaint.report.classification
            else None
        ),
        created_at=complaint.created_at,
        updated_at=complaint.updated_at,
        before_cleaning_photo_path=(
            complaint.report.image.file_path
            if complaint.report and complaint.report.image
            else None
        ),
        after_cleaning_photo_path=complaint.after_cleaning_photo_path,
        after_cleaning_photo_uploaded_at=photo_uploaded_at,
        status_history=[
            ComplaintHistoryEntry(
                previous_status=entry.previous_status,
                new_status=entry.new_status,
                event_type=entry.event_type,
                changed_at=entry.changed_at,
                staff_note=entry.staff_note,
                changed_by=entry.changed_by.full_name if entry.changed_by else None,
            )
            for entry in complaint.status_history
        ],
    )


def serialize_user(user: User) -> UserProfile:
    return UserProfile(
        id=user.id,
        email=user.email or "",
        full_name=user.full_name or "",
        role=user.role,
    )


def set_session_cookie(response: Response, user: User, request: Request) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=create_session_token(user, request.app.state.auth_secret),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=os.getenv("ECOSORT_COOKIE_SECURE", "").casefold() == "true",
        samesite="lax",
        path="/",
    )


@app.post(
    "/api/auth/register",
    response_model=UserProfile,
    status_code=status.HTTP_201_CREATED,
)
def register_citizen(
    payload: RegistrationRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> UserProfile:
    email = payload.email.strip().casefold()
    full_name = payload.full_name.strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Enter a valid email address.",
        )
    if not full_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Name must not be blank.",
        )
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        email=email,
        full_name=full_name,
        role="citizen",
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error while registering a citizen")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The account could not be created because the database is unavailable.",
        ) from exc
    set_session_cookie(response, user, request)
    return serialize_user(user)


@app.post("/api/auth/login", response_model=UserProfile)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> UserProfile:
    email = payload.email.strip().casefold()
    user = db.scalar(select(User).where(User.email == email))
    if (
        user is None
        or user.role != payload.role
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect.",
        )
    set_session_cookie(response, user, request)
    return serialize_user(user)


@app.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    response.delete_cookie(
        key=SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=os.getenv("ECOSORT_COOKIE_SECURE", "").casefold() == "true",
        samesite="lax",
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@app.get("/api/auth/me", response_model=UserProfile)
def get_profile(user: User = Depends(get_current_user)) -> UserProfile:
    return serialize_user(user)


@app.put("/api/auth/me", response_model=UserProfile)
def update_profile(
    payload: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserProfile:
    email = payload.email.strip().casefold()
    full_name = payload.full_name.strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Enter a valid email address.",
        )
    if not full_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Name must not be blank.",
        )
    duplicate = db.scalar(
        select(User).where(User.email == email, User.id != user.id)
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    user.email = email
    user.full_name = full_name
    try:
        db.commit()
        db.refresh(user)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error while updating user profile %s", user.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The profile could not be updated because the database is unavailable.",
        ) from exc
    return serialize_user(user)


@app.get("/health")
def health_check(request: Request) -> dict[str, str | bool]:
    classifier: WasteImageClassifier | None = request.app.state.classifier
    return {
        "status": "ok",
        "model_available": classifier is not None,
        "model_version": classifier.model_version if classifier else "",
    }


def get_classifier(request: Request) -> WasteImageClassifier:
    classifier: WasteImageClassifier | None = request.app.state.classifier
    if classifier is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The waste-classification model is unavailable. Train it with "
                "`python -m app.ml.train` and restart the API."
            ),
        )
    return classifier


def predict_image(
    classifier: WasteImageClassifier, content_type: str, image_bytes: bytes
) -> WastePrediction:
    if not has_valid_image_signature(content_type, image_bytes):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="The uploaded file contents do not match the declared image type.",
        )
    try:
        prediction = classifier.predict(image_bytes)
    except InvalidImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The uploaded file is not a readable image.",
        ) from exc
    except InferenceError as exc:
        logger.exception("Waste image classification failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The image could not be classified by the model.",
        ) from exc
    return WastePrediction(**prediction)


async def read_photo(photo: UploadFile) -> bytes:
    if photo.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Photo must be a JPEG, PNG, or WebP image.",
        )

    photo_bytes = await photo.read(MAX_IMAGE_SIZE + 1)
    if not photo_bytes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Photo must not be empty.",
        )
    if len(photo_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Photo must be 10 MB or smaller.",
        )
    return photo_bytes


@app.post("/api/classify", response_model=WastePrediction)
async def classify_image(
    request: Request,
    photo: Annotated[UploadFile, File()],
) -> WastePrediction:
    classifier = get_classifier(request)
    photo_bytes = await read_photo(photo)
    return predict_image(classifier, photo.content_type, photo_bytes)


@app.post(
    "/api/reports",
    response_model=GarbageReport,
    status_code=status.HTTP_201_CREATED,
)
async def create_report(
    request: Request,
    response: Response,
    description: Annotated[str, Form(min_length=1, max_length=1000)],
    photo: Annotated[UploadFile, File()],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=8, max_length=128)
    ],
    location: Annotated[str | None, Form(max_length=300)] = None,
    latitude: Annotated[float | None, Form(ge=-90, le=90)] = None,
    longitude: Annotated[float | None, Form(ge=-180, le=180)] = None,
    user: User = Depends(require_citizen),
    db: Session = Depends(get_db),
) -> GarbageReport:
    clean_description = description.strip()
    if not clean_description:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Description must not be blank.",
        )

    clean_location = location.strip() if location else ""
    has_coordinates = latitude is not None or longitude is not None
    if clean_location and has_coordinates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either an address or latitude/longitude, not both.",
        )
    if has_coordinates and (latitude is None or longitude is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide both latitude and longitude.",
        )
    if not clean_location and not has_coordinates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide an address or both latitude and longitude.",
        )

    photo_bytes = await read_photo(photo)
    if not idempotency_key.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Idempotency-Key must not be blank.",
        )
    fingerprint_payload = json.dumps(
        {
            "description": clean_description,
            "location": clean_location or None,
            "latitude": latitude,
            "longitude": longitude,
            "content_type": photo.content_type,
            "filename": photo.filename or "upload",
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    fingerprint = hashlib.sha256(fingerprint_payload + b"\0" + photo_bytes).hexdigest()
    try:
        existing_report = db.scalar(
            select(GarbageReportModel)
            .where(GarbageReportModel.idempotency_key == idempotency_key.strip())
            .options(
                joinedload(GarbageReportModel.location),
                joinedload(GarbageReportModel.image),
                joinedload(GarbageReportModel.status),
                joinedload(GarbageReportModel.classification),
                joinedload(GarbageReportModel.complaint),
            )
        )
    except SQLAlchemyError as exc:
        logger.exception("Database error while checking report idempotency key")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The report could not be checked because the database is unavailable.",
        ) from exc
    if existing_report is not None:
        if existing_report.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This Idempotency-Key has already been used.",
            )
        if existing_report.request_fingerprint != fingerprint:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This Idempotency-Key was already used with different report data.",
            )
        response.status_code = status.HTTP_200_OK
        response.headers["X-Idempotent-Replay"] = "true"
        return serialize_report(existing_report)

    classifier = get_classifier(request)
    prediction = predict_image(classifier, photo.content_type, photo_bytes)

    stored_filename = f"{uuid4().hex}{IMAGE_EXTENSIONS[photo.content_type]}"
    image_path = UPLOAD_DIR / stored_filename
    relative_image_path = (Path("uploads") / stored_filename).as_posix()

    try:
        initial_status = db.scalar(
            select(ComplaintStatus).where(ComplaintStatus.code == "new")
        )
        if initial_status is None:
            logger.error(
                "The initial complaint status is missing from complaint_statuses"
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Report statuses are not initialized. Restart the API after checking the database.",
            )

        image_path.write_bytes(photo_bytes)
        report_location = display_location(
            clean_location or None, latitude, longitude
        )
        routing = request.app.state.complaint_routing
        complaint = MunicipalComplaint(
            waste_category=prediction.category,
            description=clean_description,
            location=report_location,
            assigned_department=route_complaint(
                routing, report_location, prediction.category
            ),
            status="New",
        )
        complaint.status_history.append(
            ComplaintStatusHistory(
                previous_status=None,
                new_status="New",
                staff_note="Complaint created with report submission.",
            )
        )
        report = GarbageReportModel(
            description=clean_description,
            user_id=user.id,
            idempotency_key=idempotency_key.strip(),
            request_fingerprint=fingerprint,
            location=Location(
                address=clean_location or None,
                latitude=latitude,
                longitude=longitude,
            ),
            status=initial_status,
            image=ImageReference(
                filename=photo.filename or "upload",
                content_type=photo.content_type,
                size_bytes=len(photo_bytes),
                image_data=b"",
                file_path=relative_image_path,
            ),
            classification=WasteClassification(
                category=prediction.category,
                confidence=prediction.confidence,
                model_version=prediction.model_version,
            ),
            complaint=complaint,
        )
        report.status_history.append(
            ReportStatusHistory(status=initial_status, note="Report created.")
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return serialize_report(report)
    except SQLAlchemyError as exc:
        db.rollback()
        image_path.unlink(missing_ok=True)
        logger.exception("Database error while creating a garbage report")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The report could not be saved because the database is unavailable.",
        ) from exc
    except OSError as exc:
        db.rollback()
        image_path.unlink(missing_ok=True)
        logger.exception("Could not write uploaded image to local storage")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The uploaded image could not be saved to local storage.",
        ) from exc


@app.get(
    "/api/complaints",
    response_model=list[MunicipalComplaintResponse],
    summary="List municipal complaints",
)
def list_complaints(
    complaint_status: Annotated[
        Literal["New", "Assigned", "In Progress", "Resolved", "Closed"] | None,
        Query(alias="status"),
    ] = None,
    department: Annotated[str | None, Query(max_length=200)] = None,
    location: Annotated[str | None, Query(max_length=500)] = None,
    category: Annotated[Literal["Wet Waste", "Dry Waste"] | None, Query()] = None,
    created_after: Annotated[date | None, Query()] = None,
    created_before: Annotated[date | None, Query()] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MunicipalComplaintResponse]:
    query = select(MunicipalComplaint).options(
        selectinload(MunicipalComplaint.status_history),
        selectinload(MunicipalComplaint.status_history).selectinload(
            ComplaintStatusHistory.changed_by
        ),
        joinedload(MunicipalComplaint.report).joinedload(
            GarbageReportModel.image
        ),
    )
    if user.role == "citizen":
        query = query.where(
            MunicipalComplaint.report.has(GarbageReportModel.user_id == user.id)
        )
    if complaint_status:
        query = query.where(MunicipalComplaint.status == complaint_status)
    if department and department.strip():
        query = query.where(
            MunicipalComplaint.assigned_department.contains(
                department.strip(), autoescape=True
            )
        )
    if location and location.strip():
        query = query.where(
            MunicipalComplaint.location.contains(location.strip(), autoescape=True)
        )
    if category:
        query = query.where(MunicipalComplaint.waste_category == category)
    if created_after:
        query = query.where(
            func.date(MunicipalComplaint.created_at) >= created_after.isoformat()
        )
    if created_before:
        query = query.where(
            func.date(MunicipalComplaint.created_at) <= created_before.isoformat()
        )
    try:
        complaints = db.scalars(
            query.order_by(
                MunicipalComplaint.created_at.desc(), MunicipalComplaint.id.desc()
            )
        ).all()
        return [serialize_complaint(complaint) for complaint in complaints]
    except SQLAlchemyError as exc:
        logger.exception("Database error while listing municipal complaints")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Complaints could not be loaded because the database is unavailable.",
        ) from exc


@app.get(
    "/api/complaints/{complaint_id}",
    response_model=MunicipalComplaintResponse,
    summary="Get complaint details and status history",
)
def get_complaint(
    complaint_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MunicipalComplaintResponse:
    try:
        complaint = db.scalar(
            select(MunicipalComplaint)
            .where(MunicipalComplaint.id == complaint_id)
            .options(
                selectinload(MunicipalComplaint.status_history),
                selectinload(MunicipalComplaint.status_history).selectinload(
                    ComplaintStatusHistory.changed_by
                ),
                joinedload(MunicipalComplaint.report).joinedload(
                    GarbageReportModel.image
                ),
            )
        )
        if complaint is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Complaint {complaint_id} was not found.",
            )
        if user.role == "citizen" and complaint.report.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Complaint {complaint_id} was not found.",
            )
        return serialize_complaint(complaint)
    except SQLAlchemyError as exc:
        logger.exception("Database error while retrieving complaint %s", complaint_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The complaint could not be loaded because the database is unavailable.",
        ) from exc


@app.put(
    "/api/complaints/{complaint_id}/assignment",
    response_model=MunicipalComplaintResponse,
    summary="Assign a complaint to a department",
)
def assign_complaint(
    complaint_id: int,
    update: ComplaintAssignmentUpdate,
    user: User = Depends(require_authority),
    db: Session = Depends(get_db),
) -> MunicipalComplaintResponse:
    department = update.assigned_department.strip()
    if not department:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Assigned department must not be blank.",
        )
    try:
        complaint = db.scalar(
            select(MunicipalComplaint)
            .where(MunicipalComplaint.id == complaint_id)
            .options(
                selectinload(MunicipalComplaint.status_history).selectinload(
                    ComplaintStatusHistory.changed_by
                ),
                joinedload(MunicipalComplaint.report).joinedload(
                    GarbageReportModel.image
                ),
            )
        )
        if complaint is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Complaint {complaint_id} was not found.",
            )
        old_department = complaint.assigned_department
        complaint.assigned_department = department
        note = f"Department changed from {old_department} to {department}."
        if update.staff_note and update.staff_note.strip():
            note = f"{note} {update.staff_note.strip()}"
        complaint.status_history.append(
            ComplaintStatusHistory(
                previous_status=complaint.status,
                new_status=complaint.status,
                event_type="assignment",
                changed_by_user_id=user.id,
                staff_note=note,
            )
        )
        db.commit()
        db.refresh(complaint)
        return serialize_complaint(complaint)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error while assigning complaint %s", complaint_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The complaint assignment could not be saved because the database is unavailable.",
        ) from exc


@app.put(
    "/api/complaints/{complaint_id}/status",
    response_model=MunicipalComplaintResponse,
    summary="Update a complaint status",
    description="Requires an authenticated municipal authority account.",
)
def update_complaint_status(
    complaint_id: int,
    update: ComplaintStatusUpdate,
    user: User = Depends(require_authority),
    db: Session = Depends(get_db),
) -> MunicipalComplaintResponse:
    try:
        complaint = db.scalar(
            select(MunicipalComplaint)
            .where(MunicipalComplaint.id == complaint_id)
            .options(selectinload(MunicipalComplaint.status_history))
        )
        if complaint is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Complaint {complaint_id} was not found.",
            )
        if update.status not in COMPLAINT_STATUS_TRANSITIONS[complaint.status]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot transition complaint from {complaint.status!r} "
                    f"to {update.status!r}."
                ),
            )
        if update.status == "Resolved":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "An after-cleaning photo is required. Use "
                    "PUT /api/complaints/{complaint_id}/resolve."
                ),
            )

        previous_status = complaint.status
        complaint.status = update.status
        complaint.status_history.append(
            ComplaintStatusHistory(
                previous_status=previous_status,
                new_status=update.status,
                event_type="status",
                changed_by_user_id=user.id,
                staff_note=update.staff_note.strip() if update.staff_note else None,
            )
        )
        db.commit()
        db.refresh(complaint)
        return serialize_complaint(complaint)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error while updating complaint %s", complaint_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The complaint status could not be saved because the database is unavailable.",
        ) from exc


@app.put(
    "/api/complaints/{complaint_id}/resolve",
    response_model=MunicipalComplaintResponse,
    summary="Resolve a complaint with an after-cleaning photo",
    description="Requires municipal authority access and an after_cleaning_photo image.",
)
async def resolve_complaint(
    complaint_id: int,
    after_cleaning_photo: Annotated[UploadFile, File()],
    staff_note: Annotated[str | None, Form(max_length=1000)] = None,
    user: User = Depends(require_authority),
    db: Session = Depends(get_db),
) -> MunicipalComplaintResponse:
    photo_bytes = await read_photo(after_cleaning_photo)
    if not has_valid_image_signature(after_cleaning_photo.content_type, photo_bytes):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="The uploaded file contents do not match the declared image type.",
        )

    image_path: Path | None = None
    try:
        complaint = db.scalar(
            select(MunicipalComplaint)
            .where(MunicipalComplaint.id == complaint_id)
            .options(
                selectinload(MunicipalComplaint.status_history),
                selectinload(MunicipalComplaint.status_history).selectinload(
                    ComplaintStatusHistory.changed_by
                ),
                joinedload(MunicipalComplaint.report).joinedload(
                    GarbageReportModel.image
                ),
            )
        )
        if complaint is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Complaint {complaint_id} was not found.",
            )
        if "Resolved" not in COMPLAINT_STATUS_TRANSITIONS[complaint.status]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Complaint {complaint_id} cannot be resolved from {complaint.status!r}.",
            )

        stored_filename = (
            f"{uuid4().hex}{IMAGE_EXTENSIONS[after_cleaning_photo.content_type]}"
        )
        image_path = UPLOAD_DIR / stored_filename
        image_path.write_bytes(photo_bytes)
        previous_status = complaint.status
        complaint.status = "Resolved"
        complaint.after_cleaning_photo_path = (
            Path("uploads") / stored_filename
        ).as_posix()
        complaint.after_cleaning_photo_uploaded_at = datetime.now(timezone.utc)
        complaint.status_history.append(
            ComplaintStatusHistory(
                previous_status=previous_status,
                new_status="Resolved",
                event_type="status",
                changed_by_user_id=user.id,
                staff_note=staff_note.strip() if staff_note else None,
            )
        )
        db.commit()
        db.refresh(complaint)
        return serialize_complaint(complaint)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        if image_path is not None:
            image_path.unlink(missing_ok=True)
        logger.exception("Database error while resolving complaint %s", complaint_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The complaint resolution could not be saved because the database is unavailable.",
        ) from exc
    except OSError as exc:
        db.rollback()
        if image_path is not None:
            image_path.unlink(missing_ok=True)
        logger.exception("Could not save after-cleaning photo for complaint %s", complaint_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The after-cleaning photo could not be saved to local storage.",
        ) from exc
@app.get("/api/reports", response_model=list[GarbageReport])
def list_reports(
    user: User = Depends(require_citizen), db: Session = Depends(get_db)
) -> list[GarbageReport]:
    try:
        reports = db.scalars(
            select(GarbageReportModel)
            .options(
                joinedload(GarbageReportModel.location),
                joinedload(GarbageReportModel.image),
                joinedload(GarbageReportModel.status),
                joinedload(GarbageReportModel.classification),
                joinedload(GarbageReportModel.complaint),
            )
            .where(GarbageReportModel.user_id == user.id)
            .order_by(GarbageReportModel.created_at.desc(), GarbageReportModel.id.desc())
        ).all()
        return [serialize_report(report) for report in reports]
    except SQLAlchemyError as exc:
        logger.exception("Database error while listing garbage reports")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Reports could not be loaded because the database is unavailable.",
        ) from exc


def has_valid_image_signature(content_type: str, image: bytes) -> bool:
    if content_type == "image/jpeg":
        return image.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return image.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/webp":
        return (
            len(image) >= 12
            and image.startswith(b"RIFF")
            and image[8:12] == b"WEBP"
        )
    return False


@app.get("/uploads/{filename}", include_in_schema=False)
def serve_upload(
    filename: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    if not filename or Path(filename).name != filename:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Image was not found."
        )
    relative_path = (Path("uploads") / filename).as_posix()
    image = db.scalar(
        select(ImageReference)
        .where(ImageReference.file_path == relative_path)
        .options(joinedload(ImageReference.report))
    )
    if image is not None:
        if user.role == "citizen" and image.report.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Image was not found."
            )
    else:
        complaint = db.scalar(
            select(MunicipalComplaint)
            .where(MunicipalComplaint.after_cleaning_photo_path == relative_path)
            .options(joinedload(MunicipalComplaint.report))
        )
        if complaint is None or (
            user.role == "citizen" and complaint.report.user_id != user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Image was not found."
            )
    image_path = UPLOAD_DIR / filename
    if not image_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Image was not found."
        )
    media_type = next(
        (
            content_type
            for content_type, extension in IMAGE_EXTENSIONS.items()
            if image_path.suffix.casefold() == extension
        ),
        None,
    )
    return FileResponse(
        image_path,
        media_type=media_type,
        headers={"Cache-Control": "private, no-store"},
    )


@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend(full_path: str) -> FileResponse:
    if full_path.split("/", 1)[0] in {
        "api",
        "docs",
        "redoc",
        "openapi.json",
        "uploads",
    }:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested page was not found.",
        )

    frontend_root = FRONTEND_DIR.resolve()
    requested_file = (frontend_root / full_path).resolve()
    try:
        requested_file.relative_to(frontend_root)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested page was not found.",
        ) from None

    if requested_file.is_file():
        return FileResponse(requested_file)
    if Path(full_path).suffix:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested file was not found.",
        )

    index_file = frontend_root / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="The frontend has not been built.",
    )
