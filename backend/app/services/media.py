"""Xử lý ảnh phản ánh (PROJECT_PLAN.md mục 9.4).

Server LUÔN giải mã và mã hoá lại ảnh: xoá toàn bộ metadata (EXIF, GPS), chuẩn hoá hướng xoay,
giới hạn kích thước. Không tin client đã tự xoá EXIF.
"""

import hashlib
import io
import uuid
from dataclasses import dataclass
from datetime import datetime

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import Principal
from app.services import status_engine
from app.services.storage import Storage

Image.MAX_IMAGE_PIXELS = 40_000_000  # chặn ảnh "bom giải nén"
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "MPO"}
MAX_SIDE = 1600
THUMB_SIDE = 400
JPEG_QUALITY = 82


@dataclass(frozen=True)
class ProcessedImage:
    data: bytes
    thumb: bytes
    width: int
    height: int
    sha256: str


def process_image(raw: bytes) -> ProcessedImage:
    try:
        with Image.open(io.BytesIO(raw)) as probe:
            fmt = probe.format
            probe.verify()
        if fmt not in ALLOWED_FORMATS:
            raise AppError("UNSUPPORTED_IMAGE", "Chỉ nhận ảnh JPEG, PNG hoặc WebP", status_code=415)
        with Image.open(io.BytesIO(raw)) as img:
            img = ImageOps.exif_transpose(img)  # áp hướng xoay TRƯỚC khi bỏ EXIF
            img = img.convert("RGB")
            img.thumbnail((MAX_SIDE, MAX_SIDE))
            out = io.BytesIO()
            img.save(
                out, "JPEG", quality=JPEG_QUALITY, optimize=True
            )  # không truyền exif → không có metadata
            thumb_img = img.copy()
            thumb_img.thumbnail((THUMB_SIDE, THUMB_SIDE))
            thumb = io.BytesIO()
            thumb_img.save(thumb, "JPEG", quality=75, optimize=True)
            width, height = img.size
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as exc:
        raise AppError("INVALID_IMAGE", "Tệp không phải ảnh hợp lệ", status_code=415) from exc

    data = out.getvalue()
    return ProcessedImage(data, thumb.getvalue(), width, height, hashlib.sha256(data).hexdigest())


def attach_photo(
    db: Session,
    settings: Settings,
    storage: Storage,
    principal: Principal,
    report_id: uuid.UUID,
    raw: bytes,
    now: datetime,
) -> dict:
    report = db.execute(
        text("SELECT device_id, segment_id, dimension FROM report WHERE id = :id"),
        {"id": report_id},
    ).one_or_none()
    if report is None or str(report.device_id) != principal.device_id:
        raise AppError("REPORT_NOT_FOUND", "Không tìm thấy phản ánh", status_code=404)
    count = db.execute(
        text("SELECT count(*) FROM report_media WHERE report_id = :id"), {"id": report_id}
    ).scalar_one()
    if count >= settings.max_photos_per_report:
        raise AppError(
            "TOO_MANY_PHOTOS", f"Tối đa {settings.max_photos_per_report} ảnh mỗi phản ánh", status_code=409
        )
    if len(raw) > settings.max_upload_bytes:
        raise AppError("FILE_TOO_LARGE", "Ảnh vượt quá 5 MB", status_code=413)

    image = process_image(raw)
    duplicate_of = db.execute(
        text("""
            SELECT m.id FROM report_media m WHERE m.sha256 = :sha AND m.report_id <> :rid
            ORDER BY m.created_at LIMIT 1
        """),
        {"sha": image.sha256, "rid": report_id},
    ).scalar_one_or_none()

    media_id = uuid.uuid4()
    key = f"reports/{now:%Y/%m}/{media_id}.jpg"
    thumb_key = f"reports/{now:%Y/%m}/{media_id}_thumb.jpg"
    storage.put(key, image.data, "image/jpeg")
    storage.put(thumb_key, image.thumb, "image/jpeg")

    db.execute(
        text("""
            INSERT INTO report_media (id, report_id, storage_key, thumb_key, mime_type, width, height, bytes,
                                      sha256, duplicate_of)
            VALUES (:id, :rid, :key, :thumb, 'image/jpeg', :w, :h, :bytes, :sha, :dup)
        """),
        {
            "id": media_id,
            "rid": report_id,
            "key": key,
            "thumb": thumb_key,
            "w": image.width,
            "h": image.height,
            "bytes": len(image.data),
            "sha": image.sha256,
            "dup": duplicate_of,
        },
    )

    # Ảnh trùng với phản ánh khác không được cộng điểm "có ảnh"
    if duplicate_of is None and report.segment_id is not None:
        updated = db.execute(
            text("""
                UPDATE observation SET has_photo = true
                WHERE source_type = 'citizen_report' AND source_ref = :ref AND NOT has_photo
            """),
            {"ref": str(report_id)},
        ).rowcount
        if updated:
            status_engine.recompute(db, report.segment_id, report.dimension, now)
    db.commit()
    return {
        "media_id": str(media_id),
        "width": image.width,
        "height": image.height,
        "duplicate": duplicate_of is not None,
    }
