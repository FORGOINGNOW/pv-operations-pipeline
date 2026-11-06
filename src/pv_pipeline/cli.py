"""Safe CLI and content-addressed receipts, called by the Bash control plane."""

import argparse
import hashlib
import json
import os
import platform
import sys
import time
from functools import lru_cache
from pathlib import Path

import psutil

from . import analytics, presentation, simulate, transform
from .core import config, dates_between, digest, json_write

STEPS = {
    "generate": simulate.generate,
    "collect": transform.collect,
    "clean": transform.clean,
    "aggregate": transform.aggregate,
    "features": analytics.make_features,
    "train": analytics.train,
    "score": analytics.score,
    "evaluate": analytics.evaluate,
    "dashboard": presentation.dashboard,
    "report": presentation.report,
}
DAY_STEPS = {"generate", "collect", "clean", "aggregate", "features", "score"}
LAYERS = {"collect": "ods", "clean": "dwd", "aggregate": "dws", "features": "features", "score": "scored"}
DEPENDENCIES = {
    "generate": [],
    "collect": ["generate"],
    "clean": ["collect"],
    "aggregate": ["clean"],
    "features": ["clean"],
    "train": ["features"],
    "score": ["features", "train", "aggregate"],
    "evaluate": ["score"],
    "dashboard": ["evaluate"],
    "report": ["evaluate"],
}


@lru_cache(maxsize=1)
def code_hash():
    h = hashlib.sha256()
    for p in sorted(Path(__file__).parent.glob("*.py")):
        h.update(p.read_bytes())
    return h.hexdigest()


def receipt_path(root, step, day):
    return root / "state" / step / f"{day}.json"


def signature(root, step, day, c, allow_late):
    h = hashlib.sha256((c["config_sha256"] + code_hash() + str(allow_late)).encode())
    for dep in DEPENDENCIES[step]:
        if dep in DAY_STEPS and step in DAY_STEPS:
            paths = [receipt_path(root, dep, day)]
        elif dep in DAY_STEPS:
            paths = sorted((root / "state" / dep).glob("*.json"))
        else:
            paths = [receipt_path(root, dep, "global")]
        if not paths or not all(p.exists() for p in paths):
            raise ValueError(f"Missing dependency {dep} for {step}/{day}")
        for p in paths:
            h.update(p.read_bytes())
    if step == "generate":
        raw = root / "raw" / f"date={day}"
        if (raw / "manifest.json").exists():
            for p in sorted(raw.iterdir()):
                if p.is_file():
                    h.update(digest(p).encode())
    return h.hexdigest()


def output_files(root, step, day):
    if step in LAYERS:
        files = [root / LAYERS[step] / f"date={day}" / "part.parquet"]
        if step == "clean":
            files += [root / "quality" / f"{day}.json", root / "quarantine" / f"date={day}" / "part.parquet"]
        if step == "score":
            files += [root / "ads" / f"date={day}" / "part.parquet", root / "alerts" / f"{day}.json"]
        return files
    if step == "generate":
        return sorted((root / "raw" / f"date={day}").glob("*"))
    if step == "train":
        return sorted((root / "models").glob("*"))
    if step == "evaluate":
        return [root / "evaluation.json", root / "outbox" / "workorders.json"]
    if step == "dashboard":
        return [root / "dashboard" / "dashboard.html"]
    return sorted((root / "reports").glob("*"))


