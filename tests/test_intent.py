import time

import numpy as np
from fastapi.testclient import TestClient

from core.auth import get_current_user_id
from services import intent_service

intent_service.app.dependency_overrides[get_current_user_id] = lambda: "00000000-0000-0000-0000-000000000000"


class _FakeInput:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeSession:
    def __init__(self) -> None:
        self._providers = ["DmlExecutionProvider"]

    def get_inputs(self):
        return [_FakeInput("input")]  # type: ignore

    def run(self, *_args, **_kwargs):
        return [np.array([[0.1, 0.9]], dtype=np.float32)]

    def get_providers(self):
        return self._providers


def _fake_load_model():
    intent_service._session = _FakeSession()
    return intent_service._session


def test_classify(monkeypatch):
    monkeypatch.setattr(intent_service, "load_intent_model", _fake_load_model)
    monkeypatch.setattr(intent_service, "_session", _FakeSession())

    with TestClient(intent_service.app) as client:
        start = time.perf_counter()
        response = client.post("/api/v1/voice/intents", json={"text": "Turn on the lights"})
        latency = time.perf_counter() - start

    print(f"intent latency: {latency:.3f}s")
    assert response.status_code == 200
    data = response.json()
    assert data["label"].startswith("label_")
    assert "scores" in data
