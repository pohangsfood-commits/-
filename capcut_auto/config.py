"""파이프라인 전체에서 쓰는 설정값들."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Config:
    # 무음 탐지
    min_silence: float = 0.7          # 이 길이(초) 이상이어야 무음 구간으로 인정
    silence_noise_db: float = -30.0   # 이 값보다 조용하면 무음
    silence_pad: float = 0.12         # 무음 구간 잘라낼 때 앞뒤로 남겨둘 여유(초)

    # 버벅임(더듬는 구간) 탐지
    repeat_gap: float = 0.5           # 같은 단어가 이 간격(초) 이내로 반복되면 버벅임
    hesitation_gap: float = 0.8       # 문장 내 단어 사이 간격이 이 값(초) 이상이면 머뭇거림
    filler_words: tuple[str, ...] = ()  # 명시적으로 제거할 추임새 목록 (기본 비활성)

    # 컷 병합
    min_gap_between_cuts: float = 0.2  # 이보다 가까운 두 컷은 하나로 합침
    min_keep: float = 0.3             # 이보다 짧게 남는 조각은 인접 구간에 흡수

    # 자막
    max_chars: int = 24               # 자막 한 줄 최대 글자 수
    max_line_seconds: float = 6.0     # 자막 한 줄이 화면에 머무는 최대 시간(초)

    # Whisper
    whisper_model: str = "large-v3"
    whisper_device: str = "auto"
    whisper_language: str = "ko"
