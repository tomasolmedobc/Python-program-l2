from PIL import Image

from L2CrestMaker import image_to_l2_bmp, _apply_zone_hue_shift, CLAN_SIZE, ALLY_SIZE


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


# ── Feature 9: zona de tono (hue shift local) ───────────────────────────────

def test_apply_zone_hue_shift_only_changes_pixels_inside_the_circle():
    img = Image.new("RGB", (100, 100), (255, 0, 0))
    out = _apply_zone_hue_shift(img, 120, "circle", cx=50, cy=50, rx=20, ry=20, invert=False)
    assert out.getpixel((50, 50)) != (255, 0, 0)   # center: inside
    assert out.getpixel((2, 2))   == (255, 0, 0)   # corner: outside


def test_apply_zone_hue_shift_invert_affects_outside_instead():
    img = Image.new("RGB", (100, 100), (255, 0, 0))
    out = _apply_zone_hue_shift(img, 120, "circle", cx=50, cy=50, rx=20, ry=20, invert=True)
    assert out.getpixel((50, 50)) == (255, 0, 0)   # center: inside, now unaffected
    assert out.getpixel((2, 2))   != (255, 0, 0)   # corner: outside, now affected


def test_apply_zone_hue_shift_rect_uses_the_bounding_box_not_an_ellipse():
    img = Image.new("RGB", (100, 100), (255, 0, 0))
    out = _apply_zone_hue_shift(img, 120, "rect", cx=50, cy=50, rx=20, ry=20, invert=False)
    # (68, 68) sits inside the 20x20 half-extent box but outside a same-radius circle.
    assert out.getpixel((68, 68)) != (255, 0, 0)
    assert out.getpixel((2, 2))   == (255, 0, 0)


def test_apply_zone_hue_shift_zero_hue_is_a_no_op():
    img = Image.new("RGB", (50, 50), (10, 200, 30))
    out = _apply_zone_hue_shift(img, 0, "circle", 25, 25, 10, 10, False)
    assert out is img


def _make_split_source(tmp_path, color=(255, 0, 0, 255), size=(400, 200)):
    src = tmp_path / "split_source.png"
    Image.new("RGBA", size, color).save(src)
    return str(src)


def test_hue_zone_outside_the_clan_crop_does_not_affect_it(tmp_path):
    src = _make_split_source(tmp_path)
    hue_zone = dict(enabled=True, shape="circle", invert=False, hue=120,
                     center=(0.1, 0.5), size=(0.05, 0.05))  # deep in the ally-only region

    without = image_to_l2_bmp(src, None, CLAN_SIZE, align="clan").convert("RGB")
    with_zone = image_to_l2_bmp(src, None, CLAN_SIZE, align="clan", hue_zone=hue_zone).convert("RGB")

    assert without.tobytes() == with_zone.tobytes()


def test_hue_zone_inside_the_clan_crop_changes_it(tmp_path):
    src = _make_split_source(tmp_path)
    hue_zone = dict(enabled=True, shape="circle", invert=False, hue=120,
                     center=(0.75, 0.5), size=(0.1, 0.1))  # well inside the clan (right) half

    without = image_to_l2_bmp(src, None, CLAN_SIZE, align="clan").convert("RGB")
    with_zone = image_to_l2_bmp(src, None, CLAN_SIZE, align="clan", hue_zone=hue_zone).convert("RGB")

    assert without.tobytes() != with_zone.tobytes()


def test_hue_zone_disabled_is_a_no_op_even_with_hue_set(tmp_path):
    src = _make_split_source(tmp_path)
    hue_zone = dict(enabled=False, shape="circle", invert=False, hue=120,
                     center=(0.75, 0.5), size=(0.1, 0.1))

    without = image_to_l2_bmp(src, None, CLAN_SIZE, align="clan").convert("RGB")
    with_zone = image_to_l2_bmp(src, None, CLAN_SIZE, align="clan", hue_zone=hue_zone).convert("RGB")

    assert without.tobytes() == with_zone.tobytes()
