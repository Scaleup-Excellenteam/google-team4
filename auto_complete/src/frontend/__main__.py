from __future__ import annotations
import argparse, os, sys, json
from backend import Engine
from backend.config import TOP_K

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Autocomplete CLI (Engine-backed)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--build", action="store_true", help="Build index from --roots")
    g.add_argument("--load", action="store_true", help="Load existing index/db")

    p.add_argument("--roots", nargs="+", default=[], help="Folders to scan for .txt")
    p.add_argument("--cache", default=None, help="Pickle path for index (legacy cache)")
    p.add_argument("--db", default=None, help="SQLite path for corpus")
    p.add_argument("--acx", default=None, help="ACX path (optional fast index)")
    p.add_argument("-k", type=int, default=TOP_K, help="Top-K results")
    p.add_argument("--repl", action="store_true", help="Interactive loop after init")
    p.add_argument("--q", default=None, help="Single query to run once")
    p.add_argument("--unit", choices=["line","paragraph","window"], help="Text unit")
    p.add_argument("--window-size", type=int, default=None)
    p.add_argument("--window-step", type=int, default=None)
    p.add_argument("--json", action="store_true", help="Emit JSON rows")
    p.add_argument("--verbose", action="store_true")

    args = p.parse_args(argv)

    eng = Engine()
    try:
        if args.build:
            if not args.roots:
                p.error("--build requires --roots")
            eng.build(
                roots=args.roots,
                cache=args.cache,
                db_dsn=args.db,
                unit=args.unit,
                window_size=args.window_size,
                window_step=args.window_step,
                verbose=args.verbose,
            )
        else:
            eng.load(cache=args.cache, db_dsn=args.db, acx=args.acx, verbose=args.verbose)

        def run_query(q: str):
            rows = eng.complete(q, top_k=args.k)
            if args.json:
                print(json.dumps([r.__dict__ for r in rows], ensure_ascii=False, indent=2))
            else:
                if not rows:
                    print("(no matches)"); return
                print("#  Score  Offset   Source                               Sentence")
                for i, r in enumerate(rows, 1):
                    off = f"({r.offset[0]},{r.offset[1]})"
                    print(f"{i:<2} {r.score:<6} {off:<9} {r.source_text:<36} {r.completed_sentence}")

        if args.q:
            run_query(args.q)

        if args.repl:
            print("Type a query (empty line to exit).")
            while True:
                try:
                    q = input("> ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if not q:
                    break
                run_query(q)

        return 0
    finally:
        eng.shutdown()

if __name__ == "__main__":
    raise SystemExit(main())
