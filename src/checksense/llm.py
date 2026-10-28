"""LLM Client interface and Ollama adapter for CheckSense.

Provides a unified interface for local and external language model interaction,
defaulting to Ollama with 'qwen2.5:7b' as specified in MASTER_SPEC.md Section 5.6.

Architecture:
- LLMClient protocol defining generation and availability interfaces.
- OllamaClient implementing HTTP communication with local Ollama daemon.
- MockLLMClient for testing, CI pipelines, and offline evaluation.
- Graceful offline fallback: if Ollama is not installed or unreachable,
  is_available() returns False, enabling seamless template fallbacks.
"""

from __future__ import annotations

import json
import os
from typing import Any, Protocol, runtime_checkable

import requests


class LLMUnavailableError(RuntimeError):
    """Raised when an LLM operation is attempted on an unavailable model provider."""

    pass


@runtime_checkable
class LLMClient(Protocol):
    """Protocol defining the standard CheckSense LLM provider interface."""

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
    ) -> str:
        """Generate text completion from prompt.

        Args:
            prompt: User/task prompt string.
            system_prompt: Optional grounding system prompt.
            temperature: Sampling temperature (0.0 for deterministic output).

        Returns:
            Generated text string.

        Raises:
            LLMUnavailableError: If provider daemon is unreachable or model fails.
        """
        ...

    def is_available(self) -> bool:
        """Check whether provider daemon and configured model are reachable."""
        ...


class OllamaClient:
    """Ollama local model client per MASTER_SPEC.md Stage 6.

    Default model: qwen2.5:7b
    Default host: http://localhost:11434
    """

    def __init__(
        self,
        host: str | None = None,
        model: str | None = None,
        timeout: float = 10.0,
        ping_timeout: float = 1.5,
    ) -> None:
        self.host = (
            host
            or os.environ.get("CHECKSENSE_OLLAMA_HOST")
            or "http://localhost:11434"
        ).rstrip("/")
        self.model = (
            model
            or os.environ.get("CHECKSENSE_OLLAMA_MODEL")
            or "qwen2.5:7b"
        )
        self.timeout = timeout
        self.ping_timeout = ping_timeout

    def is_available(self) -> bool:
        """Check if local Ollama daemon is running."""
        try:
            resp = requests.get(
                f"{self.host}/api/tags",
                timeout=self.ping_timeout,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
    ) -> str:
        """Execute text generation via Ollama REST API.

        Raises:
            LLMUnavailableError: If Ollama daemon is not running or request fails.
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            resp = requests.post(
                f"{self.host}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                raise LLMUnavailableError(
                    f"Ollama returned HTTP status {resp.status_code}: {resp.text}"
                )
            data = resp.json()
            return str(data.get("response", "")).strip()
        except requests.exceptions.RequestException as e:
            raise LLMUnavailableError(
                f"Failed to communicate with Ollama at {self.host}: {e}"
            ) from e
        except json.JSONDecodeError as e:
            raise LLMUnavailableError(
                f"Invalid JSON returned by Ollama: {e}"
            ) from e


class MockLLMClient:
    """Mock LLM client for deterministic testing, CI, and validation."""

    def __init__(
        self,
        responses: dict[str, str] | list[str] | str | None = None,
        available: bool = True,
    ) -> None:
        self.responses = responses
        self.available = available
        self.call_history: list[dict[str, Any]] = []
        self._index = 0

    def is_available(self) -> bool:
        return self.available

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.0,
    ) -> str:
        if not self.available:
            raise LLMUnavailableError("Mock LLM client is set to unavailable.")

        self.call_history.append({
            "prompt": prompt,
            "system_prompt": system_prompt,
            "temperature": temperature,
        })

        if self.responses is None:
            return ""

        if isinstance(self.responses, str):
            return self.responses

        if isinstance(self.responses, list):
            if not self.responses:
                return ""
            resp = self.responses[self._index % len(self.responses)]
            self._index += 1
            return resp

        if isinstance(self.responses, dict):
            # Key matching (substring)
            for key, val in self.responses.items():
                if key in prompt:
                    return val
            # Fallback to default key or empty
            return self.responses.get("default", "")

        return ""


def get_default_llm_client() -> LLMClient:
    """Instantiate the configured default LLM client."""
    provider = os.environ.get("CHECKSENSE_LLM_PROVIDER", "ollama").lower()
    if provider == "mock":
        return MockLLMClient()
    return OllamaClient()

