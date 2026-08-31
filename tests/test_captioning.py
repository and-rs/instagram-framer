from types import SimpleNamespace

import pytest

import app.captioning as captioning
from app.captioning import (
    CaptionGenerationError,
    _collection_names,
    _normalize_caption_header,
    fallback_caption,
)


def test_collection_names_rejects_duplicates_and_prior_options():
    names = _collection_names(
        {"names": ["Luz Interior", "Bruma Azul", "bruma azul", "", "Materia Serena"]},
        ["Luz Interior"],
    )

    assert names == ["Bruma Azul", "Materia Serena"]


def test_caption_header_uses_title_case_collection_and_skips_missing_title():
    caption = _normalize_caption_header(
        caption="Mareas oníricas 01 | acrílico sobre lienzo | 35 x 25 cm\n\nDescripción.",
        collection_name="mareas oníricas",
        artwork_number="01",
        title=None,
        material="acrílico sobre lienzo",
        size="35 x 25 cm",
    )

    assert caption.startswith("Mareas Oníricas 01 | Acrílico sobre lienzo | 35 x 25 cm")
    assert "Título" not in caption


def test_fallback_caption_normalizes_header_spacing_and_capitalization():
    caption = fallback_caption(
        title=None,
        material="  acrilico   sobre lienzo ",
        size="35 x 25 cm",
        collection_name="cielo fragmentado",
        artwork_number="01",
        description="Obra original de la colección Cielo Fragmentado.",
    )

    assert caption.startswith("Cielo Fragmentado · 01 | Acrilico sobre lienzo | 35 x 25 cm")
    assert "\n            " not in caption


@pytest.mark.anyio
async def test_empty_responses_output_retries_chat_completions_with_the_image(monkeypatch):
    response_calls = []
    chat_calls = []
    monkeypatch.setattr(captioning.settings, "openai_model", "gpt-5-mini")

    class Responses:
        async def create(self, **kwargs):
            response_calls.append(kwargs)
            return SimpleNamespace(output_text="")

    class Completions:
        async def create(self, **kwargs):
            chat_calls.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"names":["Luz Serena"]}'))])

    client = SimpleNamespace(responses=Responses(), chat=SimpleNamespace(completions=Completions()))
    monkeypatch.setattr(captioning, "AsyncOpenAI", lambda api_key: client)

    result = await captioning._generate_json(
        prompt="Propón nombres.",
        image_data=b"image-bytes",
        media_type="image/jpeg",
        schema_name="collection_names",
        schema={"type": "object"},
        max_output_tokens=2000,
    )

    assert result == {"names": ["Luz Serena"]}
    assert response_calls
    assert chat_calls
    assert chat_calls[0]["messages"][0]["role"] == "system"
    image = chat_calls[0]["messages"][1]["content"][1]["image_url"]["url"]
    assert image.startswith("data:image/jpeg;base64,")
    assert response_calls[0]["reasoning"] == {"effort": "low"}
    assert chat_calls[0]["reasoning_effort"] == "low"


@pytest.mark.anyio
async def test_dual_provider_failure_preserves_both_error_details(monkeypatch):
    class Responses:
        async def create(self, **kwargs):
            return SimpleNamespace(output_text="")

    class Completions:
        async def create(self, **kwargs):
            raise RuntimeError("chat unavailable")

    client = SimpleNamespace(responses=Responses(), chat=SimpleNamespace(completions=Completions()))
    monkeypatch.setattr(captioning, "AsyncOpenAI", lambda api_key: client)

    with pytest.raises(CaptionGenerationError, match="chat unavailable"):
        await captioning._generate_json(
            prompt="Propón nombres.",
            image_data=b"image-bytes",
            media_type="image/jpeg",
            schema_name="collection_names",
            schema={"type": "object"},
            max_output_tokens=2000,
        )
