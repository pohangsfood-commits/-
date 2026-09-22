from capcut_auto.config import Config
from capcut_auto.stutter import find_stutters
from capcut_auto.transcribe import Word


def test_repeated_word_detected():
    words = [
        Word("그", 0.0, 0.2, 0.9),
        Word("그", 0.3, 0.5, 0.9),
        Word("그거는", 0.6, 1.0, 0.9),
    ]
    config = Config(repeat_gap=0.5)
    candidates = find_stutters(words, config)
    repeats = [c for c in candidates if c.reason == "stutter_repeat"]
    assert len(repeats) == 1
    # 처음 "그"부터 두번째 "그"의 끝까지만 잘라내고, 마지막 발화("그거는" 앞의 "그")는 남긴다
    assert repeats[0].start == 0.0
    assert repeats[0].end == 0.2


def test_no_repeat_when_gap_too_large():
    words = [
        Word("그", 0.0, 0.2, 0.9),
        Word("그", 2.0, 2.2, 0.9),  # 간격이 repeat_gap보다 훨씬 큼
    ]
    config = Config(repeat_gap=0.5)
    candidates = find_stutters(words, config)
    assert not [c for c in candidates if c.reason == "stutter_repeat"]


def test_different_words_not_flagged_as_repeat():
    words = [Word("안녕", 0.0, 0.3, 0.9), Word("하세요", 0.3, 0.6, 0.9)]
    config = Config()
    candidates = find_stutters(words, config)
    assert not [c for c in candidates if c.reason == "stutter_repeat"]


def test_long_gap_flagged_as_hesitation():
    words = [Word("안녕", 0.0, 0.3, 0.9), Word("하세요", 2.0, 2.3, 0.9)]
    config = Config(hesitation_gap=0.8)
    candidates = find_stutters(words, config)
    hes = [c for c in candidates if c.reason == "stutter_hesitation"]
    assert len(hes) == 1
    assert hes[0].start == 0.3
    assert hes[0].end == 2.0


def test_filler_words_off_by_default():
    words = [Word("음", 0.0, 0.2, 0.9)]
    config = Config()
    candidates = find_stutters(words, config)
    assert not [c for c in candidates if c.reason == "filler"]


def test_filler_words_when_configured():
    words = [Word("음", 0.0, 0.2, 0.9), Word("안녕", 0.3, 0.6, 0.9)]
    config = Config(filler_words=("음",))
    candidates = find_stutters(words, config)
    fillers = [c for c in candidates if c.reason == "filler"]
    assert len(fillers) == 1
    assert fillers[0].start == 0.0 and fillers[0].end == 0.2
