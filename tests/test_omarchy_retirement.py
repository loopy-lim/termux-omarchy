"""Retirement stage evidence; doubles never imply hardware termination proof."""
import importlib.util
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

REPO=Path(__file__).resolve().parents[1]


class RetirementEvidenceTests(unittest.TestCase):
    def fixture(self):
        sys.path.insert(0,str(REPO/'termux'))
        try:
            spec=importlib.util.spec_from_file_location('retirement_runtime',REPO/'termux/omarchy_runtime.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        finally:sys.path.pop(0)
        self.assertTrue(callable(getattr(module,'retire',None)), 'retirement failures do not identify the failing boundary')
        value={}
        runtime=SimpleNamespace(short=Path('/private-owned-runtime'),prefix=Path('/private-owned-prefix'),clear_runtime=Mock())
        owned=SimpleNamespace(refresh=Mock(return_value=[{'pid':42}]),terminate=Mock())
        logs=[SimpleNamespace(finish=Mock())]
        return module,value,runtime,owned,logs,[SimpleNamespace(pid=42)]

    def call(self,fixture,capture=None):
        module,value,runtime,owned,logs,children=fixture
        with patch.object(module,'capture',capture if capture is not None else Mock()),patch.object(module,'x_family',return_value=[]):
            module.retire(runtime,value,owned,logs,children)

    def test_capture_process_failure_still_retires_children_and_names_the_boundary(self):
        fixture=self.fixture();module,value,runtime,owned,logs,_=fixture
        owned.refresh.side_effect=ValueError('private process data must not be published')
        with self.assertRaises(ValueError):self.call(fixture)
        owned.terminate.assert_called_once()
        runtime.clear_runtime.assert_not_called()
        self.assertEqual(value['cleanupEvidence'],{'stage':'capture-processes','errorType':'ValueError','errno':None})

    def test_capture_filesystem_failure_preserves_errno_without_private_paths(self):
        fixture=self.fixture();module,value,runtime,owned,logs,_=fixture
        with self.assertRaises(FileNotFoundError):self.call(fixture,Mock(side_effect=FileNotFoundError(2,'private data','/private-secret')))
        owned.terminate.assert_called_once()
        runtime.clear_runtime.assert_not_called()
        self.assertEqual(value['cleanupEvidence'],{'stage':'capture-runtime','errorType':'FileNotFoundError','errno':2})

    def test_unconfirmed_child_termination_never_removes_resources_or_finishes_logs(self):
        fixture=self.fixture();module,value,runtime,owned,logs,_=fixture
        owned.terminate.side_effect=ValueError('private child command')
        with self.assertRaises(ValueError):self.call(fixture)
        runtime.clear_runtime.assert_not_called();logs[0].finish.assert_not_called()
        self.assertEqual(value['cleanupEvidence']['stage'],'terminate')

    def test_unconfirmed_log_drain_does_not_clear_resources(self):
        fixture=self.fixture();module,value,runtime,owned,logs,_=fixture
        logs[0].finish.side_effect=module.ResourceFailure('startup-log-drain-unconfirmed')
        with self.assertRaises(ValueError):self.call(fixture)
        runtime.clear_runtime.assert_not_called()
        self.assertEqual(value['cleanupEvidence']['stage'],'logs')

    def test_resource_error_is_distinct_and_successful_retry_removes_old_failure(self):
        fixture=self.fixture();module,value,runtime,owned,logs,_=fixture
        runtime.clear_runtime.side_effect=module.ResourceFailure('runtime-entry-unrecorded')
        with self.assertRaises(ValueError):self.call(fixture)
        self.assertEqual(value['cleanupEvidence']['stage'],'resources')
        runtime.clear_runtime.side_effect=None
        self.call(fixture)
        self.assertNotIn('cleanupEvidence',value)

    def test_process_error_identifies_a_fixed_reason_and_os_cause_without_private_text(self):
        fixture=self.fixture();module,value,runtime,owned,logs,_=fixture
        error=ValueError('native process identity cannot be verified')
        error.__cause__=PermissionError(13,'private data','/private-secret')
        owned.terminate.side_effect=error
        with self.assertRaises(ValueError):self.call(fixture)
        self.assertEqual(value['cleanupEvidence'].get('processReason'),'process-identity-unavailable')
        self.assertEqual(value['cleanupEvidence'].get('causeType'),'PermissionError')
        self.assertEqual(value['cleanupEvidence'].get('causeErrno'),13)
        self.assertNotIn('private',str(value))


if __name__=='__main__':unittest.main()
