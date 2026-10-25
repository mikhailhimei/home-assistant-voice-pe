"""Actual ESPHome validation: calls alone and calls together with radio and clocks."""
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class CallsBootTests(unittest.TestCase):
    def test_independent_and_combined_packages(self):
        if not importlib.util.find_spec("esphome"):
            self.skipTest("Requires ESPHome environment")
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            for module in ("calls", "baby-monitor"):
                content = (ROOT / f"modules/{module}.yaml").read_text()
                content = re.sub(r"  - source:\n.*?(?=    components:)", f"  - source:\n      type: local\n      path: {ROOT}/external_components\n", content, count=1, flags=re.DOTALL)
                (temp / f"{module}.yaml").write_text(content)
            for with_radio in (False, True):
                with self.subTest(radio=with_radio):
                    config = temp / "check.yaml"
                    config.write_text(f"substitutions:\n  name: voice-calls-check\npackages:\n  voice: !include {ROOT}/home-assistant-voice.yaml\n  calls: !include {temp}/calls.yaml\n" + (f"  monitor: !include {temp}/baby-monitor.yaml\n" if with_radio else "") + "wifi:\n  ssid: validation-only\n  password: validation-only\n")
                    env = os.environ.copy()
                    env.setdefault("PLATFORMIO_CORE_DIR", "/workspace/.cache/platformio")
                    env.setdefault("XDG_CACHE_HOME", "/workspace/.cache")
                    result = subprocess.run([sys.executable, "-m", "esphome", "config", str(config)], env=env, capture_output=True, text=True, check=False)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    merged = yaml.load(result.stdout, Loader=yaml.BaseLoader)
                    uplinks = {item["id"]: item for item in merged["baby_monitor"]}
                    self.assertEqual(uplinks["call_uplink"]["passive"], "true")
                    self.assertEqual(uplinks["call_uplink"]["port"], "8125")
                    if with_radio:
                        self.assertEqual(uplinks["monitor_uplink"]["passive"], "false")
                        self.assertEqual(uplinks["monitor_uplink"]["port"], "8124")
                    self.assertTrue(any(action["action"] == "call_ringtone_configure" for action in merged["api"]["actions"]))
                    ring = next(item for item in merged["light"] if item["id"] == "voice_assistant_leds")
                    self.assertTrue(any(effect.get("addressable_lambda", {}).get("name") == "Call ringing" for effect in ring["effects"]))
                    self.assertIn("micro_wake_word", merged)
                    self.assertIn("voice_assistant", merged)
                    self.assertEqual(len(merged["display"]), 1)
