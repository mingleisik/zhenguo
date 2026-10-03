import contextlib
import io
import os
import sys
import unittest
from unittest import mock

import build_step


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

    def test_skips_annotation_outside_actions(self):
        buffer = io.StringIO()
        with mock.patch.dict(os.environ, {'GITHUB_ACTIONS': 'false'}), \
                contextlib.redirect_stdout(buffer):
            with self.assertRaises(SystemExit):
                build_step.run([sys.executable, '-c', 'raise SystemExit(2)'], label='演示步骤')
        self.assertNotIn('::error', buffer.getvalue())


class OutputTests(unittest.TestCase):
    def test_returns_stdout(self):
        self.assertEqual(build_step.output([sys.executable, '-c', 'print("值")']).strip(), '值')

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


if __name__ == '__main__':
    unittest.main()
