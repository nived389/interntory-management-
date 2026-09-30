#!/bin/zsh
cd "$(dirname "$0")"
if [[ ! -x .venv-modern/bin/python ]]; then
  runtime_python="/Users/nived/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
  if [[ ! -x "$runtime_python" ]]; then runtime_python="python3"; fi
  "$runtime_python" -m venv .venv-modern || exit 1
  .venv-modern/bin/pip install -r requirements.txt || exit 1
fi
open http://127.0.0.1:5055
if [[ -f data/turso-connection.json ]]; then
  exec .venv-modern/bin/python run_connected.py
fi
exec .venv-modern/bin/python app.py
