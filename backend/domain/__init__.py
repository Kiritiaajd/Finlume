"""Finlume's financial domain: pure, deterministic Python.

Rules for everything under this package (enforced by tests/test_architecture.py):

- No imports from Django, DRF, ``apps``, ``infrastructure`` or any I/O library.
- Money is ``decimal.Decimal``, never ``float``.
- Same inputs and engine version always give the same outputs.

Conventions are documented in docs/data/FINANCIAL_CALCULATION_CONVENTIONS.md.
"""
