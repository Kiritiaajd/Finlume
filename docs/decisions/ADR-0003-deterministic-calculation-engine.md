# ADR-0003: Deterministic, framework-independent calculation engine

- **Status:** Accepted
- **Date:** 2026-10-25

## Context

Finlume's value depends on users trusting its numbers. Financial figures arrive in different currencies, scales (thousands, lakhs, crores, millions) and periods, often with gaps and rounding differences. Binary floats cannot represent most decimal amounts exactly. AI-assisted explanations are a planned feature, but language models are unreliable at arithmetic and can invent figures.

## Decision

- Financial calculations live in `backend/domain/`, as ordinary Python with **no Django, DRF or I/O dependencies**. An architecture test enforces this.
- **Money is `decimal.Decimal`.** Floats, NaN and infinities are rejected at the domain boundary (`ensure_finite_decimal`).
- Arithmetic runs in an **explicit decimal context** (`CALCULATION_CONTEXT`: precision 34, `ROUND_HALF_EVEN`, trapping invalid operations, division by zero and overflow), so results never depend on the caller's ambient context.
- Results are stored at **6 decimal places, half-even**. Display rounding is a presentation concern.
- Scaling to base units is exact (`Decimal.scaleb` in a context that traps any rounding).
- **Missing is not zero.** A metric with a missing input or a zero denominator returns no value plus a typed issue (`missing_input`, `zero_denominator`). Questionable results, such as a ratio with a negative denominator, are returned with a warning.
- Every metric has a stable `code` and plain-language `methodology` text, stored with its result.
- Every analysis records `ENGINE_VERSION` (`domain/calculations/version.py`, currently `0.1.0`). The version is bumped whenever any output could change for the same input, and each bump is recorded in `CHANGELOG.md`.
- **AI never computes.** Future AI features may only explain results the engine has already calculated and stored, citing those values. They must not produce or alter figures.

Detailed rules are in [FINANCIAL_CALCULATION_CONVENTIONS](../data/FINANCIAL_CALCULATION_CONVENTIONS.md).

## Consequences

### Positive
- Calculations are reproducible and auditable: the same inputs and engine version always give the same outputs.
- They can be tested exhaustively and quickly, without a database.
- The engine could later be published as a standalone library.

### Negative
- Values must be converted at the boundaries (ORM `DecimalField`, JSON strings).
- Engine-version discipline adds review overhead to every calculation change.

## Alternatives considered

- **Floats / NumPy / pandas for core arithmetic:** rejected for money because of inexact representation. pandas may still be used later for bulk import parsing, before values become `Decimal`.
- **Calculations in model methods or serializers:** rejected, because it couples arithmetic to persistence and HTTP.
- **A separate calculation microservice:** rejected as premature ([ADR-0001](ADR-0001-modular-monolith.md)).
- **LLM-performed calculations:** rejected. They are non-deterministic and unverifiable.

## Revisit when

- Multi-period metrics (growth, averages) or currency conversion are added. Extend the conventions explicitly; do not assume them.
- Performance profiling shows `Decimal` to be a bottleneck, which is unlikely at expected data volumes.
