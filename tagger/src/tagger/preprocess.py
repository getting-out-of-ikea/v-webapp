"""Image preprocessing: EXIF orientation, RGB conversion, downscale."""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

# MIME dichiarati dal client: solo un primo filtro, non una garanzia.
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}

# Formati realmente accettati, riconosciuti da Pillow sul contenuto del file.
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class InvalidImageError(ValueError):
    """Raised when the uploaded bytes are not a usable image."""


@dataclass
class PreparedImage:
    data: bytes
    width: int
    height: int
    downscaled: bool


def prepare_image(raw: bytes, max_dimension: int) -> PreparedImage:
    """Normalise an uploaded image for the Vision API.

    - Verifies the real format from the bytes, not from the client's headers.
    - Applies EXIF orientation so smartphone photos are not rotated.
    - Converts to RGB (Vision rejects some exotic modes).
    - Downscales the longest side to ``max_dimension``.
    - Re-encodes as JPEG only when a downscale happened.
    """
    try:
        with Image.open(io.BytesIO(raw)) as img:
            detected = (img.format or "").upper()
            if detected not in ALLOWED_FORMATS:
                raise InvalidImageError(
                    f"unsupported image format: {detected or 'unknown'}"
                )

            img = ImageOps.exif_transpose(img)
            if img.mode != "RGB":
                img = img.convert("RGB")

            width, height = img.size
            longest = max(width, height)
            downscaled = longest > max_dimension

            if downscaled:
                scale = max_dimension / longest
                new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                width, height = img.size

                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=85, optimize=True)
                return PreparedImage(
                    data=buffer.getvalue(),
                    width=width,
                    height=height,
                    downscaled=True,
                )

            # No downscale: keep the original bytes to avoid recompression.
            return PreparedImage(
                data=raw,
                width=width,
                height=height,
                downscaled=False,
            )
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageError("Unsupported or corrupt image") from exc
