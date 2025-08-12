#!/usr/bin/env bash
set -Eeuo pipefail

# ------------------------------------------------------------------------------
# Autocomplete project runner
# Modes:
#   -build : build artifacts (index + DB/cache)
#   -web   : run Flask UI (auto --load if cache exists, else --build)
#   -cli   : interactive CLI (Engine.complete in a REPL)
#
# Defaults expect this layout:
#   auto_complete/
#     ├─ run.sh    (this script)
#     └─ src/      (Python package)
#     Archive/     (sibling folder to src/, holds .txt corpus)
#     corpus.sqlite (created/used at project root)
#     artifacts.pkl (cache created at project root)
# ------------------------------------------------------------------------------

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$ROOT_DIR/src"

# Python resolver: prefer venv python if present
PY_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "$PY_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then PY_BIN="python3"
  else PY_BIN="python"
  fi
fi

# Defaults (relative to src when invoking -m)
DEFAULT_ROOTS="../Archive"
DEFAULT_DB="sqlite:///../corpus.sqlite"
DEFAULT_CACHE="../artifacts.pkl"
DEFAULT_HOST="127.0.0.1"
DEFAULT_PORT="8000"
DEFAULT_TOPK="10"

MODE=""          # one of: build|web|cli
REBUILD=0        # force rebuild for -web / -cli
ROOTS="$DEFAULT_ROOTS"
DB_DSN="$DEFAULT_DB"
CACHE="$DEFAULT_CACHE"
UNIT=""          # line|paragraph|window
WIN_SIZE=""
WIN_STEP=""
HOST="$DEFAULT_HOST"
PORT="$DEFAULT_PORT"
TOPK="$DEFAULT_TOPK"
VERBOSE=0

usage() {
  cat <<EOF
Usage:
  $(basename "$0") -build [options]
  $(basename "$0") -web   [options]
  $(basename "$0") -cli   [options]

Options:
  -roots "PATH[,PATH,...]"   Corpus roots (default: ${DEFAULT_ROOTS})
  -db "DSN"                  Database DSN (default: ${DEFAULT_DB})
  -cache "PATH"              Cache path   (default: ${DEFAULT_CACHE})
  -unit line|paragraph|window
  -window-size N
  -window-step N
  -host HOST                 (web only; default: ${DEFAULT_HOST})
  -port PORT                 (web only; default: ${DEFAULT_PORT})
  -k TOPK                    (cli only; default: ${DEFAULT_TOPK})
  -rebuild                   Force rebuild (web/cli)
  -v                         Verbose
  -h | --help                Show help

Examples:
  ./run.sh -build -roots "../Archive"
  ./run.sh -web                   # uses cache if present, else builds
  ./run.sh -web -rebuild -port 9000
  ./run.sh -cli -k 15             # interactive REPL over Engine
  ./run.sh -cli -rebuild -roots "../Archive,../MoreTexts"
EOF
}

# --- arg parsing ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    -build) MODE="build"; shift ;;
    -web)   MODE="web";   shift ;;
    -cli)   MODE="cli";   shift ;;
    -rebuild) REBUILD=1; shift ;;
    -roots) ROOTS="${2:-}"; shift 2 ;;
    -db)    DB_DSN="${2:-}"; shift 2 ;;
    -cache) CACHE="${2:-}"; shift 2 ;;
    -unit)  UNIT="${2:-}"; shift 2 ;;
    -window-size) WIN_SIZE="${2:-}"; shift 2 ;;
    -window-step) WIN_STEP="${2:-}"; shift 2 ;;
    -host)  HOST="${2:-}"; shift 2 ;;
    -port)  PORT="${2:-}"; shift 2 ;;
    -k)     TOPK="${2:-}"; shift 2 ;;
    -v)     VERBOSE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 1 ;;
  esac
done

if [[ -z "$MODE" ]]; then
  echo "Error: choose one of -build / -web / -cli"
  usage
  exit 1
fi

# Build common arg list
PYVERB=()
[[ $VERBOSE -eq 1 ]] && PYVERB+=(--verbose)

# Split comma-separated roots into array for argparse --roots nargs+
IFS=',' read -r -a ROOTS_ARR <<< "$ROOTS"

do_build() {
  echo "[run.sh] BUILD → roots=${ROOTS_ARR[*]} | cache=${CACHE} | db=${DB_DSN}"
  cd "$SRC_DIR"
  PYTHONPATH="$SRC_DIR" "$PY_BIN" -m frontend \
    --build \
    --roots "${ROOTS_ARR[@]}" \
    --cache "$CACHE" \
    --db "$DB_DSN" \
    ${UNIT:+--unit "$UNIT"} \
    ${WIN_SIZE:+--window-size "$WIN_SIZE"} \
    ${WIN_STEP:+--window-step "$WIN_STEP"} \
    "${PYVERB[@]}"
}

