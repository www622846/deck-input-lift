from pathlib import Path
import importlib.util
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("process_group", Path(__file__).resolve().parents[1] / "native/process_group.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ProcessGroupTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.addCleanup(self.folder.cleanup)

    def process(self, pid, name, parent):
        path = self.root / str(pid)
        path.mkdir(exist_ok=True)
        (path / "stat").write_text(f"{pid} ({name}) S {parent} 0 0 0")

    def group(self, pid):
        return module.process_group(pid, self.root)

    def test_flatpak_window_and_proxy_are_siblings_with_same_container(self):
        for pid, name, parent in [(100, 'systemd', 1), (200, 'bwrap', 100),
                                  (201, 'bwrap', 200), (202, 'xdg-dbus-proxy', 201),
                                  (203, 'bwrap', 200), (204, 'firefox-bin', 203)]:
            self.process(pid, name, parent)
        self.assertEqual(self.group(202), 200)
        self.assertEqual(self.group(204), 200)

    def test_separate_flatpak_instances_remain_separate(self):
        self.process(100, 'systemd', 1)
        for root in (200, 300):
            self.process(root, 'bwrap', 100)
            self.process(root + 1, 'firefox-bin', root)
        self.assertNotEqual(self.group(201), self.group(301))

    def test_native_app_pid_stays_exact(self):
        self.process(100, 'systemd', 1)
        self.process(200, 'konsole', 100)
        self.assertEqual(self.group(200), 200)

    def test_disappearing_process_is_handled(self):
        self.assertEqual(self.group(12345), 12345)

    def test_process_names_with_spaces_and_parentheses(self):
        self.process(200, 'bwrap', 1)
        self.process(201, 'firefox (test)', 200)
        self.assertEqual(self.group(201), 200)

    def test_cycle_is_bounded(self):
        self.process(200, 'bwrap', 201)
        self.process(201, 'firefox-bin', 200)
        self.assertEqual(self.group(201), 200)

    def test_reparented_flatpak_proxy_matches_by_unique_instance(self):
        for pid, parent in ((202, 201), (304, 303)):
            self.process(parent, 'bwrap', 100)
            self.process(pid, 'firefox-bin' if pid == 304 else 'xdg-dbus-proxy', parent)
            root = self.root / str(pid) / 'root'
            root.mkdir()
            (root / '.flatpak-info').write_text('[Application]\nname=org.mozilla.firefox\n[Instance]\ninstance-id=12345\n')
        self.assertEqual(self.group(202), 'flatpak:12345')
        self.assertEqual(self.group(304), 'flatpak:12345')

    def test_distinct_flatpak_instance_ids_do_not_match(self):
        for pid in (202, 304):
            self.process(pid, 'firefox-bin', 1)
            root = self.root / str(pid) / 'root'
            root.mkdir()
            (root / '.flatpak-info').write_text(f'[Instance]\ninstance-id={pid}\n')
        self.assertNotEqual(self.group(202), self.group(304))


if __name__ == '__main__':
    unittest.main()
