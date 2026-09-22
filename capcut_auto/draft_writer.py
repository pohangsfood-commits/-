"""pycapcut을 이용해 컷 편집 + 자막이 반영된 CapCut draft를 생성한다."""

from __future__ import annotations

from pathlib import Path

from .cutlist import KeepSegment


def _sec(t: float) -> str:
    return f"{max(t, 0.0):.3f}s"


def write_capcut_draft(
    video_path: str,
    keep_segments: list[KeepSegment],
    srt_path: str | None,
    drafts_dir: str,
    draft_name: str,
    *,
    width: int,
    height: int,
    fps: int = 30,
    allow_replace: bool = False,
) -> str:
    """CapCut draft를 생성하고 저장한다. 생성된 draft 폴더 경로를 반환한다."""
    import pycapcut as cc
    from pycapcut import trange

    if not keep_segments:
        raise ValueError("남길 구간이 없습니다 (영상 전체가 컷 대상으로 판정됨) — 임계값을 조정해주세요.")

    Path(drafts_dir).mkdir(parents=True, exist_ok=True)
    draft_folder = cc.DraftFolder(str(drafts_dir))
    script = draft_folder.create_draft(draft_name, width, height, fps, allow_replace=allow_replace)

    script.add_track(cc.TrackType.video)

    cumulative = 0.0
    for seg in keep_segments:
        duration = seg.duration
        if duration <= 0:
            continue
        video_segment = cc.VideoSegment(
            video_path,
            trange(_sec(cumulative), _sec(duration)),
            source_timerange=trange(_sec(seg.start), _sec(duration)),
        )
        script.add_segment(video_segment)
        cumulative += duration

    if srt_path:
        script.import_srt(
            srt_path,
            track_name="subtitle",
            text_style=cc.TextStyle(size=8.0, color=(1.0, 1.0, 1.0), align=1, auto_wrapping=True),
        )

    script.save()
    return str(Path(drafts_dir) / draft_name)
