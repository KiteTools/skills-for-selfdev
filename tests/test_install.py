import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("installer", Path(__file__).resolve().parents[1] / "scripts/install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / "repo"
        self.skill = self.root / "skills" / "sample"
        (self.skill / "references").mkdir(parents=True)
        (self.skill / "SKILL.md").write_text("sample instructions")
        (self.skill / "references" / "guide.md").write_text("guide")
        self.dest = self.base / "installed"

    def test_complete_copy_does_not_modify_source(self):
        installer.install(["sample"], self.dest, self.root)
        self.assertEqual((self.dest / "sample/references/guide.md").read_text(), "guide")
        self.assertEqual((self.skill / "SKILL.md").read_text(), "sample instructions")

    def test_existing_install_is_untouched(self):
        installer.install(["sample"], self.dest, self.root)
        (self.dest / "sample/SKILL.md").write_text("user edit")
        with self.assertRaises(ValueError):
            installer.install(["sample"], self.dest, self.root)
        self.assertEqual((self.dest / "sample/SKILL.md").read_text(), "user edit")

    def test_unknown_name_prevents_partial_install(self):
        with self.assertRaises(ValueError):
            installer.install(["sample", "../../outside"], self.dest, self.root)
        self.assertFalse(self.dest.exists())

    def test_source_symlink_is_refused(self):
        external = self.base / "private.txt"
        external.write_text("not to be copied")
        (self.skill / "linked.txt").symlink_to(external)
        with self.assertRaises(ValueError):
            installer.install(["sample"], self.dest, self.root)
        self.assertFalse(self.dest.exists())

    def test_destination_symlink_is_refused(self):
        real = self.base / "real"
        real.mkdir()
        self.dest.symlink_to(real, target_is_directory=True)
        with self.assertRaises(ValueError):
            installer.install(["sample"], self.dest, self.root)
        self.assertEqual(list(real.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
