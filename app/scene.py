from dataclasses import dataclass
from enum import StrEnum

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import settings


templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/scene", tags=["scene"])


class SceneStage(StrEnum):
    ORIENT = "orient"
    DETECT_PAINTING = "detect_painting"
    STRAIGHTEN = "straighten"
    COMPOSE = "compose"
    ADJUST = "adjust"
    EXPORT = "export"


@dataclass(frozen=True)
class SceneRecipe:
    stages: tuple[SceneStage, ...] = (
        SceneStage.ORIENT,
        SceneStage.DETECT_PAINTING,
        SceneStage.STRAIGHTEN,
        SceneStage.COMPOSE,
        SceneStage.ADJUST,
        SceneStage.EXPORT,
    )
    output_size: tuple[int, int] = (2000, 2000)
    full_bleed: bool = True


SCENE_RECIPE = SceneRecipe()


@router.get("", response_class=HTMLResponse)
async def scene_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="scene/index.jinja",
        context={
            "active_page": "scene",
            "max_upload_mb": settings.max_upload_mb,
            "recipe": SCENE_RECIPE,
        },
    )
