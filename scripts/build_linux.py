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
parser = argparse.ArgumentParser(description='构建红果鉴 / 真果鉴 Linux 核心和 deb 安装包')
parser.add_argument('--cn-mirrors', action='store_true', help='使用 Flutter 中国镜像')
add_variant_argument(parser)
options = parser.parse_args()
variant = BuildVariant(options.all_sources)
if platform.system() != 'Linux':
    raise SystemExit('Linux 构建需要 Linux、clang、CMake、Ninja 和 GTK3 / libmpv 开发包。')
environment = os.environ.copy()
environment.setdefault('GOPROXY', 'https://goproxy.cn,direct')
environment.setdefault('GOSUMDB', 'off')
environment['DUANJU_EDITION'] = variant.slug
flutter = shutil.which('flutter')
if not flutter:
    raise SystemExit('请先将 Flutter SDK 的 bin 目录加入 PATH。')
with china_mirror_environment(environment, options.cn_mirrors, gradle=False) as env, \
        mirrored_pub_lockfile(root, env):
    if options.cn_mirrors:
        print('本次构建启用国内依赖镜像。', flush=True)
    subprocess.run([sys.executable, str(root / 'scripts' / 'build_native.py'),
                    '--platform', 'linux', *variant.arguments],
                   cwd=root, env=env, check=True)
    subprocess.run([flutter, 'config', '--enable-linux-desktop'], cwd=root, env=env, check=True)
    subprocess.run([flutter, 'pub', 'get'], cwd=root, env=env, check=True)
    subprocess.run([flutter, 'build', 'linux', '--release', '--no-pub',
                    *variant.flutter_arguments],
                   cwd=root, env=env, check=True)
    subprocess.run([sys.executable, str(root / 'scripts' / 'package_release.py'),
                    '--platform', 'linux', *variant.arguments],
                   cwd=root, env=env, check=True)
