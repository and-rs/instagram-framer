import shutil
import time
from io import BytesIO
from pathlib import Path
from typing import Annotated
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.captioning import generate_caption
from app.config import settings
from app.image_processing import ImageProcessingError, frame_image_bytes

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="app/templates")

jobs: dict[str, dict] = {}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"max_upload_mb": settings.max_upload_mb, "max_upload_count": settings.max_upload_count},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/process", response_class=HTMLResponse)
async def process(
    request: Request,
    images: Annotated[list[UploadFile], File()],
    title: Annotated[str | None, Form()] = None,
    material: Annotated[str | None, Form()] = None,
    size: Annotated[str | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
):
    cleanup_expired_jobs()

    material = (material or "").strip()
    size = (size or "").strip()

    if not images:
        return _result(request, error="Sube al menos una imagen.")
    if len(images) > settings.max_upload_count:
        return _result(request, error=f"Sube máximo {settings.max_upload_count} imágenes.")
    if not material:
        return _result(request, error="Indica la técnica o material de la obra.")
    if not size:
        return _result(request, error="Indica las medidas de la obra.")

    job_id = uuid4().hex
    job_dir = settings.generated_dir / job_id
    filenames: list[str] = []

    try:
        for index, upload in enumerate(images, start=1):
            if upload.content_type and not upload.content_type.startswith("image/"):
                raise ImageProcessingError(f"{upload.filename or 'Archivo'} no es una imagen.")

            data = await upload.read()
            max_bytes = settings.max_upload_mb * 1024 * 1024
            if len(data) > max_bytes:
                raise ImageProcessingError(f"{upload.filename or 'Archivo'} supera {settings.max_upload_mb} MB.")

            filename = f"image_{index:03}.jpg"
            frame_image_bytes(data, job_dir / filename)
            filenames.append(filename)
    except ImageProcessingError as exc:
        shutil.rmtree(job_dir, ignore_errors=True)
        return _result(request, error=str(exc))

    caption, warning = await generate_caption(
        title=title,
        material=material,
        size=size,
        notes=notes,
        image_count=len(filenames),
    )

    jobs[job_id] = {
        "filenames": filenames,
        "caption": caption,
        "created": time.time(),
        "metadata": {"title": title, "material": material, "size": size, "notes": notes},
    }

    return _result(
        request,
        job_id=job_id,
        filenames=filenames,
        caption=caption,
        warning=warning,
    )


@app.get("/generated/{job_id}/{filename}")
async def generated(job_id: str, filename: str):
    if not _safe_job_id(job_id) or not _safe_filename(filename):
        raise HTTPException(status_code=404)

    path = settings.generated_dir / job_id / filename
    if not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type="image/jpeg")


@app.get("/download/{job_id}/images/{filename}")
async def download_image(job_id: str, filename: str):
    path = _generated_image_path(job_id, filename)
    return FileResponse(path, media_type="image/jpeg", filename=filename)


@app.get("/download/{job_id}/all.zip")
async def download_all(job_id: str):
    if not _safe_job_id(job_id):
        raise HTTPException(status_code=404)

    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404)

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for filename in job["filenames"]:
            path = _generated_image_path(job_id, filename)
            archive.write(path, arcname=filename)
        archive.writestr("caption.txt", job["caption"])
    buffer.seek(0)

    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="framed-images-{job_id}.zip"'},
    )


def _result(
    request: Request,
    *,
    job_id: str | None = None,
    filenames: list[str] | None = None,
    caption: str = "",
    warning: str | None = None,
    error: str | None = None,
):
    image_items = []
    if job_id and filenames:
        image_items = [
            {
                "filename": filename,
                "url": request.url_for("generated", job_id=job_id, filename=filename),
                "download_url": request.url_for("download_image", job_id=job_id, filename=filename),
            }
            for filename in filenames
        ]
    return templates.TemplateResponse(
        request=request,
        name="partials/result.html",
        context={
            "job_id": job_id or "",
            "images": image_items,
            "caption": caption,
            "warning": warning,
            "error": error,
            "download_all_url": request.url_for("download_all", job_id=job_id) if job_id and filenames else None,
        },
    )


def _generated_image_path(job_id: str, filename: str) -> Path:
    if not _safe_job_id(job_id) or not _safe_filename(filename):
        raise HTTPException(status_code=404)

    path = settings.generated_dir / job_id / filename
    if not path.is_file():
        raise HTTPException(status_code=404)
    return path


def cleanup_expired_jobs() -> None:
    settings.generated_dir.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - settings.generated_ttl_seconds

    for job_id, job in list(jobs.items()):
        if job.get("created", 0) < cutoff:
            jobs.pop(job_id, None)
            shutil.rmtree(settings.generated_dir / job_id, ignore_errors=True)

    for path in settings.generated_dir.iterdir():
        if path.is_dir() and path.stat().st_mtime < cutoff:
            shutil.rmtree(path, ignore_errors=True)


def _safe_job_id(job_id: str) -> bool:
    return len(job_id) == 32 and all(char in "0123456789abcdef" for char in job_id)


def _safe_filename(filename: str) -> bool:
    return filename.startswith("image_") and filename.endswith(".jpg") and Path(filename).name == filename
