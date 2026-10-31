"""Exercise CI validation and failure reporting without compiling a kernel."""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('kernel_ci', Path(__file__).with_name('kernel-ci.py'))
CI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CI)


class KernelCITest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_manifest(self):
        items = CI.entries()
        versions = [item['version'] for item in items]
        self.assertEqual(versions, ['5.15', '6.1', '6.6', '6.12', '6.18', '7.3'])

    def test_invalid_manifest(self):
        manifest = self.root / 'kernels.json'
        for items in [[], [CI.entries()[0]] * 2,
                      [{'version': '../../bad', 'sha256': 'a' * 64}],
                      [{'version': '7.3', 'sha256': 'bad'}]]:
            manifest.write_text(json.dumps(items))
            with patch.object(CI, 'MANIFEST', manifest), self.assertRaises(ValueError):
                CI.entries()

    def test_cache_detects_missing_or_changed_files(self):
        self.assertFalse(CI.kernel_cache_valid(self.root, 'key'))
        for name in ['.config', 'vmlinux', 'Module.symvers']:
            (self.root / name).write_text(name)
        (self.root / CI.STAMP).write_text(json.dumps(CI.kernel_state(self.root, 'key')))
        self.assertTrue(CI.kernel_cache_valid(self.root, 'key'))
        self.assertFalse(CI.kernel_cache_valid(self.root, 'other-key'))
        (self.root / 'Module.symvers').write_text('changed')
        self.assertFalse(CI.kernel_cache_valid(self.root, 'key'))

    def test_wrong_source_marker(self):
        (self.root / '.swt6621s-ci-source.json').write_text('{}')
        with self.assertRaises(ValueError):
            CI.source_identity(self.root, CI.entry('7.3'))

    def test_fetch_replaces_bad_cache_and_verifies_download(self):
        archive = b'test archive'
        item = {'version': '7.3', 'sha256': hashlib.sha256(archive).hexdigest()}
        cache = self.root / 'cache'
        cache.mkdir()
        (cache / 'linux-7.3.tar.xz').write_bytes(b'corrupt cache')
        args = argparse.Namespace(version='7.3', cache=cache, source=self.root / 'source')

        def download(command, **kwargs):
            if command[0] == 'curl':
                self.assertIn('--retry-all-errors', command)
                Path(command[command.index('--output') + 1]).write_bytes(archive)

        with patch.object(CI, 'entry', return_value=item), \
                patch.object(subprocess, 'run', side_effect=download) as run, \
                contextlib.redirect_stdout(io.StringIO()):
            CI.fetch(args)
        self.assertEqual(run.call_count, 2)
        self.assertEqual((cache / 'linux-7.3.tar.xz').read_bytes(), archive)
        self.assertEqual(CI.source_identity(args.source, item), {'archive': item['sha256']})

    def test_fetch_rejects_wrong_checksum(self):
        args = argparse.Namespace(version='7.3', cache=self.root / 'cache',
                                  source=self.root / 'source')

        def download(command, **kwargs):
            Path(command[command.index('--output') + 1]).write_bytes(b'wrong archive')

        with patch.object(subprocess, 'run', side_effect=download), self.assertRaises(ValueError):
            CI.fetch(args)
        self.assertFalse(args.source.exists())
        self.assertFalse((args.cache / 'linux-7.3.tar.xz').exists())

    def test_source_and_repository_cannot_be_output(self):
        for output in [CI.ROOT, CI.ROOT.parent, self.root]:
            args = argparse.Namespace(version='7.3', source=self.root, output=output,
                                      jobs=2, keep_modules=False)
            with self.assertRaises(ValueError):
                CI.build(args)

    def test_configuration_failure_is_reported(self):
        output = self.root / 'output'
        args = argparse.Namespace(version='7.3', source=self.root / 'source',
                                  output=output, jobs=2, keep_modules=False)
        with patch.object(CI, 'source_identity', side_effect=ValueError('wrong source')), \
                patch.object(subprocess, 'check_output', return_value='commit'), \
                contextlib.redirect_stderr(io.StringIO()), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(CI.build(args), 1)
        report = json.loads((output / 'result.json').read_text())
        self.assertEqual(report['result'], 'FAIL')
        self.assertEqual(report['failed_stage'], 'config')
        self.assertEqual(report['profiles'], {'sdio': 'NOT RUN', 'usb': 'NOT RUN'})

    def test_wrong_module_architecture_fails(self):
        module = self.root / 'wrong.ko'
        module.write_bytes(b'not an ARM64 ELF module')
        with self.assertRaises(ValueError):
            CI.module_details(module, 'wrong', '7.3.0')

    def report(self):
        return {'version': '7.3', 'kernel': 'PASS', 'result': 'PASS',
                'profiles': {name: 'PASS' for name in CI.PROFILES},
                'module_details': {
                    name: {module: {} for module in [bus, 'swt6621s_wifi', 'skwbt']}
                    for name, (_, _, bus) in CI.PROFILES.items()}}

    def summary(self):
        args = argparse.Namespace(results=self.root, versions=['7.3'])
        with contextlib.redirect_stdout(io.StringIO()):
            return CI.summarize(args)

    def test_complete_report(self):
        (self.root / 'result.json').write_text(json.dumps(self.report()))
        self.assertEqual(self.summary(), 0)

    def test_missing_duplicate_or_incomplete_report_fails(self):
        self.assertEqual(self.summary(), 1)
        report = self.report()
        report['module_details']['usb'].pop('skwbt')
        (self.root / 'result.json').write_text(json.dumps(report))
        self.assertEqual(self.summary(), 1)
        (self.root / 'result.json').write_text(json.dumps(self.report()))
        duplicate = self.root / 'duplicate'
        duplicate.mkdir()
        (duplicate / 'result.json').write_text(json.dumps(self.report()))
        self.assertEqual(self.summary(), 1)

    def test_failed_profile_cannot_report_success(self):
        report = self.report()
        report['profiles']['usb'] = 'FAIL'
        (self.root / 'result.json').write_text(json.dumps(report))
        self.assertEqual(self.summary(), 1)


if __name__ == '__main__':
    unittest.main()
