"""무음/버벅임 후보들을 병합해 최종 컷 리스트와 남길 구간(keep segments)을 계산한다.

이 모듈은 순수 파이썬 로직만 담고 있어 ffmpeg/Whisper 없이 단위 테스트가 가능하다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .audio import SilenceInterval
from .config import Config
from .stutter import CutCandidate


@dataclass
class CutRegion:
    start: float
    end: float
    reasons: list[str] = field(default_factory=list)
    confidence: float = 0.5

    def to_dict(self) -> dict:
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "reasons": self.reasons,
            "confidence": round(self.confidence, 3),
        }

    @staticmethod
    def from_dict(d: dict) -> "CutRegion":
        return CutRegion(start=d["start"], end=d["end"], reasons=list(d.get("reasons", [])), confidence=d.get("confidence", 0.5))


@dataclass
class KeepSegment:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


def _silence_to_regions(silence: list[SilenceInterval], duration: float, pad: float) -> list[CutRegion]:
    regions: list[CutRegion] = []
    for s in silence:
        start = max(0.0, s.start + pad)
        end = min(duration, s.end - pad)
        if end > start:
            regions.append(CutRegion(start=start, end=end, reasons=["silence"], confidence=0.9))
    return regions


def _stutter_to_regions(stutters: list[CutCandidate], duration: float, pad: float) -> list[CutRegion]:
    regions: list[CutRegion] = []
    for c in stutters:
        start, end = c.start, c.end
        if c.reason == "stutter_hesitation":
            start += pad
            end -= pad
        start = max(0.0, start)
        end = min(duration, end)
        if end > start:
            regions.append(CutRegion(start=start, end=end, reasons=[c.reason], confidence=c.confidence))
    return regions


def _merge_regions(regions: list[CutRegion], min_gap: float) -> list[CutRegion]:
    if not regions:
        return []
    regions = sorted(regions, key=lambda r: r.start)
    merged = [regions[0]]
    for r in regions[1:]:
        last = merged[-1]
        if r.start <= last.end + min_gap:
            last.end = max(last.end, r.end)
            for reason in r.reasons:
                if reason not in last.reasons:
                    last.reasons.append(reason)
            last.confidence = max(last.confidence, r.confidence)
        else:
            merged.append(r)
    return merged


def _invert(cuts: list[CutRegion], duration: float) -> list[KeepSegment]:
    keeps: list[KeepSegment] = []
    cursor = 0.0
    for c in cuts:
        if c.start > cursor:
            keeps.append(KeepSegment(cursor, c.start))
        cursor = max(cursor, c.end)
    if cursor < duration:
        keeps.append(KeepSegment(cursor, duration))
    return keeps


def build_cut_regions(
    silence: list[SilenceInterval],
    stutters: list[CutCandidate],
    duration: float,
    config: Config,
) -> list[CutRegion]:
    regions = _silence_to_regions(silence, duration, config.silence_pad)
    regions += _stutter_to_regions(stutters, duration, config.silence_pad)
    return _merge_regions(regions, config.min_gap_between_cuts)


def build_keep_segments(cuts: list[CutRegion], duration: float, config: Config) -> list[KeepSegment]:
    """짧은 컷 구간은 무시하고, 짧게 남는 조각은 흡수해 최종 keep segment를 만든다."""
    cuts = _merge_regions([CutRegion(c.start, c.end, list(c.reasons), c.confidence) for c in cuts], config.min_gap_between_cuts)

    for _ in range(len(cuts) + 1):
        keeps = _invert(cuts, duration)
        too_short = [k for k in keeps if k.duration < config.min_keep]
        if not too_short:
            return keeps
        # 가장 짧게 남는 조각을 양옆 컷 구간에 흡수시켜 다시 계산한다.
        target = min(too_short, key=lambda k: k.duration)
        cuts = _merge_regions(cuts + [CutRegion(target.start, target.end, ["min_keep_absorbed"], 0.4)], config.min_gap_between_cuts)
    return _invert(cuts, duration)
