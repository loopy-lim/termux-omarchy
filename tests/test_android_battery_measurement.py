import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('battery_measurement', Path(__file__).resolve().parents[1] / 'tools/measure_android_battery.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class BatteryMeasurementTests(unittest.TestCase):
    def samples(self):
        battery = {k: False for k in m.POWER}
        battery.update(status=3, temperature=320, **{'Charge counter': 6000000})
        return [{'elapsedSeconds': 0, 'battery': battery},
                {'elapsedSeconds': 900, 'battery': dict(battery, **{'Charge counter': 5900000})}]

    def test_discharge_has_units_but_never_claims_savings(self):
        result = m.summarize(self.samples())
        self.assertEqual(result['status'], 'MEASURED_DISCHARGE')
        self.assertEqual(result['consumedMah'], 100)
        self.assertEqual(result['averageDischargeMa'], 400)
        self.assertFalse(result['batterySavingsProven'])

    def test_rejects_power_in_any_sample_and_missing_state(self):
        for key in (*m.POWER, 'Dock powered'):
            samples = self.samples()
            samples[0]['battery'][key] = True
            self.assertEqual(m.summarize(samples)['status'], 'EXTERNAL_POWER')
        samples = self.samples()
        del samples[1]['battery']['USB powered']
        self.assertEqual(m.summarize(samples)['status'], 'NOT_CONFIRMED_DISCHARGING')

    def test_invalid_counter_and_short_window(self):
        for counter, status in [(0, 'COUNTER_UNAVAILABLE'), (None, 'COUNTER_UNAVAILABLE'),
                                (6100000, 'COUNTER_INCREASED'), (6000000, 'COUNTER_UNCHANGED')]:
            samples = self.samples()
            samples[1]['battery']['Charge counter'] = counter
            self.assertEqual(m.summarize(samples)['status'], status)
        samples = self.samples()
        samples[1]['elapsedSeconds'] = 60
        self.assertEqual(m.summarize(samples)['status'], 'TOO_SHORT')

    def test_simulated_state_and_unrecognized_fields(self):
        parsed = m.parse_battery('Current Battery Service state: (UPDATES STOPPED -- use reset to restart)\n USB powered: false\n Charge counter: 123000\n temperature: 312\n private field: secret\n')
        self.assertTrue(parsed['updatesStopped'])
        self.assertEqual(parsed['temperature'], 312)
        self.assertNotIn('private field', parsed)
        samples = self.samples()
        samples[0]['battery']['updatesStopped'] = True
        self.assertEqual(m.summarize(samples)['status'], 'SIMULATED_BATTERY_STATE')


if __name__ == '__main__':
    unittest.main()