def execute(args):
    c = config(args.config)
    root = Path(args.root or "runtime/" + c["profile"]).resolve()
    if args.step == "dates":
        print("\n".join(dates_between(args.start or c["start"], args.end or c["end"])))
        return
    if args.step == "doctor":
        import importlib.metadata
        import shutil

        print(
            json.dumps(
                {
                    "python": sys.version,
                    "executable": sys.executable,
                    "platform": platform.platform(),
                    "free_gib": shutil.disk_usage(root.anchor).free / 2**30,
                    "grid_rows": len(dates_between(c["start"], c["end"]))
                    * c["stations"]
                    * c.get("inverters", 1)
                    * 288,
                    "estimated_raw_gib": len(dates_between(c["start"], c["end"]))
                    * c["stations"]
                    * c.get("inverters", 1)
                    * 288
                    * 1100
                    / 2**30,
                    "versions": {
                        p: importlib.metadata.version(p)
                        for p in ["pandas", "numpy", "duckdb", "scikit-learn", "plotly", "PyYAML"]
                    },
                },
                indent=2,
            )
        )
        return
    if args.step == "verify":
        if args.dry_run:
            print(json.dumps({"dry_run": True, "step": "verify"}))
            return
        receipts = sorted((root / "state").glob("*/*.json"))
        if not receipts:
            raise ValueError("No completed receipts")
        for p in receipts:
            r = json.loads(p.read_text(encoding="utf-8"))
            if not all(
                (root / name).exists() and digest(root / name) == checksum
                for name, checksum in r["outputs"].items()
            ):
                raise ValueError(f"Corrupt output: {p}")
        for p in (root / "quality").glob("*.json"):
            if not json.loads(p.read_text())["reconciliation_ok"]:
                raise ValueError("Invalid row reconciliation")
        print(json.dumps({"receipts_verified": len(receipts), "status": "ok"}))
        return
    if args.step == "watermark":
        import datetime

        end = (
            (datetime.date.fromisoformat(args.date) + datetime.timedelta(days=1)).isoformat()
            if args.date
            else args.end or c["end"]
        )
        json_write(
            root / "watermark.json",
            {"last_success_end_exclusive": end, "run_id": args.run_id},
        )
        return
    days = [args.date] if args.date else dates_between(args.start or c["start"], args.end or c["end"])
    if args.step not in DAY_STEPS:
        days = ["global"]
    for day in days:
        if day != "global":
            import datetime

            datetime.date.fromisoformat(day)
        if args.dry_run:
            print(json.dumps({"dry_run": True, "step": args.step, "date": day, "root": str(root)}))
            continue
        root.mkdir(parents=True, exist_ok=True)
        sig = signature(root, args.step, day, c, args.allow_late)
        receipt = receipt_path(root, args.step, day)
        if receipt.exists() and not args.force:
            old = json.loads(receipt.read_text(encoding="utf-8"))
            if old["signature"] == sig and all(
                (root / p).exists() and digest(root / p) == v for p, v in old["outputs"].items()
            ):
                print(
                    json.dumps(
                        {"step": args.step, "date": day, "resume": "verified_content", "run_id": args.run_id}
                    )
                )
                continue
        started = time.perf_counter()
        if os.environ.get("PV_FAIL_STEP") == args.step:
            raise RuntimeError("Injected deterministic failure before commit")
        if os.environ.get("PV_TRANSIENT_ONCE") == args.step:
            marker = root / (".transient-" + args.step)
            if not marker.exists():
                marker.touch()
                raise TemporaryError("Injected temporary source outage")
        stats = STEPS[args.step](root, c, day, allow_late=args.allow_late)
        sig = signature(root, args.step, day, c, args.allow_late)
        outputs = {
            str(p.relative_to(root)): digest(p) for p in output_files(root, args.step, day) if p.is_file()
        }
        json_write(receipt, {"signature": sig, "outputs": outputs, "data_version": c["data_version"]})
        log = {
            "run_id": args.run_id,
            "step": args.step,
            "date": day,
            "attempt": args.attempt,
            "duration": round(time.perf_counter() - started, 4),
            "exit_code": 0,
            "rss_mib": round(psutil.Process().memory_info().rss / 2**20, 2),
            **stats,
        }
        logs = root / "logs"
        logs.mkdir(exist_ok=True)
        with open(logs / f"{args.run_id}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(log, ensure_ascii=False) + "\n")
        print(json.dumps(log, ensure_ascii=False))


class TemporaryError(Exception):
    pass


def main():
    parser = argparse.ArgumentParser(description="SYNTHETIC PV pipeline (end date is exclusive)")
    parser.add_argument("step", choices=list(STEPS) + ["doctor", "dates", "verify", "watermark"])
    parser.add_argument("--config", default="configs/smoke.yaml")
    parser.add_argument("--root")
    parser.add_argument("--date")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--run-id", default="manual")
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument(
        "--force", action="store_true", help="Recompute derived outputs; immutable raw is verified/reused"
    )
    parser.add_argument(
        "--allow-late", action="store_true", help="Explicit backfill accepts beyond-window late arrivals"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not all(ch.isalnum() or ch in "-_" for ch in args.run_id):
        parser.error("run-id must contain only letters, digits, dash, underscore")
    try:
        execute(args)
    except TemporaryError as e:
        print(str(e), file=sys.stderr)
        sys.exit(75)
    except Exception as e:
        print(
            json.dumps(
                {
                    "run_id": args.run_id,
                    "step": args.step,
                    "exit_code": 1,
                    "error_type": type(e).__name__,
                    "error": str(e),
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
