990 cases, 7920 references scored or attempted; 0 cases where the system failed to build or rebuild, 0 lost to a crash or timeout; 354 references passed over as ill-posed

not judged: {'unscored': 4, 'pick_failed': 8}

### Where the face is still there, in one piece

| edit | features | references | correct | silent wrong | false loss | false ambiguous | flagged wrong |
|---|---|---|---|---|---|---|---|
| A: dimension change | 10 | 463 | 437 | 26 | 0 | 0 | 0 |
| A: dimension change | 50 | 296 | 261 | 35 | 0 | 0 | 0 |
| A: dimension change | 200 | 72 | 60 | 12 | 0 | 0 | 0 |
| B: feature appended | 10 | 474 | 215 | 259 | 0 | 0 | 0 |
| B: feature appended | 50 | 313 | 108 | 205 | 0 | 0 | 0 |
| B: feature appended | 200 | 75 | 14 | 61 | 0 | 0 | 0 |
| C: feature moved | 10 | 468 | 310 | 157 | 1 | 0 | 0 |
| C: feature moved | 50 | 301 | 156 | 145 | 0 | 0 | 0 |
| C: feature moved | 200 | 71 | 26 | 45 | 0 | 0 | 0 |
| D: slot cut through (split) | 10 | 337 | 74 | 259 | 4 | 0 | 0 |
| D: slot cut through (split) | 50 | 208 | 15 | 193 | 0 | 0 | 0 |
| D: slot cut through (split) | 200 | 47 | 1 | 46 | 0 | 0 | 0 |
| E: slot shortened (merge) | 10 | 456 | 111 | 342 | 3 | 0 | 0 |
| E: slot shortened (merge) | 50 | 279 | 24 | 250 | 5 | 0 | 0 |
| E: slot shortened (merge) | 200 | 68 | 1 | 67 | 0 | 0 | 0 |
| F: feature removed | 10 | 361 | 215 | 131 | 15 | 0 | 0 |
| F: feature removed | 50 | 230 | 118 | 111 | 1 | 0 | 0 |
| F: feature removed | 200 | 52 | 28 | 24 | 0 | 0 | 0 |
| G: feature inserted upstream | 10 | 474 | 265 | 209 | 0 | 0 | 0 |
| G: feature inserted upstream | 50 | 302 | 134 | 168 | 0 | 0 | 0 |
| G: feature inserted upstream | 200 | 74 | 24 | 50 | 0 | 0 | 0 |
| H: two features reordered | 10 | 472 | 455 | 17 | 0 | 0 | 0 |
| H: two features reordered | 50 | 302 | 302 | 0 | 0 | 0 | 0 |
| H: two features reordered | 200 | 78 | 78 | 0 | 0 | 0 | 0 |
| J: edit made and undone | 10 | 476 | 476 | 0 | 0 | 0 | 0 |
| J: edit made and undone | 50 | 314 | 314 | 0 | 0 | 0 | 0 |
| J: edit made and undone | 200 | 77 | 77 | 0 | 0 | 0 | 0 |

### Where the face is gone

| edit | features | references | correctly lost | silent wrong | flagged wrong |
|---|---|---|---|---|---|
| A: dimension change | 200 | 1 | 0 | 1 | 0 |
| C: feature moved | 10 | 5 | 0 | 5 | 0 |
| C: feature moved | 50 | 3 | 0 | 3 | 0 |
| D: slot cut through (split) | 10 | 60 | 0 | 60 | 0 |
| D: slot cut through (split) | 50 | 36 | 0 | 36 | 0 |
| D: slot cut through (split) | 200 | 6 | 0 | 6 | 0 |
| E: slot shortened (merge) | 10 | 1 | 0 | 1 | 0 |
| E: slot shortened (merge) | 50 | 3 | 0 | 3 | 0 |
| E: slot shortened (merge) | 200 | 2 | 0 | 2 | 0 |
| F: feature removed | 10 | 110 | 16 | 94 | 0 |
| F: feature removed | 50 | 75 | 0 | 75 | 0 |
| F: feature removed | 200 | 18 | 0 | 18 | 0 |

### Where the surface now bounds the solid in several pieces

| edit | features | references | all pieces | ambiguity reported | one piece at pick | one piece elsewhere | some pieces | lost on split | silent wrong | flagged wrong |
|---|---|---|---|---|---|---|---|---|---|---|
| A: dimension change | 10 | 17 | 0 | 0 | 16 | 0 | 0 | 0 | 1 | 0 |
| A: dimension change | 50 | 24 | 0 | 0 | 17 | 3 | 0 | 0 | 4 | 0 |
| A: dimension change | 200 | 7 | 0 | 0 | 4 | 0 | 0 | 0 | 3 | 0 |
| B: feature appended | 10 | 4 | 0 | 0 | 0 | 1 | 0 | 0 | 3 | 0 |
| B: feature appended | 50 | 7 | 0 | 0 | 2 | 1 | 0 | 0 | 4 | 0 |
| B: feature appended | 200 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 0 |
| C: feature moved | 10 | 7 | 0 | 0 | 4 | 1 | 0 | 0 | 2 | 0 |
| C: feature moved | 50 | 15 | 0 | 0 | 4 | 2 | 0 | 0 | 9 | 0 |
| C: feature moved | 200 | 9 | 0 | 0 | 4 | 0 | 0 | 0 | 5 | 0 |
| D: slot cut through (split) | 10 | 83 | 0 | 0 | 38 | 11 | 0 | 1 | 33 | 0 |
| D: slot cut through (split) | 50 | 76 | 0 | 0 | 14 | 11 | 0 | 0 | 51 | 0 |
| D: slot cut through (split) | 200 | 19 | 0 | 0 | 1 | 1 | 0 | 0 | 17 | 0 |
| E: slot shortened (merge) | 10 | 23 | 0 | 0 | 3 | 3 | 0 | 0 | 17 | 0 |
| E: slot shortened (merge) | 50 | 38 | 0 | 0 | 4 | 1 | 0 | 0 | 33 | 0 |
| E: slot shortened (merge) | 200 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 10 | 0 |
| F: feature removed | 10 | 9 | 0 | 0 | 3 | 1 | 0 | 1 | 4 | 0 |
| F: feature removed | 50 | 14 | 0 | 0 | 4 | 1 | 0 | 0 | 9 | 0 |
| F: feature removed | 200 | 10 | 0 | 0 | 3 | 1 | 0 | 0 | 6 | 0 |
| G: feature inserted upstream | 10 | 6 | 0 | 0 | 2 | 1 | 0 | 0 | 3 | 0 |
| G: feature inserted upstream | 50 | 18 | 0 | 0 | 3 | 0 | 0 | 0 | 15 | 0 |
| G: feature inserted upstream | 200 | 6 | 0 | 0 | 1 | 0 | 0 | 0 | 5 | 0 |
| H: two features reordered | 10 | 8 | 0 | 0 | 6 | 0 | 0 | 0 | 2 | 0 |
| H: two features reordered | 50 | 18 | 0 | 0 | 18 | 0 | 0 | 0 | 0 | 0 |
| H: two features reordered | 200 | 2 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 |
| J: edit made and undone | 10 | 4 | 0 | 0 | 4 | 0 | 0 | 0 | 0 | 0 |
| J: edit made and undone | 50 | 6 | 0 | 0 | 6 | 0 | 0 | 0 | 0 | 0 |
| J: edit made and undone | 200 | 3 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 0 |

