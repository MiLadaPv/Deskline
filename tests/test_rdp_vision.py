from __future__ import annotations

import json

from deskline import rdp_vision


def test_vision_enabled_requires_pro_consent_key():
    cfg = {
        "rdp_vision_enabled": True,
        "rdp_vision_consent": True,
        "rdp_vision_api_key": "sk-test",
    }
    assert rdp_vision.vision_enabled(cfg, is_pro=True) is True
    assert rdp_vision.vision_enabled(cfg, is_pro=False) is False
    cfg["rdp_vision_consent"] = False
    assert rdp_vision.vision_enabled(cfg, is_pro=True) is False


def test_interval_clamped():
    assert rdp_vision.interval_sec({"rdp_vision_interval_sec": 30}) == 120
    assert rdp_vision.interval_sec({"rdp_vision_interval_sec": 999}) == 300
    assert rdp_vision.interval_sec({"rdp_vision_interval_sec": 180}) == 180


def test_pending_clear(monkeypatch):
    rdp_vision.clear_pending()
    assert rdp_vision.get_pending() is None
    rdp_vision._pending = rdp_vision.VisionSuggestion(
        label="1C",
        confidence=0.9,
        brand_hint="1C",
        host_hint="server",
        created_at=1.0,
        session_id=42,
        frame_hash="abc",
    )
    pending = rdp_vision.get_pending()
    assert pending["label"] == "1C"
    assert pending["session_id"] == 42
    rdp_vision.clear_pending()
    assert rdp_vision.get_pending() is None


def test_call_vision_parses_json(monkeypatch):
    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            payload = {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"label": "Cursor", "confidence": 0.88, "brand_hint": "Cursor"}
                            )
                        }
                    }
                ]
            }
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setattr(rdp_vision.urllib.request, "urlopen", lambda *a, **k: FakeResp())
    out = rdp_vision._call_vision_api(
        {
            "rdp_vision_api_key": "sk-x",
            "rdp_vision_base_url": "https://example.test/v1",
            "rdp_vision_model": "gpt-4o-mini",
        },
        b"fakepng",
    )
    assert out["label"] == "Cursor"
    assert out["confidence"] == 0.88
