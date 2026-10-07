#!/usr/bin/env python3
"""Attach a reward-1.0 non-oracle model run as solvability evidence.

    python3 fix_solvability.py ROOT [--apply]

ROOT is one task directory or a directory of task directories. Dry run unless --apply.

The framework's own action item for this failure: "Attach a complete reward-1.0 model
trajectory/result pair or valid recorded Oracle execution with exact provenance under
task_folder/evaluations/solvability/."

The run is copied verbatim from evaluations/difficulty/. Nothing is regraded, no hash is
rewritten, and the original oracle run is left in place. A provenance file records that the
attached run is the same artifact as the difficulty run, not a new execution.

Eligibility mirrors the client checker (audit_evaluations.classify_result / solvability_qc):
  - result.json files are found recursively and only leaf (terminal trial) results count
  - a run is Oracle if it has agent/oracle.txt or oracle.txt, or if any of agent_info.name,
    config.agent.name, trial_name or model STARTS WITH "oracle"
  - reward comes from verifier_result.rewards.reward first; booleans and values outside [0, 1]
    are not rewards
  - the trajectory may be agent/trajectory.json, agent/frozen_trajectory.json, trajectory.json
    or golden_trajectory.json
  - agent name and model name come from config.json, else result.json's embedded config
  - finished_at set, no exception_info, and the verifier actually wrote a reward
A task whose solvability/ already holds an eligible model run, or a structurally valid recorded
Oracle execution (all agent names "oracle", finished, reward exactly 1 in result.json and every
saved reward file), is treated as satisfied and left alone. The Oracle test here is structural
only; the client's obi_policy.oracle_solvability_evidence also depends on its
ALLOW_ORACLE_SOLVABILITY policy, so confirm with audit_evaluations.py when it matters.

NOTE for review: infra's stability evidence binds its repeats to evaluations/solvability/r1.
This script never replaces r1; it attaches the model run at the next free rN. When a task's
stability repeats point at an Oracle r1, the output flags it so a human can decide.
"""
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

TRAJECTORIES = ("agent/trajectory.json", "agent/frozen_trajectory.json", "trajectory.json", "golden_trajectory.json")
ORACLE_FILES = ("agent/oracle.txt", "oracle.txt")
REWARD_FILES = ("verifier/reward.json", "reward.json", "verifier/reward.txt", "reward.txt")


def rd(p: Path):
    try:
        v = json.loads(p.read_text())
        return v if isinstance(v, dict) else None
    except (OSError, ValueError):
        return None


