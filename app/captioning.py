import logging
from typing import Any

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_HASHTAGS = (
    "#Arte #ArteOriginal #Pintura #Cuadros #Decoracion #ArteContemporaneo "
    "#ContemporaryArt #OriginalArt #ArtForSale #ArtCollector #CollectorsArt "
    "#Painting #FineArt #InteriorDesign #HechoAMano #ArtistOnInstagram"
)


def fallback_caption(title: str | None, material: str | None, size: str | None) -> str:
    first_line_parts = [part.strip() for part in [title, material, size] if part and part.strip()]
    first_line = " | ".join(first_line_parts) if first_line_parts else "Obra original"
    return (
        f"{first_line}\n\n"
        "Obra disponible para adquisición. Para consultas sobre disponibilidad y detalles, contáctanos por interno.\n\n"
        f"{DEFAULT_HASHTAGS}"
    )


async def generate_caption(
    *,
    title: str | None,
    material: str | None,
    size: str | None,
    notes: str | None,
    image_count: int,
) -> tuple[str, str | None]:
    if not settings.openai_api_key:
        return fallback_caption(title, material, size), "OPENAI_API_KEY no está configurada; se usó un caption de respaldo."

    prompt = _build_prompt(title=title, material=material, size=size, notes=notes, image_count=image_count)
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    errors: list[str] = []

    try:
        response = await client.responses.create(
            model=settings.openai_model,
            input=prompt,
            max_output_tokens=1600,
        )
        caption = _extract_response_text(response).strip()
        if caption:
            return caption, None
        errors.append("Responses API devolvió texto vacío")
    except Exception as exc:
        logger.exception("Caption generation failed with Responses API")
        errors.append(_safe_error(exc))

    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=800,
        )
        caption = response.choices[0].message.content or ""
        caption = caption.strip()
        if caption:
            return caption, None
        errors.append("Chat Completions devolvió texto vacío")
    except Exception as exc:
        logger.exception("Caption generation failed with Chat Completions API")
        errors.append(_safe_error(exc))

    detail = " | ".join(errors[-2:])
    return fallback_caption(title, material, size), f"No se pudo generar el caption con OpenAI; se usó un respaldo. Detalle: {detail}"


def _build_prompt(*, title: str | None, material: str | None, size: str | None, notes: str | None, image_count: int) -> str:
    details = []
    if title and title.strip():
        details.append(f"Título: {title.strip()}")
    if material and material.strip():
        details.append(f"Material/técnica: {material.strip()}")
    if size and size.strip():
        details.append(f"Medidas: {size.strip()}")
    if notes and notes.strip():
        details.append(f"Notas/contexto: {notes.strip()}")

    return "\n".join(
        [
            "Escribe un caption de Instagram en español para vender una obra de arte original.",
            "Debe sonar profesional, sobrio y cálido, como una galería presentando una obra a coleccionistas y compradores potenciales.",
            "Formato recomendado:",
            "1. Primera línea breve con título si existe, material/técnica y medidas separados por |. Si no hay título, empieza con material/técnica y medidas. NO escribas 'Sin título', 'Untitled' ni frases equivalentes.",
            "2. Segundo párrafo: indica de forma profesional que la obra está disponible para adquisición o venta e invita a consultar por interno. Usa 'contáctanos' o 'consultas por interno'; no uses 'escríbeme' ni 'DM'. Evita un tono demasiado informal.",
            "3. Última línea: 12 a 18 hashtags establecidos y con buen alcance para arte original, decoración, coleccionismo y venta de arte. Mezcla español e inglés cuando ayude al alcance.",
            "Evita hashtags demasiado específicos del tema de la imagen salvo que las notas lo indiquen claramente.",
            "Evita sonar exagerado, urgente o demasiado promocional. No uses comillas alrededor del caption. Devuelve solo el caption final.",
            f"Número de imágenes del carrusel: {image_count}",
            "Datos de la obra:",
            "\n".join(details),
        ]
    )


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
