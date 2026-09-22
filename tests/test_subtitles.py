from capcut_auto.config import Config
from capcut_auto.cutlist import KeepSegment
from capcut_auto.remap import TimelineMapper
from capcut_auto.subtitles import _srt_timestamp, words_to_cues, write_srt
from capcut_auto.transcribe import Word


def test_words_group_into_single_cue_when_short():
    words = [Word("안녕하세요", 0.0, 0.5, 0.9), Word("반갑습니다", 0.5, 1.0, 0.9)]
    config = Config(max_chars=100, max_line_seconds=100)
    cues = words_to_cues(words, config)
    assert len(cues) == 1
    assert cues[0].text == "안녕하세요 반갑습니다"
    assert cues[0].start == 0.0
    assert cues[0].end == 1.0


def test_cue_breaks_on_big_gap():
    words = [Word("안녕", 0.0, 0.3, 0.9), Word("하세요", 5.0, 5.3, 0.9)]
    config = Config(max_chars=100, max_line_seconds=100)
    cues = words_to_cues(words, config)
    assert len(cues) == 2
    assert cues[0].text == "안녕"
    assert cues[1].text == "하세요"


def test_cue_breaks_on_max_chars():
    words = [Word("가나다라마바사", 0.0, 0.3, 0.9), Word("아자차카타파하", 0.3, 0.6, 0.9)]
    config = Config(max_chars=10, max_line_seconds=100)
    cues = words_to_cues(words, config)
    assert len(cues) == 2


def test_cue_uses_mapper_and_drops_cut_words():
    # 0~2초는 컷, 2~5초는 유지
    words = [Word("컷될단어", 0.0, 1.0, 0.9), Word("남는단어", 3.0, 4.0, 0.9)]
    mapper = TimelineMapper([KeepSegment(2.0, 5.0)])
    config = Config()
    cues = words_to_cues(words, config, mapper=mapper)
    assert len(cues) == 1
    assert cues[0].text == "남는단어"
    assert cues[0].start == 1.0
    assert cues[0].end == 2.0


def test_srt_timestamp_format():
    assert _srt_timestamp(0.0) == "00:00:00,000"
    assert _srt_timestamp(61.234) == "00:01:01,234"
    assert _srt_timestamp(3661.5) == "01:01:01,500"


def test_write_srt(tmp_path):
    words = [Word("안녕", 0.0, 1.0, 0.9)]
    config = Config()
    cues = words_to_cues(words, config)
    out = tmp_path / "out.srt"
    write_srt(cues, str(out))
    content = out.read_text(encoding="utf-8")
    assert "1\n00:00:00,000 --> 00:00:01,000\n안녕" in content
