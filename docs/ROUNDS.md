# Rounds: public cases and private draws

Every suite here is generated from seeds. That allows something a hand-written benchmark cannot do: the same families can be drawn again, as cases nobody has seen, and the draw can be proved afterwards.

## Why

The published cases are public, so a kernel can be tuned until they pass. That is useful, and it means a pass rate on published cases says less about the next case than it appears to. A fresh draw from the same families, run before anyone outside has seen it, measures what the published cases cannot. The difference between a kernel's public and private rates, family by family, is the measure of how far it has been fitted to the public cases.

A result nobody can check is not worth much either. So a private draw is committed to before it is run and revealed afterwards.

## The three tiers

| Tier | What | Where | Becomes public |
|---|---|---|---|
| 1 | The round named `public`: the cases this repository has always generated, and every stored result so far | Here | Always |
| 2 | Private rounds: the same generators drawn from a secret key | The key and the results are kept outside this repository until the round is revealed | When the round's results are published |
| 3 | Private families: generators and hand-written cases not yet published | A separate private repository | When retired |

Tier 2 protects against a kernel memorising cases. It does not protect against a kernel being tuned to what a public generator tends to produce, because the generator can be read. Tier 3 exists for that.

## How a private round works

1. **Commit the generator.** A round is bound to one commit of this repository.
2. **Make the round.** This writes a random 256-bit key to a file outside the repository and prints a ledger entry holding a commitment, not the key.

   ```bash
   python -m ckb.rounds new 2026-11-r1 --key-file ~/ckb-keys/2026-11-r1.key
   ```

3. **Publish the commitment before running anything.** Append the printed line to `rounds/ledger.jsonl`, commit and push. The push time is the proof that the key existed before the results did.
4. **Run the round**, on a checkout of the committed generator, with the round's name and key in the environment.

   ```bash
   CKB_ROUND=2026-11-r1 CKB_ROUND_KEY=$(cat ~/ckb-keys/2026-11-r1.key) .venv-occt/bin/python -m ckb.kernels.occt --out 2026-11-r1_occt.jsonl
   ```

   Summarise with the same two variables set.
5. **Publish and reveal together.** Replace the round's ledger line with the revealed one, and add the results under `results/`.

   ```bash
   python -m ckb.rounds reveal 2026-11-r1 --key-file ~/ckb-keys/2026-11-r1.key
   ```

6. **Anyone can check.** `python -m ckb.rounds verify` confirms every revealed key matches its commitment. Checking out the round's `generator` commit and running with the revealed key regenerates the same cases.

The commitment is the SHA-256 of the round's name, the generator's commit and the key. Binding the commit means the code that makes the cases cannot be changed after the results are seen, any more than the key can.

## What may be published before a round is revealed

Rates and public-minus-private differences, by family. Not the cases, not the per-case output, and not the key.

A failure found in a private round is worth more to a kernel's authors as a small reproducible case than as a number. Reporting it spends that case. The intended course is to reveal the round, report from it, and draw the next one.

## Rules

- A key is used for one round and never reused.
- A key is never stored in this repository, in a CI log, or anywhere a kernel's authors can read. `ckb.rounds` refuses a key file inside the repository.
- Private cases are never sent to a kernel that someone else hosts. Every adapter here runs its kernel locally.
- A round is run for every kernel with an adapter, and all of them are published at the reveal, favourable or not.
- Changing a generator changes what a key draws. Stored results name their generator commit for that reason.

## What this does not yet do

- **No round has been run for publication.** The mechanism was exercised on 2026-11-13 with a throwaway key on OCCT 8.0.1: 300 feature sequences, 2,100 near-degenerate pairs and 600 generic pairs ran and summarised normally.
- **Result files do not record their round or generator commit.** The file name and the ledger carry it for now.
- **Rounds change the draw, not the size.** The number of cases per family is fixed in `ckb/core.py`. How many private cases are needed for a difference to mean something has not been worked out.
- **The reference-survival systems draw one internal sample from a fixed seed** (`random.Random(1)` in `ckb/refsurv/systems/`). It picks a point on a face and is not part of the case; it is unchanged.
- **No tier 3 repository exists yet.**

## A side finding: one family is not stable across machines

Running the `public` round again on a different machine on 2026-11-13, OCCT 8.0.1 gave the stored outcome on 2,398 of 2,400 cases (feature sequences and near-degenerate pairs, no fuzzy tolerance). The two that differ are both `sphere_tangent` at offset exactly zero: the union is reported invalid here and was `ok` in `results/2026-11-11/`. The unmodified code on the same machine gives the same two differences, so the cause is the machine or its libraries, not the rounds change. It has not been investigated. It is the first evidence here that a kernel's outcome on a degenerate case can depend on where it runs.
