#!/usr/bin/env python3
"""
grade_acs.py -- digest of the final active-contract set from the JSON Ledger API.

Feed it the JSON your F5 client received from GET /v2/state/active-contracts:

    python3 grading/grade_acs.py < acs.json

It locates the active Listing / Offer / Sale payloads regardless of the response
envelope (it matches on YOUR field names, not on the wrapper), renders each party
by its hint -- the part before '::' in a Canton party id -- normalizes decimals,
sorts, and prints:

    DIGEST=<64 hex characters>

The digest uses the same canonical line format and hashing as the in-process
checker, so a correct ledger produces a stable, reproducible value.

Exit codes:
    0  at least one payload found and a digest produced
    2  no Listing/Offer/Sale payloads found in the input
"""

import hashlib
import json
import re
import sys

DECIMAL = re.compile(r"^-?\d+(?:\.\d+)?$")


def party(v: object) -> str:
    # "Sarah::1220ab..." -> "SARAH"; also handles ids with no namespace suffix.
    return str(v).split("::", 1)[0].strip().upper()


def dec(v: object) -> str:
    s = str(v).strip()
    return f"{float(s):.2f}" if DECIMAL.match(s) else s


def classify(d: dict) -> str | None:
    """Turn a payload record into a canonical line, or None if it isn't one."""
    k = set(d.keys())
    if {"buyer", "seller", "address", "price"} <= k:            # Sale
        return "|".join(["SALE", party(d["seller"]), party(d["buyer"]),
                         str(d["address"]), dec(d["price"]),
                         str(d.get("propertyType", ""))])
    if {"seller", "address", "askingPrice"} <= k:               # Listing
        return "|".join(["LIST", party(d["seller"]), str(d["address"]),
                         dec(d["askingPrice"]), str(d.get("propertyType", ""))])
    if {"buyer", "seller", "address", "amount"} <= k:           # Offer
        return "|".join(["OFFER", party(d["buyer"]), party(d["seller"]),
                         str(d["address"]), dec(d["amount"])])
    return None


def walk(node: object, out: set) -> None:
    if isinstance(node, dict):
        line = classify(node)
        if line:
            out.add(line)
        for v in node.values():
            walk(v, out)
    elif isinstance(node, list):
        for v in node:
            walk(v, out)


def main() -> int:
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # The endpoint may stream newline-delimited JSON objects.
        data = [json.loads(l) for l in raw.splitlines() if l.strip()]

    found: set = set()
    walk(data, found)
    records = sorted(found)

    text = ("\n".join(records) + "\n") if records else "(empty ledger)\n"
    sys.stderr.write("--- canonical final state ---\n" + text +
                     "-----------------------------\n")
    if not records:
        sys.stderr.write(
            "ERROR: no Listing/Offer/Sale payloads found. Check that you queried "
            "as a party that observes the contracts (the registry) and that the "
            "flow actually completed.\n"
        )
        return 2

    digest = hashlib.sha256(("\n".join(records) + "\n").encode("utf-8")).hexdigest()
    print(f"DIGEST={digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
