import json
import os
import subprocess
from pathlib import Path

from redis import Redis

from .celery_app import celery_app


INPUT_DIR = Path("/data/input")
OUTPUT_DIR = Path("/data/output")

REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://redis:6379/0",
)

redis_client = Redis.from_url(
    REDIS_URL,
    decode_responses=True,
)


ALLOWED_FORMATS = {
    "mp4": {
        "extension": "mp4",
        "video_codec": "libx264",
        "audio_codec": "aac",
    },
    "webm": {
        "extension": "webm",
        "video_codec": "libvpx-vp9",
        "audio_codec": "libopus",
    },
    "mkv": {
        "extension": "mkv",
        "video_codec": "libx264",
        "audio_codec": "aac",
    },
}


ALLOWED_PRESETS = {
    "1080p": {
        "width": 1920,
        "height": 1080,
        "video_codec": "libx264",
    },
    "720p": {
        "width": 1280,
        "height": 720,
        "video_codec": "libx264",
    },
    "720p_hevc": {
        "width": 1280,
        "height": 720,
        "video_codec": "libx265",
    },
}


ALLOWED_QUALITY = {
    "low": "28",
    "medium": "23",
    "high": "18",
}


def get_duration(path: Path) -> float:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        return 0

    try:
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])

    except (
        KeyError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ):
        return 0

@celery_app.task(
    bind=True,
    name="video.convert",
    acks_late=True,
)
def convert_video(
    self,
    job_id: str,
    input_path: str,
    output_path: str,
    output_format: str,
    quality: str,
    preset: str = "1080p",
):
    input_file = Path(input_path)
    output_file = Path(output_path)

    cancel_key = f"video:cancel:{job_id}"

    if redis_client.get(cancel_key):
        redis_client.delete(cancel_key)
        return {
            "job_id": job_id,
            "status": "cancelled",
            "progress": 0,
}

    if output_format not in ALLOWED_FORMATS:
        raise ValueError("Unsupported output format")

    if quality not in ALLOWED_QUALITY:
        raise ValueError("Unsupported quality")

    if preset not in ALLOWED_PRESETS:
        raise ValueError("Unsupported preset")


    format_config = ALLOWED_FORMATS[output_format]
    preset_config = ALLOWED_PRESETS[preset]

    crf = ALLOWED_QUALITY[quality]

    duration = get_duration(input_file)

    # The output container determines the compatible video codec.
    # WebM uses VP9; MP4 and MKV use the codec from the selected preset.
    if output_format == "webm":
        video_codec = "libvpx-vp9"
    else:
        video_codec = preset_config["video_codec"]

    command = [
        "ffmpeg",

        "-y",

        "-i",
        str(input_file),

      "-vf",
(
    f"scale={preset_config['width']}:{preset_config['height']}:"
    "force_original_aspect_ratio=decrease,"
    f"pad={preset_config['width']}:{preset_config['height']}:"
    "(ow-iw)/2:(oh-ih)/2"
),

        "-c:v",
        video_codec,

        "-crf",
        crf,

        "-preset",
        "veryfast",

        "-c:a",
        format_config["audio_codec"],

        "-progress",
        "pipe:1",

        "-nostats",

        str(output_file),
    ]

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    try:
        for line in process.stdout:
            line = line.strip()
            if redis_client.get(cancel_key):
                redis_client.delete(cancel_key)

                if process.poll() is None:
                    process.terminate()

                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()

                output_file.unlink(
                    missing_ok=True
                )

                input_file.unlink(
                    missing_ok=True
                )

                return {
                    "job_id": job_id,
                    "status": "cancelled",
                    "progress": 0,
                }

            if "=" not in line:
                continue

            key, value = line.split("=", 1)

            if key != "out_time_ms":
                continue

            try:
                current_time = int(value) / 1_000_000

                if duration > 0:
                    progress = int(
                        (current_time / duration) * 100
                    )

                    progress = max(
                        0,
                        min(99, progress),
                    )

                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "job_id": job_id,
                            "progress": progress,
                            "status": "processing",
                        },
                    )

            except ValueError:
                pass

        _, stderr = process.communicate()

        if process.returncode != 0:
            raise RuntimeError(stderr[-5000:])

        self.update_state(
            state="PROGRESS",
            meta={
                "job_id": job_id,
                "progress": 100,
                "status": "completed",
            },
        )

        return {
            "job_id": job_id,
            "status": "completed",
            "progress": 100,
            "output": output_file.name,
        }

    except Exception:
        if process.poll() is None:
            process.kill()

        raise