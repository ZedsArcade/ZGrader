"""Optional external vision-model hook.

Off by default. When ZGRADER_AI_ENABLED is set with an endpoint + model, the
pipeline asks an Ollama-compatible vision model for extra "AI-assisted"
observations and stores them alongside the deterministic analysis. It is a
descriptive *second opinion* only -- a VLM is not a calibrated grader, so the
output is always presented as lower-confidence and never feeds the numeric
score. The seam degrades to a no-op when unconfigured, and any error from the
model is swallowed so analysis never fails because the AI is unavailable.
"""

import base64
import logging
from typing import Protocol

from zgrader.config import config

logger = logging.getLogger(__name__)

_PROMPT = (
    "You are assisting a trading-card grader. Look at this single card image and briefly note any "
    "visible surface defects, creases, scratches, or edge/corner wear. Answer as a few short bullet "
    "points, or exactly 'No obvious defects.' if you see none. Do NOT invent measurements or assign "
    "a numeric grade."
)


class AIAnalyzer(Protocol):
    def analyze(self, image_png: bytes, side: str, language: str) -> list[dict]: ...


class OllamaAnalyzer:
    """Calls an Ollama-compatible /api/generate endpoint with the card image."""

    def __init__(self, endpoint: str, model: str, timeout: float) -> None:
        self.endpoint = endpoint
        self.model = model
        self.timeout = timeout

    def analyze(self, image_png: bytes, side: str, language: str) -> list[dict]:
        # Imported lazily, at point of use, so this optional seam adds no
        # import-time dependency to the app. The API imports this module
        # transitively at startup (main -> routers -> watcher -> pipeline),
        # so a module-level third-party import here would crash the whole
        # backend on any deployment that doesn't ship the package.
        import httpx

        b64 = base64.b64encode(image_png).decode("ascii")
        resp = httpx.post(
            self.endpoint,
            json={"model": self.model, "prompt": _PROMPT, "images": [b64], "stream": False},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        text = (resp.json().get("response") or "").strip()
        if not text:
            return []
        lines = [line.strip("-*• \t").strip() for line in text.splitlines()]
        return [{"note": line, "severity": "info"} for line in lines if line]


def get_analyzer() -> AIAnalyzer | None:
    """The configured analyzer, or None when the AI hook is disabled/unset."""
    if config.ai_enabled and config.ai_endpoint and config.ai_model:
        return OllamaAnalyzer(config.ai_endpoint, config.ai_model, config.ai_timeout_seconds)
    return None
