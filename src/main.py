import argparse
import os
import time

from common import load_objects, load_patterns
from espm import run_espm
from mpj import run_mpj
from msj import run_msj


def show_matches(name, matches, objects, limit=5):
    print(f"{name}: {len(matches)} matches")
    for match in matches[:limit]:
        items = []
        for kw, oid in sorted(match.items()):
            obj = objects[oid]
            items.append(f"{kw}->{oid}({obj['lon']:.4f},{obj['lat']:.4f})")
        print("  " + ", ".join(items))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/UK")
    parser.add_argument("--pattern", type=int, default=0)
    parser.add_argument("--algo", choices=["mpj", "msj", "espm", "all"], default="all")
    parser.add_argument("--max-matches", type=int, default=20)
    args = parser.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = args.data_dir if os.path.isabs(args.data_dir) else os.path.join(root, args.data_dir)

    objects = load_objects(os.path.join(data_dir, "loc"), os.path.join(data_dir, "doc"))
    patterns = load_patterns(os.path.join(data_dir, "pattern"))

    if args.pattern < 0 or args.pattern >= len(patterns):
        raise SystemExit(f"pattern must be between 0 and {len(patterns) - 1}")

    pattern = patterns[args.pattern]
    runners = []
    if args.algo in ("mpj", "all"):
        runners.append(("MPJ", run_mpj))
    if args.algo in ("msj", "all"):
        runners.append(("MSJ", run_msj))
    if args.algo in ("espm", "all"):
        runners.append(("ESPM", run_espm))

    print(f"objects: {len(objects)}")
    print(f"patterns: {len(patterns)}")
    print(f"using pattern: {args.pattern}")
    print()

    for name, runner in runners:
        start = time.perf_counter()
        matches = runner(objects, pattern, max_matches=args.max_matches)
        elapsed = time.perf_counter() - start
        show_matches(name, matches, objects)
        print(f"time: {elapsed:.6f}s")
        print()


if __name__ == "__main__":
    main()
