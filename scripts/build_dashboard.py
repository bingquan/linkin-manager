from __future__ import annotations

from pathlib import Path

from src.common.io import read_yaml
from src.memory.pipeline import build_coverage_dashboard


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    cfg = read_yaml(root / "config" / "user_profile.yaml")
    build_coverage_dashboard(
        dashboard_path=root / "state" / "coverage_dashboard.md",
        content_log_path=root / "state" / "content_log.jsonl",
        allocations=cfg.get("pillars_allocation", {}),
        topic_saturation_path=root / "state" / "topic_saturation.json",
    )


if __name__ == "__main__":
    main()
