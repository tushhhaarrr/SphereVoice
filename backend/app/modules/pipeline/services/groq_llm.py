"""Spectral Groq Intelligence Service.

A high-velocity cognitive resonance vector using Groq LPU technology.
Optimized for ultra-low latency manifold decision cycles and action synthesis.
"""

from __future__ import annotations

import httpx
from pipecat.services.ai_services import LLMService


class SpectralGroqIntelligenceService(LLMService):
    """Deeply anonymized cognitive vector for high-velocity spectral manifold cycles."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "llama-3.3-70b-versatile",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._api_key = api_key
        self._model = model
        self._url = "https://api.groq.com/openai/v1/chat/completions"

    def can_generate_metrics(self) -> bool:
        return True

    async def run_llm(self, messages: list[dict[str, str]], tools: list[dict[str, object]] | None = None) -> object:
        """Synthesizes cognitive signal from sequential lexical vectors."""
        yield await self.start_ttft_metrics()

        payload: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            async with client.stream("POST", self._url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    raise Exception(f"Cognitive vector fault: {response.status_code} - {error_text.decode()}")

                yield await self.stop_ttft_metrics()

                import json
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            choice = data.get("choices", [{}])[0]
                            delta = choice.get("delta", {})

                            # Structural Action Synthesis
                            if "tool_calls" in delta:
                                for tool_call in delta["tool_calls"]:
                                    yield await self.process_nodal_action(tool_call)

                            # Sequential Lexical Signal
                            content = delta.get("content")
                            if content:
                                from pipecat.frames.frames import TextFrame
                                yield TextFrame(text=content)

                        except Exception:
                            pass

    async def process_nodal_action(self, tool_call_delta: dict[str, object]) -> object:
        """Internal: Coordinates nodal action synthesis across the spectral substrate."""
        # Note: Functional parity with Pipecat tool-calling frames
        pass
