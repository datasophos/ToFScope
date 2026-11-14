"""Portable launcher preferences and real service lifecycle."""
import tempfile
import time
import unittest
from pathlib import Path

from tofscope.windows_launcher import ServiceController, load_folder, save_folder


class LauncherTests(unittest.TestCase):
    def test_open_file_uses_platform_handler(self):
        from unittest.mock import patch
        from tofscope.windows_launcher import open_local_file
        path = Path("/tmp/tofscope-config.toml")
        with patch("os.name", "posix"), patch("sys.platform", "darwin"), patch("subprocess.Popen") as process:
            open_local_file(path)
        process.assert_called_once_with(["open", str(path)])

    def test_button_icons_use_native_foreground(self):
        from types import SimpleNamespace
        from tofscope.windows_launcher import button_icons

        class Image:
            def __init__(self, **kwargs):
                self.colors = set()

            def put(self, color, position):
                self.colors.add(color)

        for color in ("#222222", "#ffffff"):
            icons = button_icons(SimpleNamespace(PhotoImage=Image), color)
            self.assertTrue(all(icon.colors == {color} for icon in icons.values()))

    def test_config_created_and_preserved(self):
        from tofscope.windows_launcher import ensure_config
        from tofscope.config import load_settings
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            config = ensure_config(state)
            self.assertIn("uncomment", config.read_text().lower())
            self.assertIn("Stop, then Start", config.read_text())
            self.assertEqual(load_settings(config, env={}, cli={"data_root": state}).response_bytes, 1024**4)
            config.write_text("[tofscope]\nresponse_bytes = 12345\n")
            self.assertEqual(ensure_config(state).read_text(), "[tofscope]\nresponse_bytes = 12345\n")

    def test_worker_loads_config_and_keeps_launcher_settings(self):
        from unittest.mock import patch
        from tofscope.windows_launcher import run_worker
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            config = state / "config.toml"
            config.write_text('[tofscope]\nresponse_bytes = 12345\nhost = "0.0.0.0"\nport = 1\n')
            with patch("tofscope.cli.run_service") as run, patch("threading.Thread"):
                run_worker([str(state), str(state / "runtime"), "1234", str(config)])
            settings = run.call_args.args[0]
            self.assertEqual(settings.response_bytes, 12345)
            self.assertEqual((settings.host, settings.port), ("127.0.0.1", 1234))

    def test_worker_reads_changes_on_next_start(self):
        from unittest.mock import patch
        from tofscope.windows_launcher import run_worker
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            config = state / "config.toml"
            arguments = [str(state), str(state / "runtime"), "1234", str(config)]
            with patch("tofscope.cli.run_service") as run, patch("threading.Thread"):
                config.write_text("[tofscope]\nresponse_bytes = 100\n")
                run_worker(arguments)
                config.write_text("[tofscope]\nresponse_bytes = 200\n")
                run_worker(arguments)
            self.assertEqual([call.args[0].response_bytes for call in run.call_args_list], [100, 200])

    def test_preferences_roundtrip_and_invalid_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            self.assertEqual(load_folder(state), "")
            folder = state / "acquisitions with spaces"
            folder.mkdir()
            save_folder(state, folder)
            self.assertEqual(load_folder(state), str(folder))
            (state / "launcher.json").write_text("broken")
            self.assertEqual(load_folder(state), "")

    def test_service_ready_duplicate_start_and_clean_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            folder = state / "acquisitions with spaces"
            folder.mkdir()
            service = ServiceController(state)
            try:
                service.start(folder)
                process = service.process
                with self.assertRaises(ValueError):
                    service.start(folder)
                deadline = time.monotonic() + 30
                while not service.ready() and time.monotonic() < deadline:
                    if process.poll() is not None:
                        self.fail(service.log_path.read_text())
                    time.sleep(0.1)
                self.assertTrue(service.ready(), service.log_path.read_text())
                self.assertIn("#bootstrap=", service.browser_url())
                service.stop()
                self.assertEqual(process.returncode, 0)
                self.assertFalse(service.ready())
                self.assertFalse(service.runtime_dir.exists())
                service.stop()
            finally:
                service.stop()

    def test_invalid_folder_does_not_start_process(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ServiceController(Path(directory))
            with self.assertRaises(ValueError):
                service.start(Path(directory) / "missing")
            self.assertIsNone(service.process)

    def test_service_stops_when_parent_pipe_closes(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ServiceController(Path(directory))
            try:
                service.start(Path(directory))
                process = service.process
                process.stdin.close()
                self.assertEqual(process.wait(timeout=15), 0, service.log_path.read_text())
            finally:
                service.stop()

    def test_startup_failure_is_available_in_log(self):
        from unittest.mock import patch
        import os
        with tempfile.TemporaryDirectory() as directory:
            service = ServiceController(Path(directory))
            try:
                with patch.dict(os.environ, {"TOFSCOPE_GLOBAL_BYTES": "invalid"}):
                    service.start(Path(directory))
                self.assertNotEqual(service.process.wait(timeout=15), 0)
                self.assertFalse(service.ready())
                self.assertIn("invalid", service.log_path.read_text())
            finally:
                service.stop()

    def test_stop_cleans_up_if_child_exits_during_pipe_write(self):
        import subprocess
        import sys
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            service = ServiceController(Path(directory))
            service.runtime_dir = Path(directory) / "runtime"
            service.runtime_dir.mkdir()
            process = subprocess.Popen([sys.executable, "-c", "pass"], stdin=subprocess.PIPE)
            process.wait(timeout=5)
            service.process = process
            # Model the child exiting immediately after the initial poll.
            with patch.object(process, "poll", return_value=None):
                service.stop()
            self.assertIsNone(service.process)
            self.assertFalse(service.runtime_dir.exists())
