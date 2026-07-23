from __future__ import annotations

import argparse
import json
import sys

from cascade.impact import build_impact_report


def cmd_impact(args: argparse.Namespace) -> None:

    with open(args.diff) as f:
        diff_data = json.load(f)
    changes = diff_data if isinstance(diff_data, list) else diff_data.get("changes", [])

    report = build_impact_report(
        source_urn=args.urn,
        changes=changes,
        fixture_path=args.fixture,
    )
    json.dump(report.to_dict(), sys.stdout, indent=2)
    sys.stdout.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cascade — schema change impact analyzer")
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    impact_p = sub.add_parser("impact", help="Build a blast-radius impact report")
    impact_p.add_argument("--urn", required=True, help="Source dataset URN")
    impact_p.add_argument("--diff", required=True, help="Path to JSON changes file")
    impact_p.add_argument("--fixture", help="Override fixture path")
    impact_p.set_defaults(func=cmd_impact)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
