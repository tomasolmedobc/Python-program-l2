from PIL import Image

import L2CrestMaker as m
import app_preview


def test_show_palette_handles_a_short_palette_without_indexerror(app, tmp_path, monkeypatch):
    # Regression test: PIL's getpalette() can return fewer than 768 entries
    # (256 * 3) for some quantized images — _show_palette used to assume a
    # full 256-color table and raised IndexError. It must pad instead.
    src = tmp_path / "src.png"
    Image.new("RGB", (50, 50), (10, 20, 30)).save(src)
    app.src_path.set(str(src))

    short_img = Image.new("P", (8, 12))
    short_img.putpalette([0, 0, 0] * 50)  # 150 entries, well under 768
    monkeypatch.setattr(app_preview, "image_to_l2_bmp", lambda *a, **k: short_img)

    app._show_palette("ally")  # must not raise

    tops = [w for w in app.winfo_children() if isinstance(w, m.tk.Toplevel)]
    assert tops
    for t in tops:
        t.destroy()


def test_show_palette_without_source_shows_prompt_and_does_not_raise(app):
    app.src_path.set("")

    app._show_palette("clan")  # must not raise, no dialog created

    tops = [w for w in app.winfo_children() if isinstance(w, m.tk.Toplevel)]
    assert not tops


def test_apply_preview_bg_recolors_result_canvases(app):
    app.preview_bg_var.set("white")

    app._apply_preview_bg()

    assert app.clan_canvas.cget("bg") == "#ffffff"
    assert app.ally_canvas.cget("bg") == "#ffffff"

    app.preview_bg_var.set("black")
    app._apply_preview_bg()

    assert app.clan_canvas.cget("bg") == "#000000"


def test_toggle_before_after_flips_mode_and_button_style(app):
    app._before_after_mode = False

    app._toggle_before_after()
    assert app._before_after_mode is True
    assert app._ba_btn.cget("relief") == "sunken"

    app._toggle_before_after()
    assert app._before_after_mode is False
    assert app._ba_btn.cget("relief") == "flat"
