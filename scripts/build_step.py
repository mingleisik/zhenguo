"""构建子进程的统一入口：实时回显输出，失败时把上下文写进 GitHub 注解。

CI 的 job 日志需要仓库管理员权限才能下载，check-run 注解可以匿名读取，所以构建
失败时把关键输出附在 ::error:: 注解上，排查不用再靠猜。Windows runner 的 stdout
不是 UTF-8，注解里出现中文或子进程输出非 ASCII 字符都会抛 UnicodeEncodeError，
因此本模块在导入时把标准输出切到 UTF-8 并放宽错误处理，注解失败也绝不打断构建。

同一套注解也用来报告工具链环境：probe 输出编译器版本，visual_studio_report 输出
Visual Studio 安装清单和 Flutter 会选用的 CMake 生成器。
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

MESSAGE_LIMIT = 6000
HEAD_LINES = 15
TAIL_LINES = 80

# Flutter 3.32.8 的 visual_studio.dart 只认主版本 17，其余主版本一律退回 16。
VISUAL_STUDIO_GENERATORS = {17: 'Visual Studio 17 2022', 16: 'Visual Studio 16 2019'}


def _configure_output():
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        return
    for stream in (sys.stdout, sys.stderr):
        configure = getattr(stream, 'reconfigure', None)
        if configure is None:
            continue
        try:
            configure(encoding='utf-8', errors='replace')
        except (OSError, ValueError):
            pass


_configure_output()


def _escape(text):
    return text.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')


def _excerpt(text):
    lines = [line.rstrip() for line in text.splitlines()]
    lines = [line for line in lines if line.strip()]
    if len(lines) > HEAD_LINES + TAIL_LINES:
        lines = lines[:HEAD_LINES] + ['...'] + lines[-TAIL_LINES:]
    return '\n'.join(lines)[-MESSAGE_LIMIT:]


def _command(command):
    return ' '.join(str(item) for item in command)


def annotate(level, title, body):
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        return
    text = _excerpt(body)
    if not text:
        return
    try:
        print('::' + level + ' title=' + _escape(title) + '::' + _escape(text), flush=True)
    except (OSError, ValueError):
        pass


def notice(title, body):
    try:
        print(body, flush=True)
    except (OSError, ValueError):
        pass
    annotate('notice', title, body)


def run(command, *, cwd=None, env=None, label=None):
    arguments = [str(item) for item in command]
    title = label or _command(arguments)
    print('--- ' + title, flush=True)
    process = subprocess.Popen(arguments, cwd=cwd, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                               errors='replace', bufsize=1)
    output = []
    with process.stdout:
        for line in process.stdout:
            try:
                sys.stdout.write(line)
                sys.stdout.flush()
            except (OSError, ValueError):
                pass
            output.append(line)
    code = process.wait()
    if code:
        annotate('error', 'build failed: ' + title,
                 'exit=' + str(code) + '\n' + ''.join(output))
        raise SystemExit('构建步骤失败（退出码 ' + str(code) + '）：' + title)
    return code


def output(command, *, cwd=None, env=None, label=None):
    code, text = capture(command, cwd=cwd, env=env)
    if code:
        annotate('error', 'build failed: ' + (label or _command(command)),
                 'exit=' + str(code) + '\n' + text)
        raise SystemExit('构建步骤失败（退出码 ' + str(code) + '）：' + (label or _command(command)))
    return text


def capture(command, *, cwd=None, env=None):
    arguments = [str(item) for item in command]
    result = subprocess.run(arguments, cwd=cwd, env=env, capture_output=True, text=True,
                            encoding='utf-8', errors='replace')
    return result.returncode, (result.stdout or '') + (result.stderr or '')


def probe(commands, notes=()):
    lines = [str(note) for note in notes]
    try:
        for label, command in commands:
            arguments = [str(item) for item in command]
            executable = shutil.which(arguments[0])
            if not executable:
                lines.append(label + '：未找到 ' + arguments[0])
                continue
            try:
                result = subprocess.run(arguments, capture_output=True, text=True,
                                        encoding='utf-8', errors='replace')
            except OSError as error:
                lines.append(label + '：' + str(error))
                continue
            text = (result.stdout or result.stderr or '').strip().splitlines()
            lines.append(label + '：' + (text[0] if text else executable))
        entries = [entry for entry in os.environ.get('PATH', '').split(os.pathsep)
                   if 'mingw' in entry.lower() or 'msys' in entry.lower()]
        if entries:
            lines.append('PATH 命中：' + ' | '.join(entries))
    except Exception as error:
        lines.append('probe 失败：' + repr(error))
    body = '\n'.join(lines)
    notice('build-env', body)


def _vswhere_path():
    program_files = os.environ.get('PROGRAMFILES(X86)')
    if not program_files:
        return None
    return (Path(program_files) / 'Microsoft Visual Studio' / 'Installer' / 'vswhere.exe')


def _version_key(version):
    parts = [int(part) for part in version.split('.') if part.isdigit()]
    return parts or [0]


def _major_version(version):
    head = version.split('.')[0]
    return int(head) if head.isdigit() else 0


class VisualStudioReport:
    """vswhere 报告的 Visual Studio 安装，以及 Flutter 3.32.8 会据此选用的 CMake 生成器。

    Flutter 只把主版本 17 映射到 "Visual Studio 17 2022"，其它主版本一律退回
    "Visual Studio 16 2019"。选中的生成器在本机没有对应的 Visual Studio 时，CMake 会以
    "Unable to generate build files" 结束，因此这里提前把生成器算出来。
    """

    def __init__(self, lines, versions):
        self.lines = lines
        self.versions = versions

    @property
    def selection(self):
        """返回 (生成器名, 生成器要求的 Visual Studio 主版本)，读不到安装信息时为 (None, None)。"""
        if not self.versions:
            return None, None
        required = 17 if _major_version(max(self.versions, key=_version_key)) == 17 else 16
        return VISUAL_STUDIO_GENERATORS[required], required

    @property
    def problem(self):
        """生成器在本机找不到对应 Visual Studio 时返回说明文本，否则返回 None。"""
        generator, required = self.selection
        if generator is None:
            return None
        if required in {_major_version(version) for version in self.versions}:
            return None
        return ('当前 Visual Studio 会让 Flutter 3.32.8 选用 CMake 生成器 ' + generator
                + '，本机没有对应的 Visual Studio ' + str(required) + '，构建会停在 '
                'Unable to generate build files。请改用装有 VS 2022（主版本 17）的机器，'
                'CI 上固定 windows-2022。')

    def notes(self):
        """整理成 ::notice:: 注解行。"""
        lines = list(self.lines)
        generator, _ = self.selection
        if generator is not None:
            lines.append('Flutter 将使用生成器：' + generator)
        return lines


def visual_studio_report(vswhere=None, runner=capture):
    """读取 vswhere 的安装清单，返回 VisualStudioReport。

    这份信息只用于诊断，读不到时返回说明文本和空版本列表，绝不抛异常。
    """
    executable = Path(vswhere) if vswhere is not None else _vswhere_path()
    if executable is None:
        return VisualStudioReport(['vswhere：环境变量 ProgramFiles(x86) 缺失'], [])
    if not executable.is_file():
        return VisualStudioReport(['vswhere：未找到 ' + str(executable)], [])
    try:
        code, text = runner([str(executable), '-products', '*', '-format', 'json', '-utf8'])
    except OSError as error:
        return VisualStudioReport(['vswhere：无法执行 ' + str(error)], [])
    try:
        installations = json.loads(text)
    except ValueError:
        return VisualStudioReport(['vswhere 输出无法解析（退出码 ' + str(code) + '）：'
                                   + text.strip()[:500]], [])
    entries = [item for item in installations if isinstance(item, dict)] \
        if isinstance(installations, list) else []
    versions = [version for version in
                (str(item.get('installationVersion', '')).strip() for item in entries) if version]
    if not entries or not versions:
        return VisualStudioReport(['vswhere 未返回安装实例（退出码 ' + str(code) + '）'], [])
    lines = ['Visual Studio：' + ' '.join(part for part in
                                          (str(item.get('displayName', '')),
                                           str(item.get('installationVersion', '')),
                                           str(item.get('installationPath', ''))) if part)
             for item in entries]
    return VisualStudioReport(lines, versions)
