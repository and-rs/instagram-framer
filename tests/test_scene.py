import re

import httpx
import pytest

from app.main import app
from app.scene import SCENE_RECIPE, SceneStage


def test_scene_recipe_is_full_bleed_square_output():
    assert SCENE_RECIPE.output_size == (2000, 2000)
    assert SCENE_RECIPE.full_bleed is True
    assert SCENE_RECIPE.stages == (
        SceneStage.ORIENT,
        SceneStage.DETECT_PAINTING,
        SceneStage.STRAIGHTEN,
        SceneStage.COMPOSE,
        SceneStage.ADJUST,
        SceneStage.EXPORT,
    )


@pytest.mark.anyio
async def test_pages_render_with_active_navigation():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        home_response = await client.get("/")
        scene_response = await client.get("/scene")

    assert home_response.status_code == 200
    assert re.search(r'href="/"\s+aria-current="page"', home_response.text)
    assert scene_response.status_code == 200
    assert "Flujo previsto" in scene_response.text
    assert re.search(r'href="/scene"\s+aria-current="page"', scene_response.text)
