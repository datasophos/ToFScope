import argparse
import json
from pathlib import Path
import tempfile
from tofscope.api.app import create_app
from tofscope.config import Settings

p = argparse.ArgumentParser()
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
with tempfile.TemporaryDirectory() as d:
    schema = create_app(Settings(Path(d), runtime_dir=Path(d) / "runtime")).openapi()
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(json.dumps(schema, sort_keys=True, indent=2) + "\n")
