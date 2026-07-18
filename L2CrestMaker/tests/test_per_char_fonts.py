from L2CrestMaker import _per_char_fonts, _font_from_path

SIZE_PX = lambda pct: max(4, int(1000 * pct / 100))
OFF_PX  = lambda pct: int(1000 * pct / 100)
FALLBACK = _font_from_path(None, 40)


def test_no_font_paths_returns_none_none():
    fonts, offsets = _per_char_fonts("AB", None, None, None, 60, SIZE_PX, OFF_PX, FALLBACK)
    assert fonts is None
    assert offsets is None


def test_empty_font_paths_returns_none_none():
    fonts, offsets = _per_char_fonts("AB", [], None, None, 60, SIZE_PX, OFF_PX, FALLBACK)
    assert fonts is None
    assert offsets is None


def test_fully_specified_text_returns_one_font_per_char():
    fonts, offsets = _per_char_fonts(
        "ABC", ["", "", ""], [50, 80, 30], [10, -5, 0],
        60, SIZE_PX, OFF_PX, FALLBACK,
    )
    assert len(fonts) == 3
    assert offsets == [100, -50, 0]


def test_shorter_font_paths_pads_with_fallback_font_and_zero_offset():
    fonts, offsets = _per_char_fonts(
        "ABC", ["", ""], [50, 80], [10, -5],
        60, SIZE_PX, OFF_PX, FALLBACK,
    )
    assert len(fonts) == 3
    assert len(offsets) == 3
    assert fonts[2] is FALLBACK
    assert offsets[2] == 0


def test_missing_size_pct_entry_falls_back_to_base_size_pct():
    # Only one size% given for two chars — the second char should use base_size_pct (60).
    fonts, offsets = _per_char_fonts(
        "AB", ["", ""], [50], None,
        60, SIZE_PX, OFF_PX, FALLBACK,
    )
    base_font = _font_from_path("", SIZE_PX(60))
    assert fonts[1].size == base_font.size


def test_missing_y_offset_defaults_to_zero():
    fonts, offsets = _per_char_fonts(
        "AB", ["", ""], [50, 50], [15],
        60, SIZE_PX, OFF_PX, FALLBACK,
    )
    assert offsets == [150, 0]


def test_font_paths_longer_than_text_is_truncated():
    fonts, offsets = _per_char_fonts(
        "A", ["", "", ""], [50, 60, 70], [1, 2, 3],
        60, SIZE_PX, OFF_PX, FALLBACK,
    )
    assert len(fonts) == 1
    assert offsets == [10]
