# SPM Benchmark

Small benchmark for three spatial pattern matching implementations:

- MPJ
- MSJ
- ESPM

The code is in `src/`. The sample data is in `data/UK/`.

Run all three algorithms:

```bash
python src/main.py --algo all --pattern 0
```

Run one algorithm:

```bash
python src/main.py --algo espm --pattern 0
```

Use `--max-matches 0` to return every match.