do_web() {
  echo "[run.sh] WEB  → host=${HOST} port=${PORT} | cache=${CACHE} | db=${DB_DSN}"
  cd "$SRC_DIR"
  # If rebuild requested OR cache missing → build mode; else load
  if [[ $REBUILD -eq 1 || ! -f "$CACHE" ]]; then
    echo "[run.sh] (web) cache missing or -rebuild set → building first"
    PYTHONPATH="$SRC_DIR" "$PY_BIN" -m frontend.web \
      --build \
      --roots "${ROOTS_ARR[@]}" \
      --db "$DB_DSN" \
      --host "$HOST" --port "$PORT" \
      ${UNIT:+--unit "$UNIT"} \
      ${WIN_SIZE:+--window-size "$WIN_SIZE"} \
      ${WIN_STEP:+--window-step "$WIN_STEP"} \
      "${PYVERB[@]}"
  else
    PYTHONPATH="$SRC_DIR" "$PY_BIN" -m frontend.web \
      --load \
      --cache "$CACHE" \
      --db "$DB_DSN" \
      --host "$HOST" --port "$PORT" \
      "${PYVERB[@]}"
  fi
}

do_cli() {
  echo "[run.sh] CLI  → top-k=${TOPK} | cache=${CACHE} | db=${DB_DSN}"
  cd "$SRC_DIR"
  # Decide build vs load for the REPL
  MODE_ENV="load"
  if [[ $REBUILD -eq 1 || ! -f "$CACHE" ]]; then
    echo "[run.sh] (cli) cache missing or -rebuild set → building first"
    MODE_ENV="build"
  fi

  # Run a tiny REPL against Engine.complete
  PYTHONPATH="$SRC_DIR" \
  RUN_MODE="$MODE_ENV" ROOTS_JSON="$(printf '%s\n' "${ROOTS_ARR[@]}" | jq -Rsc 'split("\n")[:-1]')" \
  DB_DSN="$DB_DSN" CACHE="$CACHE" TOPK="$TOPK" UNIT="$UNIT" WIN_SIZE="$WIN_SIZE" WIN_STEP="$WIN_STEP" VERBOSE="$VERBOSE" \
  "$PY_BIN" - <<'PY'
import os, json, sys
from backend.engine import Engine

def env(name, default=""):
    return os.environ.get(name, default)

mode = env("RUN_MODE", "load")
roots = json.loads(env("ROOTS_JSON", "[]"))
db_dsn = env("DB_DSN", "sqlite:///../corpus.sqlite")
cache = env("CACHE", "../artifacts.pkl")
topk = int(env("TOPK", "10") or 10)
unit = env("UNIT", "") or None
win_size = int(env("WIN_SIZE") or 0) or None
win_step = int(env("WIN_STEP") or 0) or None
verbose = bool(int(env("VERBOSE", "0")))

e = Engine()
try:
    if mode == "build":
        if not roots:
            roots = ["../Archive"]
        e.build(
            roots=roots, cache=cache, db_dsn=db_dsn,
            unit=unit, window_size=win_size, window_step=win_step,
            verbose=verbose,
        )
    else:
        e.load(cache=cache, db_dsn=db_dsn, acx=None, verbose=verbose)

    print(f"\nAutocomplete CLI (mode={mode}, top_k={topk})")
    print("Type a query and press Enter. Commands: :q to quit, :k N to set top-k.\n")

    while True:
        try:
            line = input("> ").rstrip("\n")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line.strip() in (":q", ":quit", ":exit"):
            break
        if line.startswith(":k "):
            try:
                topk = max(1, min(50, int(line.split()[1])))
                print(f"top_k set to {topk}")
            except Exception:
                print("usage: :k N  (1..50)")
            continue

        rows = e.complete(line, top_k=topk)
        if not rows:
            print("(no matches)")
            continue

        for i, r in enumerate(rows, 1):
            sent = (r.get("completed_sentence") or "").replace("\n"," ")
            off = r.get("offset") or ["-","-"]
            print(f"{i:>2}. score={r.get('score')} off=({off[0]},{off[1]})  {sent[:140]}")
except Exception as ex:
    print("Error:", ex, file=sys.stderr)
finally:
    try:
        e.shutdown()
    except Exception:
        pass
PY
}

# --- dispatch ---
case "$MODE" in
  build) do_build ;;
  web)   do_web ;;
  cli)   do_cli ;;
  *) echo "Unknown mode: $MODE"; exit 1 ;;
esac
