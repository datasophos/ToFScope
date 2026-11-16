"""Capture documentation screenshots from the deterministic demo dataset."""

import base64
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"
CAPTURES = (
    "tofscope-explore.png",
    "tofscope-front-projection-xz.png",
    "tofscope-front-projection-yz.png",
    "tofscope-isotope-identification.png",
    "tofscope-save-copy.png",
    "tofscope-download-copy.png",
    "tofscope-isotope-measurements.png",
    "tofscope-3d.png",
    "tofscope-3d-signal-settings.png",
    "tofscope-raw-preparation.png",
)
SVG_CAPTURES = {
    "signal-editor.png": "tofscope-signal-editor.svg",
    "depth-calibration.png": "tofscope-depth-calibration.svg",
    "profile-relative.png": "tofscope-profiles-relative.svg",
    "profile-mean.png": "tofscope-profiles-mean.svg",
    "3d-display-settings.png": "tofscope-3d-display-settings.svg",
}


def screenshot_svg(path, *, numbered=False):
    data = path.read_bytes()
    width, height = struct.unpack(">II", data[16:24])
    image = base64.b64encode(data).decode("ascii")
    markers = ""
    if numbered:
        positions = [
            (700, 146),
            (700, 198),
            (400, 285),
            (1600, 285),
            (400, 635),
            (1600, 635),
        ]
        markers = '<g fill="#102536" stroke="white" stroke-width="4" font-family="sans-serif" font-size="30" font-weight="bold" text-anchor="middle" dominant-baseline="central">'
        markers += "".join(
            f'<g><circle cx="{x}" cy="{y}" r="22"/><text x="{x}" y="{y}" fill="white" stroke="none">{i}</text></g>'
            for i, (x, y) in enumerate(positions, 1)
        )
        markers += "</g>"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<image href="data:image/png;base64,{image}" width="{width}" height="{height}"/>{markers}</svg>\n'
    )


def main():
    with tempfile.TemporaryDirectory(prefix="tofscope-doc-images-") as directory:
        env = os.environ | {
            "TOFSCOPE_DOC_OUTPUT": directory,
            "PATH": str(Path(sys.executable).parent)
            + os.pathsep
            + os.environ.get("PATH", ""),
            "PYTHONPATH": str(ROOT / "src"),
        }
        subprocess.run(
            ["npm", "--prefix", "frontend", "run", "capture:docs"],
            cwd=ROOT,
            env=env,
            check=True,
        )
        for name in (*CAPTURES, *SVG_CAPTURES):
            if not (Path(directory) / name).is_file():
                raise RuntimeError(f"Capture did not produce {name}")
        for name in CAPTURES:
            shutil.copyfile(Path(directory) / name, ASSETS / name)
        for source, target in SVG_CAPTURES.items():
            (ASSETS / target).write_text(screenshot_svg(Path(directory) / source))
        (ASSETS / "tofscope-explore-numbered.svg").write_text(
            screenshot_svg(Path(directory) / "tofscope-explore.png", numbered=True)
        )
        print(
            f"Updated {len(CAPTURES) + len(SVG_CAPTURES) + 1} documentation screenshots."
        )


if __name__ == "__main__":
    main()
