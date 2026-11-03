"""Run the actual blueprint sequence with HA's script and template engine."""
import asyncio
from pathlib import Path
import tempfile
import unittest

from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.core import HomeAssistant, Context
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.script import Script
from homeassistant.util.yaml import load_yaml

ROOT = Path(__file__).resolve().parents[1]


class AnnounceAndMatrixTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.hass = HomeAssistant(self.directory.name)
        blueprint = Blueprint(load_yaml(str(ROOT / 'blueprints/script/announce_and_matrix.yaml')),
                              schema=BLUEPRINT_SCHEMA, expected_domain='script')
        inputs = BlueprintInputs(blueprint, {'use_blueprint': {'path': 'test', 'input': {
            'satellite': 'assist_satellite.kitchen', 'matrix_action': 'esphome.kitchen_matrix_show'}}})
        inputs.validate()
        self.config = inputs.async_substitute()
        self.script = Script(self.hass, cv.SCRIPT_SCHEMA(self.config['sequence']),
                             'Announce and matrix', 'script', script_mode=self.config['mode'])
        self.calls = []

        async def matrix(call):
            self.calls.append(('matrix', dict(call.data)))

        async def announce(call):
            self.calls.append(('speech', dict(call.data)))
            await asyncio.sleep(0.01)

        self.hass.services.async_register('esphome', 'kitchen_matrix_show', matrix)
        self.hass.services.async_register('assist_satellite', 'announce', announce)

    async def asyncTearDown(self):
        await self.hass.async_stop()
        self.directory.cleanup()

    async def run_script(self, **fields):
        await self.script.async_run({**self.config['variables'], **fields}, context=Context())

    async def test_icon_dropdown_matches_firmware_icons(self):
        options = self.config['fields']['icon']['selector']['select']
        self.assertEqual(options['mode'], 'dropdown')
        self.assertEqual([item['value'] for item in options['options']],
                         ['none', 'smile', 'sad', 'heart', 'check', 'cross', 'bell'])

    async def test_picture_and_speech_target_selected_speaker(self):
        await self.run_script(speech=' Еда готова ', icon='heart', duration=15)
        self.assertEqual(self.calls, [
            ('matrix', {'message': '', 'icon': 'heart', 'duration': 15, 'start_delay': 0}),
            ('speech', {'message': 'Еда готова', 'entity_id': ['assist_satellite.kitchen']}),
        ])

    async def test_text_display_and_default_duration(self):
        await self.run_script(speech='Привет', message='Привет')
        self.assertEqual(self.calls[0], ('matrix', {
            'message': 'Привет', 'icon': 'none', 'duration': 10, 'start_delay': 0}))

    async def test_speech_only_does_not_clear_the_clock(self):
        await self.run_script(speech='Привет')
        self.assertEqual([kind for kind, _ in self.calls], ['speech'])

    async def test_bad_fields_fail_before_display_or_speech(self):
        for fields in ({'speech': ' '}, {'speech': 'Привет', 'icon': 'unknown'},
                       {'speech': 'Привет', 'duration': 0}, {'speech': 'Привет', 'start_delay': -1}):
            with self.subTest(fields=fields):
                await self.run_script(**fields)
                self.assertEqual(self.calls, [])
        self.assertEqual(self.calls, [])

    async def test_delay_applies_before_both_actions(self):
        task = asyncio.create_task(self.run_script(speech='Привет', icon='bell', start_delay=1))
        await asyncio.sleep(0.05)
        self.assertEqual(self.calls, [])
        await task
        self.assertEqual([kind for kind, _ in self.calls], ['matrix', 'speech'])

    async def test_multiple_calls_are_queued(self):
        await asyncio.gather(self.run_script(speech='Первое', icon='heart'),
                             self.run_script(speech='Второе', icon='check'))
        self.assertEqual([kind for kind, _ in self.calls], ['matrix', 'speech', 'matrix', 'speech'])
        self.assertEqual([data['message'] for kind, data in self.calls if kind == 'speech'], ['Первое', 'Второе'])


if __name__ == '__main__':
    unittest.main()
