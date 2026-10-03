import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
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

    def test_includes_extra_notes(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            build_step.probe([], notes=['Visual Studio：17.14.37710.0'])
        self.assertIn('17.14.37710.0', buffer.getvalue())

    def test_capture_returns_code_and_output(self):
        code, text = build_step.capture([sys.executable, '-c',
                                         'import sys; sys.stderr.write("nope\\n"); sys.exit(6)'])
        self.assertEqual(code, 6)
        self.assertIn('nope', text)


class VisualStudioTests(unittest.TestCase):
    def report(self, output, code=0):
        with tempfile.TemporaryDirectory() as directory:
            stub = Path(directory) / 'vswhere.exe'
            stub.write_text('', encoding='utf-8')
            return build_step.visual_studio_report(stub, runner=lambda command: (code, output))

    def installations(self, *versions):
        return json.dumps([{'displayName': 'Visual Studio ' + version,
                            'installationVersion': version,
                            'installationPath': 'C:/VS/' + version} for version in versions])

    def test_reports_missing_vswhere(self):
        report = build_step.visual_studio_report(Path('C:/definitely/missing/vswhere.exe'))
        self.assertEqual(report.versions, [])
        self.assertEqual(report.selection, (None, None))
        self.assertIn('未找到', report.notes()[0])

    def test_keeps_2022_installation_usable(self):
        report = self.report(self.installations('17.14.37710.0'))
        self.assertEqual(report.selection, ('Visual Studio 17 2022', 17))
        self.assertIsNone(report.problem)
        self.assertIn('Visual Studio 17 2022', report.notes()[-1])

    def test_keeps_2019_installation_usable(self):
        report = self.report(self.installations('16.11.40.0'))
        self.assertEqual(report.selection, ('Visual Studio 16 2019', 16))
        self.assertIsNone(report.problem)

    def test_flags_2026_installation_as_problem(self):
        report = self.report(self.installations('18.5.1.0'))
        self.assertEqual(report.selection, ('Visual Studio 16 2019', 16))
        self.assertIn('windows-2022', report.problem)

    def test_uses_highest_installed_version(self):
        report = self.report(self.installations('17.14.0.0', '18.5.1.0'))
        self.assertEqual(report.selection, ('Visual Studio 16 2019', 16))
        self.assertIn('Unable to generate build files', report.problem)

    def test_accepts_newer_installation_alongside_2019(self):
        report = self.report(self.installations('16.11.40.0', '17.14.0.0'))
        self.assertEqual(report.selection, ('Visual Studio 17 2022', 17))
        self.assertIsNone(report.problem)

    def test_reports_unparsable_output(self):
        report = self.report('nope', code=1)
        self.assertEqual(report.versions, [])
        self.assertIn('无法解析', report.notes()[0])

    def test_reports_empty_installation_list(self):
        report = self.report('[]')
        self.assertEqual(report.versions, [])
        self.assertIn('未返回安装实例', report.notes()[0])

    def test_survives_unrunnable_vswhere(self):
        with tempfile.TemporaryDirectory() as directory:
            stub = Path(directory) / 'vswhere.exe'
            stub.write_text('', encoding='utf-8')

            def explode(command):
                raise OSError('拒绝访问')

            report = build_step.visual_studio_report(stub, runner=explode)
        self.assertEqual(report.versions, [])
        self.assertIn('无法执行', report.notes()[0])


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
