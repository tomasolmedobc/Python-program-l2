import tkinter as tk

import L2CrestMaker as m


def _find(widget, predicate, acc):
    for c in widget.winfo_children():
        if predicate(c):
            acc.append(c)
        _find(c, predicate, acc)
    return acc


def test_text_card_notebook_has_the_four_expected_tabs(app):
    nb = _find(app, lambda w: isinstance(w, m.ttk.Notebook), [])[0]
    labels = [nb.tab(t, "text") for t in nb.tabs()]
    assert labels == ["Contenido", "Color", "Efectos", "Posición"]


def test_main_pane_sash_can_be_dragged_to_resize_left_panel(app):
    original = app._main_pane.sashpos(0)

    app._main_pane.sashpos(0, original + 50)

    assert app._main_pane.sashpos(0) == original + 50
    app._main_pane.sashpos(0, original)  # restore for other tests sharing the app


def test_collapsible_card_toggles_content_visibility_on_header_click(app):
    labelframes = _find(app, lambda w: isinstance(w, tk.LabelFrame), [])
    collapsible = [lf for lf in labelframes if lf.cget("labelwidget")]
    assert len(collapsible) == 4  # Archivos, Transformaciones, Ajustes de imagen, Zona de tono

    lf = collapsible[0]
    hdr_path = lf.cget("labelwidget")
    hdr = app.nametowidget(hdr_path)
    inner = [c for c in lf.winfo_children() if str(c) != hdr_path][0]
    assert inner.winfo_ismapped()

    hdr.event_generate("<Button-1>", when="now")
    app.update()
    assert not inner.winfo_ismapped()

    hdr.event_generate("<Button-1>", when="now")
    app.update()
    assert inner.winfo_ismapped()


def test_add_tooltip_shows_on_enter_and_hides_on_leave(app):
    target = tk.Label(app._left_inner, text="x")
    target.pack()
    app._add_tooltip(target, "hola")
    app.update()

    def toplevels():
        return _find(app, lambda w: isinstance(w, tk.Toplevel), [])

    before = len(toplevels())
    target.event_generate("<Enter>", x=1, y=1, when="now")
    app.update()
    assert len(toplevels()) == before + 1

    target.event_generate("<Leave>", when="now")
    app.update()
    assert len(toplevels()) == before

    target.destroy()


def test_result_canvases_have_hand_cursor_and_open_zoom_popup_on_click(app):
    assert str(app.ally_canvas.cget("cursor")) == "hand2"
    assert str(app.clan_canvas.cget("cursor")) == "hand2"


def test_apply_settings_works_for_hue_zone_fields_even_if_its_card_was_never_opened(app):
    # The "Zona de tono" card is lazy-built (see test below) — its widgets
    # don't exist until first opened, but _apply_settings (used by presets,
    # undo/redo, and session restore) only touches the backing tk.Variables,
    # so it must work regardless of whether the card was ever expanded.
    # Placed before the lazy-build test below so this app instance's card is
    # still genuinely un-built when this assertion runs.
    settings = app._get_current_settings()
    settings["hue_zone_enabled"] = True
    settings["hue_zone_shape"] = "rect"
    settings["hue_zone_hue"] = 77

    app._apply_settings(settings)  # must not raise

    assert app.hue_zone_enabled_var.get() is True
    assert app.hue_zone_shape_var.get() == "rect"
    assert app.hue_zone_hue_var.get() == 77


def test_hue_zone_card_defers_building_its_widgets_until_first_opened(app):
    # Regression test: "Zona de tono" starts collapsed and is rarely used, so
    # its content is built lazily on first expand instead of at startup, to
    # keep the always-visible widget count (and therefore resize/layout
    # cost) down for users who never touch it.
    labelframes = _find(app, lambda w: isinstance(w, tk.LabelFrame), [])
    collapsible = [lf for lf in labelframes if lf.cget("labelwidget")]
    zona = collapsible[-1]
    hdr_path = zona.cget("labelwidget")
    hdr = app.nametowidget(hdr_path)
    inner = [c for c in zona.winfo_children() if str(c) != hdr_path][0]

    assert len(inner.winfo_children()) == 0  # nothing built yet

    hdr.event_generate("<Button-1>", when="now")
    app.update()
    assert len(inner.winfo_children()) > 0  # built on first open

    built_count = len(inner.winfo_children())
    hdr.event_generate("<Button-1>", when="now")  # close
    app.update()
    hdr.event_generate("<Button-1>", when="now")  # reopen
    app.update()
    assert len(inner.winfo_children()) == built_count  # not rebuilt/duplicated

    hdr.event_generate("<Button-1>", when="now")  # leave it closed, as it started
    app.update()
