from PIL import Image

from L2CrestMaker import image_to_l2_bmp, CLAN_SIZE, ALLY_SIZE


def _make_source(tmp_path, size=(200, 200)):
    src = tmp_path / "source.png"
    Image.new("RGBA", size, (30, 120, 200, 255)).save(src)
    return str(src)


def test_clan_conversion_produces_correct_size_and_mode(tmp_path):
    src = _make_source(tmp_path)
    img = image_to_l2_bmp(src, None, CLAN_SIZE, align="clan")
    assert img.size == CLAN_SIZE
    assert img.mode == "P"  # quantized to a 256-color palette, per L2 BMP format


def test_ally_conversion_produces_correct_size(tmp_path):
    src = _make_source(tmp_path)
    img = image_to_l2_bmp(src, None, ALLY_SIZE, align="ally")
    assert img.size == ALLY_SIZE


def test_dest_path_none_does_not_write_a_file(tmp_path):
    src = _make_source(tmp_path)
    dest = tmp_path / "out.bmp"
    image_to_l2_bmp(src, None, CLAN_SIZE, align="clan")
    assert not dest.exists()


def test_dest_path_writes_a_readable_bmp(tmp_path):
    src = _make_source(tmp_path)
    dest = tmp_path / "out.bmp"
    image_to_l2_bmp(src, str(dest), CLAN_SIZE, align="clan")
    assert dest.exists()
    with Image.open(dest) as saved:
        assert saved.size == CLAN_SIZE


def test_single_line_text_renders_without_raising(tmp_path):
    src = _make_source(tmp_path)
    img = image_to_l2_bmp(
        src, None, CLAN_SIZE, align="clan",
        texts=[("AB", (0.5, 0.5), 60)],
    )
    assert img.size == CLAN_SIZE


def test_text_changes_pixels_versus_no_text(tmp_path):
    src = _make_source(tmp_path)
    plain = image_to_l2_bmp(src, None, CLAN_SIZE, align="clan").convert("RGB")
    with_text = image_to_l2_bmp(
        src, None, CLAN_SIZE, align="clan",
        texts=[("AB", (0.5, 0.5), 80)], text_color="#ff0000",
    ).convert("RGB")
    assert plain.tobytes() != with_text.tobytes()


def test_multi_font_single_text_entry_renders_without_raising(tmp_path):
    src = _make_source(tmp_path)
    img = image_to_l2_bmp(
        src, None, CLAN_SIZE, align="clan",
        texts=[("AB", (0.5, 0.5), 60)],
        char_font_paths=[None, None],
        char_size_pcts=[50, 70],
        char_y_offsets_pct=[5, -5],
    )
    assert img.size == CLAN_SIZE


def test_char_font_paths_ignored_when_multiple_active_texts(tmp_path):
    # Regression test: char_font_paths/size/offset describe a single string's
    # per-character styling. With more than one active text (e.g. smart
    # layout), they must not be misapplied to every entry — this used to
    # raise/misrender before the len(active_texts) == 1 guard was added.
    src = _make_source(tmp_path)
    img = image_to_l2_bmp(
        src, None, CLAN_SIZE, align="clan",
        texts=[("A", (0.3, 0.5), 60), ("BC", (0.7, 0.5), 40)],
        char_font_paths=[None, None],
        char_size_pcts=[50, 70],
        char_y_offsets_pct=[5, -5],
    )
    assert img.size == CLAN_SIZE
