"""Create the approved neutral bass double chime; requires ffmpeg."""
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import wave

RATE = 24000
TARGET = Path(__file__).resolve().parents[1] / 'sounds/reminder-neutral-bass.flac'
DURATION = 1.85
PEAK = 0.78  # Leave headroom for playback/resampling; do not change device volume.


def render_pcm():
    samples = []
    for index in range(round(RATE * DURATION)):
        time = index / RATE
        sample = 0.0
        # Two warm G3 strikes with a G2 undertone, matching the approved preview.
        for start in (0.0, 0.8):
            end = start + 0.95
            if start <= time < end:
                elapsed = time - start
                attack = math.sin(math.pi / 2 * min(1.0, elapsed / 0.03)) ** 2
                release = math.sin(math.pi / 2 * min(1.0, (end - time) / 0.22)) ** 2
                phase = 2 * math.pi * 196 * elapsed
                tone = math.sin(phase) + 0.16 * math.sin(2 * phase) + 0.28 * math.sin(phase / 2)
                sample += attack * release * math.exp(-3.0 * elapsed) * tone
        samples.append(sample)
    gain = PEAK / max(abs(sample) for sample in samples)
    return b''.join(struct.pack('<h', round(sample * gain * 32767)) for sample in samples)


def generate():
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / 'reminder-neutral-bass.wav'
        with wave.open(str(source), 'wb') as output:
            output.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
            output.writeframes(render_pcm())
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(source),
                        '-compression_level', '8', str(TARGET)], check=True)


if __name__ == '__main__':
    generate()
