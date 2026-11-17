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


# ---- fetch_music (Mixkit) --------------------------------------------------------------------------
LISTING = """<html><a href="/license/#musicFree">licence</a>
<div data-test-id="audio-player" data-controller="audio-player"
 data-audio-player-preview-url-value="https://assets.mixkit.co/music/623/623.mp3" data-audio-player-item-id-value="623">
 <div class="item-grid-card__meta"><h2 class="item-grid-card__title"> Deep Urban </h2>
 <p class="item-grid-music-preview__author"> by Eugenio Mininni </p>
 <a class="meta-links__link" data-global--meta-links-target="link" href="/free-stock-music/house/">House</a>
 <div class="item-grid-music-preview__meta-time" data-test-id="duration"> 4:49 </div></div>
<div data-test-id="audio-player" data-controller="audio-player"
 data-audio-player-preview-url-value="https://assets.mixkit.co/music/7/7.mp3" data-audio-player-item-id-value="7">
 <h2 class="item-grid-card__title"> Short </h2><div data-test-id="duration"> 0:12 </div></div></html>"""


def test_music_listing_parses_tracks():
    import fetch_music as fm
    items = fm.parse_listing(LISTING)
    assert [x["id"] for x in items] == ["623", "7"]
    assert items[0]["title"] == "Deep Urban" and items[0]["author"] == "Eugenio Mininni"
    assert items[0]["duration_s"] == 289 and items[0]["tags"] == ["House"]


def test_music_search_filters_length_and_requires_licence(monkeypatch):
    import fetch_music as fm
    monkeypatch.setattr(fm, "fetch", lambda u: LISTING.encode())
    r = fm.search("workout", 30)
    assert r["ok"] and [x["id"] for x in r["results"]] == ["623"]
    monkeypatch.setattr(fm, "fetch", lambda u: LISTING.replace("#musicFree", "").encode())
    r = fm.search("workout", 30)
    assert not r["ok"] and all("licence" in t for t in r["tried"])
