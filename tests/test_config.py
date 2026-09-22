from capcut_auto.config import Config


def test_to_dict_from_dict_roundtrip():
    cfg = Config(min_silence=1.2, filler_words=("음", "어"))
    d = cfg.to_dict()
    assert d["filler_words"] == ["음", "어"]
    restored = Config.from_dict(d)
    assert restored == cfg


def test_from_dict_parses_comma_string_filler_words():
    cfg = Config.from_dict({"filler_words": "음, 어 ,그니까"})
    assert cfg.filler_words == ("음", "어", "그니까")


def test_from_dict_ignores_unknown_keys_and_uses_defaults():
    cfg = Config.from_dict({"min_silence": 2.0, "unknown_field": 123})
    assert cfg.min_silence == 2.0
    assert cfg.silence_pad == Config().silence_pad


def test_from_dict_empty_uses_all_defaults():
    assert Config.from_dict({}) == Config()
