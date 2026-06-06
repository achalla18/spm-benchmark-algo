# SPM Benchmark

Clean version of the spatial pattern matching benchmark.

Algorithms included:

- MPJ
- MSJ
- ESPM

The input files are in `data/UK`.

Run all three algorithms on one pattern:

```bash
python src/main.py --pattern 0 --algo all
```

Run one algorithm:

```bash
python src/main.py --pattern 0 --algo espm
```

Use `--max-matches 0` if you want every match instead of stopping early.
