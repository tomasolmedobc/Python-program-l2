from PIL import Image

import L2CrestMaker as m


def test_set_text_color_updates_value_and_swatch_relief(app):
    app._set_text_color("#123456")

    assert app.text_color == "#123456"
    # None of the three quick-pick swatches match this custom color.
    assert all(btn.cget("relief") == "flat" for btn in app._color_btns.values())

    app._set_text_color("#ffffff")
    assert app._color_btns["#ffffff"].cget("relief") == "sunken"


def test_snap_text_pos_moves_to_named_anchor(app):
    app.text_pos = (0.5, 0.5)

    app._snap_text_pos("nw")
    assert app.text_pos == (0.10, 0.10)

    app._snap_text_pos("se")
    assert app.text_pos == (0.90, 0.90)

    app._snap_text_pos("c")
    assert app.text_pos == (0.5, 0.5)


def test_apply_gradient_preset_sets_colors_and_enables_gradient(app):
    app.text_gradient_var.set(False)

    app._apply_gradient_preset("#ffe680", "#7b3000")

    assert app._gradient_color1 == "#ffe680"
    assert app._gradient_color2 == "#7b3000"
    assert app.text_gradient_var.get() is True
    assert app._grad_btn1.cget("bg") == "#ffe680"
    assert app._grad_btn2.cget("bg") == "#7b3000"


def test_reset_outline_color_clears_custom_value(app):
    app._outline_color_val = "#ff00ff"

    app._reset_outline_color()

    assert app._outline_color_val is None
    assert app._outline_color_btn.cget("text") == "Auto"


def _make_split_image(folder, left=(255, 0, 0), right=(0, 0, 255), size=(400, 200)):
    img = Image.new("RGB", size, right)
    half = Image.new("RGB", (size[0] // 2, size[1]), left)
    img.paste(half, (0, 0))
    path = folder / "split.png"
    img.save(path)
    return str(path)


def test_auto_text_color_reads_the_live_split_ratio_not_a_stale_copy(app, tmp_path, monkeypatch):
    # Regression test: this used to read self._split_ratio, an instance
    # attribute frozen at __init__ time (8/24) and never updated when the
    # user drags the crop-split handle. It must read the shared,
    # live-updated _core._split_ratio instead, so the background-color
    # detection matches whatever split the user actually set.
    src = _make_split_image(tmp_path)
    app.src_path.set(src)
    app.brightness_var.set(1.0)
    app.contrast_var.set(1.0)
    app.saturation_var.set(1.0)
    app.hue_var.set(0)
    monkeypatch.setattr(m, "_split_ratio", 0.5)  # split lands exactly on the color boundary

    captured = {}
    monkeypatch.setattr(
        app.__class__, "_show_color_recommendation",
        lambda self, bg_hex, *a, **k: captured.update(bg_hex=bg_hex)
    )

    app._auto_text_color()

    assert captured["bg_hex"].lower() == "#0000ff"
