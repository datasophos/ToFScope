"""Small desktop launcher for the portable Windows distribution.

Tk is imported only by the GUI; the controller can be exercised without a display.
"""

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import webbrowser


def state_directory():
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "state")) / "ToFScope"


def load_folder(state):
    try:
        value = json.loads((state / "launcher.json").read_text(encoding="utf-8"))
        folder = value.get("acquisition_folder", "")
        return folder if isinstance(folder, str) else ""
    except (OSError, ValueError, AttributeError):
        return ""


def save_folder(state, folder):
    state.mkdir(parents=True, exist_ok=True)
    temporary = state / "launcher.json.tmp"
    temporary.write_text(json.dumps({"acquisition_folder": str(folder)}), encoding="utf-8")
    temporary.replace(state / "launcher.json")


class ServiceController:
    """Own one service child, its private runtime folder, and its log."""

    def __init__(self, state):
        self.state = Path(state)
        self.log_path = self.state / "service.log"
        self.process = None
        self.runtime_dir = None
        self.started = 0
        self._url = None

    def start(self, folder):
        if self.process is not None:
            raise ValueError("Stop the current service before starting another.")
        folder = Path(folder).expanduser().resolve()
        if not folder.is_dir():
            raise ValueError("Choose an existing acquisition folder.")
        self.state.mkdir(parents=True, exist_ok=True)
        # The service binds this port itself and reports a clear failure if raced.
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        if getattr(sys, "frozen", False):
            command = [str(Path(sys.executable).with_name("ToFScope-cli.exe"))]
        else:
            command = [sys.executable, "-m", "tofscope.windows_launcher"]
        self.runtime_dir = Path(tempfile.mkdtemp(prefix="runtime-", dir=self.state))
        command += ["--launcher-service", str(folder), str(self.runtime_dir), str(port)]
        try:
            with self.log_path.open("w", encoding="utf-8") as log:
                self.process = subprocess.Popen(
                    command, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
        except OSError:
            shutil.rmtree(self.runtime_dir, ignore_errors=True)
            raise
        self.started = time.monotonic()
        self._url = None

    def ready(self):
        if self.process is None or self.process.poll() is not None:
            return False
        try:
            credential = json.loads((self.runtime_dir / "launch.json").read_text())
            # Loopback requests must bypass corporate HTTP proxy settings.
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(credential["url"] + "/readyz", timeout=0.2) as response:
                if response.status != 200:
                    return False
            self._url = credential["url"] + "/#bootstrap=" + credential["secret"]
            return True
        except (OSError, ValueError, KeyError):
            return False

    def browser_url(self):
        if self._url is None:
            raise ValueError("ToFScope is still starting.")
        return self._url

    def stop(self):
        if self.process is None:
            return
        process = self.process
        try:
            if process.poll() is None:
                try:
                    process.stdin.write(b"stop\n")
                    process.stdin.flush()
                except (OSError, ValueError):
                    pass
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        finally:
            try:
                process.stdin.close()
            except OSError:
                # Buffered close can flush again after an earlier broken pipe.
                pass
            self.process = None
            self._url = None
            shutil.rmtree(self.runtime_dir, ignore_errors=True)


def run_worker(arguments):
    from tofscope.cli import run_service
    from tofscope.config import load_settings

    folder, runtime, port = arguments
    settings = load_settings(cli={"data_root": folder, "runtime_dir": runtime, "port": int(port), "mode": "local", "host": "127.0.0.1"})
    shutdown = threading.Event()

    def wait_for_parent():
        # EOF also stops the service if the launcher crashes or is terminated.
        sys.stdin.buffer.readline()
        shutdown.set()

    threading.Thread(target=wait_for_parent, daemon=True).start()
    run_service(settings, shutdown_event=shutdown)
    return 0


def main():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from filelock import FileLock, Timeout

    root = tk.Tk()
    root.title("ToFScope")
    root.resizable(False, False)
    icon = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "tofscope.ico"
    if icon.is_file():
        root.iconbitmap(str(icon))
    state = state_directory()
    state.mkdir(parents=True, exist_ok=True)
    lock = FileLock(state / "launcher.lock")
    try:
        lock.acquire(timeout=0)
    except Timeout:
        messagebox.showinfo("ToFScope", "The ToFScope launcher is already open.", parent=root)
        root.destroy()
        return 0
    service = ServiceController(state)
    folder = tk.StringVar(value=load_folder(state))
    status = tk.StringVar(value="Choose the folder containing your acquisitions.")
    frame = ttk.Frame(root, padding=20)
    frame.grid()
    ttk.Label(frame, text="Acquisition folder").grid(row=0, column=0, sticky="w")
    entry = ttk.Entry(frame, textvariable=folder, width=58)
    entry.grid(row=1, column=0, pady=(6, 12))

    def browse():
        selected = filedialog.askdirectory(parent=root, title="Choose acquisition folder", mustexist=True)
        if selected:
            folder.set(selected)

    browse_button = ttk.Button(frame, text="Browse…", command=browse)
    browse_button.grid(row=1, column=1, padx=(10, 0), pady=(6, 12))
    ttk.Label(frame, textvariable=status, wraplength=470).grid(row=2, column=0, columnspan=2, sticky="w", pady=8)
    opened = False

    def stop():
        nonlocal opened
        service.stop()
        opened = False
        entry.configure(state="normal")
        browse_button.configure(state="normal")
        start_button.configure(text="Start", state="normal")
        stop_button.configure(state="disabled")
        status.set("ToFScope stopped.")

    def open_browser():
        try:
            if not webbrowser.open(service.browser_url()):
                raise OSError("Windows could not open the default browser.")
        except (OSError, ValueError) as exc:
            messagebox.showerror("Could not open browser", str(exc), parent=root)

    def start():
        if service.process is not None:
            open_browser()
            return
        if not folder.get().strip():
            messagebox.showerror("Choose a folder", "Choose an existing acquisition folder.", parent=root)
            return
        try:
            service.start(folder.get())
        except (OSError, ValueError) as exc:
            messagebox.showerror("Could not start ToFScope", str(exc), parent=root)
            return
        try:
            save_folder(state, Path(folder.get()).expanduser().resolve())
        except OSError:
            messagebox.showwarning("Folder preference", "ToFScope started, but the folder preference could not be saved.", parent=root)
        entry.configure(state="disabled")
        browse_button.configure(state="disabled")
        start_button.configure(state="disabled")
        stop_button.configure(state="normal")
        status.set("Starting ToFScope…")

    start_button = ttk.Button(frame, text="Start", command=start)
    start_button.grid(row=3, column=0, sticky="w", pady=10)
    stop_button = ttk.Button(frame, text="Stop", command=stop, state="disabled")
    stop_button.grid(row=3, column=1, pady=10)

    def show_log():
        if service.log_path.exists():
            os.startfile(service.log_path)
        else:
            messagebox.showinfo("ToFScope log", "No service log yet. Start ToFScope first.", parent=root)

    ttk.Button(frame, text="Open log", command=show_log).grid(row=4, column=0, sticky="w")

    def tick():
        nonlocal opened
        if service.process is not None:
            failed = service.process.poll() is not None
            if not opened and not failed and service.ready():
                opened = True
                status.set("ToFScope is running. Keep this window open while you work.")
                start_button.configure(text="Open in browser", state="normal")
                open_browser()
            elif failed or (not opened and time.monotonic() - service.started > 60):
                stop()
                status.set("ToFScope could not start or stopped unexpectedly. Open the log for details.")
                messagebox.showerror("ToFScope stopped", status.get(), parent=root)
        root.after(250, tick)

    def close():
        if service.process is not None and not messagebox.askokcancel(
            "Stop ToFScope?", "Closing this window stops ToFScope. Save your work in the browser first.", parent=root
        ):
            return
        stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    root.after(250, tick)
    try:
        root.mainloop()
    finally:
        service.stop()
        lock.release()
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--launcher-service":
        raise SystemExit(run_worker(sys.argv[2:]))
    raise SystemExit(main())
