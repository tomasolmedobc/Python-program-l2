import os

from PIL import Image

import L2CrestMaker as m


def _close_dialog(app):
    for w in app.winfo_children():
        if isinstance(w, m.tk.Toplevel):
            w.destroy()
    app._gallery_open = False


def _dialog(app):
    tops = [w for w in app.winfo_children() if isinstance(w, m.tk.Toplevel)]
    assert tops, "gallery dialog was not created"
    return tops[0]


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


def _clickable_thumbs(app):
    dlg = _dialog(app)
    return [w for w in _walk(dlg)
            if isinstance(w, m.tk.Label) and str(w.cget("cursor")) == "hand2"]


def _make_png(folder, name, size=(30, 30), color=(10, 200, 30, 200)):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    Image.new("RGBA", size, color).save(path)
    return path


def test_gallery_creates_folders_when_missing(app):
    app._open_asset_gallery()
    assert os.path.isdir(m.OVERLAYS_DIR)
    assert os.path.isdir(m.TEMPLATES_DIR)
    _close_dialog(app)


def test_gallery_renders_thumbnail_for_existing_png(app):
    _make_png(m.OVERLAYS_DIR, "logo.png")
    # Should not raise even though a real image needs to be thumbnailed
    # and composited onto the picker background.
    app._open_asset_gallery()
    assert len(_clickable_thumbs(app)) == 1
    _close_dialog(app)


def test_thumbnail_stays_alive_after_dialog_opens(app):
    # Regression test: PhotoImage objects used to live only in a local list
    # inside _open_asset_gallery(), so they were garbage-collected — and the
    # underlying Tk image data freed — the instant the method returned,
    # leaving every thumbnail blank. They must now be cached on the app
    # itself so they outlive the method call.
    path = _make_png(m.OVERLAYS_DIR, "logo.png")
    app._open_asset_gallery()
    assert path in app._asset_thumb_cache
    ph = app._asset_thumb_cache[path]
    assert ph.width() == 72 and ph.height() == 72  # raises TclError if the image was freed
    _close_dialog(app)


def test_clicking_thumbnail_sets_overlay_path_and_closes_dialog(app):
    path = _make_png(m.OVERLAYS_DIR, "logo.png")
    app._open_asset_gallery()
    app.update_idletasks()
    thumb = _clickable_thumbs(app)[0]

    thumb.event_generate("<Button-1>", x=1, y=1)
    app.update()

    assert app.src_path2.get() == path
    assert not app._gallery_open
    assert not [w for w in app.winfo_children() if isinstance(w, m.tk.Toplevel)]


def test_reentrancy_guard_prevents_second_dialog(app):
    app._open_asset_gallery()
    app._open_asset_gallery()
    tops = [w for w in app.winfo_children() if isinstance(w, m.tk.Toplevel)]
    assert len(tops) == 1
    _close_dialog(app)


def test_grid_wraps_past_six_files_into_a_second_row(app):
    for i in range(7):
        _make_png(m.OVERLAYS_DIR, f"logo{i}.png")
    app._open_asset_gallery()
    thumbs = _clickable_thumbs(app)
    assert len(thumbs) == 7
    rows = {int(t.master.grid_info()["row"]) for t in thumbs}
    assert rows == {0, 1}
    _close_dialog(app)
