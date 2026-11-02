"""Create a clear, gently enveloped three-note reminder chime; requires ffmpeg."""
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import wave

RATE = 48000
TARGET = Path(__file__).resolve().parents[1] / 'sounds/reminder-chime.flac'
DURATION = 1.3
PEAK = 0.82  # Leave headroom for playback/resampling; do not change device volume.


def render_pcm():
    samples = []
    for index in range(round(RATE * DURATION)):
        time = index / RATE
        sample = 0.0
        # E5, G#5, B5: a bright major arpeggio that carries on a small speaker.
        for start, end, frequency in ((0.0, 0.32, 659.255), (0.30, 0.65, 830.609),
                                      (0.63, 1.22, 987.767)):
            if start <= time < end:
                elapsed = time - start
                attack = math.sin(math.pi / 2 * min(1.0, elapsed / 0.018)) ** 2
                release = math.sin(math.pi / 2 * min(1.0, (end - time) / 0.18)) ** 2
                phase = 2 * math.pi * frequency * elapsed
                tone = math.sin(phase) + 0.16 * math.sin(2 * phase) + 0.04 * math.sin(3 * phase)
                sample += attack * release * math.exp(-1.8 * elapsed) * tone
        samples.append(sample)
    gain = PEAK / max(abs(sample) for sample in samples)
    return b''.join(struct.pack('<h', round(sample * gain * 32767)) for sample in samples)


def generate():
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / 'reminder-chime.wav'
        with wave.open(str(source), 'wb') as output:
            output.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
            output.writeframes(render_pcm())
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(source),
                        '-compression_level', '8', str(TARGET)], check=True)


if __name__ == '__main__':
    generate()
