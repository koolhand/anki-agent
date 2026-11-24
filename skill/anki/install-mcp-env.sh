#!/usr/bin/env bash
# install-mcp-env.sh — build the pinned interpreter the anki MCP server runs on.
#
# WHY a venv and not `uv run --script` (2026-11-24): the agent starts the anki MCP
# server as a long-lived process per session. `uv run` holds ~/.cache/uv/.lock for
# the life of that process, which blocks `uv cache prune`, so the shared package
# cache grew to 11 GB that could not be reclaimed while any agent session was up.
# A venv has no lock of its own: build it from requirements.lock, point the agent
# at .venv/bin/python, and the cache is free to prune whenever it is idle.
#
# Declared, not accumulated: the interpreter is the host's apt python, the packages
# are requirements.lock. Re-running this script is the upgrade path.
#
# Usage: ./install-mcp-env.sh [--python /path/to/python3]
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python_bin="/usr/bin/python3"
if [[ "${1:-}" == "--python" ]]; then python_bin="${2:?--python needs a path}"; fi

command -v uv >/dev/null || { echo "install-mcp-env: uv not on PATH" >&2; exit 1; }
[[ -x "$python_bin" ]] || { echo "install-mcp-env: no interpreter at $python_bin" >&2; exit 1; }

uv venv --python "$python_bin" "$here/.venv" --allow-existing >/dev/null
uv pip install --quiet --python "$here/.venv/bin/python" -r "$here/requirements.lock"

# Readback — a silent no-op is impossible if the interpreter has to answer.
"$here/.venv/bin/python" - <<'PY'
import sys
import mcp
print(f"install-mcp-env: {sys.executable} python {sys.version.split()[0]} mcp {mcp.__version__ if hasattr(mcp, '__version__') else 'ok'}")
PY
