"""Server-owned POSIX data-root policy shared by listings, reads and writes."""
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from explorer import DEFAULT_FILE


@dataclass(frozen=True)
class ServerSettings:
    data_root: Path
    allow_writes: bool = False
    initial_file: Path | None = None

    def __post_init__(self):
        root=Path(self.data_root).expanduser().resolve()
        if not root.is_dir():
            raise ValueError('TOFSCOPE_DATA_ROOT must name an existing directory.')
        object.__setattr__(self,'data_root',root)
        if self.initial_file is not None:
            initial=Path(self.initial_file).expanduser().resolve()
            try: relative=initial.relative_to(root)
            except ValueError: raise ValueError('TOF_FILE must be inside TOFSCOPE_DATA_ROOT.') from None
            object.__setattr__(self,'initial_file',resolve_data_path(self,str(relative),require_file=True))


def load_server_settings(env: Mapping[str,str]) -> ServerSettings:
    configured='TOFSCOPE_DATA_ROOT' in env
    root=Path(env['TOFSCOPE_DATA_ROOT']) if configured else DEFAULT_FILE.parent
    value=env.get('TOFSCOPE_ALLOW_WRITES','false').lower()
    if value not in ('true','false'):
        raise ValueError('TOFSCOPE_ALLOW_WRITES must be true or false.')
    initial=env.get('TOF_FILE')
    if initial is None and not configured and DEFAULT_FILE.is_file():initial=str(DEFAULT_FILE)
    if initial is not None:
        candidate=Path(initial).expanduser()
        initial=candidate if candidate.is_absolute() else root/candidate
    return ServerSettings(root,value=='true',initial)


def resolve_data_path(settings, relative_path: str, *, require_file: bool=False) -> Path:
    """Reject traversal and escaping symlinks; root ownership must be trusted."""
    if not isinstance(relative_path,str) or '\x00' in relative_path:
        raise ValueError('A root-relative data path is required.')
    relative=Path(relative_path)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Paths must stay inside the configured data root.')
    target=(settings.data_root/relative).resolve()
    if not target.is_relative_to(settings.data_root):
        raise ValueError('Paths must stay inside the configured data root.')
    if not target.exists():raise ValueError('The selected data path no longer exists.')
    if require_file and not target.is_file():raise ValueError('Select an existing acquisition file.')
    return target
