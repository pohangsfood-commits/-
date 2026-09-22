"""단어 목록을 자막 줄(cue)로 묶고 SRT로 저장한다."""

from __future__ import annotations

from dataclasses import dataclass

from .config import Config
from .remap import TimelineMapper
from .transcribe import Word

_SENTENCE_END = (".", "!", "?", "다", "요", "죠", "네", "됨")
_BREAK_GAP = 0.4  # 새 타임라인 기준, 이 이상 벌어지면 자연스러운 줄바꿈 지점으로 취급


@dataclass
class Cue:
    text: str
    start: float
    end: float

    def to_dict(self) -> dict:
        return {"text": self.text, "start": round(self.start, 3), "end": round(self.end, 3)}


def words_to_cues(words: list[Word], config: Config, mapper: TimelineMapper | None = None) -> list[Cue]:
    """단어들을 화면에 표시할 자막 줄들로 묶는다.

    mapper가 주어지면 컷 편집된 새 타임라인 기준으로, 없으면 원본 타임라인 기준으로 매핑한다.
    """
    mapped: list[tuple[str, float, float]] = []
    for w in words:
        if mapper is None:
            mapped.append((w.text, w.start, w.end))
        else:
            r = mapper.map_range(w.start, w.end)
            if r is not None:
                mapped.append((w.text, r[0], r[1]))

    cues: list[Cue] = []
    cur_texts: list[str] = []
    cur_start: float | None = None
    cur_end: float | None = None

    def flush():
        nonlocal cur_texts, cur_start, cur_end
        if cur_texts and cur_start is not None and cur_end is not None:
            cues.append(Cue(text=" ".join(cur_texts), start=cur_start, end=cur_end))
        cur_texts, cur_start, cur_end = [], None, None

    for text, start, end in mapped:
        if cur_start is None:
            cur_start, cur_end = start, end
            cur_texts = [text]
            continue

        candidate_text = " ".join(cur_texts + [text])
        gap = start - cur_end
        too_long_chars = len(candidate_text) > config.max_chars
        too_long_time = (end - cur_start) > config.max_line_seconds
        big_gap = gap > _BREAK_GAP

        if too_long_chars or too_long_time or big_gap:
            flush()
            cur_start, cur_end = start, end
            cur_texts = [text]
            continue

        cur_texts.append(text)
        cur_end = end

        if cur_texts[-1].endswith(_SENTENCE_END):
            flush()

    flush()
    return cues


def _srt_timestamp(t: float) -> str:
    if t < 0:
        t = 0.0
    ms = round(t * 1000)
    hh, ms = divmod(ms, 3600_000)
    mm, ms = divmod(ms, 60_000)
    ss, ms = divmod(ms, 1000)
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"


def write_srt(cues: list[Cue], out_path: str) -> str:
    lines = []
    for i, cue in enumerate(cues, start=1):
        lines.append(str(i))
        lines.append(f"{_srt_timestamp(cue.start)} --> {_srt_timestamp(cue.end)}")
        lines.append(cue.text)
        lines.append("")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return out_path
