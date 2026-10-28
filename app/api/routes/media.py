from io import BytesIO
from pathlib import Path
from uuid import uuid4
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.feed_cache import invalidate_author_feeds
from app.dependencies.auth import get_current_user
from app.models.media import MediaAsset
from app.models.post import Post
from app.models.user import User
from app.schemas.media import MediaRead

router = APIRouter()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
ALLOWED_FORMATS = {
    "image/jpeg": ("JPEG", ".jpg"),
    "image/png": ("PNG", ".png"),
    "image/webp": ("WEBP", ".webp"),
}


def normalize_image(contents: bytes, content_type: str | None) -> tuple[bytes, str, str]:
    mime_type = content_type or ""
    expected = ALLOWED_FORMATS.get(mime_type)
    if expected is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only JPEG, PNG, and WebP images are supported",
        )

    try:
        with Image.open(BytesIO(contents)) as image:
            if image.format != expected[0]:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="The uploaded file does not match its content type",
                )
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Image dimensions are too large",
                )
            if getattr(image, "is_animated", False):
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="Animated images are not supported",
                )
            image.verify()

        with Image.open(BytesIO(contents)) as image:
            image = ImageOps.exif_transpose(image)
            output = BytesIO()
            if expected[0] == "JPEG":
                image.convert("RGB").save(output, format="JPEG", quality=90, optimize=True)
            elif expected[0] == "WEBP":
                image.save(output, format="WEBP", quality=90, method=4)
            else:
                image.save(output, format="PNG", optimize=True)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Could not read the uploaded image"
        ) from None

    normalized = output.getvalue()
    if len(normalized) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Processed image exceeds the 10 MB limit",
        )
    return normalized, mime_type, expected[1]


@router.post(
    "/posts/{post_id}/media",
    response_model=MediaRead,
    status_code=status.HTTP_201_CREATED,
)
def upload_post_image(
    post_id: int,
    image: Annotated[UploadFile, File()],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MediaAsset:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if post.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only add media to your own posts",
        )

    contents = image.file.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image must be 10 MB or smaller",
        )
    contents, content_type, extension = normalize_image(contents, image.content_type)

    file_name = f"{uuid4().hex}{extension}"
    file_path = Path(settings.media_dir) / file_name
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(contents)

    media = MediaAsset(post_id=post.id, file_name=file_name, content_type=content_type)
    db.add(media)
    try:
        db.commit()
        db.refresh(media)
    except Exception:
        db.rollback()
        file_path.unlink(missing_ok=True)
        raise
    invalidate_author_feeds(db, current_user.id)
    return media


@router.delete(
    "/posts/{post_id}/media/{media_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_post_image(
    post_id: int,
    media_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if post.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only remove media from your own posts",
        )

    media = db.get(MediaAsset, media_id)
    if media is None or media.post_id != post_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    file_path = Path(settings.media_dir) / media.file_name
    db.delete(media)
    db.commit()
    invalidate_author_feeds(db, current_user.id)
    file_path.unlink(missing_ok=True)
