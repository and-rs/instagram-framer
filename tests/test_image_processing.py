from io import BytesIO

import pytest
from PIL import Image
from pydantic import ValidationError

from app.config import Settings, settings
from app.image_processing import (
    DEFAULT_BACKGROUND,
    OUTPUT_SIZE,
    ImageProcessingError,
    frame_image_bytes,
    _load_image,
)


def _jpeg_bytes(size: tuple[int, int], color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", size, color)
    buffer = BytesIO()
    image.save(buffer, "JPEG")
    return buffer.getvalue()


def test_square_image_outputs_2000_square_without_frame(tmp_path):
    output = tmp_path / "square.jpg"

    frame_image_bytes(_jpeg_bytes((600, 600), (210, 30, 40)), output)

    result = Image.open(output)
    assert result.size == (OUTPUT_SIZE, OUTPUT_SIZE)
    assert result.getpixel((50, 50))[0] > 180
    assert result.getpixel((50, 50))[1] < 70
    assert result.getpixel((50, 50))[2] < 80


def test_non_square_image_is_framed_on_off_white_background(tmp_path):
    output = tmp_path / "framed.jpg"
    settings.frame_background = "#f7f3ea"

    frame_image_bytes(_jpeg_bytes((1200, 800), (20, 120, 200)), output)

    result = Image.open(output)
    assert result.size == (OUTPUT_SIZE, OUTPUT_SIZE)
    corner = result.getpixel((20, 20))
    assert all(abs(corner[index] - DEFAULT_BACKGROUND[index]) < 5 for index in range(3))
    center = result.getpixel((OUTPUT_SIZE // 2, OUTPUT_SIZE // 2))
    assert center[2] > 150


def test_image_pixel_limit_is_enforced(monkeypatch):
    monkeypatch.setattr(settings, "max_image_pixels", 3)

    with pytest.raises(ImageProcessingError, match="límite"):
        _load_image(_jpeg_bytes((2, 2), (20, 120, 200)))


def test_output_larger_than_configured_limit_is_rejected(tmp_path, monkeypatch):
    output = tmp_path / "too-large.jpg"
    monkeypatch.setattr(settings, "max_output_mb", 0.0001)

    with pytest.raises(ImageProcessingError, match="MAX_OUTPUT_MB"):
        frame_image_bytes(_jpeg_bytes((600, 600), (210, 30, 40)), output)

    assert not output.exists()


@pytest.mark.parametrize("opacity", ["nan", "inf", "-inf"])
def test_non_finite_shadow_opacity_is_rejected(opacity):
    with pytest.raises(ValidationError, match="FRAME_SHADOW_OPACITY"):
        Settings(_env_file=None, FRAME_SHADOW_OPACITY=opacity)
