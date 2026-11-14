"""Portable launcher preferences and real service lifecycle."""
import tempfile
import time
import unittest
from pathlib import Path

from tofscope.windows_launcher import ServiceController, load_folder, save_folder


class LauncherTests(unittest.TestCase):
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
