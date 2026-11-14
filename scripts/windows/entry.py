"""Dispatch the portable GUI, CLI, and launcher-owned service."""

from pathlib import Path
import sys


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--launcher-service":
        from tofscope.windows_launcher import run_worker
        return run_worker(sys.argv[2:])
    if Path(sys.executable).stem.lower() == "tofscope-cli" or len(sys.argv) > 1:
        from tofscope.cli import main as cli_main
        return cli_main()

    from tofscope.windows_launcher import main as launcher_main, state_directory
    state = state_directory()
    state.mkdir(parents=True, exist_ok=True)
    # Windowed executables have no stdout/stderr. Keep unexpected GUI errors
    # available even when startup fails before the launcher window appears.
    with (state / "launcher.log").open("a", encoding="utf-8", buffering=1) as log:
        sys.stdout = sys.stderr = log
        try:
            return launcher_main()
        except Exception:
            import traceback
            traceback.print_exc()
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                None, f"Could not open ToFScope. See {state / 'launcher.log'} for details.",
                "ToFScope startup error", 0x10,
            )
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
