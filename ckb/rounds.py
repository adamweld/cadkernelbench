# SPDX-License-Identifier: MIT OR Apache-2.0
"""Rounds: which draw of the generated cases a run uses.

The published cases are round "public": every case's random choices come
from a fixed formula on its id, as they always have, so stored results
stay reproducible.

A private round draws the same families from a secret key instead. The
key is committed to before the round is run and revealed after its
results are published, so that anyone can then regenerate the cases and
check the result. See docs/ROUNDS.md.

    python -m ckb.rounds new NAME --key-file PATH   make a key, print its ledger entry
    python -m ckb.rounds reveal NAME --key-file PATH  print the entry with the key filled in
    python -m ckb.rounds verify [LEDGER]            check every revealed entry

The key reaches a run through two environment variables, which worker
processes inherit:

    CKB_ROUND      the round's name
    CKB_ROUND_KEY  its key, 64 hex characters
"""
import argparse
import datetime
import hashlib
import json
import os
import random
import secrets
import subprocess
import sys

PUBLIC = "public"
LEDGER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rounds", "ledger.jsonl")


def current():
    """(name, key) of the round this process runs. key is None for the public round."""
    name = os.environ.get("CKB_ROUND", PUBLIC)
    key = os.environ.get("CKB_ROUND_KEY")
    if name == PUBLIC:
        if key:
            raise SystemExit("CKB_ROUND_KEY is set but CKB_ROUND is not: name the round")
        return PUBLIC, None
    if not key:
        raise SystemExit(f"round {name!r} needs its key in CKB_ROUND_KEY")
    _check_key(key)
    return name, key


def _check_key(key):
    if len(key) != 64 or any(ch not in "0123456789abcdef" for ch in key):
        raise SystemExit("a round key is 64 lower-case hex characters")


def rng(stream, case_id, public_seed):
    """The random generator for one stream of one case.

    stream names what the numbers are for ("boolean", "chain", ...), so
    that two streams of one case are independent. public_seed is the seed
    this stream has always had in the public round.
    """
    name, key = current()
    if key is None:
        return random.Random(public_seed)
    h = hashlib.sha256(f"ckb-case-v1\n{key}\n{stream}\n{case_id}".encode()).digest()
    return random.Random(int.from_bytes(h, "big"))


def commitment(name, generator, key):
    """What is published before a round is run. It binds the key to the
    round's name and to the commit of the generator, so neither the cases
    nor the code that makes them can be chosen after the results are seen."""
    return hashlib.sha256(f"ckb-round-v1\n{name}\n{generator}\n{key}".encode()).hexdigest()


def _head():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dirty = subprocess.run(["git", "-C", root, "status", "--porcelain", "--untracked-files=no"],
                           capture_output=True, text=True, check=True).stdout.strip()
    if dirty:
        raise SystemExit("commit your changes first: a round is bound to a commit of the generator")
    return subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()


def _entries(path):
    if not os.path.exists(path):
        return []
    return [json.loads(line) for line in open(path) if line.strip()]


def verify(path):
    """Every revealed entry's key must reproduce its commitment, and names must be unique."""
    bad, seen = 0, set()
    for e in _entries(path):
        if e["round"] in seen or e["round"] == PUBLIC:
            print(f"{e['round']}: name used twice or reserved")
            bad += 1
        seen.add(e["round"])
        if e.get("key") is None:
            print(f"{e['round']}: committed {e['committed']}, not yet revealed")
        elif commitment(e["round"], e["generator"], e["key"]) == e["commitment"]:
            print(f"{e['round']}: revealed {e['revealed']}, key matches its commitment")
        else:
            print(f"{e['round']}: KEY DOES NOT MATCH ITS COMMITMENT")
            bad += 1
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for cmd in ("new", "reveal"):
        p = sub.add_parser(cmd)
        p.add_argument("name")
        p.add_argument("--key-file", required=True, help="where the key is kept; never inside this repository")
        p.add_argument("--ledger", default=LEDGER)
    sub.add_parser("verify").add_argument("ledger", nargs="?", default=LEDGER)
    a = ap.parse_args()
    today = datetime.date.today().isoformat()
    if a.cmd == "verify":
        sys.exit(1 if verify(a.ledger) else 0)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if os.path.commonpath([root, os.path.abspath(a.key_file)]) == root:
        raise SystemExit("the key file must be outside this repository")
    entries = _entries(a.ledger)
    if a.cmd == "new":
        if a.name == PUBLIC or any(e["round"] == a.name for e in entries):
            raise SystemExit(f"round name {a.name!r} is taken")
        if os.path.exists(a.key_file):
            raise SystemExit(f"{a.key_file} exists; a key is never overwritten")
        key, generator = secrets.token_hex(32), _head()
        fd = os.open(a.key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(key + "\n")
        entry = {"round": a.name, "commitment": commitment(a.name, generator, key), "generator": generator,
                 "committed": today, "revealed": None, "key": None}
        print(json.dumps(entry))
        print(f"key written to {a.key_file}. Append the line above to {a.ledger}, commit and push it "
              "BEFORE running the round.", file=sys.stderr)
    else:
        key = open(a.key_file).read().strip()
        _check_key(key)
        match = [e for e in entries if e["round"] == a.name]
        if not match:
            raise SystemExit(f"no round {a.name!r} in {a.ledger}")
        e = match[0]
        if commitment(e["round"], e["generator"], key) != e["commitment"]:
            raise SystemExit("this key does not match the round's commitment")
        e.update(revealed=today, key=key)
        print(json.dumps(e))
        print(f"Replace the round's line in {a.ledger} with the line above, and publish the results with it.",
              file=sys.stderr)


if __name__ == "__main__":
    main()
