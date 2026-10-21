"""Shallow directory enumeration; no HDF5 reads during browsing."""
import os
from dataclasses import dataclass,asdict
from pathlib import Path
from tofscope.config import resolve_data_path, is_private_output_path


@dataclass(frozen=True)
class DirectoryPage:
    path: str
    entries: list[dict]
    total: int
    next_offset: int | None

    def to_dict(self):return asdict(self)


def list_data_files(settings, relative_dir: str='', *, query: str='', offset: int=0, limit: int=100):
    if type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=200:
        raise ValueError('Directory offset must be nonnegative and page size between 1 and 200.')
    if not isinstance(query,str) or len(query)>256:raise ValueError('Search must be at most 256 characters.')
    directory=resolve_data_path(settings,relative_dir)
    if is_private_output_path(settings, directory):raise ValueError("Use the owner-scoped saved file list.")
    if not directory.is_dir():raise ValueError('Select a directory to browse.')
    entries=[]
    with os.scandir(directory) as scan:
        for entry in scan:
            name=entry.name
            if name.startswith('.') or name.endswith('~') or any(mark in name.lower() for mark in ('.tmp.','.bak.','.lock.','.backup.')):continue
            if query.casefold() not in name.casefold():continue
            try:
                stat=entry.stat()
                target=resolve_data_path(settings,str((directory/name).relative_to(settings.data_root)))
                if is_private_output_path(settings, target):continue
                kind='directory' if target.is_dir() else 'file'
                if kind=='file' and (target.suffix.lower() not in ('.h5','.hdf5') or not target.is_file()):continue
            except (OSError,ValueError):continue
            entries.append(dict(name=name,path=str((directory/name).relative_to(settings.data_root)),kind=kind,size=stat.st_size,mtime=stat.st_mtime))
    entries.sort(key=lambda e:(e['kind']!='directory',e['name'].casefold(),e['name']))
    total=len(entries);end=offset+limit
    return DirectoryPage(str(directory.relative_to(settings.data_root)) if directory!=settings.data_root else '',entries[offset:end],total,end if end<total else None)
