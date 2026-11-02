"""Verify the shipped cue is audible, unclipped, and matches its source."""
from array import array
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOUND = ROOT / 'sounds/reminder-neutral-bass.flac'


class ReminderSoundTests(unittest.TestCase):
    def test_embedded_audio_format_and_signal_level(self):
        metadata = json.loads(subprocess.check_output([
            'ffprobe', '-v', 'error', '-show_entries',
            'stream=codec_name,sample_rate,channels,bits_per_raw_sample',
            '-of', 'json', str(SOUND),
        ]))['streams'][0]
        self.assertEqual(metadata, {'codec_name': 'flac', 'sample_rate': '24000',
                                    'channels': 1, 'bits_per_raw_sample': '16'})
        pcm = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(SOUND),
                                       '-f', 's16le', '-'])
        samples = array('h', pcm)
        duration = len(samples) / 24000
        self.assertGreater(duration, 1.7)
        self.assertLess(duration, 2.0)
        peak = max(abs(value) for value in samples) / 32768
        rms = math.sqrt(sum((value / 32768) ** 2 for value in samples) / len(samples))
        self.assertGreater(peak, 0.75)
        self.assertLess(peak, 0.9)  # Headroom, no hard clipping.
        self.assertGreater(rms, 0.2)  # Prevent a return to the nearly silent cue.
        self.assertLess(rms, 0.5)
        self.assertEqual(samples[0], 0)
        self.assertEqual(samples[-1], 0)
        # No abrupt sample discontinuities at note boundaries.
        self.assertLess(max(abs(b - a) for a, b in zip(samples, samples[1:])), 6000)
        spec = importlib.util.spec_from_file_location('reminder_sound', ROOT / 'scripts/generate_reminder_sound.py')
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        self.assertEqual(pcm, generator.render_pcm())


if __name__ == '__main__':
    unittest.main()
