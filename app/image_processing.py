from io import BytesIO
from pathlib import Path
import warnings

from PIL import Image, ImageColor, ImageFilter, ImageOps, UnidentifiedImageError

from app.config import settings

OUTPUT_SIZE = 2000
DEFAULT_BACKGROUND = (247, 243, 234)
BACKGROUND = DEFAULT_BACKGROUND


class ImageProcessingError(ValueError):
    pass


def _load_image(data: bytes) -> Image.Image:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            image = Image.open(BytesIO(data))
        _validate_image_pixels(image)
        image.verify()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            image = Image.open(BytesIO(data))
        _validate_image_pixels(image)
        image = ImageOps.exif_transpose(image)
        return image.convert("RGBA")
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as exc:
        raise ImageProcessingError("El archivo subido no es una imagen válida") from exc


def _validate_image_pixels(image: Image.Image) -> None:
    if image.width * image.height > settings.max_image_pixels:
        raise ImageProcessingError(
            f"La imagen supera el límite de {settings.max_image_pixels:,} píxeles."
        )


def _flatten(
    image: Image.Image, background: tuple[int, int, int] = (255, 255, 255)
) -> Image.Image:
    canvas = Image.new("RGBA", image.size, background + (255,))
    canvas.alpha_composite(image)
    return canvas.convert("RGB")


def frame_image_bytes(data: bytes, output_path: Path) -> Path:
    image = _load_image(data)
    width, height = image.size
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if width == height:
        result = _flatten(image).resize(
            (OUTPUT_SIZE, OUTPUT_SIZE), Image.Resampling.LANCZOS
        )
        _save_jpeg(result, output_path)
        return output_path

    max_side = int(OUTPUT_SIZE * 0.90)
    framed = Image.new("RGB", (OUTPUT_SIZE, OUTPUT_SIZE), _frame_background())
    work = image.copy()
    work.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

    x = (OUTPUT_SIZE - work.width) // 2
    y = (OUTPUT_SIZE - work.height) // 2

    shadow = Image.new("RGBA", (OUTPUT_SIZE, OUTPUT_SIZE), (0, 0, 0, 0))
    mask = Image.new("L", work.size, 0)
    alpha = work.getchannel("A")
    mask.paste(alpha)
    shadow_layer = Image.new("RGBA", work.size, (0, 0, 0, 0))
    shadow_alpha = _shadow_alpha()
    shadow_layer.putalpha(mask.point(lambda value: value * shadow_alpha // 255))
    shadow.alpha_composite(shadow_layer, (x, y + 18))
    shadow = shadow.filter(ImageFilter.GaussianBlur(38))
    framed = Image.alpha_composite(framed.convert("RGBA"), shadow)

    image_rgb = _flatten(work)
    framed.alpha_composite(image_rgb.convert("RGBA"), (x, y))
    _save_jpeg(framed.convert("RGB"), output_path)
    return output_path


def _shadow_alpha() -> int:
    return round(settings.frame_shadow_opacity * 255)


def _save_jpeg(image: Image.Image, output_path: Path) -> None:
    max_bytes = settings.max_output_mb * 1024 * 1024

    for quality in range(92, 19, -4):
        buffer = BytesIO()
        image.save(buffer, "JPEG", quality=quality, optimize=True, progressive=True)
        if buffer.tell() <= max_bytes:
            output_path.write_bytes(buffer.getvalue())
            return

    raise ImageProcessingError(
        "El resultado supera MAX_OUTPUT_MB incluso con la compresión mínima permitida."
    )


def _frame_background() -> tuple[int, int, int]:
    color = settings.frame_background.strip().strip("\"'")
    if len(color) in (3, 6) and all(char in "0123456789abcdefABCDEF" for char in color):
        color = f"#{color}"

    try:
        return ImageColor.getrgb(color)
    except ValueError as exc:
        raise ImageProcessingError(
            "FRAME_BACKGROUND debe ser un color CSS válido, por ejemplo #f7f3ea"
        ) from exc
