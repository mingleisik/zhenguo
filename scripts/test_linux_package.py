import tempfile
import unittest
from pathlib import Path
from unittest import mock

import linux_package


class DesktopEntryTests(unittest.TestCase):
    def test_entry_points_at_opt_payload(self):
        entry = linux_package.desktop_entry('hongguojian', '红果鉴')
        self.assertTrue(entry.startswith('[Desktop Entry]\n'))
        self.assertTrue(entry.endswith('\n'))
        self.assertIn('Name=红果鉴\n', entry)
        self.assertIn('Exec=/opt/hongguojian/duanju_app %U\n', entry)
        self.assertIn('Icon=hongguojian\n', entry)
        self.assertIn('StartupWMClass=com.duanju.hongguojian\n', entry)
        self.assertNotIn('\r', entry)

    def test_edition_slug_drives_every_path(self):
        entry = linux_package.desktop_entry('zhenguojian', '真果鉴')
        self.assertIn('Exec=/opt/zhenguojian/duanju_app %U\n', entry)
        self.assertIn('Icon=zhenguojian\n', entry)
        self.assertIn('StartupWMClass=com.duanju.zhenguojian\n', entry)


class ControlFileTests(unittest.TestCase):
    def test_binary_control_carries_version_and_depends(self):
        text = linux_package.binary_control('zhenguojian', '真果鉴', '0.2.101+3',
                                            'someone <a@b.c>', 'libc6 (>= 2.34)')
        self.assertIn('Package: zhenguojian\n', text)
        self.assertIn('Version: 0.2.101+3\n', text)
        self.assertIn('Architecture: amd64\n', text)
        self.assertIn('Maintainer: someone <a@b.c>\n', text)
        self.assertIn('Depends: libc6 (>= 2.34)\n', text)

    def test_description_continuation_is_indented(self):
        lines = linux_package.binary_control('hongguojian', '红果鉴', '1.0', 'm', 'libc6').splitlines()
        position = lines.index('Description: 红果鉴桌面版')
        self.assertTrue(lines[position + 1].startswith(' '))

    def test_source_control_declares_the_same_package(self):
        text = linux_package.source_control('hongguojian', '红果鉴', '1.0', 'm')
        self.assertIn('Source: hongguojian\n', text)
        self.assertIn('\nPackage: hongguojian\n', text)
        self.assertIn('Depends: ${shlibs:Depends}, ${misc:Depends}\n', text)


class DependencyTests(unittest.TestCase):
    def test_dlopen_library_is_appended(self):
        self.assertEqual(linux_package.merge_depends('libc6 (>= 2.34), libgtk-3-0t64'),
                         'libc6 (>= 2.34), libgtk-3-0t64, libmpv2 | libmpv1')

    def test_existing_mpv_entry_is_not_duplicated(self):
        self.assertEqual(linux_package.merge_depends('libc6, libmpv2'), 'libc6, libmpv2')

    def test_empty_result_falls_back_to_curated_list(self):
        for computed in ['', '   ', ',,']:
            self.assertEqual(linux_package.merge_depends(computed),
                             linux_package.FALLBACK_DEPENDS)


class BundleValidationTests(unittest.TestCase):
    def test_every_missing_entry_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            self.assertEqual(set(linux_package.missing_bundle_entries(bundle)),
                             set(linux_package.REQUIRED_BUNDLE_ENTRIES))
            for name in linux_package.REQUIRED_BUNDLE_ENTRIES:
                target = bundle / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('x', encoding='utf-8')
            self.assertEqual(linux_package.missing_bundle_entries(bundle), [])

    def test_incomplete_bundle_is_rejected_before_packaging(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(SystemExit):
                linux_package.build_deb(root / 'bundle', root / 'dist', 'hongguojian',
                                        '红果鉴', '1.0', 'm', root / 'app_icon.png',
                                        root / 'work')


class StagingTests(unittest.TestCase):
    def test_payload_layout_and_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / 'bundle'
            for name in linux_package.REQUIRED_BUNDLE_ENTRIES:
                target = bundle / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('x', encoding='utf-8')
            icon = root / 'app_icon.png'
            icon.write_bytes(b'\x89PNG')
            output = root / 'dist'
            output.mkdir()
            workspace = root / 'work'
            with mock.patch('linux_package.shutil.which', return_value=None), \
                    mock.patch('linux_package.subprocess.run') as runner:
                target = linux_package.build_deb(bundle, output, 'hongguojian', '红果鉴',
                                                 '0.2.102+4', 'm <a@b.c>', icon, workspace)
            package = workspace / 'debian' / 'hongguojian'
            command = runner.call_args.args[0]
            self.assertEqual(command[:3], ['dpkg-deb', '--build', '--root-owner-group'])
            self.assertEqual(command[3], str(package))
            self.assertEqual(command[4], str(target))
            self.assertEqual(target, output / 'hongguojian_0.2.102+4_amd64.deb')
            self.assertTrue((package / 'opt/hongguojian/duanju_app').is_file())
            self.assertTrue((package / 'opt/hongguojian/lib/libduanju_core.so').is_file())
            self.assertTrue((package / 'opt/hongguojian/data/icudtl.dat').is_file())
            self.assertTrue((package / 'usr/share/applications/hongguojian.desktop').is_file())
            self.assertTrue(
                (package / 'usr/share/icons/hicolor/256x256/apps/hongguojian.png').is_file())
            self.assertTrue((workspace / 'debian/control').is_file())
            control = (package / 'DEBIAN/control').read_text(encoding='utf-8')
            self.assertIn('Package: hongguojian\n', control)
            self.assertIn('Version: 0.2.102+4\n', control)
            depends = [line for line in control.splitlines() if line.startswith('Depends: ')]
            self.assertEqual(len(depends), 1)
            self.assertIn('libmpv', depends[0])


if __name__ == '__main__':
    unittest.main()
