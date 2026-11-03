"""Run the actual blueprint sequence with HA's script and template engine."""
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


class ClockDisplayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.hass = HomeAssistant(self.directory.name)
        blueprint = Blueprint(load_yaml(str(ROOT / 'blueprints/script/announce_and_matrix.yaml')),
                              schema=BLUEPRINT_SCHEMA, expected_domain='script')
        inputs = BlueprintInputs(blueprint, {'use_blueprint': {'path': 'test', 'input': {
            'matrix_action': 'esphome.kitchen_matrix_show'}}})
        inputs.validate()
        self.config = inputs.async_substitute()
        self.script = Script(self.hass, cv.SCRIPT_SCHEMA(self.config['sequence']),
                             'Clock display', 'script', script_mode=self.config['mode'])
        self.calls = []

        async def matrix(call):
            self.calls.append(('matrix', dict(call.data)))

        async def announce(call):
            self.calls.append(('speech', dict(call.data)))

        self.hass.services.async_register('esphome', 'kitchen_matrix_show', matrix)
        self.hass.services.async_register('assist_satellite', 'announce', announce)

    async def asyncTearDown(self):
        await self.hass.async_stop()
        self.directory.cleanup()

    async def run_script(self, **fields):
        await self.script.async_run(fields, context=Context())

    async def test_icon_dropdown_matches_firmware_icons(self):
        options = self.config['fields']['icon']['selector']['select']
        self.assertEqual(options['mode'], 'dropdown')
        self.assertEqual([item['value'] for item in options['options']],
                         ['none', 'smile', 'sad', 'heart', 'check', 'cross', 'bell'])

    async def test_no_speech_fields_or_satellite_setup(self):
        self.assertNotIn('speech', self.config['fields'])
        self.assertNotIn('variables', self.config)

    async def test_picture_only(self):
        await self.run_script(icon='heart', duration=15)
        self.assertEqual(self.calls, [
            ('matrix', {'message': '', 'icon': 'heart', 'duration': 15, 'start_delay': 0}),
        ])

    async def test_text_display_and_default_duration(self):
        await self.run_script(message=' Привет ')
        self.assertEqual(self.calls, [('matrix', {
            'message': 'Привет', 'icon': 'none', 'duration': 10, 'start_delay': 0})])

    async def test_empty_fields_return_clock_without_speech(self):
        await self.run_script()
        self.assertEqual(self.calls, [('matrix', {
            'message': '', 'icon': 'none', 'duration': 10, 'start_delay': 0})])

    async def test_zero_duration_clears_the_screen(self):
        await self.run_script(icon='heart', duration=0)
        self.assertEqual(self.calls[0][1]['duration'], 0)

    async def test_bad_fields_fail_before_display(self):
        for fields in ({'icon': 'unknown'}, {'duration': -1}, {'start_delay': -1}, {'duration': 3601}):
            with self.subTest(fields=fields):
                await self.run_script(**fields)
                self.assertEqual(self.calls, [])

    async def test_delay_is_forwarded_to_firmware(self):
        await self.run_script(icon='bell', start_delay=2)
        self.assertEqual(self.calls, [('matrix', {
            'message': '', 'icon': 'bell', 'duration': 10, 'start_delay': 2})])

    async def test_legacy_speech_is_ignored(self):
        await self.run_script(speech='Это не должно озвучиваться', icon='check')
        self.assertEqual([kind for kind, _ in self.calls], ['matrix'])


if __name__ == '__main__':
    unittest.main()
