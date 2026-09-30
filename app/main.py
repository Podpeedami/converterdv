import os
import re
import uuid

from redis import Redis

from pathlib import Path

from celery.result import AsyncResult

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .celery_app import celery_app

from .tasks import (
    ALLOWED_FORMATS,
    ALLOWED_PRESETS,
    ALLOWED_QUALITY,
    convert_video,
)


INPUT_DIR = Path("/data/input")
OUTPUT_DIR = Path("/data/output")

INPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

redis_client = Redis.from_url(
    os.getenv(
        "REDIS_URL",
        "redis://redis:6379/0",
    ),
    decode_responses=True,
)

def parse_size(value: str) -> int:
    value = value.strip().upper()

    units = {
        "B": 1,
        "K": 1024,
        "M": 1024 ** 2,
        "G": 1024 ** 3,
        "T": 1024 ** 4,
    }

    for suffix, multiplier in units.items():
        if value.endswith(suffix):
            number = float(value[:-1])
            return int(number * multiplier)

    return int(value)

MAX_UPLOAD_SIZE = parse_size(
    os.getenv(
        "MAX_UPLOAD_SIZE",
        "2G",
    )
)


app = FastAPI(
    title="Video Converter API",
    version="3.0.0",
)


app.mount(
    "/static",
    StaticFiles(
        directory="app/static"
    ),
    name="static",
)


def safe_filename(filename: str) -> str:
    filename = Path(filename).name

    filename = re.sub(
        r"[^a-zA-Z0-9а-яА-ЯёЁ._-]",
        "_",
        filename,
    )

    return filename[:200] or "video"


async def save_upload(
    upload: UploadFile,
    destination: Path,
):
    total = 0

    with destination.open("wb") as output:
        while True:
            chunk = await upload.read(
                1024 * 1024
            )

            if not chunk:
                break

            total += len(chunk)

            if total > MAX_UPLOAD_SIZE:
                destination.unlink(
                    missing_ok=True
                )

                raise HTTPException(
                    status_code=413,
                    detail="Файл слишком большой",
                )

            output.write(chunk)

    return total


@app.get("/")
async def index():
    return FileResponse(
        "app/static/index.html"
    )


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "video-converter",
    }

@app.get("/api/input-files")
async def get_input_files():
    files = []

    for path in INPUT_DIR.iterdir():
        if not path.is_file():
            continue

        files.append({
            "name": path.name,
            "size": path.stat().st_size,
        })

    return {
        "files": files,
    }

@app.post("/api/convert-existing")
async def convert_existing_file(
    filename: str = Form(...),
    output_format: str = Form("mp4"),
    quality: str = Form("medium"),
    preset: str = Form("1080p"),
):
    if output_format not in ALLOWED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail="Неподдерживаемый формат",
        )

    if quality not in ALLOWED_QUALITY:
        raise HTTPException(
            status_code=400,
            detail="Неподдерживаемое качество",
        )

    if preset not in ALLOWED_PRESETS:
        raise HTTPException(
            status_code=400,
            detail="Неподдерживаемое разрешение",
        )

    safe_name = Path(filename).name
    input_path = INPUT_DIR / safe_name

    if not input_path.exists() or not input_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Файл не найден",
        )

    job_id = str(uuid.uuid4())

    output_extension = ALLOWED_FORMATS[output_format]["extension"]

    output_name = (
        f"{Path(safe_name).stem}"
        f"_{preset}"
        f"_{job_id[:8]}."
        f"{output_extension}"
    )

    output_path = OUTPUT_DIR / output_name

    task = convert_video.apply_async(
        kwargs={
            "job_id": job_id,
            "input_path": str(input_path),
            "output_path": str(output_path),
            "output_format": output_format,
            "quality": quality,
            "preset": preset,
        },
        task_id=job_id,
    )

    return {
        "job_id": task.id,
        "status": "queued",
        "filename": safe_name,
        "size": input_path.stat().st_size,
        "preset": preset,
        "format": output_format,
    }

