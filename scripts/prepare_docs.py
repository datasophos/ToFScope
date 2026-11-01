"""Prepare shared assets and narrative text exports before Quarto renders.

Great Docs runs this hook from its generated ``great-docs/`` folder. Its
0.17.0 release links to LLM text exports but skips creating them when the
Python API reference is disabled, so create those exports from our guides.
"""

import io
import shutil
from pathlib import Path
from urllib.parse import urljoin

import great_docs
from yaml12 import read_yaml

build = Path.cwd()
repository = build.parent
shutil.copytree(repository / "docs" / "assets", build / "assets", dirs_exist_ok=True)
shutil.copytree(repository / "docs" / "assets", build / "docs" / "assets", dirs_exist_ok=True)
# Great Docs 0.17 only includes this script for gradient navbars, although its
# sticky-sidebar fix is also needed with a solid navbar color.
navbar_script = Path(great_docs.__file__).parent / "assets" / "navbar-style.js"
(build / "navbar-style-include.html").write_text(
    "<script>\n" + navbar_script.read_text(encoding="utf-8") + "\n</script>\n",
    encoding="utf-8",
)
config = read_yaml(repository / "great-docs.yml")
index = [
    "# ToFScope",
    "",
    "> A local application for exploring ToF-SIMS acquisitions.",
    "",
    "## Guides",
    "",
]
full = ["# ToFScope documentation", ""]
for section in config["sections"]:
    section_dir = build / section["dir"]
    for path in sorted(section_dir.glob("*.qmd")):
        _, header, body = path.read_text(encoding="utf-8").split("---", 2)
        title = read_yaml(io.StringIO(header))["title"]
        url = urljoin(config["site_url"], f"{section['dir']}/{path.stem}.html")
        index.append(f"- [{title}]({url})")
        full.extend([f"## {title}", "", f"Source: {url}", "", body.strip(), ""])
(build / "llms.txt").write_text("\n".join(index) + "\n", encoding="utf-8")
(build / "llms-full.txt").write_text("\n".join(full) + "\n", encoding="utf-8")
