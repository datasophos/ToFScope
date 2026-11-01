"""Release prep. End users install bundled assets; npm is never invoked by pip."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def source_hash():
    h = hashlib.sha256()
    for p in sorted(
        [
            *(ROOT / "frontend/src").rglob("*"),
            ROOT / "frontend/package.json",
            ROOT / "frontend/package-lock.json",
            ROOT / "frontend/vite.config.ts",
            ROOT / "frontend/tsconfig.json",
            ROOT / "frontend/index.html",
        ]
    ):
        if p.is_file():
            h.update(str(p.relative_to(ROOT)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def main():
    subprocess.run(["npm", "run", "build"], cwd=ROOT / "frontend", check=True)
    target = ROOT / "src/tofscope/static"
    target.mkdir(exist_ok=True)
    for p in list(target.iterdir()):
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
    shutil.copytree(ROOT / "frontend/dist", target, dirs_exist_ok=True)
    assets = {
        str(p.relative_to(target)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(target.rglob("*"))
        if p.is_file()
    }
    (target / "manifest.json").write_text(
        json.dumps(
            dict(version="0.1.1", source_sha256=source_hash(), assets=assets),
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
    print(f"Bundled {len(assets)} verified local assets.")


if __name__ == "__main__":
    main()
