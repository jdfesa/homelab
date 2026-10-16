"""Cross-module ownership and public links; no access to private evidence or servers."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
IGNORED = {".git", ".local", "tmp", "__pycache__", "appdata", "data", "downloads", "cache", "secrets", "backups", "exports"}


def public(path):
    return not any(part in IGNORED for part in path.relative_to(ROOT).parts)


class RepositoryLayoutTests(unittest.TestCase):
    def test_public_top_level_directories_have_readmes(self):
        for path in ROOT.iterdir():
            if path.is_dir() and not path.name.startswith(".") and path.name not in IGNORED:
                with self.subTest(directory=path.name):
                    self.assertTrue((path / "README.md").is_file())

    def test_public_markdown_links_exist(self):
        for document in ROOT.rglob("*.md"):
            if not public(document):
                continue
            for link in re.findall(r"\]\(([^)]+)\)", document.read_text()):
                if "://" in link or link.startswith(("#", "mailto:")):
                    continue
                with self.subTest(document=str(document.relative_to(ROOT)), link=link):
                    self.assertTrue((document.parent / link.split("#", 1)[0]).exists())

    def test_workload_tests_and_readmes_stay_in_own_module(self):
        for module in ROOT.iterdir():
            if not module.is_dir() or not (module / "ROADMAP.md").is_file():
                continue
            with self.subTest(module=module.name):
                self.assertTrue((module / "README.md").is_file())
                for folder in ("docs", "scripts", "tests"):
                    if (module / folder).is_dir():
                        self.assertTrue((module / folder / "README.md").is_file())
                prefix = "test_" + module.name.replace("-", "_")
                self.assertFalse(list((ROOT / "tests").glob(prefix + "*.py")))

    def test_private_directory_ignored_at_any_module_depth(self):
        patterns = (ROOT / ".gitignore").read_text().splitlines()
        self.assertIn(".local/", patterns)


if __name__ == "__main__":
    unittest.main()
