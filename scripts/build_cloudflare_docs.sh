#!/bin/sh
set -eu

# Cloudflare Pages uses Linux x86-64. Keep the renderer aligned with docs.yml.
quarto_version=1.10.20
if ! command -v quarto >/dev/null 2>&1 || [ "$(quarto --version)" != "$quarto_version" ]; then
  quarto_dir="${TMPDIR:-/tmp}/tofscope-quarto-$quarto_version"
  mkdir -p "$quarto_dir"
  curl -fsSL "https://github.com/quarto-dev/quarto-cli/releases/download/v$quarto_version/quarto-$quarto_version-linux-amd64.tar.gz" |
    tar -xz -C "$quarto_dir"
  PATH="$quarto_dir/quarto-$quarto_version/bin:$PATH"
  export PATH
fi

if ! command -v uv >/dev/null 2>&1; then
  python3 -m pip install --user 'uv==0.13.5'
  PATH="$(python3 -m site --user-base)/bin:$PATH"
  export PATH
fi

uv sync --frozen --only-group docs
uv run --frozen --only-group docs great-docs build
uv run --frozen --only-group docs python scripts/check_docs.py great-docs/_site

# Preview deployments should not compete with the canonical GitHub Pages site.
cat > great-docs/_site/_headers <<'EOF'
/*
  X-Robots-Tag: noindex
EOF
