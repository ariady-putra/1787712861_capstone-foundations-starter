# Capstone: Property Ledger

## Overview

- **Capstone ID:** A-CAP-1
- **Learning Path:** Path A: Daml 3 Foundations
- **Prerequisites:** F1, F2, F3, F4, F5
- **Estimated Duration:** 8-12 hours
- **Description:** The final project of Path A. You build a small multi-party
  real-estate ledger, write a test suite for it, and produce a machine-checkable
  digest that certifies the model is correct. You start from an almost-empty
  `daml/Realty.daml` and write the model, the tests, and the project structure
  yourself.

This brief tells you what to build and what each part must guarantee. It does not
give you the code. Every authorization and behavioral decision is yours to make;
the digest in Stage 6 checks that you made them correctly.

## What you are modeling

A seller lists a property. Buyers make offers. The seller accepts one offer and
the property changes hands; the other offers are withdrawn or rejected. A neutral
`registry` party observes every contract so there is always one party that can
see the whole ledger.

Three kinds of participant appear: sellers, buyers, and the registry. A single
party can be a seller in one deal and a buyer in another.

## How grading works

Model correctness is graded by a single digest. In Stage 6 you copy a sealed
checker into your project. It runs a fixed sequence of about twenty transactions
against your model, several of which must be rejected, then prints your ledger's
final state and a SHA-256 digest of it. There is one correct digest. A model with
a missing `ensure`, a wrong controller, an `Accept` that does not archive the
listing, a missing validation, or a `Sale` built from the wrong fields produces a
different final state and therefore a different digest.

Your own test suite (Stage 5) is graded separately, on coverage and structure.
Write it first; it is how you find the bugs before the digest does.

Stage 7 adds a second digest, over the final state of a real Canton ledger you
drive over HTTP. It uses the same reduction, so the same model that passes the
in-process check will pass it once you have driven the ledger correctly.

---

## Stage 1: The language layer (F1)

Add a type and a helper to `Realty.daml`, with no ledger involved yet.

1. Define an enum `PropertyType` with the values `House`, `Condo`, and `Land`.
2. Define a helper `propertyLabel` that maps each kind to a display label, using a
   `case` expression: `House` to `Detached house`, `Condo` to `Condominium`, and
   `Land` to `Vacant land`. Pay attention to the string's case. 
   The acceptance checker renders a property's kind through this function, so these strings must match exactly.

Replace the placeholder in `Realty.daml` with these definitions and run
`dpm build`.

```bash
dpm build
```

**What this code does:** Compiles the project. Confirm the type and helper
compile before moving on.

---

## Stage 2: The listing (F2)

Model a property for sale as a template named `Listing` with fields for the
seller, the registry, the address, the property type, and an asking price (a
`Decimal`).

Requirements for the `where` block:

- The seller is the sole signatory.
- The registry is an observer. Buyers do not observe the `Listing`; they act
  through standalone offers in Stage 3.
- A `Listing` must never exist with an asking price of zero or less. Enforce this
  with `ensure`.

Add two choices:

- `Reprice`, controlled by the seller. It takes a new price and produces an
  updated listing. Reject a non-positive new price inside the choice with
  `assertMsg`.
- `Delist`, controlled by the seller. It ends the listing.

Decide which of these two choices consumes the contract and which does not.

---

## Stage 3: Offers and acceptance (F2)

A completed sale needs the authority of both the buyer and the seller, and no
single party can supply both. This is the propose-accept pattern from F2.

Model a buyer's bid as a template named `Offer` with fields for the buyer, the
seller, the registry, the address, and the amount (a `Decimal`).

Requirements for the `where` block:

- The buyer is the signatory.
- The seller and registry are observers.
- An `Offer` must never exist with an amount of zero or less. Enforce this with
  `ensure`.

Add three choices:

- `Withdraw`, controlled by the buyer. The buyer retracts the offer.
- `Reject`, controlled by the seller. The seller declines the offer.
- `Accept`, controlled by the seller. It takes the contract ID of the matching
  listing and completes the sale, doing the following in order, in one
  transaction:
  1. `fetch` the listing.
  2. Verify the listing matches the offer: same address and same seller. If
     either does not match, fail with `assertMsg`.
  3. `archive` the listing.
  4. `create` a `Sale` (Stage 4).

The `Sale` created in step 4 requires both the buyer's and the seller's
authority. `Accept` runs with the seller's authority because the seller is the
controller. The buyer's authority comes from consuming this `Offer`, which the
buyer signed. Make `Accept` consuming so that authority is available.

> **Key Takeaway:** The address-and-seller check in step 2 is important.
> Without it, `Accept` could archive an unrelated listing and record a sale with
> mismatched data, and the digest will catch it.

---

## Stage 4: The sale (F2)

Model a completed sale as a template named `Sale` with fields for the buyer, the
seller, the registry, the address, the price (a `Decimal`), and the property
type. Carry the property type over from the listing you fetched in `Accept`.

Requirements for the `where` block:

- The buyer and the seller are both signatories.
- The registry is an observer.

Add one choice:

- `GetPrice`, controlled by the buyer, marked `nonconsuming`. It returns the
  price without changing the contract.

You now have the full workflow: list, offer, accept, sell, and the paths where a
deal does not complete.

---

## Stage 5: The test suite (F4)

