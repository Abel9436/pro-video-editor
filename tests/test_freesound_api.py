"""fetch_sfx's Freesound API path (2026-11-20): CC0-only, rated first, key from env or ~/.pve, no network in tests."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fetch_sfx  # noqa: E402


def _hit(i, lic, rating, n):
    return {"id": i, "name": f"s{i}", "username": "u", "license": lic, "url": f"https://freesound.org/people/u/sounds/{i}/",
            "previews": {"preview-hq-mp3": f"https://cdn.freesound.org/previews/{i}-hq.mp3"}, "duration": 2.0,
            "avg_rating": rating, "num_ratings": n}


def test_api_search_keeps_cc0_and_ranks(monkeypatch):
    seen = {}

    def fake_get(url):
        seen["url"] = url
        return json.dumps({"results": [_hit(1, "http://creativecommons.org/licenses/by/4.0/", 5, 50),
                                       _hit(2, "http://creativecommons.org/publicdomain/zero/1.0/", 4.2, 30),
                                       _hit(3, "http://creativecommons.org/publicdomain/zero/1.0/", 5.0, 1),
                                       _hit(4, "http://creativecommons.org/publicdomain/zero/1.0/", 4.8, 12)]}).encode()

    monkeypatch.setattr(fetch_sfx, "get", fake_get)
    out = fetch_sfx.api_search("impact", "KEY", 0, 4, 2)
    assert [h["id"] for h in out] == [4, 2, 3]          # attribution sound dropped; well-rated with >=3 ratings first
    assert "Creative+Commons+0" in seen["url"] and "duration%3A%5B0+TO+4%5D" in seen["url"]
    assert out[0]["license_url"].endswith("/zero/1.0/")


def test_api_error_raises(monkeypatch):
    monkeypatch.setattr(fetch_sfx, "get", lambda url: b'{"detail": "Invalid token"}')
    try:
        fetch_sfx.api_search("x", "BAD", 0, 4, 1)
    except OSError as e:
        assert "Invalid token" in str(e)
    else:
        raise AssertionError("expected OSError")


def test_key_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("FREESOUND_API_KEY", "abc")
    assert fetch_sfx.api_key() == "abc"
    monkeypatch.delenv("FREESOUND_API_KEY")
    monkeypatch.setattr(fetch_sfx.Path, "home", lambda: tmp_path)
    assert fetch_sfx.api_key() is None
    (tmp_path / ".pve").mkdir()
    (tmp_path / ".pve" / "freesound_key").write_text("k2\n")
    assert fetch_sfx.api_key() == "k2"
