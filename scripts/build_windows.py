import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from build_mirrors import china_mirror_environment, mirrored_pub_lockfile
from app_build import BuildVariant, add_variant_argument

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description='构建红果鉴 / 真果鉴 Windows 核心和应用')
parser.add_argument('--cn-mirrors', action='store_true', help='使用 Flutter 中国镜像')
add_variant_argument(parser)
options = parser.parse_args()
variant = BuildVariant(options.all_sources)
if platform.system() != 'Windows':
    raise SystemExit('Windows 构建需要 Windows、MinGW-w64 和 Visual Studio 生成工具。')
environment = os.environ.copy()
environment.setdefault('GOPROXY', 'https://goproxy.cn,direct')
environment.setdefault('GOSUMDB', 'off')
flutter = shutil.which('flutter')
if not flutter:
    raise SystemExit('请先将 Flutter SDK 的 bin 目录加入 PATH。')
with china_mirror_environment(environment, options.cn_mirrors, gradle=False) as env, \
        mirrored_pub_lockfile(root, env):
    if options.cn_mirrors:
        print('本次构建启用国内依赖镜像。', flush=True)
    subprocess.run([sys.executable, str(root / 'scripts' / 'build_native.py'),
                    '--platform', 'windows', *variant.arguments],
                   cwd=root, env=env, check=True)
    subprocess.run([flutter, 'config', '--enable-windows-desktop'], cwd=root, env=env, check=True)
    subprocess.run([flutter, 'pub', 'get'], cwd=root, env=env, check=True)
    subprocess.run([flutter, 'build', 'windows', '--release', '--no-pub',
                    *variant.flutter_arguments],
                   cwd=root, env=env, check=True)
    subprocess.run([sys.executable, str(root / 'scripts' / 'package_release.py'),
                    '--platform', 'windows', *variant.arguments],
                   cwd=root, env=env, check=True)
