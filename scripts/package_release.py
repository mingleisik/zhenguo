import argparse
import hashlib
import platform
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from app_build import BuildVariant, add_variant_argument
from linux_package import ICON_SOURCE, build_deb

MAINTAINER = 'jipinwa <jipinwa@users.noreply.github.com>'

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--platform', choices=['android', 'windows', 'linux'], required=True)
parser.add_argument('--abi', action='append', choices=['arm64-v8a', 'armeabi-v7a', 'x86_64'])
add_variant_argument(parser)
options = parser.parse_args()
variant = BuildVariant(options.all_sources)
match = re.search(r'^version:\s*([\w.+-]+)\s*$', (root / 'pubspec.yaml').read_text(encoding='utf-8'), re.MULTILINE)
if not match:
    raise SystemExit('pubspec.yaml 缺少合法版本号。')
version = match.group(1)
output = root / 'dist' / options.platform
output.mkdir(parents=True, exist_ok=True)
artifacts = []

if options.platform == 'android':
    for abi in options.abi or ['arm64-v8a', 'armeabi-v7a', 'x86_64']:
        source = root / 'build' / 'app' / 'outputs' / 'flutter-apk' / f'app-{abi}-release.apk'
        if not source.is_file():
            raise SystemExit('缺少 APK：' + str(source))
        with zipfile.ZipFile(source) as archive:
            names = set(archive.namelist())
            required = [f'lib/{abi}/{library}' for library in
                        ['libduanju_core.so', 'libflutter.so', 'libapp.so', 'libmpv.so']]
            missing = set(required) - names
            if missing:
                raise SystemExit('APK 缺少原生库：' + ', '.join(sorted(missing)))
        target = output / f'{variant.slug}-{version}-{abi}.apk'
        shutil.copy2(source, target)
        artifacts.append(target)
elif options.platform == 'windows':
    release = root / 'build' / 'windows' / 'x64' / 'runner' / 'Release'
    if not release.is_dir():
        raise SystemExit('缺少 Windows 构建产物：' + str(release))
    required = ['duanju_app.exe', 'duanju_core.dll', 'flutter_windows.dll']
    missing = [name for name in required if not (release / name).is_file()]
    if missing:
        raise SystemExit('Windows 产物缺少文件：' + ', '.join(missing))
    if not (release / 'data' / 'flutter_assets').is_dir():
        raise SystemExit('Windows 产物缺少资源目录：' + str(release / 'data' / 'flutter_assets'))
    target = output / f'{variant.slug}-{version}-windows-x64.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(release.rglob('*')):
            if path.is_file():
                archive.write(path, Path(variant.slug) / path.relative_to(release))
    artifacts.append(target)
elif options.platform == 'linux':
    if platform.system() != 'Linux':
        raise SystemExit('deb 打包需要在 Linux 上执行。')
    if not shutil.which('dpkg-deb'):
        raise SystemExit('缺少 dpkg-deb，请先安装 dpkg。')
    bundle = root / 'build' / 'linux' / 'x64' / 'release' / 'bundle'
    if not bundle.is_dir():
        raise SystemExit('缺少 Linux 构建产物：' + str(bundle))
    with tempfile.TemporaryDirectory(prefix='duanju-deb-') as workspace:
        artifacts.append(build_deb(bundle, output, variant.slug, variant.name, version,
                                   MAINTAINER, root.joinpath(*ICON_SOURCE),
                                   Path(workspace)))

checksums = []
for artifact in sorted(set(output.glob(f'*-{version}-*')) | set(output.glob(f'*_{version}_*'))):
    digest = hashlib.sha256()
    with artifact.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    checksums.append(f'{digest.hexdigest()}  {artifact.name}')
    print(artifact)
(output / 'SHA256SUMS.txt').write_text('\n'.join(checksums) + '\n', encoding='ascii')
