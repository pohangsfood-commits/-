from capcut_auto.cutlist import KeepSegment
from capcut_auto.remap import TimelineMapper


def make_mapper():
    # 원본 0~2초는 컷, 2~5초는 유지, 5~6초는 컷, 6~10초는 유지
    return TimelineMapper([KeepSegment(2.0, 5.0), KeepSegment(6.0, 10.0)])


def test_map_inside_first_keep_segment():
    mapper = make_mapper()
    assert mapper.map(2.0) == 0.0
    assert mapper.map(4.0) == 2.0
    assert mapper.map(5.0) == 3.0


def test_map_inside_second_keep_segment_has_offset():
    mapper = make_mapper()
    assert mapper.map(6.0) == 3.0
    assert mapper.map(10.0) == 7.0


def test_map_inside_cut_region_returns_none():
    mapper = make_mapper()
    assert mapper.map(0.5) is None
    assert mapper.map(5.5) is None


def test_map_range_fully_inside_keep_segment():
    mapper = make_mapper()
    r = mapper.map_range(3.0, 4.0)
    assert r == (1.0, 2.0)


def test_map_range_fully_cut_returns_none():
    mapper = make_mapper()
    assert mapper.map_range(5.2, 5.8) is None


def test_map_range_straddling_cut_boundary_clamps():
    mapper = make_mapper()
    # 4.5~5.5는 (2~5 keep)과 (5~6 cut)에 걸쳐 있음 -> keep 부분(4.5~5.0)만 남아야 함
    r = mapper.map_range(4.5, 5.5)
    assert r == (2.5, 3.0)


def test_total_duration():
    mapper = make_mapper()
    assert mapper.total_duration == 7.0
