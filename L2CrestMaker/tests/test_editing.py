import types

from PIL import Image

import L2CrestMaker as m


def test_push_undo_then_undo_restores_previous_text_size(app):
    app.text_size.set(50)
    app._push_undo()
    app.text_size.set(90)

    app._undo()

    assert app.text_size.get() == 50


def test_redo_after_undo_reapplies_the_changed_value(app):
    app.text_size.set(50)
    app._push_undo()
    app.text_size.set(90)
    app._undo()

    app._redo()

    assert app.text_size.get() == 90


def test_undo_on_empty_stack_does_nothing(app):
    app._undo_stack.clear()
    app.text_size.set(77)

    app._undo()  # must not raise

    assert app.text_size.get() == 77


def test_nudge_text_moves_position_and_clamps_to_unit_range(app):
    app.text_pos = (0.5, 0.5)
    app._nudge_pushed = False

    app._nudge_text(0.01, 0.0)
    assert app.text_pos[0] == 0.51

    for _ in range(200):
        app._nudge_text(0.01, 0.0)
    assert app.text_pos[0] == 1.0  # clamped, never exceeds the unit square


def test_split_drag_updates_shared_ratio_and_clamps_range(app, monkeypatch):
    monkeypatch.setattr(m, "_split_ratio", 8 / 24)
    app._src_disp_rect = (0, 0, 240, 120)  # off_x, off_y, disp_w, disp_h

    app._split_drag_start(types.SimpleNamespace(x=int(8 / 24 * 240), y=60))
    assert app._dragging_split is True

    app._split_drag_move(types.SimpleNamespace(x=180, y=60))  # ratio ~0.75, above the 0.55 cap
    assert m._split_ratio == 0.55  # clamped

    app._split_drag_move(types.SimpleNamespace(x=5, y=60))  # ratio ~0.02, below the 0.15 floor
    assert m._split_ratio == 0.15  # clamped


def test_split_drag_start_ignores_clicks_far_from_the_handle(app, monkeypatch):
    monkeypatch.setattr(m, "_split_ratio", 8 / 24)
    app._src_disp_rect = (0, 0, 240, 120)
    app._dragging_split = False

    app._split_drag_start(types.SimpleNamespace(x=239, y=60))  # far from the split line

    assert app._dragging_split is False


def test_reset_split_restores_default_ratio(app, monkeypatch):
    monkeypatch.setattr(m, "_split_ratio", 0.5)

    app._reset_split()

    assert m._split_ratio == 8 / 24


def test_auto_adjust_sets_brightness_and_contrast_from_a_dark_image(app, tmp_path):
    src = tmp_path / "dark.png"
    Image.new("RGB", (100, 100), (10, 10, 10)).save(src)
    app.src_path.set(str(src))
    app.brightness_var.set(1.0)
    app.contrast_var.set(1.0)

    app._auto_adjust()

    # A near-black, flat image should be brightened (mean well below 128).
    assert app.brightness_var.get() > 1.0
    assert "Auto-ajuste" in app.status_var.get()


def test_auto_adjust_without_source_shows_prompt_and_does_not_raise(app):
    app.src_path.set("")

    app._auto_adjust()

    assert "imagen" in app.status_var.get().lower()


def test_pick_color_from_image_sets_text_color_from_sampled_pixel(app, tmp_path):
    src = tmp_path / "solid.png"
    Image.new("RGB", (100, 100), (200, 10, 10)).save(src)
    app.src_path.set(str(src))
    app.brightness_var.set(1.0)
    app.contrast_var.set(1.0)
    app.saturation_var.set(1.0)
    app.hue_var.set(0)
    app._src_disp_rect = (0, 0, 100, 100)
    app._src_img_size = (100, 100)

    app._pick_color_from_image(types.SimpleNamespace(x=50, y=50))

    assert app.text_color.lower() == "#c80a0a"


def test_start_color_replace_records_replacement_and_updates_button(app, tmp_path, monkeypatch):
    src = tmp_path / "solid.png"
    Image.new("RGB", (60, 60), (0, 255, 0)).save(src)
    app.src_path.set(str(src))
    app._src_disp_rect = (0, 0, 60, 60)
    app._src_img_size = (60, 60)
    app._color_replacements = []
    monkeypatch.setattr(m.colorchooser, "askcolor", lambda **kw: ((0, 0, 0), "#000000"))

    app._start_color_replace(types.SimpleNamespace(x=10, y=10))

    assert len(app._color_replacements) == 1
    src_color, dst_color, _tol = app._color_replacements[0]
    assert src_color == (0, 255, 0)
    assert dst_color == (0, 0, 0)
    assert "1" in app._repl_btn.cget("text")


