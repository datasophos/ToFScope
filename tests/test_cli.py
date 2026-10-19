import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tofscope.config import load_settings
from tofscope.cli import main


class CLITests(unittest.TestCase):
    def test_precedence_and_booleans(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            f = p / "config.toml"
            f.write_text("[tofscope]\nport=8000\n")
            s = load_settings(
                f,
                {"TOFSCOPE_PORT": "8001", "TOFSCOPE_DATA_ROOT": d},
                {"port": 8002, "runtime_dir": p / "runtime"},
            )
            self.assertEqual(s.port, 8002)
            with self.assertRaises(ValueError):
                load_settings(
                    None, {"TOFSCOPE_ALLOW_WRITES": "maybe", "TOFSCOPE_DATA_ROOT": d}
                )
            with self.assertRaises(ValueError):
                load_settings(None, {"TOFSCOPE_DATA_ROOT": str(p / "missing")})

    def test_no_browser_service_and_doctor(self):
        with (
            tempfile.TemporaryDirectory() as d,
            patch("tofscope.cli.webbrowser.open") as browser,
            patch("tofscope.cli.run_service") as run,
        ):
            self.assertEqual(
                main(
                    [
                        "serve",
                        "--data-root",
                        d,
                        "--runtime-dir",
                        str(Path(d) / "runtime"),
                        "--no-browser",
                    ]
                ),
                0,
            )
            run.assert_called_once()
            browser.assert_not_called()
    def test_browser_opens_only_after_readiness(self):
        from tofscope.cli import open_after_ready
        from urllib.error import URLError
        from threading import Event
        from unittest.mock import MagicMock
        response=MagicMock();response.__enter__.return_value.status=200
        with patch('tofscope.cli.urllib.request.urlopen',side_effect=[URLError('starting'),response]) as fetch,patch('tofscope.cli.webbrowser.open') as browser:
            open_after_ready('http://127.0.0.1:8765','test-token',Event());self.assertEqual(fetch.call_count,2);browser.assert_called_once()
    def test_occupied_port_never_opens_browser(self):
        from tofscope.cli import run_service
        from tofscope.config import Settings
        with tempfile.TemporaryDirectory() as d,patch('tofscope.cli.socket.socket') as socket,patch('tofscope.cli.webbrowser.open') as browser:
            socket.return_value.bind.side_effect=OSError('occupied')
            with self.assertRaisesRegex(ValueError,'Port'):run_service(Settings(Path(d),runtime_dir=Path(d)/'runtime'),browser=True)
            browser.assert_not_called()
