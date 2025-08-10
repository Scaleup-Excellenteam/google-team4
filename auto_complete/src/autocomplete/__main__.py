from __future__ import annotations
import sys
from .engine import Engine, build_index_fast
from .config import TOP_K
from . import config as CFG  # <-- add

def _print_results(results):
    if not results:
        print("(no matches)")
        return
    for r in results:
        print(f"- {r.completed_sentence}  | {r.source_text}:{r.offset}  | score={r.score}")

def main():
    eng = Engine()

    CFG.READ_MODE = "threads"
    CFG.WORKERS = 16   

    build_index_fast(eng)

    if len(sys.argv) > 1:
        prefix = " ".join(sys.argv[1:])
        _print_results(eng.query(prefix, k=TOP_K))
        return

    print("Type a prefix and press Enter (empty to quit).")
    while True:
        try:
            prefix = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not prefix:
            break
        _print_results(eng.query(prefix, k=TOP_K))

if __name__ == "__main__":
    main()
