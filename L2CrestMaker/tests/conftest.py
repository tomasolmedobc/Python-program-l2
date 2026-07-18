import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


@pytest.fixture(scope="session")
def _shared_tk_app():
    # tkinterdnd2 loads its Tcl extension via tcl_findLibrary; repeatedly
    # creating/destroying Tk() instances in one process makes that lookup
    # fail intermittently on later instances (invalid command "tcl_findLibrary").
    # One shared root reused across the whole test session avoids it.
    import L2CrestMaker as m
    application = m.L2CrestApp()
    yield application
    application.destroy()


@pytest.fixture
def app(_shared_tk_app, tmp_path, monkeypatch):
    """The shared app instance, reset to a clean state and pointed at
    scratch files/folders so no test ever touches the user's real presets,
    overlays, or templates."""
    import L2CrestMaker as m

    monkeypatch.setattr(m, "PRESETS_FILE", str(tmp_path / "presets.json"))
    monkeypatch.setattr(m, "OVERLAYS_DIR", str(tmp_path / "overlays"))
    monkeypatch.setattr(m, "TEMPLATES_DIR", str(tmp_path / "templates"))
    monkeypatch.setattr(m.messagebox, "askyesno", lambda *a, **k: True)
    monkeypatch.setattr(m.messagebox, "showwarning", lambda *a, **k: None)
    monkeypatch.setattr(m.messagebox, "showerror", lambda *a, **k: None)
    monkeypatch.setattr(m.messagebox, "showinfo", lambda *a, **k: None)

    _shared_tk_app.presets = {}
    _shared_tk_app.preset_name.set("")
    _shared_tk_app.src_path2.set("")
    _shared_tk_app.preset_combo["values"] = []
    _shared_tk_app._asset_thumb_cache = {}
    _shared_tk_app._gallery_open = False
    for w in list(_shared_tk_app.winfo_children()):
        if isinstance(w, m.tk.Toplevel):
            w.destroy()
    return _shared_tk_app
