"""HyperFrames design engine (2026-11-15): the EDL design block becomes an editable HyperFrames
project. Offline: builds a project from a tiny design block and checks its structure; no render."""
from __future__ import annotations

import re
from pathlib import Path

from lib import hf_design as H


def _design():
    return {"brand": {"accent": "#F4C76B", "glow": "#6C4CF1"}, "face_y": 0.44, "matte": True, "caption_style": "phrase",
            "layout": [{"s": 0, "e": 50, "mode": "full"}, {"s": 50, "e": 100, "mode": "split"}, {"s": 100, "e": 150, "mode": "hidden"}],
            "scenes": [{"s": 50, "e": 100, "type": "Equation", "p": {"terms": [{"t": "1", "kind": "num", "at": 2}], "result": {"to": 10, "at": 10}}},
                       {"s": 100, "e": 150, "type": "AppReveal", "p": {"name": "Demo", "sub": "a line", "at": 3}}],
            "overlays": [{"s": 5, "e": 40, "type": "Halo", "behind": True, "p": {"x": 0.5, "y": 0.4, "r": 0.3}},
                         {"s": 120, "e": 140, "type": "Counter", "p": {"to": 600, "y": 0.3}}],
            "bg": [{"s": 0, "e": 30, "color": "bw"}],
            "fx": [{"at": 50, "type": "zoomblur"}, {"at": 100, "type": "leakdip"}, {"at": 0, "type": "overexpose"}]}


def test_unsupported_lists_what_only_remotion_draws():
    d = _design()
    assert H.unsupported(d) == []
    d["scenes"].append({"s": 0, "e": 5, "type": "Paywall", "p": {}})
    d["caption_style"] = "neon"
    assert H.unsupported(d) == ["scene Paywall", "caption_style neon"]


def test_build_writes_an_editable_project(tmp_path):
    for n in ("base.mp4", "fg.webm", "bw.mp4", "soft.mp4", "master.wav"):
        (tmp_path / n).write_bytes(b"x")
    caps = [{"s": 2, "e": 20, "words": [{"w": "Hello", "s": 2, "emph": False}, {"w": "world", "s": 8, "emph": True}]}]
    hf = H.build(_design(), caps, [0.66], 25.0, 1080, 1920, 150, tmp_path / "hf",
                 {"base": tmp_path / "base.mp4", "fg": tmp_path / "fg.webm", "bw": tmp_path / "bw.mp4", "soft": tmp_path / "soft.mp4",
                  "master": tmp_path / "master.wav"}, "", [True])
    root = (hf / "index.html").read_text(encoding="utf-8")
    assert 'data-composition-id="main"' in root and 'data-duration="6.0"' in root and 'window.__timelines["main"]' in root
    # every scene / overlay host id == its composition id == its file, and the file registers that timeline
    hosts = re.findall(r'<div id="([^"]+)" data-composition-id="([^"]+)" data-composition-src="compositions/([^"]+)\.html"', root)
    assert len(hosts) == 5 and all(a == b == c for a, b, c in hosts)
    for _, cid, _ in hosts:
        sub = (hf / "compositions" / f"{cid}.html").read_text(encoding="utf-8")
        assert sub.startswith("<template>") and f'window.__timelines["{cid}"]' in sub and 'id="root"' in sub
    # split span: blurred copy + feathered speaker; bg span: B&W copy from the same media time
    assert 'id="spb0"' in root and 'data-media-start="2.0" data-track-index="2" src="assets/base_soft.mp4"' in root
    assert 'src="assets/base_bw.mp4"' in root
    # the cut-out is visible only while the behind overlay is on screen in a full layout
    assert 'tl.set("#camfg", { opacity: 1 }, 0.200);' in root and 'tl.set("#camfg", { opacity: 0 }, 1.600);' in root
    cap = (hf / "compositions" / "captions.html").read_text(encoding="utf-8")
    assert 'class="in scrim"' in cap and 'class="e">world<' in cap and "top:1267px" in cap
    assert (hf / "assets" / "base.mp4").exists() and (hf / "assets" / "fg.webm").exists()


def test_fonts_inline_points_into_assets(tmp_path):
    (tmp_path / "fonts.css").write_text("@font-face { font-family: 'X'; src: url('x-0.woff2') format('woff2'); }\n", encoding="utf-8")
    assert "url('assets/fonts/x-0.woff2')" in H.fonts_inline(tmp_path)


def test_bigword_strikes_and_registers():
    cx = H.Ctx(24.0, 1080, 1920, {"accent": "#F2C14E"}, "")
    out = H.ov_bigword(cx, "o1", 2.5, {"items": [{"t": "TIME", "at": 2, "y": 0.17, "size": 330, "strikeAt": 22},
                                                    {"t": "ONE & ALL", "at": 30, "y": 0.3, "size": 200, "font": "Instrument Serif"}]})
    assert 'window.__timelines["o1"]' in out and out.count('class="bw"') == 2
    assert 'id="o1-s0"' in out and 'id="o1-s1"' not in out          # only the first word is struck
    assert "ONE &amp; ALL" in out and "font-style: italic" in out     # escaped text; the serif is set italic
    assert '"BigWord"' not in repr(H.unsupported({"overlays": [{"type": "BigWord"}]}))


