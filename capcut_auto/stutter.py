"""반복되는 단어(더듬는 구간)와 문장 중간의 비정상적인 머뭇거림을 탐지한다.

일부러 보수적으로 동작한다: 애매한 추임새("음", "어", "그")는 기본적으로 건드리지 않고,
명백한 신호(같은 단어의 짧은 간격 반복 / 비정상적으로 긴 단어 간 침묵)만 컷 후보로 만든다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .config import Config
from .transcribe import Word

_PUNCT_RE = re.compile(r"[.,!?~…·\"'‘’“”]+")


@dataclass
class CutCandidate:
    start: float
    end: float
    reason: str          # "stutter_repeat" | "stutter_hesitation" | "filler"
    detail: str
    confidence: float


def _normalize(text: str) -> str:
    return _PUNCT_RE.sub("", text).strip().lower()


def find_stutters(words: list[Word], config: Config) -> list[CutCandidate]:
    candidates: list[CutCandidate] = []
    candidates.extend(_find_repeats(words, config))
    candidates.extend(_find_hesitations(words, config))
    if config.filler_words:
        candidates.extend(_find_fillers(words, config))
    return candidates


def _find_repeats(words: list[Word], config: Config) -> list[CutCandidate]:
    candidates: list[CutCandidate] = []
    n = len(words)
    i = 0
    while i < n - 1:
        run = [i]
        j = i + 1
        while j < n:
            gap = words[j].start - words[run[-1]].end
            if _normalize(words[j].text) == _normalize(words[run[-1]].text) and gap <= config.repeat_gap:
                run.append(j)
                j += 1
            else:
                break
        if len(run) >= 2:
            # 마지막 발화만 남기고 그 앞의 반복은 모두 잘라낸다.
            cut_start = words[run[0]].start
            cut_end = words[run[-2]].end
            candidates.append(
                CutCandidate(
                    start=cut_start,
                    end=cut_end,
                    reason="stutter_repeat",
                    detail=f"'{words[run[0]].text}' 가 {len(run)}번 반복됨",
                    confidence=min(0.6 + 0.1 * len(run), 0.95),
                )
            )
            i = run[-1]
        else:
            i += 1
    return candidates


def _find_hesitations(words: list[Word], config: Config) -> list[CutCandidate]:
    candidates: list[CutCandidate] = []
    for a, b in zip(words, words[1:]):
        gap = b.start - a.end
        if gap >= config.hesitation_gap:
            candidates.append(
                CutCandidate(
                    start=a.end,
                    end=b.start,
                    reason="stutter_hesitation",
                    detail=f"'{a.text}' 와 '{b.text}' 사이 {gap:.2f}초 머뭇거림",
                    confidence=0.5,
                )
            )
    return candidates


def _find_fillers(words: list[Word], config: Config) -> list[CutCandidate]:
    filler_set = {_normalize(w) for w in config.filler_words}
    candidates: list[CutCandidate] = []
    for w in words:
        if _normalize(w.text) in filler_set:
            candidates.append(
                CutCandidate(
                    start=w.start,
                    end=w.end,
                    reason="filler",
                    detail=f"추임새 '{w.text}'",
                    confidence=0.7,
                )
            )
    return candidates
