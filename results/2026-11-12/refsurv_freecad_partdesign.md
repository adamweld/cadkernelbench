905 cases, 7192 references scored or attempted; 6 cases where the system failed to build or rebuild, 6 lost to a crash or timeout; 253 references passed over as ill-posed

not judged: {'pick_failed': 7}

### Where the face is still there, in one piece

| edit | features | references | correct | silent wrong | false loss | false ambiguous | flagged wrong |
|---|---|---|---|---|---|---|---|
| A: dimension change | 10 | 463 | 462 | 0 | 1 | 0 | 0 |
| A: dimension change | 50 | 296 | 290 | 0 | 6 | 0 | 0 |
| A: dimension change | 200 | 8 | 8 | 0 | 0 | 0 | 0 |
| B: feature appended | 10 | 476 | 467 | 0 | 9 | 0 | 0 |
| B: feature appended | 50 | 313 | 288 | 24 | 1 | 0 | 0 |
| C: feature moved | 10 | 468 | 424 | 0 | 44 | 0 | 0 |
| C: feature moved | 50 | 302 | 274 | 0 | 28 | 0 | 0 |
| D: slot cut through (split) | 10 | 337 | 297 | 0 | 40 | 0 | 0 |
| D: slot cut through (split) | 50 | 208 | 188 | 0 | 20 | 0 | 0 |
| E: slot shortened (merge) | 10 | 456 | 352 | 0 | 104 | 0 | 0 |
| E: slot shortened (merge) | 50 | 279 | 215 | 1 | 63 | 0 | 0 |
| F: feature removed | 10 | 361 | 357 | 0 | 4 | 0 | 0 |
| F: feature removed | 50 | 231 | 229 | 0 | 2 | 0 | 0 |
| G: feature inserted upstream | 10 | 474 | 471 | 0 | 3 | 0 | 0 |
| G: feature inserted upstream | 50 | 302 | 287 | 13 | 2 | 0 | 0 |
| H: two features reordered | 10 | 472 | 472 | 0 | 0 | 0 | 0 |
| H: two features reordered | 50 | 295 | 295 | 0 | 0 | 0 | 0 |
| J: edit made and undone | 10 | 476 | 449 | 0 | 27 | 0 | 0 |
| J: edit made and undone | 50 | 299 | 280 | 6 | 13 | 0 | 0 |

### Where the face is gone

| edit | features | references | correctly lost | silent wrong | flagged wrong |
|---|---|---|---|---|---|
| C: feature moved | 10 | 5 | 5 | 0 | 0 |
| C: feature moved | 50 | 3 | 3 | 0 | 0 |
| D: slot cut through (split) | 10 | 60 | 60 | 0 | 0 |
| D: slot cut through (split) | 50 | 36 | 35 | 1 | 0 |
| E: slot shortened (merge) | 10 | 1 | 1 | 0 | 0 |
| E: slot shortened (merge) | 50 | 3 | 3 | 0 | 0 |
| F: feature removed | 10 | 110 | 110 | 0 | 0 |
| F: feature removed | 50 | 75 | 74 | 1 | 0 |

### Where the surface now bounds the solid in several pieces

| edit | features | references | all pieces | ambiguity reported | one piece at pick | one piece elsewhere | some pieces | lost on split | silent wrong | flagged wrong |
|---|---|---|---|---|---|---|---|---|---|---|
| A: dimension change | 10 | 17 | 0 | 0 | 15 | 2 | 0 | 0 | 0 | 0 |
| A: dimension change | 50 | 24 | 0 | 0 | 22 | 1 | 0 | 1 | 0 | 0 |
| B: feature appended | 10 | 4 | 0 | 0 | 4 | 0 | 0 | 0 | 0 | 0 |
| B: feature appended | 50 | 7 | 0 | 0 | 5 | 1 | 0 | 1 | 0 | 0 |
| C: feature moved | 10 | 7 | 0 | 0 | 6 | 0 | 0 | 1 | 0 | 0 |
| C: feature moved | 50 | 15 | 0 | 0 | 14 | 0 | 0 | 1 | 0 | 0 |
| D: slot cut through (split) | 10 | 83 | 0 | 0 | 31 | 8 | 0 | 44 | 0 | 0 |
| D: slot cut through (split) | 50 | 76 | 0 | 0 | 26 | 7 | 0 | 42 | 1 | 0 |
| E: slot shortened (merge) | 10 | 23 | 0 | 0 | 14 | 6 | 0 | 3 | 0 | 0 |
| E: slot shortened (merge) | 50 | 38 | 0 | 0 | 22 | 2 | 0 | 13 | 1 | 0 |
| F: feature removed | 10 | 9 | 0 | 0 | 9 | 0 | 0 | 0 | 0 | 0 |
| F: feature removed | 50 | 14 | 0 | 0 | 14 | 0 | 0 | 0 | 0 | 0 |
| G: feature inserted upstream | 10 | 6 | 0 | 0 | 6 | 0 | 0 | 0 | 0 | 0 |
| G: feature inserted upstream | 50 | 18 | 0 | 0 | 15 | 0 | 0 | 0 | 3 | 0 |
| H: two features reordered | 10 | 8 | 0 | 0 | 8 | 0 | 0 | 0 | 0 | 0 |
| H: two features reordered | 50 | 17 | 0 | 0 | 17 | 0 | 0 | 0 | 0 | 0 |
| J: edit made and undone | 10 | 4 | 0 | 0 | 4 | 0 | 0 | 0 | 0 | 0 |
| J: edit made and undone | 50 | 6 | 0 | 0 | 6 | 0 | 0 | 0 | 0 | 0 |

