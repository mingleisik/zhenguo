import contextlib
import io
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import build_step

SCRIPTS = Path(__file__).resolve().parent


class EscapeTests(unittest.TestCase):
    def test_escapes_workflow_command_characters(self):
        self.assertEqual(build_step._escape('100%\n下一行'), '100%25%0A下一行')


class ExcerptTests(unittest.TestCase):
    def test_keeps_short_output(self):
        self.assertEqual(build_step._excerpt('a\n\nb\n'), 'a\nb')

    def test_trims_long_output_and_keeps_both_ends(self):
        excerpt = build_step._excerpt('\n'.join(f'line{index}' for index in range(400)))
        self.assertLessEqual(len(excerpt), build_step.MESSAGE_LIMIT)
        self.assertIn('line0', excerpt)
        self.assertIn('line399', excerpt)


class RunTests(unittest.TestCase):
    def test_returns_zero_for_success(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(build_step.run([sys.executable, '-c', 'print("ok")']), 0)

    def test_streams_non_ascii_child_output(self):
        code = 'import sys; sys.stdout.buffer.write("\\u221a \\u4e2d\\u6587\\n".encode("utf-8"))'
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(build_step.run([sys.executable, '-c', code]), 0)
        self.assertIn('中文', buffer.getvalue())

    def test_annotates_failure_with_output(self):
        buffer = io.StringIO()
        with mock.patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'}), \
                contextlib.redirect_stdout(buffer):
            with self.assertRaises(SystemExit) as raised:
                build_step.run([sys.executable, '-c',
                                'import sys; sys.stdout.write("boom-line\\n"); sys.exit(4)'],
                               label='演示步骤')
        printed = buffer.getvalue()
        self.assertIn('::error title=', printed)
        self.assertIn('boom-line', printed)
        self.assertIn('演示步骤', str(raised.exception))

    def test_annotates_exit_code_when_output_is_empty(self):
        buffer = io.StringIO()
        with mock.patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'}), \
                contextlib.redirect_stdout(buffer):
            with self.assertRaises(SystemExit):
                build_step.run([sys.executable, '-c', 'raise SystemExit(5)'], label='demo')
        self.assertIn('exit=5', buffer.getvalue())

    def test_skips_annotation_outside_actions(self):
        buffer = io.StringIO()
        with mock.patch.dict(os.environ, {'GITHUB_ACTIONS': 'false'}), \
                contextlib.redirect_stdout(buffer):
            with self.assertRaises(SystemExit):
                build_step.run([sys.executable, '-c', 'raise SystemExit(2)'], label='演示步骤')
        self.assertNotIn('::error', buffer.getvalue())


class OutputTests(unittest.TestCase):
    def test_returns_stdout(self):
        code = 'import sys; sys.stdout.buffer.write("\\u503c\\n".encode("utf-8"))'
        self.assertEqual(build_step.output([sys.executable, '-c', code]).strip(), '值')

    def test_annotates_failure(self):
        buffer = io.StringIO()
        with mock.patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'}), \
                contextlib.redirect_stdout(buffer):
            with self.assertRaises(SystemExit):
                build_step.output([sys.executable, '-c',
                                   'import sys; sys.stderr.write("bad\\n"); sys.exit(3)'],
                                  label='演示步骤')
        self.assertIn('bad', buffer.getvalue())


class ProbeTests(unittest.TestCase):
    def test_reports_missing_command(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            build_step.probe([('不存在', ['duanju-missing-command-xyz'])])
        self.assertIn('未找到', buffer.getvalue())

    def test_never_raises_for_broken_entries(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            build_step.probe([('坏条目', [])])
        self.assertIn('probe 失败', buffer.getvalue())


class NarrowStdoutTests(unittest.TestCase):
    def test_annotation_survives_narrow_stdout(self):
        environment = os.environ.copy()
        environment['GITHUB_ACTIONS'] = 'true'
        environment['PYTHONIOENCODING'] = 'cp1252'
        result = subprocess.run(
            [sys.executable, '-c',
             'import build_step; build_step.notice("build-env", "\\u221a \\u4e2d\\u6587")'],
            cwd=SCRIPTS, env=environment, capture_output=True, text=True,
            encoding='utf-8', errors='replace')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('::notice title=', result.stdout)


if __name__ == '__main__':
    unittest.main()
