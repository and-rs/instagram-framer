import base64
import json
import logging
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_HASHTAGS = (
    "#Arte #ArteOriginal #Pintura #Cuadros #Decoracion #ArteContemporaneo "
    "#ContemporaryArt #OriginalArt #ArtForSale #ArtCollector #CollectorsArt "
    "#Painting #FineArt #InteriorDesign #HechoAMano #ArtistOnInstagram"
)
COLLECTION_MAX_OUTPUT_TOKENS = 2000
CAPTION_MAX_OUTPUT_TOKENS = 8000
SYSTEM_PROMPT_PATH = Path(__file__).with_name("prompts") / "caption_system.md"


class CaptionGenerationError(ValueError):
    pass


def fallback_caption(
    *,
    title: str | None,
    material: str | None,
    size: str | None,
    collection_name: str,
    artwork_number: str,
    description: str,
) -> str:
    first_line_parts = [f"{_title_case(collection_name)} · {_display_value(artwork_number)}"]
    first_line_parts.extend(_display_value(part) for part in [title, material, size] if part and part.strip())
    return (
        f"{' | '.join(first_line_parts)}\n\n"
        f"{description}\n\n"
        "Obra disponible para adquisición. Para consultas sobre disponibilidad y detalles, contáctanos por interno.\n\n"
        f"{DEFAULT_HASHTAGS}"
    )


async def generate_collection_names(
    *,
    image_data: bytes,
    media_type: str,
    collection_description: str,
    previous_names: list[str],
) -> tuple[list[str], str | None]:
    if not settings.openai_api_key:
        raise CaptionGenerationError("OPENAI_API_KEY no está configurada; escribe un nombre de colección para continuar.")

    payload = await _generate_json(
        prompt=_build_collection_prompt(collection_description, previous_names),
        image_data=image_data,
        media_type=media_type,
        schema_name="collection_names",
        schema={
            "type": "object",
            "properties": {
                "names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 5,
                    "maxItems": 5,
                }
            },
            "required": ["names"],
            "additionalProperties": False,
        },
        max_output_tokens=COLLECTION_MAX_OUTPUT_TOKENS,
    )
    names = _collection_names(payload, previous_names)
    if len(names) != 5:
        raise CaptionGenerationError("La respuesta no contenía cinco nombres de colección válidos.")
    return names, None


async def generate_caption(
    *,
    title: str | None,
    material: str | None,
    size: str | None,
    notes: str | None,
    image_count: int,
    collection_name: str,
    artwork_number: str,
    collection_description: str | None,
    image_data: bytes,
    media_type: str,
) -> tuple[str, str, str | None]:
    fallback_description = f"Obra original de la colección {collection_name}."
    if not settings.openai_api_key:
        return (
            fallback_caption(
                title=title,
                material=material,
                size=size,
                collection_name=collection_name,
                artwork_number=artwork_number,
                description=fallback_description,
            ),
            fallback_description,
            "OPENAI_API_KEY no está configurada; se usó un caption de respaldo.",
        )

    payload = await _generate_json(
        prompt=_build_caption_prompt(
            title=title,
            material=material,
            size=size,
            notes=notes,
            image_count=image_count,
            collection_name=collection_name,
            artwork_number=artwork_number,
            collection_description=collection_description,
        ),
        image_data=image_data,
        media_type=media_type,
        schema_name="artwork_caption",
        schema={
            "type": "object",
            "properties": {
                "description": {"type": "string"},
                "caption": {"type": "string"},
            },
            "required": ["description", "caption"],
            "additionalProperties": False,
        },
        max_output_tokens=CAPTION_MAX_OUTPUT_TOKENS,
    )
    description = str(payload["description"]).strip()
    caption = str(payload["caption"]).strip()
    if not description or not caption:
        raise CaptionGenerationError("La respuesta no incluyó descripción y caption.")
    caption = _normalize_caption_header(
        caption=caption,
        collection_name=collection_name,
        artwork_number=artwork_number,
        title=title,
        material=material,
        size=size,
    )
    return caption, description, None


async def _generate_json(
    *,
    prompt: str,
    image_data: bytes,
    media_type: str,
    schema_name: str,
    schema: dict[str, Any],
    max_output_tokens: int,
) -> dict[str, Any]:
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    encoded_image = base64.b64encode(image_data).decode("ascii")
    system_prompt = _load_system_prompt()
    responses_error: Exception | None = None
    try:
        response_kwargs: dict[str, Any] = {
            "model": settings.openai_model,
            "instructions": system_prompt,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": f"data:{media_type};base64,{encoded_image}"},
                    ],
                }
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                }
            },
            "max_output_tokens": max_output_tokens,
        }
        if _uses_gpt5_reasoning():
            response_kwargs["reasoning"] = {"effort": "low"}
        response = await client.responses.create(**response_kwargs)
        return _json_object(_extract_response_text(response), _response_detail(response))
    except Exception as exc:
        responses_error = exc
        logger.warning("Responses structured output failed: %s", _safe_error(exc))

    try:
        chat_kwargs: dict[str, Any] = {
            "model": settings.openai_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"{prompt}\n\nDevuelve únicamente un objeto JSON válido."},
                        {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{encoded_image}"}},
                    ],
                }
            ],
            "response_format": {"type": "json_object"},
            "max_completion_tokens": max_output_tokens,
        }
        if _uses_gpt5_reasoning():
            chat_kwargs["reasoning_effort"] = "low"
        response = await client.chat.completions.create(**chat_kwargs)
        text = response.choices[0].message.content or ""
        return _json_object(text, "Chat Completions")
    except Exception as chat_error:
        logger.warning("Chat structured output failed: %s", _safe_error(chat_error))
        raise CaptionGenerationError(
            f"Responses API: {_safe_error(responses_error)} | Chat Completions: {_safe_error(chat_error)}"
        ) from chat_error


