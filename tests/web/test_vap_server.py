from __future__ import annotations

from starlette.testclient import TestClient

from buddy.web import vap_server


class RecordingRunner:
    def __init__(self):
        self.seen = []

    def run_turn(self, text):
        self.seen.append(text)
        return f"spoken: {text}"


def make_client(runner, transcribe):
    vap_server.configure(runner=runner, transcribe=transcribe)
    return TestClient(vap_server.app)


def test_api_utterance_drives_run_turn():
    runner = RecordingRunner()
    client = make_client(runner, transcribe=lambda wav: "hey buddy whats up")
    resp = client.post("/api/utterance", content=b"FAKEWAVBYTES")
    assert resp.status_code == 200
    body = resp.json()
    assert body["heard"] == "hey buddy whats up"
    assert body["response"] == "spoken: hey buddy whats up"
    assert runner.seen == ["hey buddy whats up"]


def test_empty_transcription_skips_run_turn():
    runner = RecordingRunner()
    client = make_client(runner, transcribe=lambda wav: "")
    resp = client.post("/api/utterance", content=b"")
    assert resp.status_code == 200
    assert resp.json()["response"] == ""
    assert runner.seen == []
