#!/usr/bin/env python3
"""
grade.py -- turn the acceptance scenario's output into one digest.

Usage:
    dpm test --files daml/Acceptance.daml 2>&1 | python3 grading/grade.py

Reads `dpm test` output on stdin, extracts the lines the sealed Acceptance.daml
emitted (each tagged `@@STATE@@`), normalizes them so the digest does not depend
on how the SDK renders `show (x : Decimal)` or on emission order, and prints:

    DIGEST=<64-hex-char SHA-256>

Submit that DIGEST string.

Exit codes:
    0  a complete BEGIN..END block was found and a digest was produced
    2  no block found (model did not compile, or a should-succeed step failed)
    3  block found but malformed
"""

import hashlib
import re
import sys

TAG = re.compile(r"@@STATE@@([^\"\r\n]*)")
DECIMAL = re.compile(r"^-?\d+(?:\.\d+)?$")


def normalize_field(tok: str) -> str:
    """Any field that is a plain decimal is reformatted to 2dp; others untouched.
    Addresses ('12 Oak St') and labels ('SARAH') are never plain decimals."""
    t = tok.strip()
    if DECIMAL.match(t):
        return f"{float(t):.2f}"
    return t


def canonical(line: str) -> str:
    return "|".join(normalize_field(f) for f in line.split("|"))


def main() -> int:
    raw = sys.stdin.read()
    payloads = [m.group(1).strip() for m in TAG.finditer(raw)]
    if not payloads:
        sys.stderr.write(
            "ERROR: no @@STATE@@ lines found. The acceptance scenario did not "
            "run to completion -- usually the model does not compile, or an "
            "operation that should succeed was rejected.\n"
        )
        return 2

    try:
        begin = payloads.index("BEGIN")
        end = payloads.index("END")
    except ValueError:
        sys.stderr.write("ERROR: BEGIN/END markers missing or out of order.\n")
        return 3

    body = [l for l in payloads[begin + 1 : end] if l]
    records = sorted(canonical(l) for l in body)
    text = "\n".join(records) + "\n"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()

    sys.stderr.write("--- canonical final state ---\n")
    sys.stderr.write(text if records else "(empty ledger)\n")
    sys.stderr.write("-----------------------------\n")
    print(f"DIGEST={digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
