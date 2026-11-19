# SPDX-License-Identifier: MIT OR Apache-2.0
"""Run with: python -m unittest discover tests"""
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest

from ckb import rounds

KEY = "ab" * 32


class Env:
    def __init__(self, **kv):
        self.kv = kv

    def __enter__(self):
        self.old = {k: os.environ.pop(k, None) for k in ("CKB_ROUND", "CKB_ROUND_KEY")}
        os.environ.update(self.kv)

    def __exit__(self, *a):
        for k in ("CKB_ROUND", "CKB_ROUND_KEY"):
            os.environ.pop(k, None)
            if self.old[k] is not None:
                os.environ[k] = self.old[k]


class Rounds(unittest.TestCase):
    def test_public_round_is_the_old_seed(self):
        with Env():
            for i in (0, 7, 4199):
                seed = 1_000_003 * i + 17
                self.assertEqual(rounds.rng("boolean", i, seed).random(), random.Random(seed).random())

    def test_private_round_differs_and_repeats(self):
        with Env(CKB_ROUND="r", CKB_ROUND_KEY=KEY):
            a = rounds.rng("boolean", 3, 99).random()
            self.assertEqual(a, rounds.rng("boolean", 3, 99).random())
            self.assertNotEqual(a, random.Random(99).random())
            self.assertNotEqual(a, rounds.rng("chain", 3, 99).random())
            self.assertNotEqual(a, rounds.rng("boolean", 4, 99).random())
        with Env(CKB_ROUND="r", CKB_ROUND_KEY="cd" * 32):
            self.assertNotEqual(a, rounds.rng("boolean", 3, 99).random())

    def test_key_without_name_or_name_without_key_stops(self):
        for kv in ({"CKB_ROUND_KEY": KEY}, {"CKB_ROUND": "r"}, {"CKB_ROUND": "r", "CKB_ROUND_KEY": "short"}):
            with Env(**kv), self.assertRaises(SystemExit):
                rounds.current()

    def test_commit_reveal_verify(self):
        with tempfile.TemporaryDirectory() as d:
            ledger, keyfile = os.path.join(d, "ledger.jsonl"), os.path.join(d, "r1.key")
            run = lambda *a: subprocess.run([sys.executable, "-m", "ckb.rounds", *a], capture_output=True, text=True)
            new = run("new", "r1", "--key-file", keyfile, "--ledger", ledger)
            if "commit your changes first" in new.stderr:
                self.skipTest("working tree has uncommitted changes")
            self.assertEqual(new.returncode, 0, new.stderr)
            entry = json.loads(new.stdout)
            self.assertIsNone(entry["key"])
            self.assertEqual(os.stat(keyfile).st_mode & 0o777, 0o600)
            open(ledger, "w").write(new.stdout)
            self.assertNotEqual(run("new", "r1", "--key-file", keyfile + "2", "--ledger", ledger).returncode, 0)
            rev = run("reveal", "r1", "--key-file", keyfile, "--ledger", ledger)
            self.assertEqual(rev.returncode, 0, rev.stderr)
            open(ledger, "w").write(rev.stdout)
            self.assertEqual(run("verify", ledger).returncode, 0)
            e = json.loads(rev.stdout)
            e["key"] = "00" * 32
            open(ledger, "w").write(json.dumps(e) + "\n")
            self.assertNotEqual(run("verify", ledger).returncode, 0)

    def test_key_file_inside_the_repository_is_refused(self):
        inside = os.path.join(os.path.dirname(rounds.LEDGER), "x.key")
        p = subprocess.run([sys.executable, "-m", "ckb.rounds", "new", "x", "--key-file", inside],
                           capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertFalse(os.path.exists(inside))


if __name__ == "__main__":
    unittest.main()
