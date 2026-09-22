"""분석 결과를 사람이 읽기 쉬운 마크다운 요약으로 만든다."""

from __future__ import annotations

from .cutlist import CutRegion, KeepSegment


def _fmt(t: float) -> str:
    m, s = divmod(max(t, 0.0), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{int(h):02d}:{int(m):02d}:{s:05.2f}"
    return f"{int(m):02d}:{s:05.2f}"


def build_report(
    *,
    video_path: str,
    duration: float,
    cuts: list[CutRegion],
    keeps: list[KeepSegment],
) -> str:
    cut_total = sum(c.end - c.start for c in cuts)
    keep_total = sum(k.duration for k in keeps)

    lines = [
        f"# 분석 결과: {video_path}",
        "",
        f"- 원본 길이: {_fmt(duration)}",
        f"- 컷 편집 후 길이: {_fmt(keep_total)} (약 {cut_total / duration * 100:.1f}% 잘려나감, {_fmt(cut_total)})",
        f"- 컷 구간 수: {len(cuts)}",
        "",
        "## 잘라낼 구간",
        "",
        "| # | 시작 | 끝 | 길이 | 이유 | 신뢰도 |",
        "|---|---|---|---|---|---|",
    ]
    for i, c in enumerate(cuts, start=1):
        lines.append(
            f"| {i} | {_fmt(c.start)} | {_fmt(c.end)} | {c.end - c.start:.2f}s | {', '.join(c.reasons)} | {c.confidence:.2f} |"
        )

    lines += [
        "",
        "## 남는 구간 (CapCut 타임라인에 순서대로 이어붙여집니다)",
        "",
        "| # | 원본 시작 | 원본 끝 | 길이 |",
        "|---|---|---|---|",
    ]
    for i, k in enumerate(keeps, start=1):
        lines.append(f"| {i} | {_fmt(k.start)} | {_fmt(k.end)} | {k.duration:.2f}s |")

    lines += [
        "",
        "> `cutlist.json`을 직접 수정한 뒤 `capcut_auto build`를 실행하면 수정한 내용이 반영됩니다.",
    ]
    return "\n".join(lines)