def _json_object(text: str, source: str) -> dict[str, Any]:
    if not text or not text.strip():
        raise ValueError(f"{source} devolvió texto vacío")
    result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError(f"{source} no devolvió un objeto JSON")
    return result


def _load_system_prompt() -> str:
    try:
        prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise CaptionGenerationError(f"No se pudo leer el prompt del sistema: {exc}") from exc
    if not prompt:
        raise CaptionGenerationError("El prompt del sistema está vacío.")
    return prompt


def _uses_gpt5_reasoning() -> bool:
    return settings.openai_model.lower().startswith("gpt-5")


def _response_detail(response: Any) -> str:
    status = getattr(response, "status", None)
    incomplete = getattr(response, "incomplete_details", None)
    detail = f"Responses API (estado: {status or 'desconocido'})"
    if incomplete:
        detail = f"{detail}; incompleta: {incomplete}"
    return detail


def _display_value(value: str) -> str:
    cleaned = " ".join(value.split())
    return cleaned[:1].upper() + cleaned[1:]


def _normalize_caption_header(
    *,
    caption: str,
    collection_name: str,
    artwork_number: str,
    title: str | None,
    material: str | None,
    size: str | None,
) -> str:
    header_parts = [f"{_title_case(collection_name)} {_display_value(artwork_number)}"]
    header_parts.extend(_display_value(value) for value in [title, material, size] if value and value.strip())
    lines = caption.splitlines()
    for index, line in enumerate(lines):
        if line.strip():
            lines[index] = " | ".join(header_parts)
            break
    return "\n".join(lines).strip()


def _title_case(value: str) -> str:
    return " ".join(word[:1].upper() + word[1:] for word in value.split())


def _build_collection_prompt(collection_description: str, previous_names: list[str]) -> str:
    excluded = ", ".join(previous_names) if previous_names else "Ninguno"
    return "\n".join(
        [
            "Propón exactamente cinco nombres de colección para una obra de arte.",
            "Usa la imagen como referencia visual y la descripción de la colección como dirección conceptual.",
            "Los nombres deben ser sencillos, descriptivos, sobrios y breves (de dos a cinco palabras).",
            "No uses comillas, números, hashtags, subtítulos ni explicaciones.",
            "No repitas ni variantes obvias de estos nombres ya mostrados: " + excluded,
            f"Descripción de la colección: {collection_description.strip()}",
        ]
    )


def _build_caption_prompt(
    *,
    title: str | None,
    material: str | None,
    size: str | None,
    notes: str | None,
    image_count: int,
    collection_name: str,
    artwork_number: str,
    collection_description: str | None,
) -> str:
    details = [
        f"Colección: {collection_name}",
        f"Número de obra: {artwork_number}",
        f"Número de imágenes del carrusel: {image_count}",
    ]
    for label, value in (
        ("Título", title),
        ("Material/técnica", material),
        ("Medidas", size),
        ("Notas/contexto", notes),
        ("Descripción de la colección", collection_description),
    ):
        if value and value.strip():
            details.append(f"{label}: {value.strip()}")

    return "\n".join(
        [
            "Redacta contenido de Instagram en español para vender una obra de arte original.",
            "Examina la imagen adjunta y los datos de la obra.",
            "Devuelve una descripción breve de la pintura: un solo párrafo sobrio de dos o tres oraciones, basado solo en lo visible y los datos proporcionados.",
            "Describe únicamente elementos observables: objetos, formas, disposición, colores, superficies y técnica visible. No interpretes símbolos, emociones, atmósferas, movimiento, intenciones ni estilos; evita adjetivos abstractos o poéticos.",
            "Devuelve también el caption final. Debe incluir esa descripción literalmente como su segundo párrafo.",
            "Primera línea del caption: colección y número de obra, seguidos de título, material/técnica y medidas cuando existan, separados por |.",
            "Si no se proporciona título, omítelo por completo: no inventes un título ni uses 'Sin título', 'Untitled' o equivalentes.",
            "Tercer párrafo: indica profesionalmente que la obra está disponible para adquisición e invita a consultar por interno. Usa 'contáctanos' o 'consultas por interno'; no uses 'escríbeme' ni 'DM'.",
            "Última línea: 12 a 18 hashtags establecidos, mezclando español e inglés cuando ayude al alcance.",
            "Sé conciso: no repitas ideas ni sobreexplique la obra.",
            "Evita un tono urgente, exagerado o demasiado promocional. No uses comillas alrededor de la descripción ni del caption.",
            "Datos de la obra:",
            *details,
        ]
    )


def _collection_names(payload: dict[str, Any], previous_names: list[str]) -> list[str]:
    previous = {name.casefold() for name in previous_names}
    names: list[str] = []
    for value in payload.get("names", []):
        name = str(value).strip()
        if 2 <= len(name) <= 80 and name.casefold() not in previous and name.casefold() not in {item.casefold() for item in names}:
            names.append(name)
    return names


def _extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return str(output_text)

    parts: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                parts.append(str(text))
    return "\n".join(parts)


def _safe_error(exc: Exception) -> str:
    message = str(exc).replace(settings.openai_api_key or "", "[redacted]")
    return f"{type(exc).__name__}: {message[:500]}"