def nested(d, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def reward_number(v):
    """A strict, finite Harbor reward; booleans and out-of-range values are not rewards."""
    if type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1:
        return None
    return float(v)


def reward_of(res: dict):
    for v in (nested(res, "verifier_result", "rewards", "reward"), nested(res, "rewards", "reward"), res.get("reward")):
        if v is not None:
            return reward_number(v)
    return None


def leaf_results(axis: Path) -> list[Path]:
    results = sorted(axis.rglob("result.json")) if axis.is_dir() else []
    return [r for r in results
            if not any(o != r and r.parent in o.parents and o.parent != r.parent for o in results)]


def first(run: Path, rels) -> Path | None:
    return next((run / r for r in rels if (run / r).is_file()), None)


def oracle_declared(res: dict) -> bool:
    values = [nested(res, "agent_info", "name"), nested(res, "config", "agent", "name"),
              res.get("trial_name"), res.get("model")]
    return any(str(v or "").lower().startswith("oracle") for v in values)


def eligible(run: Path) -> bool:
    """Mirror audit_evaluations.solvability_qc's model_passing test."""
    res = rd(run / "result.json")
    if res is None:
        return False
    cfg = rd(run / "config.json") or {}
    agent = nested(cfg, "agent", "name") or nested(res, "config", "agent", "name")
    model = nested(cfg, "agent", "model_name") or nested(res, "config", "agent", "model_name")
    return (
        reward_of(res) == 1.0
        and not (first(run, ORACLE_FILES) or oracle_declared(res))
        and first(run, TRAJECTORIES) is not None
        and bool(agent) and bool(model)
        and bool(res.get("finished_at"))
        and not res.get("exception_info")
        and nested(res, "verifier_result", "rewards", "reward") is not None
    )


def oracle_evidence(run: Path) -> bool:
    """Structural subset of obi_policy.oracle_solvability_evidence (policy flag not consulted)."""
    res = rd(run / "result.json")
    if not res or not res.get("finished_at") or res.get("exception_info"):
        return False
    if str(res.get("status", "completed")).lower() not in {"completed", "complete", "success", "succeeded"}:
        return False
    cfg, lock = rd(run / "config.json"), rd(run / "lock.json")
    agents = [nested(c, "agent") for c in (cfg, res.get("config")) if isinstance(c, dict)]
    agents += [res.get("agent_info"), nested(lock, "agent")]
    names = [a.get("name") for a in agents if isinstance(a, dict) and a.get("name")]
    if not names or any(str(n).strip().lower() != "oracle" for n in names):
        return False
    if reward_number(nested(res, "verifier_result", "rewards", "reward")) != 1.0:
        return False
    for rel in REWARD_FILES:
        p = run / rel
        if not p.exists():
            continue
        try:
            raw = json.loads(p.read_text()) if p.suffix == ".json" else float(p.read_text())
        except (OSError, ValueError):
            return False
        if reward_number(raw.get("reward") if isinstance(raw, dict) else raw) != 1.0:
            return False
    return True


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def stability_binds_oracle_r1(task: Path) -> bool:
    r1 = task / "evaluations" / "solvability" / "r1"
    if not (first(r1, ORACLE_FILES) or oracle_declared(rd(r1 / "result.json") or {})):
        return False
    for res in leaf_results(task / "evaluations" / "stability"):
        if (rd(res) or {}).get("source_trial") == "evaluations/solvability/r1":
            return True
    return False


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        raise SystemExit("usage: fix_solvability.py ROOT [--apply]")
    root, apply = Path(args[0]).resolve(), "--apply" in sys.argv
    tasks = [root] if (root / "task.toml").is_file() else sorted(d for d in root.iterdir() if d.is_dir())

    changed, flagged = [], []
    for task in tasks:
        solv = task / "evaluations" / "solvability"
        runs = [r.parent for r in leaf_results(solv)]
        if any(eligible(r) for r in runs):
            continue  # already has model evidence
        if any(oracle_evidence(r) for r in runs):
            print(f"OK    {task.name}: valid recorded Oracle execution already present (confirm with audit_evaluations.py)")
            continue
        cands = [r.parent for r in leaf_results(task / "evaluations" / "difficulty") if eligible(r.parent)]
        if not cands:
            print(f"SKIP  {task.name}: no eligible model run")
            continue
        src = cands[0]
        taken = {p.name for p in solv.iterdir()} if solv.is_dir() else set()
        n = 2
        while f"r{n}" in taken:
            n += 1
        dst = solv / f"r{n}"
        rel = src.relative_to(task).as_posix()
        print(f"FIX   {task.name}: {rel} -> evaluations/solvability/{dst.name}")
        if stability_binds_oracle_r1(task):
            print(f"      REVIEW: stability repeats bind to an Oracle solvability/r1; attaching at {dst.name} "
                  "does not change what they bind to")
            flagged.append(task.name)
        if apply:
            solv.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dst, symlinks=True)
            traj = first(src, TRAJECTORIES)
            (dst / "ATTACHED_FROM.json").write_text(json.dumps({
                "attached_from": rel,
                "reason": "solvability evidence: reward-1.0 non-oracle model run already present in this package",
                "copied_verbatim": True,
                "regraded": False,
                "result_sha256": sha(src / "result.json"),
                "trajectory": traj.relative_to(src).as_posix(),
                "trajectory_sha256": sha(traj),
            }, indent=2) + "\n")
        changed.append((task.name, rel, dst.name))

    print(f"\n{'APPLIED' if apply else 'DRY RUN'}: {len(changed)} tasks")
    if flagged:
        print(f"REVIEW ({len(flagged)}): stability bound to Oracle r1: {flagged}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
