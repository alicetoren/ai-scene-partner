"""Conservative tail trimming and volume matching for 16-bit PCM WAV speech."""

from array import array
from io import BytesIO
import logging
import math
import struct
import sys
import wave


# About -60 dBFS: preserve even very quiet speech. Never remove internal pauses.
SILENCE_PEAK = 32
MINIMUM_TAIL_SECONDS = 0.3
RETAIN_TAIL_SECONDS = 0.15
logger = logging.getLogger(__name__)

# One gain for the whole line: approximate loudness matching, not a compressor.
TARGET_RMS = 32768 * 10 ** (-20 / 20)
MIN_ACTIVE_RMS = 32768 * 10 ** (-50 / 20)
PEAK_CEILING = int(32767 * 10 ** (-1 / 20))
MAX_GAIN = 2.0
MIN_GAIN = 0.5
RMS_WINDOW_SECONDS = 0.02


def normalize_volume(audio: bytes) -> bytes:
    """Match active-window RMS conservatively while preserving waveform/dynamics."""
    try:
        with wave.open(BytesIO(audio), "rb") as source:
            if source.getsampwidth() != 2 or source.getcomptype() != "NONE":
                return audio
            params = source.getparams()
            samples = array("h", source.readframes(source.getnframes()))
        if sys.byteorder != "little":
            samples.byteswap()
        window_size = max(1, round(params.framerate * RMS_WINDOW_SECONDS)) * params.nchannels
        active_energy = 0
        active_count = 0
        for start in range(0, len(samples), window_size):
            window = samples[start:start + window_size]
            energy = sum(sample * sample for sample in window)
            if energy / len(window) >= MIN_ACTIVE_RMS ** 2:
                active_energy += energy
                active_count += len(window)
        if not active_count:
            return audio  # Never amplify silence or very quiet noise.
        rms = math.sqrt(active_energy / active_count)
        peak = max(abs(sample) for sample in samples)
        gain = min(MAX_GAIN, max(MIN_GAIN, TARGET_RMS / rms), PEAK_CEILING / peak)
        if abs(gain - 1) < 0.001:
            return audio
        # Peak-limited linear gain preserves relative channel levels; no hard clipping.
        adjusted = array("h", (round(sample * gain) for sample in samples))
        if sys.byteorder != "little":
            adjusted.byteswap()
        result = BytesIO()
        with wave.open(result, "wb") as target:
            target.setparams(params._replace(nframes=len(samples) // params.nchannels))
            target.writeframes(adjusted.tobytes())
        return result.getvalue()
    except (wave.Error, EOFError, ValueError, struct.error, OverflowError) as error:
        logger.warning("Speech volume processing skipped: type=%s", type(error).__name__)
        return audio


def trim_silent_tail(audio: bytes) -> bytes:
    try:
        with wave.open(BytesIO(audio), "rb") as source:
            if source.getsampwidth() != 2 or source.getcomptype() != "NONE":
                return audio
            params = source.getparams()
            frames = source.readframes(source.getnframes())
        samples = array("h", frames)
        if sys.byteorder != "little":
            samples.byteswap()
        last_audible = next(
            (index // params.nchannels for index in range(len(samples) - 1, -1, -1)
             if abs(samples[index]) > SILENCE_PEAK),
            None,
        )
        frame_count = len(frames) // (params.nchannels * 2)
        keep_frames = frame_count
        # Preserve all-silent audio and short tails; normalize placeholder headers too.
        if last_audible is not None:
            tail_frames = frame_count - last_audible - 1
            if tail_frames >= params.framerate * MINIMUM_TAIL_SECONDS:
                keep_frames = last_audible + 1 + round(params.framerate * RETAIN_TAIL_SECONDS)
        if keep_frames == params.nframes:
            return audio
        result = BytesIO()
        with wave.open(result, "wb") as target:
            # Provider WAVs can declare an unknown (0xffffffff) data length.
            # Copying that nframes can overflow RIFF's uint32 size when writing.
            target.setparams(params._replace(nframes=keep_frames))
            target.writeframes(frames[:keep_frames * params.nchannels * 2])
        return result.getvalue()
    except (wave.Error, EOFError, ValueError, struct.error, OverflowError) as error:
        # Optional post-processing must not discard otherwise usable provider audio.
        logger.warning("Speech audio post-processing skipped: type=%s", type(error).__name__)
        return audio
