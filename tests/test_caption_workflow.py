import re

import httpx
import pytest

from app import main


@pytest.mark.anyio
async def test_upload_page_explains_reference_image_selection():
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert "Selecciona una o más imágenes arriba" in response.text
    assert "data-reference-options" in response.text


@pytest.mark.anyio
async def test_collection_selection_happens_before_caption_generation(monkeypatch, tmp_path):
    main.jobs.clear()
    monkeypatch.setattr(main.settings, "generated_dir", tmp_path)
    caption_calls = []

    def frame_image(data, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(data)
        return output_path

    async def collection_names(**kwargs):
        assert kwargs["image_data"] == b"reference"
        return ["Tierra Serena", "Luz Doméstica", "Materia Azul", "Casa Interior", "Ritmo Quieto"], None

    async def caption(**kwargs):
        caption_calls.append(kwargs)
        return "Caption final", "Descripción de la pintura.", None

    monkeypatch.setattr(main, "frame_image_bytes", frame_image)
    monkeypatch.setattr(main, "generate_collection_names", collection_names)
    monkeypatch.setattr(main, "generate_caption", caption)

    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/process",
            data={
                "artwork_number": "12",
                "collection_description": "interiores de luz tenue",
                "material": "óleo sobre tela",
                "size": "40 x 50 cm",
                "reference_index": "2",
            },
            files=[
                ("images", ("first.jpg", b"other", "image/jpeg")),
                ("images", ("second.jpg", b"reference", "image/jpeg")),
            ],
        )

        job_id = re.search(r"/process/([0-9a-f]{32})/finalize", response.text).group(1)
        assert response.status_code == 200
        assert "Tierra Serena" in response.text
        assert caption_calls == []

        finalized = await client.post(f"/process/{job_id}/finalize", data={"collection_name": "Tierra Serena"})

    assert finalized.status_code == 200
    assert "Caption final" in finalized.text
    assert "data-copy-caption" in finalized.text
    assert "data-caption-text" in finalized.text
    assert caption_calls[0]["collection_name"] == "Tierra Serena"
    assert caption_calls[0]["image_data"] == b"reference"