Write a test suite in a new file `daml/Test.daml` (module `Test`).

- Write a shared `setup` script that allocates your parties and returns them, so
  each test starts from the same state.
- Write one behavior per test. Do not combine unrelated checks in one script.
- For happy-path tests, read the ledger back with `query` or `queryContractId`
  and assert on the result. Do not stop at a successful `submit`; a submission
  that returns without error does not prove the intended state change occurred.
- For failure-path tests, use `submitMustFail`, and cover each kind of failure:
  an authorization failure, an `ensure` violation, and an in-choice `assertMsg`
  failure.
- Run `dpm test` and read the coverage report. Every choice you wrote must be
  exercised by a test. Add a test for any choice that is not.

---

## Stage 6: The digest (machine check)

When the model builds and your own tests pass, bring in the checker.

1. Copy `grading/Acceptance.daml` into `daml/`. Do not edit it.
2. Run:

```bash
dpm clean
dpm build
dpm test --files daml/Acceptance.daml 2>&1 | python3 grading/grade.py
```

**What this code does:** `dpm test` runs the sealed acceptance scenario against
your model. The scenario emits your ledger's final state, tagged for the grader.
`grade.py` normalizes and hashes that state and prints:

```
DIGEST=<64 hex characters>
```

Submit the `DIGEST` string.

If the digest does not match the expected value, `grade.py` prints the canonical
final state above the digest. Read it to locate the fault:

- A stray `LIST` line means an `Accept`, `Delist`, or `Reject` did not archive
  the contract it should have.
- A stray `OFFER` line means an offer choice is not consuming, or a should-fail
  create was accepted (a missing `ensure`).
- A `SALE` with the buyer and seller swapped means the fields in `Accept`'s
  `create Sale` are wired wrong.
- A `SALE` showing `9 Pine Rd` or `Land` means the address-match check in
  `Accept` is missing.

If you see `ERROR: no @@STATE@@ lines found`, the scenario did not run to
completion: either the model does not compile because your names or signatures do
not match the interface below, or an operation that should have succeeded was
rejected.

---

## Stage 7: Ledger interaction over the JSON Ledger API (F5)

Everything so far has happened in a simulator. `dpm test` runs your model on the
IDE Ledger, a stand-in that never leaves your process. Now you take the same
model onto a real Canton ledger and watch an actual property change hands over
the wire. Think of it as moving from the flight simulator into the cockpit: the
controls are the same, but this time the ledger is really running, listening on a
port, and remembering everything that happens to it.

### Open the registry office

Start the ledger and register your contracts with it:

1. Run `dpm build`, then `dpm sandbox`. Upload your DAR to `/v2/dars` so the
   sandbox knows what a `Listing`, an `Offer`, and a `Sale` are.
2. Bring three people into this world, allocating them with the hints `Registry`,
   `Sarah`, and `Bob`. `Registry` is the public land-records office that quietly
   witnesses every deal; Sarah is a homeowner; Bob is a buyer. Use these exact
   hints -- the grader reads a party's name from its hint, so `Sarah` and `Sara`
   are different people to it. Pay attention to the hint's casing.
3. Give each person the keys they need: provision the user(s) and development
   JWT(s) with the `CanActAs` and `CanReadAs` rights that the steps below require.

### Make the sale

Now play out one clean transaction, three moves, each made by the person named in
parentheses:

1. (Sarah) Sarah puts her house on the market. Create a `Listing`: seller Sarah,
   registry Registry, address `12 Oak St`, property type `House`, asking price
   `500000`.
2. (Bob) Bob likes it and bids a little under asking. Create an `Offer`: buyer
   Bob, seller Sarah, registry Registry, address `12 Oak St`, amount `480000`.
3. (Sarah) Sarah takes the offer. Exercise `Accept` on Bob's offer, handing it
   the contract ID of the listing from step 1.

That third move is where the ledger earns its keep. You have to reach into the
response from step 1, pull out the listing's contract ID, and pass it to the
exercise -- and you have to submit that exercise as Sarah, because the deed will
not be filed unless the person the choice names as controller is the one who
signs for it.

### Ask the registry what it saw

The dust settles. One house sold, the listing and the offer gone, a single deed
on file. Ask the land-records office for its books and take their fingerprint:

4. Query `GET /v2/state/active-contracts` as Registry, the one party that sees
   everything. Save the JSON it returns to a file.
5. Reduce that to a digest:

```bash
python3 grading/grade_acs.py < acs.json
```

If the deal went as it should, the registry now holds exactly one contract: the
`Sale` of `12 Oak St` from Sarah to Bob for `480000`, and nothing else. If your
digest is wrong, `grade_acs.py` prints the records it actually found, and they
tell the story of what went sideways: a leftover `LIST` line means Sarah's
listing never came off the market when the sale closed; a leftover `OFFER` line
means an offer was never cleared away; an unfamiliar name in a party column means
someone was allocated under the wrong hint. (Unlike Stage 6, the kind column here
shows the raw value the ledger stored, e.g. `House`, not the `propertyLabel`
display string.)

---

## What to submit

1. Your `daml/Realty.daml`.
2. Your `daml/Test.daml`.
3. The `DIGEST` string from Stage 6 (in-process acceptance).
4. The `DIGEST` string from Stage 7 (ledger interaction).
