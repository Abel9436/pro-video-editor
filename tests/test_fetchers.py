"""fetch_fontet.py / fetch_3dicons.py parsing and licence gates: offline, synthetic, 2026-11-17."""
from __future__ import annotations

import fetch_3dicons as I
import fetch_fontet as F

CAT = [{"name": "Menbere", "slug": "menbere", "licenses": [{"name": "SIL Open Font License"}],
        "file": {"url": "/uploads/Menbere_Variable.ttf"}, "staticFiles": [], "isVariableFont": True},
       {"name": "Nokia Pure Headline", "slug": "nokia", "licenses": [{"name": "Commercial"}], "file": {"url": "/u/n.ttf"}},
       {"name": "Unlisted", "slug": "unl", "licenses": [], "file": {"url": "/u/x.ttf"}},
       {"name": "Mulat Addis", "slug": "mulat", "licenses": [{"name": "SIL Open Font License "}],
        "file": {"url": "/u/Mulat_Regular.ttf"}, "staticFiles": [{"url": "/u/Mulat_Bold.ttf"}, {"url": "/u/Mulat_Regular.ttf"}]}]


def test_only_ofl_passes_the_gate():
    assert [f["name"] for f in CAT if F.is_ofl(f)] == ["Menbere", "Mulat Addis"]


def test_non_ofl_is_refused_without_download(tmp_path, monkeypatch):
    monkeypatch.setattr(F, "fetch", lambda url: (_ for _ in ()).throw(AssertionError("must not download")))
    res = F.get_fonts(tmp_path, ["Nokia Pure Headline", "Unlisted", "nope"], CAT)
    assert not res["ok"] and len(res["failed"]) == 3
    assert "not SIL OFL" in res["failed"][0]["error"] and "not in the font.et catalogue" in res["failed"][2]["error"]


def test_files_dedup_and_weights():
    assert F.files_of(CAT[3]) == ["/u/Mulat_Regular.ttf", "/u/Mulat_Bold.ttf"]
    assert F.weight_of("Mulat_Bold", None) == "700" and F.weight_of("X_ExtraBold", None) == "800"
    assert F.weight_of("Anything", (100, 700)) == "100 700"


def test_get_writes_css_licence_and_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(F, "fetch", lambda url: b"\x00\x01\x00\x00" + b"0" * 64)
    res = F.get_fonts(tmp_path, ["Mulat Addis"], CAT)
    css = (tmp_path / "fonts" / "fonts.css").read_text(encoding="utf-8")
    assert res["ok"] and css.count("@font-face") == 2 and "font-weight: 700" in css
    assert (tmp_path / "fonts" / "LICENSE.mulat.txt").exists()
    F.get_fonts(tmp_path, ["Mulat Addis"], CAT)                       # second run must not duplicate
    assert (tmp_path / "fonts" / "fonts.css").read_text(encoding="utf-8").count("/* font.et: Mulat Addis */") == 1
    import json
    led = json.loads((tmp_path / "licenses.json").read_text(encoding="utf-8"))["assets"]
    assert [x["id"] for x in led] == ["font:fontet:mulat"]


def test_non_font_bytes_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(F, "fetch", lambda url: b"<html>not found</html>")
    assert not F.get_fonts(tmp_path, ["Menbere"], CAT)["ok"]


def test_3dicons_meta_and_png():
    md = "---\nid: 31\nfile-slug: crown\ncolor: https://cdn/x/crow-dynamic-color.png\npremium: https://cdn/p.png\n---\nbody"
    m = I.parse_meta(md)
    assert m["color"].endswith("crow-dynamic-color.png") and m["file-slug"] == "crown"
    assert I.is_png(b"\x89PNG\r\n\x1a\nrest") and not I.is_png(b"<?xml")
