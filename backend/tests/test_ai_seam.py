import numpy as np

from zgrader.analysis import ai, pipeline
from zgrader.config import config


def test_get_analyzer_none_when_disabled(monkeypatch):
    monkeypatch.setattr(config, "ai_enabled", False)
    assert ai.get_analyzer() is None


def test_get_analyzer_configured(monkeypatch):
    monkeypatch.setattr(config, "ai_enabled", True)
    monkeypatch.setattr(config, "ai_endpoint", "http://ollama:11434/api/generate")
    monkeypatch.setattr(config, "ai_model", "llava")
    assert isinstance(ai.get_analyzer(), ai.OllamaAnalyzer)


class _StubAnalyzer:
    def analyze(self, image_png, side, language):
        return [{"note": "visible crease along the left third", "severity": "info"}]


class _RaisingAnalyzer:
    def analyze(self, image_png, side, language):
        raise RuntimeError("model is down")


def test_run_ai_stores_observations(monkeypatch):
    monkeypatch.setattr(ai, "get_analyzer", lambda: _StubAnalyzer())
    img = np.zeros((20, 20, 3), dtype=np.uint8)
    out = pipeline._run_ai_analysis(img, "front", "en", "SUB-00001")
    assert out == [{"note": "visible crease along the left third", "severity": "info"}]


def test_run_ai_swallows_model_errors(monkeypatch):
    # An unavailable/erroring model must never fail the analysis pipeline.
    monkeypatch.setattr(ai, "get_analyzer", lambda: _RaisingAnalyzer())
    img = np.zeros((20, 20, 3), dtype=np.uint8)
    assert pipeline._run_ai_analysis(img, "front", "en", "SUB-00001") == []


def test_run_ai_noop_when_unconfigured(monkeypatch):
    monkeypatch.setattr(ai, "get_analyzer", lambda: None)
    img = np.zeros((20, 20, 3), dtype=np.uint8)
    assert pipeline._run_ai_analysis(img, "front", "en", "SUB-00001") == []
