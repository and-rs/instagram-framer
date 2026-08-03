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

from app.captioning import CaptionGenerationError, generate_caption, generate_collection_names
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
        name="index.jinja",
        context={
            "active_page": "home",
            "max_upload_mb": settings.max_upload_mb,
            "max_upload_count": settings.max_upload_count,
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/process", response_class=HTMLResponse)
async def process(
    request: Request,
    images: Annotated[list[UploadFile], File()],
    title: Annotated[str | None, Form()] = None,
    artwork_number: Annotated[str | None, Form()] = None,
    collection_name: Annotated[str | None, Form()] = None,
    collection_description: Annotated[str | None, Form()] = None,
    reference_index: Annotated[int | None, Form()] = None,
    material: Annotated[str | None, Form()] = None,
    size: Annotated[str | None, Form()] = None,
    notes: Annotated[str | None, Form()] = None,
):
    cleanup_expired_jobs()

    material = (material or "").strip()
    size = (size or "").strip()
    artwork_number = (artwork_number or "").strip()
    collection_name = (collection_name or "").strip()
    collection_description = (collection_description or "").strip()

    if not images:
        return _result(request, error="Sube al menos una imagen.")
    if len(images) > settings.max_upload_count:
        return _result(request, error=f"Sube máximo {settings.max_upload_count} imágenes.")
    if not material:
        return _result(request, error="Indica la técnica o material de la obra.")
    if not size:
        return _result(request, error="Indica las medidas de la obra.")
    if not artwork_number:
        return _result(request, error="Indica el número de la obra.")
    if reference_index is None or not 1 <= reference_index <= len(images):
        return _result(request, error="Elige la imagen de referencia de la obra.")
    if not collection_name and not collection_description:
        return _result(request, error="Describe brevemente la colección para generar nombres.")

    job_id = uuid4().hex
    job_dir = settings.generated_dir / job_id
    filenames: list[str] = []
    reference_data: bytes | None = None
    reference_media_type = "image/jpeg"

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
            if index == reference_index:
                reference_data = data
                reference_media_type = upload.content_type or reference_media_type
    except ImageProcessingError as exc:
        shutil.rmtree(job_dir, ignore_errors=True)
        return _result(request, error=str(exc))

    jobs[job_id] = {
        "filenames": filenames,
        "created": time.time(),
        "metadata": {
            "title": title,
            "material": material,
            "size": size,
            "notes": notes,
            "artwork_number": artwork_number,
            "collection_description": collection_description or None,
        },
        "reference_path": job_dir / "reference-upload",
        "reference_media_type": reference_media_type,
        "collection_options": [],
    }
    assert reference_data is not None
    (job_dir / "reference-upload").write_bytes(reference_data)

    if not collection_name:
        try:
            options, warning = await generate_collection_names(
                image_data=reference_data,
                media_type=reference_media_type,
                collection_description=collection_description,
                previous_names=[],
            )
        except CaptionGenerationError as exc:
            shutil.rmtree(job_dir, ignore_errors=True)
            jobs.pop(job_id, None)
            return _result(request, error=f"No se pudieron generar nombres de colección. Detalle: {exc}")
        jobs[job_id]["collection_options"] = options
        return _collection_review(request, job_id=job_id, options=options, warning=warning)

    try:
        caption, description, warning = await _generate_final_caption(job_id, collection_name)
    except CaptionGenerationError as exc:
        shutil.rmtree(job_dir, ignore_errors=True)
        jobs.pop(job_id, None)
        return _result(request, error=f"No se pudo generar el caption con OpenAI. Detalle: {exc}")

    return _result(
        request,
        job_id=job_id,
        filenames=filenames,
        caption=caption,
        description=description,
        warning=warning,
    )


@app.post("/process/{job_id}/collection-options", response_class=HTMLResponse)
async def more_collection_options(request: Request, job_id: str):
    job = _job_or_404(job_id)
    metadata = job["metadata"]
    try:
        options, warning = await generate_collection_names(
            image_data=Path(job["reference_path"]).read_bytes(),
            media_type=job["reference_media_type"],
            collection_description=metadata["collection_description"],
            previous_names=job["collection_options"],
        )
    except CaptionGenerationError as exc:
        return templates.TemplateResponse(
            request=request,
            name="partials/collection_options.jinja",
            context={"options": [], "warning": f"No se pudieron generar más opciones. Detalle: {exc}"},
        )
    job["collection_options"].extend(options)
    return templates.TemplateResponse(
        request=request,
        name="partials/collection_options.jinja",
        context={"options": options, "warning": warning},
    )


@app.post("/process/{job_id}/finalize", response_class=HTMLResponse)
async def finalize(request: Request, job_id: str, collection_name: Annotated[str | None, Form()] = None):
    job = _job_or_404(job_id)
    collection_name = (collection_name or "").strip()
    if collection_name not in job["collection_options"]:
        return _collection_review(
            request,
            job_id=job_id,
            options=job["collection_options"],
            error="Elige uno de los nombres de colección propuestos.",
        )

    try:
        caption, description, warning = await _generate_final_caption(job_id, collection_name)
    except CaptionGenerationError as exc:
        return _collection_review(
            request,
            job_id=job_id,
            options=job["collection_options"],
            error=f"No se pudo generar el caption con OpenAI. Detalle: {exc}",
        )
    return _result(
        request,
        job_id=job_id,
        filenames=job["filenames"],
        caption=caption,
        description=description,
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
    description: str = "",
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
        name="partials/result.jinja",
        context={
            "job_id": job_id or "",
            "images": image_items,
            "caption": caption,
            "description": description,
            "warning": warning,
            "error": error,
            "download_all_url": request.url_for("download_all", job_id=job_id) if job_id and filenames else None,
        },
    )


def _collection_review(
    request: Request,
    *,
    job_id: str,
    options: list[str],
    warning: str | None = None,
    error: str | None = None,
):
    return templates.TemplateResponse(
        request=request,
        name="partials/collection_review.jinja",
        context={
            "job_id": job_id,
            "options": options,
            "warning": warning,
            "error": error,
        },
    )


async def _generate_final_caption(job_id: str, collection_name: str) -> tuple[str, str, str | None]:
    job = _job_or_404(job_id)
    metadata = job["metadata"]
    caption, description, warning = await generate_caption(
        title=metadata["title"],
        material=metadata["material"],
        size=metadata["size"],
        notes=metadata["notes"],
        image_count=len(job["filenames"]),
        collection_name=collection_name,
        artwork_number=metadata["artwork_number"],
        collection_description=metadata["collection_description"],
        image_data=Path(job["reference_path"]).read_bytes(),
        media_type=job["reference_media_type"],
    )
    job["caption"] = caption
    job["description"] = description
    metadata["collection_name"] = collection_name
    return caption, description, warning


def _job_or_404(job_id: str) -> dict:
    if not _safe_job_id(job_id):
        raise HTTPException(status_code=404)
    job = jobs.get(job_id)
    if not job or not Path(job["reference_path"]).is_file():
        raise HTTPException(status_code=404)
    return job


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
