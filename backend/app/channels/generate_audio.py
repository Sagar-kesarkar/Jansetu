"""Generate 8 kHz mono 16-bit PCM WAV prompt audio assets.

Narrowband telephony format (8000 Hz, 1 channel, 16-bit signed PCM).
Zero external tool dependencies — runs anywhere with Python standard library.
"""
from __future__ import annotations

import math
from pathlib import Path
import struct
import wave

from app.channels.prompts import DIGIT_WORDS, PROMPTS
from app.config import get_settings


def synthesize_narrowband_tone(
    filename: Path,
    duration_sec: float = 0.8,
    freq_hz: float = 440.0,
    sample_rate: int = 8000,
    volume: float = 0.5,
) -> None:
    """Write an 8 kHz mono 16-bit PCM WAV file."""
    filename.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(duration_sec * sample_rate)
    max_val = 32767

    with wave.open(str(filename), "wb") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)

        # Smooth envelope (attack and decay) to prevent clicks
        fade_samples = int(sample_rate * 0.05)
        raw_bytes = bytearray()

        for i in range(num_samples):
            # Sine wave with harmonics for warm telephony audio
            t = float(i) / sample_rate
            sample = math.sin(2.0 * math.pi * freq_hz * t)
            # Add subtle harmonic
            sample += 0.25 * math.sin(2.0 * math.pi * (freq_hz * 1.5) * t)

            # Envelope
            if i < fade_samples:
                envelope = float(i) / fade_samples
            elif i > num_samples - fade_samples:
                envelope = float(num_samples - i) / fade_samples
            else:
                envelope = 1.0

            val = int(sample * envelope * volume * max_val)
            val = max(-max_val, min(max_val, val))
            raw_bytes.extend(struct.pack("<h", val))

        wav_file.writeframes(raw_bytes)


def generate_all_prompts(target_dir: Path | None = None) -> int:
    """Generate prompt audio assets in data/ivr_prompts."""
    base_dir = target_dir or Path(get_settings().ivr_prompt_dir)
    count = 0

    # 1. Base Prompts per language
    # Assign distinctive pitch frequencies for each prompt type
    freq_map = {
        "GREETING_LANG_MENU": 523.25,  # C5
        "RECORD_NEED_BEEP": 880.00,    # A5 beep
        "PROCESSING_WAIT": 392.00,     # G4
        "CONFIRMATION_NOTICE": 587.33, # D5
        "DOCKET_REF_INTRO": 493.88,    # B4
        "REPEAT_MENU": 440.00,         # A4
        "THANK_YOU": 523.25,           # C5
        "NO_INPUT_RETRY": 349.23,      # F4
        "INVALID_OPTION_RETRY": 329.63,# E4
        "TIMEOUT_HANGUP": 293.66,      # D4
        "ERROR_MSG": 261.63,           # C4
    }

    for prompt_key, lang_dict in PROMPTS.items():
        freq = freq_map.get(prompt_key, 440.0)
        for lang in lang_dict.keys():
            wav_path = base_dir / lang / f"{prompt_key}.wav"
            synthesize_narrowband_tone(wav_path, duration_sec=1.0, freq_hz=freq)
            count += 1

    # 2. Digit audio prompts (0-9)
    digit_freqs = {
        "0": 261.63, "1": 293.66, "2": 329.63, "3": 349.23, "4": 392.00,
        "5": 440.00, "6": 493.88, "7": 523.25, "8": 587.33, "9": 659.25,
    }
    for digit, freq in digit_freqs.items():
        digit_path = base_dir / "digits" / f"{digit}.wav"
        synthesize_narrowband_tone(digit_path, duration_sec=0.5, freq_hz=freq)
        count += 1

    return count


if __name__ == "__main__":
    generated = generate_all_prompts()
    print(f"Successfully generated {generated} telephony audio prompt files.")
