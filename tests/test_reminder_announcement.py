"""Firmware owns the reminder cue and a single ordered announcement queue."""
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


class ReminderAnnouncementTests(unittest.TestCase):
    def setUp(self):
        self.config = yaml.load((ROOT / 'home-assistant-voice.base.yaml').read_text(), Loader=yaml.BaseLoader)
        self.script = next(item for item in self.config['script'] if item['id'] == 'play_reminder')

    def test_api_only_accepts_speech_url_and_rejects_empty_url(self):
        action = next(item for item in self.config['api']['actions'] if item['action'] == 'reminder_announce')
        self.assertEqual(action['variables'], {'url': 'string'})
        guard = action['then'][0]['if']
        self.assertEqual(guard['condition']['lambda'], 'return !url.empty();')
        self.assertEqual(guard['then'], [{'script.execute': {'id': 'play_reminder', 'url': 'return url;'}}])

    def test_embedded_chime_precedes_speech_in_same_queue(self):
        self.assertEqual(self.script['mode'], 'queued')
        self.assertEqual(self.script['max_runs'], '8')
        steps = self.script['then']
        queued = [step['media_player.enqueue'] for step in steps if 'media_player.enqueue' in step]
        self.assertEqual([step['media_url'] for step in queued],
                         ['audio-file://reminder_sound', 'return url;'])
        self.assertTrue(all(step['id'] == 'external_media_player' and step['announcement'] == 'true' for step in queued))
        sound = next(item for item in self.config['audio_file'] if item['id'] == 'reminder_sound')
        self.assertEqual(sound['file'], '${reminder_sound_file}')
        self.assertTrue((ROOT / 'sounds/reminder-neutral-bass.flac').is_file())
        self.assertTrue(self.config['substitutions']['reminder_sound_file'].endswith('/sounds/reminder-neutral-bass.flac'))
        self.assertNotIn('media_player.stop', str(steps))
        self.assertNotIn('delay:', str(steps))

    def test_waits_for_current_playback_and_for_its_own_queue_to_finish(self):
        steps = self.script['then']
        conditions = steps[0]['wait_until']['condition']['and']
        self.assertIn({'switch.is_off': 'timer_ringing'}, conditions)
        self.assertIn({'not': {'voice_assistant.is_running': {'id': 'va'}}}, conditions)
        self.assertIn({'not': {'media_player.is_announcing': 'external_media_player'}}, conditions)
        self.assertEqual(steps[-3]['wait_until']['condition'], {'media_player.is_announcing': 'external_media_player'})
        self.assertEqual(steps[-2]['wait_until']['condition'], {'not': {'media_player.is_announcing': 'external_media_player'}})

    def test_volume_is_set_before_cue_and_restored_after_speech(self):
        import subprocess
        import tempfile
        steps = self.script['then']
        self.assertEqual(steps[2]['media_player.volume_set'], {'id': 'external_media_player', 'volume': '80%'})
        self.assertIn('media_player.enqueue', steps[3])
        self.assertIn('media_player.enqueue', steps[4])
        snapshot = steps[1]['lambda']
        restore = steps[-1]['lambda']
        source = r'''
#include <cassert>
#include <cmath>
#include <initializer_list>
#define id(x) x
struct Player {
  float volume;
  struct Call { Player *player; float value; void set_volume(float v){ value=v; }
    void perform(){ player->volume=value; } };
  Call make_call(){ return {this, volume}; }
} external_media_player;
struct { bool state; } timer_ringing;
bool alert_snapshot_valid=false;
float reminder_previous_volume=0.5f, alert_previous_volume=0.5f;
void snapshot(){
''' + snapshot + r'''
}
void restore(){
''' + restore + r'''
}
int main(){
  for(float previous : {0.0f, 0.4f, 0.65f, 0.85f}) {
    external_media_player.volume=previous;
    snapshot(); external_media_player.volume=0.8f; restore();
    assert(external_media_player.volume==previous);
  }
  external_media_player.volume=0.55f;
  snapshot(); external_media_player.volume=0.8f;
  timer_ringing.state=true; alert_snapshot_valid=true;
  external_media_player.volume=0.3f; alert_previous_volume=0.8f;
  restore();
  assert(external_media_player.volume==0.3f);
  assert(alert_previous_volume==0.55f);
  timer_ringing.state=false;
  external_media_player.volume=alert_previous_volume;
  snapshot(); external_media_player.volume=0.8f; restore();
  assert(external_media_player.volume==0.55f);
}
'''
        with tempfile.TemporaryDirectory() as directory:
            cpp, binary = Path(directory) / 'volume.cpp', Path(directory) / 'volume'
            cpp.write_text(source)
            subprocess.run(['g++', '-std=c++17', str(cpp), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()
