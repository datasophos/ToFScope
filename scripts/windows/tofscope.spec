# Both executables share one set of dependencies in the portable folder.
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

repository = Path(SPECPATH).parent.parent
icon = str(repository / "scripts/windows/tofscope.ico")
datas, binaries, hiddenimports = collect_all("tofscope")
datas.append((icon, "."))
a = Analysis(
    [str(repository / "scripts/windows/entry.py")],
    pathex=[str(repository / "src")],
    binaries=binaries, datas=datas, hiddenimports=hiddenimports,
)
pyz = PYZ(a.pure)
gui = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ToFScope", console=False, icon=icon)
cli = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ToFScope-cli", console=True, icon=icon)
coll = COLLECT(gui, cli, a.binaries, a.datas, name="ToFScope")
