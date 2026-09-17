# Defects and Diagnostics

## Ask

Unrealistic ask (A1); AI-voiced prompt (A1); no single answer (A2); answer leakage (A3); field-name leakage (A3); method spelled out (A3); ambiguity fork (A4); under-specification (A4); no client value (A5); phantom entity (A6).

## Grading

Uncovered primary goal (G1); uncovered ask (G2); unasked requirement (G3); grades the account (G4); excessive self-report (G4); narrow-to-golden (G5); single-tool trap (G5); synonym gap (G5); decoy inside tolerance (G5); count-only floor (G5); free point (G6); denominator gaming (G6); avoidable judge (G7); invertible rubric (G7); judge contamination (G7).

## Measurement

Non-reproducible Oracle (M1); out of band, high (M2); unproven zero (M2); bimodal spread (M3); grading failure counted (M4); profile drift (M5); inflated floor (M6).

## Hygiene

Mirror out of sync (H1); leaked answer key (H2); missing engine (H3); stale number (H4).

## Diagnostic mapping

- Oracle fails: inspect gold, trajectory, verifier, and secondary-rubric cleanup.
- Zero reward with exception: infrastructure, not difficulty.
- High pass rate: task may be too easy, prompt may leak, or verifiers may be loose.
- Bimodal spread: likely A4 ambiguity or unstable judge.
- Score floor: identify always-passing verifiers and remove free points.
- Different passing verifiers at same mean: profile drift.
- Judged check varies while deterministic checks hold: G7 judge instability.

