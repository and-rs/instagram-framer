import httpx

from app.config import settings


class InstagramError(RuntimeError):
    pass


async def publish_carousel(image_urls: list[str], caption: str) -> dict[str, str]:
    if not settings.instagram_access_token or not settings.instagram_user_id:
        raise InstagramError("Las credenciales de Instagram no están configuradas.")
    if not image_urls:
        raise InstagramError("No hay imágenes disponibles para publicar.")

    base_url = f"https://graph.facebook.com/{settings.graph_api_version}"
    token = settings.instagram_access_token
    user_id = settings.instagram_user_id

    async with httpx.AsyncClient(timeout=90) as client:
        if len(image_urls) == 1:
            creation_id = await _create_single_container(client, base_url, user_id, token, image_urls[0], caption)
        else:
            creation_id = await _create_carousel_container(client, base_url, user_id, token, image_urls, caption)

        response = await client.post(
            f"{base_url}/{user_id}/media_publish",
            data={"creation_id": creation_id, "access_token": token},
        )
        published = _checked_payload(response)
        media_id = published.get("id")
        if not media_id:
            raise InstagramError("Instagram no devolvió un ID de publicación.")

        return await _publication_result(client, base_url, token, str(media_id))


async def _create_single_container(
    client: httpx.AsyncClient,
    base_url: str,
    user_id: str,
    token: str,
    image_url: str,
    caption: str,
) -> str:
    response = await client.post(
        f"{base_url}/{user_id}/media",
        data={"image_url": image_url, "caption": caption, "access_token": token},
    )
    payload = _checked_payload(response)
    creation_id = payload.get("id")
    if not creation_id:
        raise InstagramError("Instagram no devolvió un ID de contenedor de imagen.")
    return str(creation_id)


async def _create_carousel_container(
    client: httpx.AsyncClient,
    base_url: str,
    user_id: str,
    token: str,
    image_urls: list[str],
    caption: str,
) -> str:
    child_ids: list[str] = []
    for image_url in image_urls:
        response = await client.post(
            f"{base_url}/{user_id}/media",
            data={"image_url": image_url, "is_carousel_item": "true", "access_token": token},
        )
        payload = _checked_payload(response)
        child_id = payload.get("id")
        if not child_id:
            raise InstagramError("Instagram no devolvió un ID de contenedor de imagen.")
        child_ids.append(str(child_id))

    response = await client.post(
        f"{base_url}/{user_id}/media",
        data={
            "media_type": "CAROUSEL",
            "children": ",".join(child_ids),
            "caption": caption,
            "access_token": token,
        },
    )
    payload = _checked_payload(response)
    creation_id = payload.get("id")
    if not creation_id:
        raise InstagramError("Instagram no devolvió un ID de contenedor de carrusel.")
    return str(creation_id)


async def _publication_result(client: httpx.AsyncClient, base_url: str, token: str, media_id: str) -> dict[str, str]:
    result = {"id": media_id}
    response = await client.get(
        f"{base_url}/{media_id}",
        params={"fields": "permalink", "access_token": token},
    )
    if response.is_success:
        permalink = response.json().get("permalink")
        if permalink:
            result["permalink"] = str(permalink)
    return result


def _checked_payload(response: httpx.Response) -> dict:
    try:
        payload = response.json()
    except ValueError as exc:
        raise InstagramError("Instagram devolvió una respuesta inválida.") from exc

    if response.is_error or "error" in payload:
        error = payload.get("error", {})
        message = error.get("message") or "La solicitud a la API de Instagram falló."
        raise InstagramError(message)
    return payload
