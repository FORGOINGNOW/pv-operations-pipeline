"""Default dry-run; only expired generated JSONL logs in this project's runtime."""

import argparse
import json
import time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--root", default="runtime/demo")
p.add_argument("--older-days", type=int, default=30)
p.add_argument("--apply", action="store_true")
a = p.parse_args()
workspace = Path(__file__).resolve().parents[1]
runtime_base = workspace / "runtime"
boundary = runtime_base.resolve()
root_argument = Path(a.root).absolute()
root = root_argument.resolve()
if runtime_base.is_symlink() or root_argument != root:
    p.error("symlinked or noncanonical cleanup root is forbidden")
if not root.is_relative_to(boundary) or root == boundary or a.older_days < 1:
    p.error("root must be a project runtime subdirectory; age must be >=1 day")
folder = root / "logs"
if folder.resolve() != folder or root.is_symlink():
    p.error("symlinked cleanup target is forbidden")
cutoff = time.time() - a.older_days * 86400
for path in sorted(folder.glob("*.jsonl")):
    if (
        path.is_symlink()
        or not path.is_file()
        or path.resolve().parent != folder
        or path.stat().st_mtime >= cutoff
    ):
        continue
    print(json.dumps({"dry_run": not a.apply, "path": str(path), "action": "expire_generated_log"}))
    if a.apply:
        path.unlink()
