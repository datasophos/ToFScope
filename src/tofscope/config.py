"""Server-owned root, runtime and resource policy. CLI > environment > TOML."""

import os
import sys
import tempfile
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from pathlib import Path


def default_runtime_dir() -> Path:
    """Use a per-user temp directory, retaining the UID suffix on Unix."""
    name = f"tofscope-{os.getuid()}" if hasattr(os, "getuid") else "tofscope"
    return Path(tempfile.gettempdir()) / name


@dataclass(frozen=True)
class Settings:
    data_root: Path = field(default_factory=lambda: Path.cwd())
    runtime_dir: Path = field(default_factory=default_runtime_dir)
    lock_dir: Path | None = None
    output_root: Path | None = None
    mode: str = "local"
    host: str = "127.0.0.1"
    port: int = 8765
    allow_writes: bool = False
    allow_unverified_native: bool = False
    initial_file: Path | None = None
    trusted_proxies: tuple[str, ...] = ()
    identity_header: str = "x-tofscope-user"
    public_origin: str | None = None
    global_bytes: int = 1024**5
    user_bytes: int = 1024**5
    analysis_bytes: int = 1024**5
    response_bytes: int = 1024**4
    analyses_per_user: int = 8
    analyses_global: int = 32
    jobs_per_analysis: int = 4
    jobs_per_user: int = 8
    jobs_global: int = 32
    signals_per_analysis: int = 129
    signals_per_user: int = 512
    signals_global: int = 2048
    workers: int = 2
    lease_seconds: int = 45
    reconnect_seconds: int = 120
    idle_seconds: int = 900

    def __post_init__(self):
        root = Path(self.data_root).expanduser().resolve()
        if not root.is_dir() or not os.access(root, os.R_OK | os.X_OK):
            raise ValueError("Data root must be an accessible directory.")
        object.__setattr__(self, "data_root", root)
        runtime = Path(self.runtime_dir).expanduser().resolve()
        runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock = (
            Path(self.lock_dir).expanduser().resolve()
            if self.lock_dir
            else runtime / "locks"
        )
        lock.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not os.access(runtime, os.W_OK) or not os.access(lock, os.W_OK):
            raise ValueError("Runtime and lock directories must be writable.")
        object.__setattr__(self, "runtime_dir", runtime)
        output = (
            Path(self.output_root).expanduser().resolve() if self.output_root else root
        )
        object.__setattr__(self, "output_root", output)
        object.__setattr__(self, "lock_dir", lock)
        if self.mode not in ("local", "proxy"):
            raise ValueError("Mode must be local or proxy.")
        if self.mode == "local" and self.host not in ("127.0.0.1", "::1", "localhost"):
            raise ValueError("Local mode requires loopback binding.")
        if self.mode == "proxy" and not self.trusted_proxies:
            raise ValueError("Proxy mode requires trusted proxy addresses.")
        for f in fields(self):
            if f.type is bool and type(getattr(self, f.name)) is not bool:
                raise ValueError(f"{f.name} must be true or false.")
            if f.type is int and (
                type(getattr(self, f.name)) is not int or getattr(self, f.name) <= 0
            ):
                raise ValueError(f"{f.name} must be a positive integer.")
        if self.initial_file is not None:
            p = Path(self.initial_file)
            p = p if p.is_absolute() else root / p
            if not p.resolve().is_relative_to(root):
                raise ValueError("Initial acquisition must be inside data root.")
            object.__setattr__(self, "initial_file", p.resolve())


# Storage validators use the policy fields directly; no alternate launcher defaults.


def config_paths(platform: str, env: Mapping[str, str]) -> list[Path]:
    """Return system and user configuration locations in precedence order."""
    home = Path(env.get("HOME") or Path.home())
    if platform == "win32":
        system = Path(env.get("PROGRAMDATA") or "C:/ProgramData")
        user = Path(env.get("LOCALAPPDATA") or home / "AppData/Local")
        return [system / "ToFScope/config.toml", user / "ToFScope/config.toml"]
    if platform == "darwin":
        return [
            Path("/Library/Application Support/ToFScope/config.toml"),
            home / "Library/Application Support/ToFScope/config.toml",
            home / ".config/tofscope/config.toml",
        ]
    xdg = Path(env.get("XDG_CONFIG_HOME") or home / ".config")
    if not xdg.is_absolute():
        xdg = home / ".config"
    return [Path("/etc/tofscope.toml"), xdg / "tofscope/config.toml"]


def load_settings(file=None, env: Mapping[str, str] | None = None, cli=None):
    """Load effective settings from discovered and explicit sources."""
    return load_settings_with_sources(file, env, cli)[0]


def load_settings_with_sources(
    file=None, env: Mapping[str, str] | None = None, cli=None
):
    """Return effective settings and the configuration files actually loaded."""
    env = os.environ if env is None else env
    values = {}
    sources = []
    paths = [(path, False) for path in config_paths(sys.platform, env)]
    if file is not None:
        explicit = Path(file)
        paths = [
            (path, required)
            for path, required in paths
            if path.resolve() != explicit.resolve()
        ]
        paths.append((explicit, True))
    for path, required in paths:
        try:
            with path.open("rb") as stream:
                document = tomllib.load(stream)
        except FileNotFoundError as exc:
            if not required:
                continue
            raise ValueError(f"Cannot load configuration {path}: {exc}") from exc
        except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
            raise ValueError(f"Cannot load configuration {path}: {exc}") from exc
        section = document.get("tofscope", {})
        if not isinstance(section, dict):
            raise TypeError(
                f"Invalid configuration {path}: [tofscope] must be a table."
            )
        unknown = section.keys() - {f.name for f in fields(Settings)}
        if unknown:
            raise ValueError(
                f"Invalid configuration {path}: unknown settings: {', '.join(sorted(unknown))}."
            )
        values.update(section)
        sources.append(path)
    for f in fields(Settings):
        key = "TOFSCOPE_" + f.name.upper()
        if key in env:
            v = env[key]
            if f.type is bool:
                if v.lower() not in ("true", "false"):
                    raise ValueError(f"{key} must be true or false.")
                v = v.lower() == "true"
            elif f.type is int:
                v = int(v)
            elif f.name == "trusted_proxies":
                v = tuple(x.strip() for x in v.split(",") if x.strip())
            values[f.name] = v
    if "TOF_FILE" in env:
        values["initial_file"] = env["TOF_FILE"]
    values.update({k: v for k, v in (cli or {}).items() if v is not None})
    return Settings(**values), sources


def resolve_data_path(settings, relative_path, *, require_file=False):
    if not isinstance(relative_path, str) or "\x00" in relative_path:
        raise ValueError("A root-relative path is required.")
    p = Path(relative_path)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError("Path must stay within data root.")
    try:
        target = (settings.data_root / p).resolve()
    except RuntimeError:
        raise ValueError("Invalid symbolic link.") from None
    if not target.is_relative_to(settings.data_root) or not target.exists():
        raise ValueError("Data path is unavailable.")
    if require_file and not target.is_file():
        raise ValueError("Select an acquisition file.")
    return target


def is_private_output_path(settings, path):
    """Keep owner output trees private even when acquisition/output roots coincide."""
    if not path.is_relative_to(settings.output_root):
        return False
    if not settings.data_root.is_relative_to(settings.output_root):
        return True
    parts = path.relative_to(settings.output_root).parts
    # Owner directories use the SHA-256 identity namespace. The shared root and
    # ordinary acquisition folders remain browsable; owner folders never do.
    return bool(
        parts and len(parts[0]) == 64 and all(c in "0123456789abcdef" for c in parts[0])
    )
