"""웹 UI에서 쓰는 작업(Job) 상태 관리 + 백그라운드 파이프라인 실행.

핵심 로직(무음/버벅임 탐지, 컷 병합, 타임라인 리매핑, draft 생성)은 전부
capcut_auto의 기존 모듈을 그대로 재사용한다. 이 파일은 그 위에 "진행 상태를
Job 객체에 기록하며 백그라운드 스레드에서 실행"하는 오케스트레이션만 담당한다.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .. import audio, draft_writer, report, stutter, subtitles, transcribe
from ..config import Config
from ..cutlist import CutRegion, build_cut_regions, build_keep_segments
from ..drafts_dir import default_drafts_dir
from ..remap import TimelineMapper
from ..transcribe import Word

DATA_DIR = Path.home() / ".capcut_auto" / "webapp" / "jobs"


@dataclass
class Job:
    id: str
    work_dir: Path
    video_path: str
    original_filename: str
    status: str = "uploaded"  # uploaded -> analyzing -> analyzed -> building -> done / error
    progress: str = ""
    logs: list[str] = field(default_factory=list)
    error: str | None = None

    duration: float | None = None
    cuts: list[dict] | None = None
    keep_stats: dict | None = None
    report_md: str | None = None
    preview_srt: str | None = None

    draft_result: dict | None = None
    config: Config = field(default_factory=Config)

    def log(self, message: str) -> None:
        self.logs.append(message)
        self.progress = message

    def to_status_dict(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "progress": self.progress,
            "logs": self.logs,
            "error": self.error,
            "original_filename": self.original_filename,
            "duration": self.duration,
            "cuts": self.cuts,
            "keep_stats": self.keep_stats,
            "report_md": self.report_md,
            "preview_srt": self.preview_srt,
            "draft_result": self.draft_result,
        }


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create_job(self, upload_stream, original_filename: str) -> Job:
        job_id = uuid.uuid4().hex[:12]
        work_dir = DATA_DIR / job_id
        work_dir.mkdir(parents=True, exist_ok=True)

        suffix = Path(original_filename).suffix or ".mp4"
        video_path = work_dir / f"source{suffix}"
        with open(video_path, "wb") as f:
            while True:
                chunk = upload_stream.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)

        job = Job(id=job_id, work_dir=work_dir, video_path=str(video_path), original_filename=original_filename)
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def start_analyze(self, job: Job, config: Config) -> None:
        job.status = "analyzing"
        job.error = None
        job.config = config
        thread = threading.Thread(target=_run_analyze, args=(job, config), daemon=True)
        thread.start()

    def start_build(self, job: Job, draft_name: str, drafts_dir: str | None, allow_replace: bool) -> None:
        job.status = "building"
        job.error = None
        thread = threading.Thread(target=_run_build, args=(job, draft_name, drafts_dir, allow_replace), daemon=True)
        thread.start()

    def update_cutlist(self, job: Job, cuts: list[dict]) -> None:
        cut_regions = [CutRegion.from_dict(c) for c in cuts]
        (job.work_dir / "cutlist.json").write_text(
            json.dumps([c.to_dict() for c in cut_regions], ensure_ascii=False, indent=2), encoding="utf-8"
        )
        job.cuts = [c.to_dict() for c in cut_regions]
        job.keep_stats = _keep_stats(cut_regions, job.duration, job.config)


def _keep_stats(cuts: list[CutRegion], duration: float, config: Config) -> dict:
    keeps = build_keep_segments(cuts, duration, config)
    keep_total = sum(k.duration for k in keeps)
    return {
        "keep_segment_count": len(keeps),
        "keep_total": round(keep_total, 2),
        "cut_total": round(duration - keep_total, 2),
        "duration": round(duration, 2),
    }


def _run_analyze(job: Job, config: Config) -> None:
    try:
        job.log("영상 정보 확인 중...")
        duration = audio.probe_duration(job.video_path)
        job.duration = duration

        job.log("오디오 추출 중...")
        wav_path = str(job.work_dir / "audio.wav")
        audio.extract_audio(job.video_path, wav_path)

        job.log("무음 구간 탐지 중...")
        silence = audio.detect_silence(
            wav_path,
            noise_db=config.silence_noise_db,
            min_duration=config.min_silence,
            total_duration=duration,
        )
        job.log(f"무음 구간 {len(silence)}개 발견")

        job.log(f"한국어 음성 인식 중... (모델: {config.whisper_model}) — 영상 길이에 따라 시간이 걸릴 수 있습니다")
        words = transcribe.transcribe(
            wav_path,
            model_size=config.whisper_model,
            device=config.whisper_device,
            language=config.whisper_language,
        )
        job.log(f"단어 {len(words)}개 인식 완료")

        job.log("버벅임(반복/머뭇거림) 탐지 중...")
        stutter_candidates = stutter.find_stutters(words, config)
        job.log(f"버벅임 후보 {len(stutter_candidates)}개 발견")

        cuts = build_cut_regions(silence, stutter_candidates, duration, config)
        job.log(f"컷 리스트 {len(cuts)}개 구간으로 병합 완료")

        (job.work_dir / "meta.json").write_text(
            json.dumps({"video": job.video_path, "duration": duration}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (job.work_dir / "transcript.json").write_text(
            json.dumps([w.to_dict() for w in words], ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (job.work_dir / "cutlist.json").write_text(
            json.dumps([c.to_dict() for c in cuts], ensure_ascii=False, indent=2), encoding="utf-8"
        )

        preview_cues = subtitles.words_to_cues(words, config, mapper=None)
        srt_path = str(job.work_dir / "preview.srt")
        subtitles.write_srt(preview_cues, srt_path)
        job.preview_srt = Path(srt_path).read_text(encoding="utf-8")

        keeps = build_keep_segments(cuts, duration, config)
        job.report_md = report.build_report(video_path=job.original_filename, duration=duration, cuts=cuts, keeps=keeps)
        job.cuts = [c.to_dict() for c in cuts]
        job.keep_stats = _keep_stats(cuts, duration, config)

        job.status = "analyzed"
        job.log("분석 완료 — 컷 리스트를 검토한 뒤 draft를 생성하세요.")
    except Exception as exc:  # noqa: BLE001 - 백그라운드 작업 실패를 사용자에게 보여줘야 함
        job.status = "error"
        job.error = str(exc)
        job.log(f"오류 발생: {exc}")


def _run_build(job: Job, draft_name: str, drafts_dir: str | None, allow_replace: bool) -> None:
    try:
        meta = json.loads((job.work_dir / "meta.json").read_text(encoding="utf-8"))
        duration = meta["duration"]
        words = [Word(**w) for w in json.loads((job.work_dir / "transcript.json").read_text(encoding="utf-8"))]
        cuts = [CutRegion.from_dict(c) for c in json.loads((job.work_dir / "cutlist.json").read_text(encoding="utf-8"))]

        config = job.config
        keeps = build_keep_segments(cuts, duration, config)
        if not keeps:
            raise ValueError("남는 구간이 없습니다. 컷 리스트를 조정해주세요.")

        job.log("자막 재동기화 중...")
        mapper = TimelineMapper(keeps)
        cues = subtitles.words_to_cues(words, config, mapper=mapper)
        srt_path = str(job.work_dir / "final.srt")
        subtitles.write_srt(cues, srt_path)

        resolved_dir = drafts_dir or (str(default_drafts_dir()) if default_drafts_dir() else None)
        if not resolved_dir:
            raise ValueError("CapCut draft 폴더를 찾지 못했습니다. 경로를 직접 입력해주세요.")

        job.log("영상 정보 확인 중...")
        width, height, fps = audio.probe_video_info(job.video_path)

        job.log(f"CapCut draft 생성 중... ({resolved_dir}/{draft_name})")
        result_path = draft_writer.write_capcut_draft(
            job.video_path,
            keeps,
            srt_path,
            resolved_dir,
            draft_name,
            width=width,
            height=height,
            fps=round(fps),
            allow_replace=allow_replace,
        )

        job.draft_result = {"path": result_path, "draft_name": draft_name, "drafts_dir": resolved_dir}
        job.status = "done"
        job.log(f"완료! CapCut에서 '{draft_name}' 프로젝트를 여세요.")
    except Exception as exc:  # noqa: BLE001
        job.status = "error"
        job.error = str(exc)
        job.log(f"오류 발생: {exc}")


manager = JobManager()
