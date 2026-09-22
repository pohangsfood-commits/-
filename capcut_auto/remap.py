"""컷 편집 후 원본 시간 -> 새 타임라인 시간으로 변환한다."""

from __future__ import annotations

from .cutlist import KeepSegment


class TimelineMapper:
    def __init__(self, keep_segments: list[KeepSegment]):
        self.keep_segments = keep_segments
        self.offsets: list[float] = []
        acc = 0.0
        for k in keep_segments:
            self.offsets.append(acc)
            acc += k.duration
        self.total_duration = acc

    def map(self, t: float) -> float | None:
        for k, off in zip(self.keep_segments, self.offsets):
            if k.start <= t <= k.end:
                return off + (t - k.start)
        return None

    def map_range(self, start: float, end: float) -> tuple[float, float] | None:
        """(start, end) 구간을 새 타임라인으로 매핑한다.

        구간이 컷 경계에 걸쳐 있으면 keep segment와 겹치는 부분만 남긴다.
        완전히 컷된 구간이면 None을 반환한다.
        """
        new_start = self.map(start)
        new_end = self.map(end)
        if new_start is not None and new_end is not None and new_end >= new_start:
            return new_start, new_end

        for k, off in zip(self.keep_segments, self.offsets):
            overlap_start = max(start, k.start)
            overlap_end = min(end, k.end)
            if overlap_end > overlap_start:
                return off + (overlap_start - k.start), off + (overlap_end - k.start)
        return None
