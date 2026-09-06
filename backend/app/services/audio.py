"""Conservative tail trimming for provider-generated 16-bit PCM WAV audio."""

from array import array
from io import BytesIO
import logging
import struct
import sys
import wave


# About -60 dBFS: preserve even very quiet speech. Never remove internal pauses.
SILENCE_PEAK = 32
MINIMUM_TAIL_SECONDS = 0.3
RETAIN_TAIL_SECONDS = 0.15
logger = logging.getLogger(__name__)


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
