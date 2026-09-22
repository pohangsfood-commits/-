"""ffmpeg를 이용한 오디오 추출 및 무음 구간 탐지."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class FfmpegNotFoundError(RuntimeError):
    pass


def _require_ffmpeg(binary: str) -> None:
    if shutil.which(binary) is None:
        raise FfmpegNotFoundError(
            f"'{binary}'를 찾을 수 없습니다. ffmpeg를 설치하고 PATH에 등록해주세요: "
            "https://ffmpeg.org/download.html"
        )


def probe_duration(video_path: str) -> float:
    """ffprobe로 영상 길이(초)를 가져온다."""
    _require_ffmpeg("ffprobe")
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def probe_video_info(video_path: str) -> tuple[int, int, float]:
    """ffprobe로 (width, height, fps)를 가져온다."""
    _require_ffmpeg("ffprobe")
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate",
            "-of", "default=noprint_wrappers=1",
            video_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    info: dict[str, str] = {}
    for line in result.stdout.strip().splitlines():
        key, _, value = line.partition("=")
        info[key] = value

    width = int(info.get("width", "1920"))
    height = int(info.get("height", "1080"))

    fps_raw = info.get("r_frame_rate", "30/1")
    if "/" in fps_raw:
        num, den = fps_raw.split("/")
        fps = float(num) / float(den) if float(den) != 0 else 30.0
    else:
        fps = float(fps_raw)

    return width, height, fps


def extract_audio(video_path: str, out_wav_path: str, *, sample_rate: int = 16000) -> str:
    """Whisper 입력용으로 16kHz mono WAV를 추출한다."""
    _require_ffmpeg("ffmpeg")
    Path(out_wav_path).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vn",
            "-ac", "1",
            "-ar", str(sample_rate),
            "-acodec", "pcm_s16le",
            out_wav_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return out_wav_path


@dataclass
class SilenceInterval:
    start: float
    end: float


_SILENCE_START_RE = re.compile(r"silence_start:\s*(-?[\d.]+)")
_SILENCE_END_RE = re.compile(r"silence_end:\s*(-?[\d.]+)")


def detect_silence(
    audio_path: str,
    *,
    noise_db: float = -30.0,
    min_duration: float = 0.7,
    total_duration: float | None = None,
) -> list[SilenceInterval]:
    """ffmpeg의 silencedetect 필터로 무음 구간을 찾는다."""
    _require_ffmpeg("ffmpeg")
    filt = f"silencedetect=noise={noise_db}dB:d={min_duration}"
    result = subprocess.run(
        ["ffmpeg", "-i", audio_path, "-af", filt, "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    log = result.stderr

    intervals: list[SilenceInterval] = []
    pending_start: float | None = None
    for line in log.splitlines():
        start_match = _SILENCE_START_RE.search(line)
        if start_match:
            pending_start = float(start_match.group(1))
            continue
        end_match = _SILENCE_END_RE.search(line)
        if end_match and pending_start is not None:
            intervals.append(SilenceInterval(pending_start, float(end_match.group(1))))
            pending_start = None

    # 파일이 무음으로 끝나면 silence_end 로그가 없을 수 있으므로 duration으로 마무리
    if pending_start is not None and total_duration is not None:
        intervals.append(SilenceInterval(pending_start, total_duration))

    return intervals
