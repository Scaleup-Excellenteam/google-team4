from __future__ import annotations
import argparse, os, sys
from . import initialize, complete
from .normalize import normalize_only

def _supports_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR", "") == ""

CSI = "\033["
def _c(text: str, code: str) -> str:
    if not _supports_color(): return text
    return f"{CSI}{code}m{text}{CSI}0m"

def _clear_screen():
    # ANSI clear; fallback to newlines if not a TTY
    if sys.stdout.isatty():
        print("\033[2J\033[H", end="", flush=True)
    else:
        print("\n" * 100)

def _print_table(rows):
    if not rows:
        print(_c("(no matches)", "2;37")); return
    print(_c("#  Score  Offset   Source                               Sentence", "1;37"))
    for r in rows:
        print(f"{r['rank']:<2} {r['score']:<6} {r['offset']:<9} {r['source']:<36} {r['sentence']}")

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Autocomplete REPL (fast-start, multi-line aware)")
    parser.add_argument("--roots", nargs="+", default=[], help="Roots (required when rebuilding)")
    parser.add_argument("--cache", default=None)
    parser.add_argument("--acx", default=None)
    parser.add_argument("--db", default=None)
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--single-line", action="store_true")
    parser.add_argument("--unit", choices=["line","paragraph","window"], default=None)
    parser.add_argument("--window-size", type=int, default=None)
    parser.add_argument("--window-step", type=int, default=None)
    parser.add_argument("--echo", action="store_true", help="Echo normalized query as [query] '...'")
    args = parser.parse_args(argv)

    if args.verbose:
        os.environ["AUTOCOMPLETE_VERBOSE"] = "1"

    initialize(args.roots, cache=args.cache, rebuild=args.rebuild, verbose=args.verbose,
               acx=args.acx, db=args.db, unit=args.unit,
               window_size=args.window_size, window_step=args.window_step)

    echo = args.echo
    mode = "single-line" if args.single_line else "incremental"
    print(f"Type a prefix and press Enter (empty to quit).  Type '#' to reset the buffer.  [{mode} mode]")
    print(_c("Commands: :echo on|off, :clear, :reset", "2;37"))

    buffer = ""
    while True:
        try:
            raw = input("> ")
        except EOFError:
            print(); break
        cmd = raw.strip().lower()
        if raw == "":
            print("Goodbye!"); break
        if cmd == "#":
            buffer = ""; print(_c("(reset)", "2;36")); continue
        if cmd == ":reset":
            buffer = ""; print(_c("(reset)", "2;36")); continue
        if cmd in (":clear", ":cls"):
            _clear_screen(); continue
        if cmd == ":echo on":
            echo = True; print(_c("(echo on)", "2;36")); continue
        if cmd == ":echo off":
            echo = False; print(_c("(echo off)", "2;36")); continue

        query = raw if args.single_line else (buffer + raw)
        if not args.single_line:
            buffer = query
        if echo:
            print(f"[query] {normalize_only(query)!r}")

        hits = complete(query)
        rows = []
        for i, h in enumerate(hits, start=1):
            rows.append({
                "rank": i, "score": h.score,
                "offset": f"({h.offset[0]},{h.offset[1]})",
                "source": (h.source_text[:34] + "..") if len(h.source_text) > 36 else h.source_text,
                "sentence": h.completed_sentence
            })
        _print_table(rows)
    return 0

if __name__ == "__main__":
    sys.exit(main())
