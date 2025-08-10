# src/autocomplete/__main__.py
import sys
from .engine import load_corpus, get_best_k_completions

def main():
    if len(sys.argv) < 2:
        print("usage: python -m autocomplete <root1> [<root2> ...]")
        sys.exit(1)

    roots = sys.argv[1:]
    corpus = load_corpus(roots)
    print(f"loaded {len(corpus.sentences)} sentences from {len(roots)} root(s).")
    print("enter a prefix (empty line to quit)")

    while True:
        try:
            q = input("> ")
        except EOFError:
            break
        if not q.strip():
            break

        results = get_best_k_completions(q)
        if not results:
            print("(no results yet; waiting for search implementation)")
        for r in results:
            print(f"{r.score:4d} | {r.source_text}:{r.offset} | {r.completed_sentence}")

if __name__ == "__main__":
    main()
