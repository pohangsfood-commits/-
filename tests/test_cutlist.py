from capcut_auto.audio import SilenceInterval
from capcut_auto.config import Config
from capcut_auto.cutlist import build_cut_regions, build_keep_segments
from capcut_auto.stutter import CutCandidate


def test_silence_becomes_cut_with_padding():
    config = Config(silence_pad=0.1, min_gap_between_cuts=0.05)
    silence = [SilenceInterval(2.0, 4.0)]
    cuts = build_cut_regions(silence, [], duration=10.0, config=config)
    assert len(cuts) == 1
    assert cuts[0].start == 2.1
    assert cuts[0].end == 3.9
    assert cuts[0].reasons == ["silence"]


def test_overlapping_regions_merge():
    config = Config(silence_pad=0.0, min_gap_between_cuts=0.1)
    silence = [SilenceInterval(1.0, 3.0)]
    stutters = [CutCandidate(start=2.5, end=4.0, reason="stutter_repeat", detail="x", confidence=0.8)]
    cuts = build_cut_regions(silence, stutters, duration=10.0, config=config)
    assert len(cuts) == 1
    assert cuts[0].start == 1.0
    assert cuts[0].end == 4.0
    assert set(cuts[0].reasons) == {"silence", "stutter_repeat"}


def test_keep_segments_are_complement_of_cuts():
    config = Config(min_keep=0.0, silence_pad=0.0)
    silence = [SilenceInterval(2.0, 3.0), SilenceInterval(6.0, 7.0)]
    cuts = build_cut_regions(silence, [], duration=10.0, config=config)
    keeps = build_keep_segments(cuts, duration=10.0, config=config)
    assert [(k.start, k.end) for k in keeps] == [(0.0, 2.0), (3.0, 6.0), (7.0, 10.0)]


def test_short_keep_segment_is_absorbed():
    # 2.0~2.2 사이에 아주 짧게 남는 조각(0.2s)은 min_keep(0.5) 미만이므로 흡수되어야 한다.
    config = Config(min_keep=0.5, min_gap_between_cuts=0.0, silence_pad=0.0)
    silence = [SilenceInterval(0.0, 2.0), SilenceInterval(2.2, 4.0)]
    cuts = build_cut_regions(silence, [], duration=10.0, config=config)
    keeps = build_keep_segments(cuts, duration=10.0, config=config)
    # 0.2s짜리 조각이 사라지고 하나의 큰 컷(0~4)만 남아야 한다
    assert all(k.duration >= 0.5 for k in keeps)
    assert (0.0, 4.0) not in [(k.start, k.end) for k in keeps]


def test_no_silence_keeps_whole_video():
    config = Config()
    keeps = build_keep_segments([], duration=5.0, config=config)
    assert len(keeps) == 1
    assert keeps[0].start == 0.0
    assert keeps[0].end == 5.0
