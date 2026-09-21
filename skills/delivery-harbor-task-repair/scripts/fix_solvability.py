#!/usr/bin/env python3
"""Attach a reward-1.0 non-oracle model run as solvability evidence.

The framework's own action item for this failure: "Attach a reward-1.0 non-oracle model
trajectory/result pair with exact provenance under task_folder/evaluations/solvability/."

The run is copied verbatim from evaluations/difficulty/rN. Nothing is regraded, no hash is
rewritten, and the original oracle run is left in place. A provenance file records that the
attached run is the same artifact as the difficulty run, not a new execution.
"""
import json, shutil, sys, hashlib
from pathlib import Path

ROOT = Path(sys.argv[1])
APPLY = "--apply" in sys.argv


def rd(p):
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def reward_of(res):
    r = res.get("reward")
    if r is None:
        r = ((res.get("verifier_result") or {}).get("rewards") or {}).get("reward")
    return r


def eligible(run):
    """Mirror audit_evaluations.solvability_qc's acceptance test."""
    res, cfg = rd(run / "result.json"), rd(run / "config.json")
    ag = cfg.get("agent") or {}
    return (
        reward_of(res) == 1.0
        and isinstance(res, dict) and res
        and (ag.get("name") or "").lower() != "oracle"
        and not (run / "agent" / "oracle.txt").exists()
        and (run / "agent" / "trajectory.json").exists()
        and ag.get("name") and ag.get("model_name")
        and bool(res.get("finished_at"))
        and not res.get("exception_info")
        and ((res.get("verifier_result") or {}).get("rewards") or {}).get("reward") is not None
    )


changed = []
for task in sorted(d for d in ROOT.iterdir() if d.is_dir()):
    solv = task / "evaluations" / "solvability"
    if any(eligible(r) for r in sorted(solv.glob("r*")) if r.is_dir()):
        continue  # already satisfied
    cands = [r for r in sorted((task / "evaluations" / "difficulty").glob("r*")) if r.is_dir() and eligible(r)]
    if not cands:
        print(f"SKIP  {task.name}: no eligible model run")
        continue
    src = cands[0]
    taken = {r.name for r in solv.glob("r*")} if solv.exists() else set()
    n = 2
    while f"r{n}" in taken:
        n += 1
    dst = solv / f"r{n}"
    print(f"FIX   {task.name}: difficulty/{src.name} -> solvability/{dst.name}")
    if APPLY:
        solv.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst)
        (dst / "ATTACHED_FROM.json").write_text(json.dumps({
            "attached_from": f"evaluations/difficulty/{src.name}",
            "reason": "solvability evidence: reward-1.0 non-oracle model run already present in this package",
            "copied_verbatim": True,
            "regraded": False,
            "result_sha256": hashlib.sha256((src / "result.json").read_bytes()).hexdigest(),
            "trajectory_sha256": hashlib.sha256((src / "agent" / "trajectory.json").read_bytes()).hexdigest(),
        }, indent=2) + "\n")
    changed.append((task.name, src.name, dst.name))

print(f"\n{'APPLIED' if APPLY else 'DRY RUN'}: {len(changed)} tasks")
