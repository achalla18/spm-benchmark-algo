# Montevideo -- Scale-Free Query (BA m=2), DB Size Sweep

_Run date: 2026-06-06 04:34 UTC_

**Region:** Montevideo, Uruguay -- lat [-35.4, -34.4] x lon [-56.7, -55.7]
**Query:** 20 nodes, 37 edges

| DB nodes | Obj/kw | MPJ matches | MPJ time | MSJ matches | MSJ time | ESPM matches | ESPM time |
|----------|--------|-------------|----------|-------------|----------|--------------|-----------|
| 1,000 | 50 | 0 | 0.2015s | 0 | 0.0887s | 0 | 3.7051s |
| 10,000 | 500 | timeout | >1800s | 10 (cap) | 7.3515s | timeout | >1800s |
| 50,000 | 2500 | timeout | >1800s | timeout | >1800s | timeout | >1800s |
