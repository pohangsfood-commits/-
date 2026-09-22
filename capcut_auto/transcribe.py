"""faster-whisper를 이용한 단어 단위 타임스탬프 음성인식."""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class Word:
    text: str
    start: float
    end: float
    probability: float

    def to_dict(self) -> dict:
        return asdict(self)


def transcribe(
    audio_path: str,
    *,
    model_size: str = "large-v3",
    device: str = "auto",
    language: str = "ko",
) -> list[Word]:
    """오디오를 전사하고 단어 단위 타임스탬프 목록을 반환한다."""
    from faster_whisper import WhisperModel  # 지연 임포트: CLI --help 등에서 불필요한 로딩 방지

    compute_type = "float16" if device == "cuda" else "int8"
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    segments, _info = model.transcribe(
        audio_path,
        language=language,
        word_timestamps=True,
        vad_filter=False,  # 무음 판단은 audio.detect_silence가 별도로 담당
    )

    words: list[Word] = []
    for segment in segments:
        if not segment.words:
            continue
        for w in segment.words:
            text = w.word.strip()
            if not text:
                continue
            words.append(
                Word(
                    text=text,
                    start=float(w.start),
                    end=float(w.end),
                    probability=float(w.probability),
                )
            )
    return words


def words_from_dicts(items: list[dict]) -> list[Word]:
    return [Word(text=i["text"], start=i["start"], end=i["end"], probability=i["probability"]) for i in items]
