"""Pipeline services — Ambient background sound mixing.

Loads ambient MP3 files from app/assets/ambient/, resamples them to the
pipeline sample rate, and mixes them into outgoing TTS audio frames at a
configurable volume so the caller hears realistic background noise throughout
the call.

The sound loops seamlessly — the playback position advances per-chunk and
wraps around without clicking or restarting.

Usage:
    mixer = BackgroundSoundMixer(sound_key="coffee_shop", volume=0.15, sample_rate=16000)
    # Returns a Pipecat FrameProcessor; insert after TTS, before transport.output()
    processor = mixer.get_processor()
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import ClassVar

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

# Directory containing the bundled ambient MP3 files.
# ambient.py lives at app/modules/pipeline/services/ambient.py
# so 4 parents up reaches app/, then we descend into assets/ambient/.
_ASSETS_DIR = Path(__file__).parent.parent.parent.parent / "assets" / "ambient"

# Maps frontend dropdown value → filename in the assets directory.
SOUND_FILE_MAP: dict[str, str] = {
    "call_center": "Call Center.mp3",
    "coffee_shop": "Coffee Shop.mp3",
    "convention_hall": "Convention hall.mp3",
    "keyboard_typing": "Keyboard Typing.mp3",
    "mountain_outdoor": "Mountain Outdoor.mp3",
    "static_noise": "Static Noise.mp3",
    "summer_outdoor": "Summer Outdoor.mp3",
}

# Maximum allowed background volume (cap prevents drowning out TTS voice).
_MAX_VOLUME = 0.5
# Target pipeline sample rate (matches LiveKit transport default).
_DEFAULT_SAMPLE_RATE = 16000


def _load_and_resample(file_path: Path, target_rate: int) -> np.ndarray:
    """Load an MP3 and resample to *target_rate* Hz, returning int16 PCM.

    Returns a 1-D int16 numpy array (mono).  Stereo files are
    down-mixed to mono before resampling.
    """
    import soundfile as sf
    from scipy.signal import resample_poly
    from math import gcd

    data, src_rate = sf.read(str(file_path), dtype="float32", always_2d=False)
    # Down-mix stereo → mono
    if data.ndim == 2:
        data = data.mean(axis=1)

    if src_rate != target_rate:
        g = gcd(src_rate, target_rate)
        up, down = target_rate // g, src_rate // g
        data = resample_poly(data, up, down).astype(np.float32)

    # Normalise to [-1, 1] so the volume coefficient is predictable.
    peak = np.abs(data).max()
    if peak > 0:
        data /= peak

    return (data * 32767).astype(np.int16)


# Module-level PCM cache so we only decode + resample each file once per process.
_pcm_cache: dict[tuple[str, int], np.ndarray] = {}


def _get_pcm(sound_key: str, sample_rate: int) -> np.ndarray | None:
    """Return cached PCM for *sound_key* at *sample_rate*, loading on first call."""
    cache_key = (sound_key, sample_rate)
    if cache_key in _pcm_cache:
        return _pcm_cache[cache_key]

    filename = SOUND_FILE_MAP.get(sound_key)
    if not filename:
        logger.warning("ambient_unknown_sound_key", sound_key=sound_key)
        return None

    file_path = _ASSETS_DIR / filename
    if not file_path.exists():
        logger.warning("ambient_file_not_found", path=str(file_path))
        return None

    try:
        pcm = _load_and_resample(file_path, sample_rate)
        _pcm_cache[cache_key] = pcm
        logger.info(
            "ambient_loaded",
            sound_key=sound_key,
            sample_rate=sample_rate,
            duration_s=round(len(pcm) / sample_rate, 1),
        )
        return pcm
    except Exception:
        logger.warning("ambient_load_failed", sound_key=sound_key, exc_info=True)
        return None


class BackgroundSoundMixer:
    """Mixes looping ambient audio into outgoing TTS frames.

    Wraps a Pipecat FrameProcessor that intercepts ``TTSAudioRawFrame``
    values, mixes background audio into each chunk at the requested
    volume, and passes the blended frame downstream.

    The background PCM loops seamlessly — the position counter advances
    across frames and wraps around at the end of the buffer, so there
    are no clicks or restarts at loop boundaries.

    Args:
        sound_key:   One of the keys in SOUND_FILE_MAP (e.g. "coffee_shop").
        volume:      Mix ratio in [0.05, 0.5].  0.15 (15 %) is a good default.
        sample_rate: Pipeline audio sample rate (default 16 000 Hz).
    """

    def __init__(
        self,
        sound_key: str,
        volume: float,
        sample_rate: int = _DEFAULT_SAMPLE_RATE,
    ) -> None:
        self._sound_key = sound_key
        self._volume = max(0.05, min(float(volume), _MAX_VOLUME))
        self._sample_rate = sample_rate
        self._pcm: np.ndarray | None = _get_pcm(sound_key, sample_rate)

    def get_processor(self) -> object:
        """Return a Pipecat FrameProcessor that mixes ambient audio.

        Returns a passthrough processor when the sound file could not be
        loaded, so the pipeline continues to work without background sound.
        """
        from pipecat.processors.frame_processor import FrameProcessor

        if self._pcm is None:
            # No audio loaded — create a transparent no-op processor.
            class _PassthroughProcessor(FrameProcessor):
                async def process_frame(self_inner, frame: object, direction: object) -> None:  # noqa: N805
                    await super(_PassthroughProcessor, self_inner).process_frame(frame, direction)
                    await self_inner.push_frame(frame, direction)

            return _PassthroughProcessor()

        pcm = self._pcm
        volume = self._volume

        class _MixerProcessor(FrameProcessor):
            _pos: int = 0  # current read position in pcm buffer

            async def process_frame(self_inner, frame: object, direction: object) -> None:  # noqa: N805
                await super(_MixerProcessor, self_inner).process_frame(frame, direction)
                from pipecat.frames.frames import TTSAudioRawFrame

                if isinstance(frame, TTSAudioRawFrame):
                    try:
                        voice = np.frombuffer(frame.audio, dtype=np.int16).copy().astype(np.float32)
                        n = len(voice)
                        buf_len = len(pcm)

                        # Gather background samples, wrapping around the buffer.
                        pos = self_inner._pos
                        if pos + n <= buf_len:
                            bg = pcm[pos : pos + n].astype(np.float32)
                            self_inner._pos = (pos + n) % buf_len
                        else:
                            first = buf_len - pos
                            bg = np.concatenate([pcm[pos:], pcm[: n - first]]).astype(np.float32)
                            self_inner._pos = n - first

                        # bg is already in int16 range [-32768, 32767], so just
                        # scale by the volume coefficient directly.
                        mixed = np.clip(
                            voice + bg * volume,
                            -32768,
                            32767,
                        ).astype(np.int16)

                        frame = TTSAudioRawFrame(
                            audio=mixed.tobytes(),
                            sample_rate=frame.sample_rate,
                            num_channels=frame.num_channels,
                        )
                    except Exception:
                        pass  # Pass original frame on any error

                await self_inner.push_frame(frame, direction)

        return _MixerProcessor()


def resolve_background_sound(agent: object) -> tuple[str, float] | None:
    """Extract (sound_key, volume) from agent config or return None.

    Reads ``agent.config.settings.speech.backgroundSound`` and
    ``agent.config.settings.speech.backgroundSoundVolume``.
    Returns None when sound is "none" or absent.
    """
    try:
        config = getattr(agent, "config", None) or {}
        settings = config.get("settings") if isinstance(config, dict) else None
        if not isinstance(settings, dict):
            return None
        speech = settings.get("speech")
        if not isinstance(speech, dict):
            return None
        sound_key = speech.get("backgroundSound", "none")
        if not sound_key or sound_key == "none":
            return None
        volume = float(speech.get("backgroundSoundVolume", 0.15))
        return sound_key, max(0.05, min(volume, _MAX_VOLUME))
    except Exception:
        return None
