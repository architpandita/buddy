from __future__ import annotations

from buddy.loop.build import build_turn_runner


def test_builds_companion_runner(tmp_path, monkeypatch):
    from buddy import config

    monkeypatch.setattr(config, "VAP_SANDBOX_DIR", tmp_path / "sb")
    monkeypatch.setattr(config, "VAP_STATE_DIR", tmp_path / "st")
    monkeypatch.setattr(config, "VAP_MEMORY_DIR", tmp_path / "mem")
    runner = build_turn_runner("companion", speak=lambda _t: None)
    assert runner._agent.name == "companion"
    assert runner._agent.model
    assert (tmp_path / "sb").is_dir()
    assert runner._memory is not None


def test_engine_env_never_carries_api_key(tmp_path, monkeypatch):
    """End-to-end guardrail (plan §7): the real engine strips ANTHROPIC_API_KEY."""
    from buddy import config
    from tests.conftest import FakeRunner, StubAgent, stream_json

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-leak")
    monkeypatch.setattr(config, "VAP_SANDBOX_DIR", tmp_path / "sb")
    monkeypatch.setattr(config, "VAP_STATE_DIR", tmp_path / "st")
    monkeypatch.setattr(config, "VAP_MEMORY_DIR", tmp_path / "mem")

    runner = build_turn_runner("companion", speak=lambda _t: None)
    fake = FakeRunner(stdout=stream_json())
    runner._engine._runner = fake
    runner.run_turn("hello")
    assert "ANTHROPIC_API_KEY" not in fake.last.env
