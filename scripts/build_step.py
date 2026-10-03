"""构建子进程的统一入口：实时回显输出，失败时把上下文写进 GitHub 注解。

CI 的 job 日志需要仓库管理员权限才能下载，check-run 注解可以匿名读取，所以构建
失败时把关键输出附在 ::error:: 注解上，排查不用再靠猜。Windows runner 的 stdout
不是 UTF-8，注解里出现中文或子进程输出非 ASCII 字符都会抛 UnicodeEncodeError，
因此本模块在导入时把标准输出切到 UTF-8 并放宽错误处理，注解失败也绝不打断构建。
"""

import os
import shutil
import subprocess
import sys

MESSAGE_LIMIT = 6000
HEAD_LINES = 15
TAIL_LINES = 80


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
    arguments = [str(item) for item in command]
    title = label or _command(arguments)
    result = subprocess.run(arguments, cwd=cwd, env=env, capture_output=True, text=True,
                            encoding='utf-8', errors='replace')
    if result.returncode:
        annotate('error', 'build failed: ' + title,
                 'exit=' + str(result.returncode) + '\n' +
                 (result.stdout or '') + (result.stderr or ''))
        raise SystemExit('构建步骤失败（退出码 ' + str(result.returncode) + '）：' + title)
    return result.stdout


def probe(commands):
    lines = []
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
    print(body, flush=True)
    notice('build-env', body)
