"""Public process failure classification must not expose application output."""
import importlib.util
from pathlib import Path
import sys
import unittest


class OperationEvidenceTests(unittest.TestCase):
    def module(self):
        source=Path(__file__).resolve().parents[1]/'termux/omarchy_runtime.py'
        sys.path.insert(0,str(source.parent))
        try:
            spec=importlib.util.spec_from_file_location('runtime_operation_evidence',source)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        finally:sys.path.pop(0)
        self.assertTrue(callable(getattr(module,'operation_evidence',None)), 'supervisor failure has no public classification')
        return module

    def test_unknown_error_text_and_cause_paths_are_never_published(self):
        module=self.module();error=ValueError('/private/account.txt')
        error.__cause__=OSError(13,'private account secret','/private/account.txt')
        value=module.operation_evidence('refresh',error)
        self.assertEqual(value,{'stage':'refresh','errorType':'ValueError','errno':None,'causeType':'PermissionError','causeErrno':13})

    def test_known_identity_error_can_be_distinguished_from_a_count_limit(self):
        module=self.module()
        self.assertEqual(module.operation_evidence('refresh',ValueError('native process identity cannot be verified'))['processReason'],'process-identity-unavailable')
        self.assertEqual(module.operation_evidence('refresh',ValueError('native descendant count exceeds bound'))['processReason'],'descendant-bound')

    def test_resource_cause_survives_later_cleanup_failure_without_private_text(self):
        module=self.module()
        value=module.operation_evidence('resources',module.ResourceFailure('resource-type'))
        self.assertEqual(value['resourceReason'],'resource-type')
        self.assertNotIn('resourceReason',module.operation_evidence('resources',module.ResourceFailure('/private/account.txt')))

    def test_changed_field_metadata_is_limited_to_identity_fields(self):
        module=self.module();error=ValueError('native process identity changed; refusing signal')
        error.identity_changed_fields=('command',)
        self.assertEqual(module.operation_evidence('terminate',error)['identityChangedFields'],['command'])
        error.identity_changed_fields=('private-value',)
        self.assertNotIn('identityChangedFields',module.operation_evidence('terminate',error))


if __name__=='__main__':unittest.main()
