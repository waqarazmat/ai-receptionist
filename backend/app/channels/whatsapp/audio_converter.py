"""Audio format conversion via ffmpeg subprocess.

All heavy work runs in asyncio.to_thread so the event loop is never blocked.
ffmpeg (with libopus) must be available in PATH.
  - Railway / Nixpacks: add `ffmpeg` to nixpacks.toml packages.
  - Local dev: `brew install ffmpeg` / `apt install ffmpeg`.
"""

import asyncio
import subprocess
from pathlib import Path

import structlog

logger = structlog.get_logger()


class AudioConversionError(Exception):
    """ffmpeg failed, timed-out, or isn't installed."""


async def to_wav_16k_mono(input_path: Path, output_path: Path) -> None:
    """Convert any audio (ogg/opus, mp4, webm …) to 16 kHz mono WAV.

    This is the format Whisper-family STT APIs accept with the best accuracy.
    Runs ffmpeg in a thread executor so the event loop stays free.
    """
    await asyncio.to_thread(
        _run_ffmpeg,
        input_path,
        output_path,
        ["-ar", "16000", "-ac", "1"],
    )
    logger.info("audio_converted_to_wav", src=str(input_path), dst=str(output_path))


async def to_ogg_opus_mono(input_path: Path, output_path: Path) -> None:
    """Convert TTS output (mp3, wav …) to WhatsApp-compatible OGG/OPUS mono.

    Meta requires audio/ogg with the opus codec and a mono channel for
    voice-message delivery. 48 kHz is the native opus sample rate.
    """
    await asyncio.to_thread(
        _run_ffmpeg,
        input_path,
        output_path,
        ["-ar", "48000", "-ac", "1", "-c:a", "libopus", "-b:a", "64k"],
    )
    logger.info("audio_converted_to_ogg_opus", src=str(input_path), dst=str(output_path))


async def probe_duration_seconds(audio_path: Path) -> float:
    """Return the audio duration via ffprobe (runs in thread). Returns 0.0 if
    ffprobe fails — callers should treat that as 'unknown, allow through'."""
    try:
        return await asyncio.to_thread(_ffprobe_duration, audio_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ffprobe_duration_failed", path=str(audio_path), error=str(exc))
        return 0.0


# ── internals ──────────────────────────────────────────────────────────────


def _run_ffmpeg(input_path: Path, output_path: Path, extra_args: list[str]) -> None:
    cmd = [
        "ffmpeg",
        "-y",          # overwrite output without prompting
        "-i", str(input_path),
        *extra_args,
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired as exc:
        raise AudioConversionError("ffmpeg timed out after 60 s") from exc
    except FileNotFoundError as exc:
        raise AudioConversionError(
            "ffmpeg not found — install ffmpeg on the server (see audio_converter.py header)"
        ) from exc
    if result.returncode != 0:
        # Keep stderr bounded — it can be verbose on some inputs.
        raise AudioConversionError(
            f"ffmpeg exited {result.returncode}: {result.stderr[-600:]}"
        )


def _ffprobe_duration(audio_path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        raise AudioConversionError(f"ffprobe failed: {result.stderr}")
    return float(result.stdout.strip() or "0")
