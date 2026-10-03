import shutil
import subprocess
from pathlib import Path

BINARY_NAME = 'duanju_app'
ARCHITECTURE = 'amd64'
ICON_SIZE = '256x256'
ICON_SOURCE = ('linux', 'runner', 'resources', 'app_icon.png')
MPV_DEPENDS = 'libmpv2 | libmpv1'
FALLBACK_DEPENDS = 'libgtk-3-0 | libgtk-3-0t64, libmpv2 | libmpv1'
DEPENDENCY_LIBRARIES = (
    'lib/libflutter_linux_gtk.so',
    'lib/libapp.so',
    'lib/libduanju_core.so',
)
REQUIRED_BUNDLE_ENTRIES = (
    BINARY_NAME,
    'lib/libflutter_linux_gtk.so',
    'lib/libapp.so',
    'lib/libduanju_core.so',
    'data/icudtl.dat',
    'data/flutter_assets',
)


def desktop_entry(slug, name):
    return (
        '[Desktop Entry]\n'
        'Type=Application\n'
        f'Name={name}\n'
        'Comment=设备端短剧浏览与播放\n'
        f'Exec=/opt/{slug}/{BINARY_NAME} %U\n'
        f'Icon={slug}\n'
        'Terminal=false\n'
        'Categories=AudioVideo;Video;Player;\n'
        'StartupNotify=true\n'
        f'StartupWMClass=com.duanju.{slug}\n'
    )


def source_control(slug, name, version, maintainer):
    return (
        f'Source: {slug}\n'
        'Section: video\n'
        'Priority: optional\n'
        f'Maintainer: {maintainer}\n'
        'Standards-Version: 4.6.0\n'
        '\n'
        f'Package: {slug}\n'
        f'Architecture: {ARCHITECTURE}\n'
        'Depends: ${shlibs:Depends}, ${misc:Depends}\n'
        f'Description: {name}桌面版\n'
        ' 设备端完成站源请求、解析与在线播放的独立短剧应用。\n'
    )


def binary_control(slug, name, version, maintainer, depends):
    return (
        f'Package: {slug}\n'
        f'Version: {version}\n'
        f'Architecture: {ARCHITECTURE}\n'
        'Section: video\n'
        'Priority: optional\n'
        f'Maintainer: {maintainer}\n'
        f'Depends: {depends}\n'
        f'Description: {name}桌面版\n'
        ' 设备端完成站源请求、解析与在线播放的独立短剧应用。\n'
    )


def merge_depends(computed):
    """合并 dpkg-shlibdeps 结果；libmpv 是运行时 dlopen，必须手工补上。"""
    entries = [item.strip() for item in computed.split(',') if item.strip()]
    if not entries:
        return FALLBACK_DEPENDS
    if not any(item.startswith('libmpv') for item in entries):
        entries.append(MPV_DEPENDS)
    return ', '.join(entries)


def shared_library_depends(workspace, slug):
    """用 dpkg-shlibdeps 解析捆绑库的系统依赖；无法解析时返回空字符串。"""
    tool = shutil.which('dpkg-shlibdeps')
    if tool is None:
        return ''
    prefix = Path('debian') / slug / 'opt' / slug
    targets = [prefix / name for name in DEPENDENCY_LIBRARIES]
    if not all((workspace / target).is_file() for target in targets):
        return ''
    result = subprocess.run([tool, '-O', *[str(target) for target in targets]],
                            cwd=str(workspace), capture_output=True, text=True)
    if result.returncode != 0:
        print('dpkg-shlibdeps 未返回结果，改用内置依赖清单：' + result.stderr.strip(), flush=True)
        return ''
    for line in result.stdout.splitlines():
        _, separator, value = line.partition('=')
        if separator and value.strip():
            return value.strip()
    return ''


def resolve_depends(workspace, slug):
    return merge_depends(shared_library_depends(workspace, slug))


def missing_bundle_entries(bundle):
    return [name for name in REQUIRED_BUNDLE_ENTRIES if not (bundle / name).exists()]


def build_deb(bundle, output, slug, name, version, maintainer, icon, workspace):
    missing = missing_bundle_entries(bundle)
    if missing:
        raise SystemExit('Linux 产物缺少文件：' + ', '.join(missing))
    if not icon.is_file():
        raise SystemExit('缺少应用图标：' + str(icon))
    package = workspace / 'debian' / slug
    if package.exists():
        shutil.rmtree(package)
    shutil.copytree(bundle, package / 'opt' / slug)

    desktop = package / 'usr' / 'share' / 'applications' / f'{slug}.desktop'
    desktop.parent.mkdir(parents=True, exist_ok=True)
    desktop.write_text(desktop_entry(slug, name), encoding='utf-8')

    icon_target = package / 'usr' / 'share' / 'icons' / 'hicolor' / ICON_SIZE / 'apps' / f'{slug}.png'
    icon_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(icon, icon_target)

    source = workspace / 'debian' / 'control'
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(source_control(slug, name, version, maintainer), encoding='utf-8')

    control = package / 'DEBIAN' / 'control'
    control.parent.mkdir(parents=True, exist_ok=True)
    control.write_text(
        binary_control(slug, name, version, maintainer, resolve_depends(workspace, slug)),
        encoding='utf-8')

    target = output / f'{slug}_{version}_{ARCHITECTURE}.deb'
    subprocess.run(['dpkg-deb', '--build', '--root-owner-group', str(package), str(target)],
                   check=True)
    return target
