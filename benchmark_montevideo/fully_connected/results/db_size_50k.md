# Montevideo -- Fully-Connected Query, DB Size Sweep

_Run date: 2026-06-06 04:34 UTC_

**Region:** Montevideo, Uruguay -- lat [-35.4, -34.4] x lon [-56.7, -55.7]
**Query:** 20 nodes, 190 edges

| DB nodes | Obj/kw | MPJ matches | MPJ time | MSJ matches | MSJ time | ESPM matches | ESPM time |
|----------|--------|-------------|----------|-------------|----------|--------------|-----------|
| 1,000 | 50 | 0 | 0.5240s | 0 | 0.4311s | 0 | 6.9196s |
| 10,000 | 500 | timeout | >1800s | 10 (cap) | 48.1610s | timeout | >1800s |
| 50,000 | 2500 | timeout | >1800s | timeout | >1800s | timeout | >1800s |
