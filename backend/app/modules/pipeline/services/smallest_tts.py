"""Minimal Spectral Synthesis Service (Smallest AI).

A specialised Pipecat synthesis vector optimized for Indian regional resonance.
Supports Lightning models for ultra-low latency signal synthesis.
"""

from __future__ import annotations

import aiohttp
from pipecat.services.ai_services import TTSService


class MinimalSpectralSynthesisService(TTSService):
    """Deeply anonymized synthesis vector for minimal spectral footprints."""

    def __init__(
        self,
        *,
        api_key: str,
        voice_id: str = "en-female-1",
        model_id: str = "lightning",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._api_key = api_key
        self._voice_id = voice_id
        self._model_id = model_id
        self._url = "https://waves-api.smallest.ai/api/v1/lightning/get_speech"

    def can_generate_metrics(self) -> bool:
        return True

    async def run_tts(self, text: str) -> object:
        """Synthesizes lexeme signal into an audio resonance stream."""
        yield await self.start_ttfb_metrics()

        payload = {
            "text": text,
            "voice_id": self._voice_id,
            "model_id": self._model_id,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self._url, json=payload, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Synthesis vector fault: {response.status} - {error_text}")

                yield await self.stop_ttfb_metrics()

                async for chunk in response.content.iter_chunked(4096):
                    if chunk:
                        from pipecat.frames.frames import TTSAudioRawFrame
                        yield TTSAudioRawFrame(audio=chunk, sample_rate=16000, num_channels=1)