def test_motion_scenes_and_box_captions():
    cx = H.Ctx(24.0, 1080, 1920, {"accent": "#FFD21F", "glow": "#6B4BFF"}, "")
    cal = H.sc_calendarblocks(cx, "s0", 1920, 7.0, {"kicker": "a & b", "blocks": [{"day": 0, "top": 0, "len": 0.25, "t": "Email", "c": "#3D7BFF"},
                                                                                 {"day": 4, "top": 0.5, "len": 0.5, "t": "Plan", "c": "#FFD21F"}], "stampAt": 100})
    assert 'window.__timelines["s0"]' in cal and cal.count('class="blk"') == 2 and "a &amp; b" in cal and "assets/icons3d/clock_color.png" in cal
    ch = H.sc_choicecards(cx, "s1", 1920, 3.0, {"cards": [{"t": "A", "icon": "rocket"}, {"t": "B", "icon": "bulb"}, {"t": "C", "icon": "star"}], "pick": 2, "pickAt": 30})
    assert ch.count('class="cc"') == 3 and "#s1-all #s1-c2" in ch
    pile = H.sc_pileup(cx, "s2", 1920, 6.0, {"items": [{"t": "One", "icon": "fire"}, {"t": "Two", "icon": "wallet"}, {"t": "Three", "icon": "rocket"}], "win": 1, "winAt": 90})
    assert pile.count('class="nc"') == 3 and pile.count('class="b1"') == 1      # one winner badge only
    assert 'y: 352' in pile                                                    # the first card ends two slots (2 x 176 px) down
    fi = H.ov_floaticons(cx, "o0", 3.0, {"items": [{"icon": "clock", "x": 0.2, "y": 0.2, "at": 1, "slashAt": 20}]})
    assert 'id="o0-s0"' in fi
    caps = [{"s": 2, "e": 30, "words": [{"w": "Your", "s": 2, "emph": False}, {"w": "priorities", "s": 8, "emph": True}]}]
    box = H.captions_box(cx, caps, [0.655], 96)
    assert "font-size:96.0px" in box and 'class="e">priorities' in box and "Montserrat" in box and 'window.__timelines["captions"]' in box
    assert H.unsupported({"caption_style": "box", "scenes": [{"type": "PileUp"}], "overlays": [{"type": "FloatIcons"}]}) == []


def test_typewall_short_word_leaves_before_the_next():
    import re as _re
    cx = H.Ctx(24.0, 1080, 1920, {}, "")
    out = H.sc_typewall(cx, "t0", 1920, 3.0, {"words": [{"t": "from", "at": 1}, {"t": "managing", "at": 5}, {"t": "TIME", "at": 16}]})
    # 'from' lives 4 frames (0.167 s): its entrance must end before its exit starts
    tin = float(_re.search(r'#t0-w0", \{ opacity: 0, scale: 1.5.*?duration: ([0-9.]+)', out).group(1))
    out_at = float(_re.search(r'#t0-w0", \{ opacity: 1.*?immediateRender: false \}, ([0-9.]+)\)', out).group(1))
    assert 1 / 24 + tin <= out_at + 1e-6
    assert 'tl.set("#t0-w0", { opacity: 0 }' in out


def test_lockup_captions_and_camera():
    cx = H.Ctx(24.0, 1080, 1920, {"accent": "#FFD21F"}, "")
    caps = [{"s": 2, "e": 40, "words": [{"w": "Your", "s": 2, "emph": False}, {"w": "priorities", "s": 8, "emph": True}, {"w": "do.", "s": 20, "emph": False}]},
            {"s": 40, "e": 60, "words": [{"w": "You", "s": 40, "emph": False}, {"w": "have", "s": 46, "emph": False}]}]
    out = H.captions_lockup(cx, caps, [0.66, 0.66], 176, ["priorities"])
    assert 'id="cp0k">priorities' in out and 'id="cp0f"' in out          # keyword + selection frame
    assert 'clipPath: "inset(-20% 100% -30% -5%)"' in out and "duration: 0.250" in out   # 6-frame wipe at 24 fps
    assert 'id="cp1k"' not in out and 'class="l1 pl"' in out             # no keyword -> one plain line, no fake keyword
    root = H.root_file(cx, 3.0, [{"s": 0, "e": 72, "mode": "full"}], [], [], [], [], 0.3, False, False, False, [], [],
                       [{"s": 0, "e": 24, "z0": 1.1, "z1": 1.2, "rot0": -1}])
    assert "scale: 1.1, rotation: -1" in root and "scale: 1.2" in root and 'tl.set("#cam", { scale: 1, rotation: 0 }, 1.0)' in root