# ── Feature 9: zona de tono — drag/resize sobre el canvas ───────────────────

def _reset_hue_zone_state(app):
    # Blank the source path so _refresh_text_preview() (called by the drag
    # handlers) is a no-op and can't clobber the _src_disp_rect set below —
    # the shared app instance may still have a real (stale) path from
    # another test otherwise.
    app.src_path.set("")
    app.hue_zone_enabled_var.set(True)
    app._hue_zone_center = (0.5, 0.5)
    app._hue_zone_size = (0.15, 0.15)
    app._dragging_hue_zone = None
    app._src_disp_rect = (0, 0, 200, 100)  # off_x, off_y, disp_w, disp_h


def test_hue_zone_hit_test_detects_inside_edge_and_outside(app):
    _reset_hue_zone_state(app)
    app.hue_zone_shape_var.set("circle")
    # geometry in canvas px: center (100, 50), rx=30, ry=15

    assert app._hue_zone_hit_test(100, 50) == "move"       # dead center
    assert app._hue_zone_hit_test(130, 65) == "resize"      # bottom-right handle
    assert app._hue_zone_hit_test(199, 99) is None           # far corner, outside


def test_hue_zone_hit_test_disabled_when_no_disp_rect(app):
    _reset_hue_zone_state(app)
    app._src_disp_rect = None
    assert app._hue_zone_hit_test(100, 50) is None


def test_on_canvas_button1_starts_hue_zone_move_when_click_lands_inside(app):
    _reset_hue_zone_state(app)
    app._undo_stack.clear()

    app._on_canvas_button1(types.SimpleNamespace(x=100, y=50))

    assert app._dragging_hue_zone == "move"
    assert len(app._undo_stack) == 1  # drag start pushes an undo snapshot


def test_on_canvas_button1_falls_through_to_text_drag_when_outside_zone(app, monkeypatch):
    _reset_hue_zone_state(app)
    called = []
    monkeypatch.setattr(app.__class__, "_text_drag_start", lambda self, e: called.append(e))

    app._on_canvas_button1(types.SimpleNamespace(x=199, y=99))

    assert app._dragging_hue_zone is None
    assert called


def test_on_canvas_button1_ignores_zone_when_tool_disabled(app, monkeypatch):
    _reset_hue_zone_state(app)
    app.hue_zone_enabled_var.set(False)
    called = []
    monkeypatch.setattr(app.__class__, "_text_drag_start", lambda self, e: called.append(e))

    app._on_canvas_button1(types.SimpleNamespace(x=100, y=50))  # dead center of the (disabled) zone

    assert app._dragging_hue_zone is None
    assert called


def test_update_hue_zone_from_canvas_moves_center(app):
    _reset_hue_zone_state(app)
    app._dragging_hue_zone = "move"

    app._update_hue_zone_from_canvas(50, 25)  # quarter-way into the 200x100 display rect

    assert app._hue_zone_center == (0.25, 0.25)


def test_update_hue_zone_from_canvas_resizes_and_has_a_minimum(app):
    _reset_hue_zone_state(app)
    app._dragging_hue_zone = "resize"

    app._update_hue_zone_from_canvas(160, 70)  # 60px right, 20px down from center (100,50)

    rx, ry = app._hue_zone_size
    assert rx == 60 / 200
    assert ry == 20 / 100

    # Dragging the handle back onto the center must not collapse to zero.
    app._update_hue_zone_from_canvas(100, 50)
    rx, ry = app._hue_zone_size
    assert rx == 6 / 200 and ry == 6 / 100


def test_reset_hue_zone_restores_defaults(app):
    _reset_hue_zone_state(app)
    app._hue_zone_center = (0.9, 0.1)
    app._hue_zone_size = (0.4, 0.4)

    app._reset_hue_zone()

    assert app._hue_zone_center == (0.5, 0.5)
    assert app._hue_zone_size == (0.15, 0.15)
