from pathlib import Path
import unittest


class WebAssetsTest(unittest.TestCase):
    def test_web_console_assets_exist(self) -> None:
        root = Path("apps/web")

        self.assertTrue((root / "index.html").exists())
        self.assertTrue((root / "static/styles.css").exists())
        self.assertTrue((root / "static/app.js").exists())

    def test_web_console_mount_paths_are_present(self) -> None:
        html = Path("apps/web/index.html").read_text(encoding="utf-8")

        self.assertIn("/static/styles.css", html)
        self.assertIn("/static/app.js", html)
        self.assertIn('data-view="live"', html)
        self.assertIn('data-views="quality"', html)
        self.assertIn('id="match-select"', html)


if __name__ == "__main__":
    unittest.main()