@app.post("/api/convert")
async def create_conversion(
    files: list[UploadFile] = File(...),

    output_format: str = Form(
        "mp4"
    ),

    quality: str = Form(
        "medium"
    ),

    preset: str = Form(
        "1080p"
    ),
):
    if output_format not in ALLOWED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail="Неподдерживаемый формат",
        )

    if quality not in ALLOWED_QUALITY:
        raise HTTPException(
            status_code=400,
            detail="Неподдерживаемое качество",
        )

    if preset not in ALLOWED_PRESETS:
        raise HTTPException(
            status_code=400,
            detail="Неподдерживаемое разрешение",
        )

    if not files:
        raise HTTPException(
            status_code=400,
            detail="Не выбраны файлы",
        )

    jobs = []

    for file in files:
        job_id = str(uuid.uuid4())

        original_name = safe_filename(
            file.filename or "video"
        )

        input_path = (
            INPUT_DIR
            / f"{job_id}_{original_name}"
        )

        output_extension = (
            ALLOWED_FORMATS[
                output_format
            ]["extension"]
        )

        output_name = (
            f"{Path(original_name).stem}"
            f"_{preset}"
            f"_{job_id[:8]}."
            f"{output_extension}"
        )

        output_path = (
            OUTPUT_DIR / output_name
        )

        file_size = await save_upload(
            file,
            input_path,
        )

        task = convert_video.apply_async(
            kwargs={
                "job_id": job_id,
                "input_path": str(input_path),
                "output_path": str(output_path),
                "output_format": output_format,
                "quality": quality,
                "preset": preset,
            },
            task_id=job_id,
        )

        jobs.append({
            "job_id": task.id,
            "status": "queued",
            "filename": original_name,
            "size": file_size,
            "preset": preset,
            "format": output_format,
        })

    return {
        "jobs": jobs,
    }

@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    task = AsyncResult(
        job_id,
        app=celery_app,
    )

    if task.state == "SUCCESS":
        raise HTTPException(
            status_code=409,
            detail="Перекодировка уже завершена",
        )

    if task.state == "FAILURE":
        raise HTTPException(
            status_code=409,
            detail="Перекодировка уже завершилась с ошибкой",
        )

    if task.state == "REVOKED":
        return {
            "job_id": job_id,
            "status": "cancelled",
        }

    redis_client.setex(
        f"video:cancel:{job_id}",
        3600,
        "1",
    )

    return {
        "job_id": job_id,
        "status": "cancelling",
    }



@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    task = AsyncResult(job_id, app=celery_app)

    if task.state == "PENDING":
        return {
            "job_id": job_id,
            "status": "queued",
            "progress": 0,
        }

    if task.state == "STARTED":
        return {
            "job_id": job_id,
            "status": "processing",
            "progress": 0,
        }

    if task.state == "PROGRESS":
        info = task.info or {}
        return {
            "job_id": job_id,
            "status": "processing",
            "progress": info.get("progress", 0),
        }

    if task.state == "SUCCESS":
        result = task.result

        if isinstance(result, dict) and result.get("status") == "cancelled":
            return {
                "job_id": job_id,
                "status": "cancelled",
                "progress": 0,
            }

        return {
            "job_id": job_id,
            "status": "completed",
            "progress": 100,
            "output": result["output"],
            "download_url": f"/api/download/{job_id}",
        }

    if task.state == "FAILURE":
        return {
            "job_id": job_id,
            "status": "error",
            "progress": 0,
            "error": str(task.result),
        }

    if task.state == "REVOKED":
        return {
            "job_id": job_id,
            "status": "cancelled",
            "progress": 0,
        }

    return {
        "job_id": job_id,
        "status": task.state.lower(),
        "progress": 0,
    }

@app.get("/api/download/{job_id}")
async def download_result(
    job_id: str,
):
    task = AsyncResult(
        job_id,
        app=celery_app,
    )

    if task.state != "SUCCESS":
        raise HTTPException(
            status_code=409,
            detail="Видео ещё не готово",
        )

    result = task.result

    output_name = result.get(
        "output"
    )

    if not output_name:
        raise HTTPException(
            status_code=404,
            detail="Результат не найден",
        )

    output_path = (
        OUTPUT_DIR / output_name
    )

    if not output_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Файл не найден",
        )

    return FileResponse(
        output_path,
        media_type={
            ".mp4": "video/mp4",
            ".webm": "video/webm",
            ".mkv": "video/x-matroska",
        }.get(
            output_path.suffix.lower(),
            "application/octet-stream",
        ),
        filename=output_path.name,
    )
