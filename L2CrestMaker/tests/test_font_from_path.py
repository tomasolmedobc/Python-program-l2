from PIL import ImageFont

from L2CrestMaker import _font_from_path


def test_none_path_falls_back_to_default_font():
    font = _font_from_path(None, 20)
    assert font is not None


def test_missing_file_falls_back_without_raising():
    font = _font_from_path(r"C:\does\not\exist.ttf", 20)
    assert font is not None


def test_same_args_return_cached_identical_object():
    a = _font_from_path(None, 24)
    b = _font_from_path(None, 24)
    assert a is b


def test_different_size_is_not_cached_together():
    a = _font_from_path(None, 24)
    b = _font_from_path(None, 25)
    assert a is not b


def test_real_font_file_loads_truetype(tmp_path):
    # Windows always ships Arial; skip if this particular machine doesn't.
    arial = r"C:\Windows\Fonts\arial.ttf"
    import os
    if not os.path.isfile(arial):
        import pytest
        pytest.skip("arial.ttf not present on this machine")
    font = _font_from_path(arial, 30)
    assert isinstance(font, ImageFont.FreeTypeFont)
