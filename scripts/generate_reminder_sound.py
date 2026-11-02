"""Create the original, soft descending reminder cue; requires ffmpeg."""
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import wave

RATE = 48000
TARGET = Path(__file__).resolve().parents[1] / 'sounds/reminder-soft.flac'


def generate():
    frames = bytearray()
    for index in range(round(RATE * 0.78)):
        time = index / RATE
        sample = 0.0
        for start, end, frequency in ((0.0, 0.28, 392.0), (0.32, 0.72, 330.0)):
            if start <= time < end:
                elapsed = time - start
                attack = math.sin(math.pi / 2 * min(1.0, elapsed / 0.04)) ** 2
                release = math.sin(math.pi / 2 * min(1.0, (end - time) / 0.18)) ** 2
                sample = 0.15 * attack * release * math.sin(2 * math.pi * frequency * elapsed)
        frames.extend(struct.pack('<h', round(sample * 32767)))
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / 'reminder-soft.wav'
        with wave.open(str(source), 'wb') as output:
            output.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
            output.writeframes(frames)
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(source),
                        '-compression_level', '8', str(TARGET)], check=True)


if __name__ == '__main__':
    generate()
