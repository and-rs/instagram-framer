from types import SimpleNamespace

import pytest

import app.captioning as captioning
from app.captioning import (
    CaptionGenerationError,
    SYSTEM_PROMPT_PATH,
    _build_caption_prompt,
    _build_collection_prompt,
    _collection_names,
    _normalize_caption_header,
    fallback_caption,
)


def test_collection_prompt_uses_description_and_excludes_prior_options():
    prompt = _build_collection_prompt("paisajes nocturnos y luz suave", ["Luz Interior"])

    assert "paisajes nocturnos y luz suave" in prompt
    assert "Luz Interior" in prompt
    assert "exactamente cinco" in prompt


def test_collection_names_rejects_duplicates_and_prior_options():
    names = _collection_names(
        {"names": ["Luz Interior", "Bruma Azul", "bruma azul", "", "Materia Serena"]},
        ["Luz Interior"],
    )

    assert names == ["Bruma Azul", "Materia Serena"]


def test_caption_prompt_includes_complete_metadata_and_normalization_rules():
    prompt = _build_caption_prompt(
        title="casa azul",
        material="oleo sobre tela",
        size="40 x 50 cm",
        notes="pintada al atardecer",
        image_count=3,
        collection_name="Luz Interior",
        artwork_number="12",
        collection_description="espacios domésticos iluminados",
    )

    assert "Colección: Luz Interior" in prompt
    assert "Número de obra: 12" in prompt
    assert "Título: casa azul" in prompt
    assert "Número de imágenes del carrusel: 3" in prompt
    assert "Debe incluir esa descripción literalmente" in prompt
    assert "Sé conciso" in prompt
    assert "elementos observables" in prompt
    assert "No interpretes símbolos" in prompt


def test_caption_prompt_forbids_inventing_a_title_when_none_is_given():
    prompt = _build_caption_prompt(
        title=None,
        material="óleo sobre tela",
        size="40 x 50 cm",
        notes=None,
        image_count=1,
        collection_name="Luz Interior",
        artwork_number="12",
        collection_description=None,
    )

    assert "Si no se proporciona título, omítelo por completo" in prompt
    assert "Título:" not in prompt


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


def test_system_prompt_is_loaded_from_markdown_file():
    prompt = captioning._load_system_prompt()

    assert SYSTEM_PROMPT_PATH.name == "caption_system.md"
    assert "Correct Spanish grammar" in prompt


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
