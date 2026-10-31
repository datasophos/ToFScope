import io
import json
import os
import socket
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tofscope.cli import main
from tofscope.config import load_settings


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
    def test_doctor_reports_success_and_supports_json(self):
        with tempfile.TemporaryDirectory() as d:
            args = ["doctor", "--data-root", d, "--runtime-dir", str(Path(d) / "runtime")]
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(args), 0)
            self.assertIn("Everything looks good", output.getvalue())
            self.assertNotIn('"data_root"', output.getvalue())

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main([*args, "--json"]), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(Path(report["data_root"]), Path(d).resolve())
            self.assertIn("asset_version", report)

    def test_doctor_reports_asset_failure(self):
        with tempfile.TemporaryDirectory() as d:
            output = io.StringIO()
            with (
                patch("tofscope.cli.asset_status", side_effect=ValueError("Assets missing")),
                redirect_stdout(io.StringIO()),
                redirect_stderr(output),
            ):
                self.assertEqual(main(["doctor", "--data-root", d]), 2)
            self.assertIn("Assets missing", output.getvalue())

    @unittest.skipIf(os.name == "nt", "POSIX address reuse semantics")
    def test_service_restarts_after_connection_and_rejects_active_listener(self):
        from tofscope.cli import run_service
        from tofscope.config import Settings

        with tempfile.TemporaryDirectory() as d, socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
            probe.close()
            settings = Settings(Path(d), runtime_dir=Path(d) / "runtime", port=port)
            calls = []

            def serve_once(*, sockets):
                listener = sockets[0]
                # Another process must not be able to take over a live port.
                with socket.socket() as contender:
                    contender.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    with self.assertRaises(OSError):
                        contender.bind(("127.0.0.1", port))
                        contender.listen()
                # Server closes first so its connection enters TIME_WAIT.
                with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
                    connection, _ = listener.accept()
                    connection.close()
                    self.assertEqual(client.recv(1), b"")
                calls.append(True)

            with (
                patch("tofscope.cli.asset_status"),
                patch("tofscope.cli.create_app"),
                patch("tofscope.cli.uvicorn.Config"),
                patch("tofscope.cli.uvicorn.Server") as server,
                redirect_stdout(io.StringIO()),
            ):
                server.return_value.run.side_effect = serve_once
                run_service(settings)
                run_service(settings)
            self.assertEqual(len(calls), 2)

    def test_browser_opens_only_after_readiness(self):
        from threading import Event
        from unittest.mock import MagicMock
        from urllib.error import URLError

        from tofscope.cli import open_after_ready
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
