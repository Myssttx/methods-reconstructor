from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.evaluation.training_export import export_jsonl  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export source-backed reconstruction claims as provider-neutral JSONL."
    )
    parser.add_argument("--storage-root", default=".local_storage")
    parser.add_argument("--out", default="eval/reports/training-source-backed.jsonl")
    args = parser.parse_args()

    n_protocols, n_examples = export_jsonl(Path(args.storage_root), Path(args.out))
    print(f"Wrote {n_examples} examples from {n_protocols} protocols to {args.out}")
    print("These are filtered pseudo-labels, not human-validated gold labels.")


if __name__ == "__main__":
    main()
