"""Publicly rebuilt payloads must pass the actual installation admission checks."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'runtime'))


class PreparedRuntimeTests(unittest.TestCase):
    def test_rebuilt_guest_workflow_and_input_are_admitted(self):
        import prepare_runtime_payloads as factory
        from prepare_runtime_guest import prepare
        import omarchy_guest_install as guest
        import omarchy_workflow_install as workflow
        import omarchy_input_install as korean
        components = json.loads((ROOT / 'manifests/runtime-build.json').read_text())['components']
        outputs = factory.workflow(ROOT, components['workflow'])
        for name in ('guest', 'inputConfig'):
            outputs.update(prepare(ROOT, name, components[name]))
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            for name, data in outputs.items():
                (target / name).write_bytes(data)
            self.assertEqual(len(guest.Payload(target / 'guest-payload.tar',
                                              target / 'guest-manifest.json').files), 11)
            self.assertEqual(len(workflow.validate(target / 'workflow-payload.tar',
                                                   target / 'workflow-manifest.json').files), 15)
            self.assertEqual(len(guest.Payload(target / 'input-config-payload.tar',
                                              target / 'input-config-manifest.json',
                                              component=korean.COMPONENT).files), 5)

    def test_weston_admission_pins_match_factory(self):
        import omarchy_host_install as host
        component = json.loads((ROOT / 'manifests/runtime-build.json').read_text())['components']['nativeWeston']
        self.assertEqual(component['artifacts']['payload.tar'],
                         {'bytes': host.PAYLOAD_BYTES, 'sha256': host.PAYLOAD_SHA})
        self.assertEqual(component['artifacts']['payload-manifest.json'],
                         {'bytes': host.MANIFEST_BYTES, 'sha256': host.MANIFEST_SHA})


if __name__ == '__main__':
    unittest.main()
