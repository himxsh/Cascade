from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cascade.agent import choose_and_rewrite
from cascade.apply import run_apply
from cascade.datahub_live import resolve_catalog
from cascade.demo import DEFAULT_DIFF, DEFAULT_MODELS, DEFAULT_URN, run_demo
from cascade.impact import build_impact_report
from cascade.diff_parser import load_changes


def cmd_impact(args: argparse.Namespace) -> None:

    changes = load_changes(args.diff)

    catalog = resolve_catalog(args.source, args.urn, args.fixture)
    report = build_impact_report(
        source_urn=args.urn,
        changes=changes,
        catalog=catalog,
    )

    if getattr(args, "generate", False):
        remediations = choose_and_rewrite(
            changes=changes,
            catalog=catalog,
            models_dir=args.models_dir,
            source_urn=args.urn,
        )
        report.remediations = remediations
        out_dir = getattr(args, "out", None)
        if out_dir:
            out_path = Path(out_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            for rem in remediations:
                rewritten = rem.get("rewritten_sql")
                if rewritten:
                    src = Path(rem["path"])
                    dest = out_path / src.name
                    dest.write_text(rewritten)
            (out_path / "impact_report.json").write_text(
                json.dumps(report.to_dict(), indent=2)
            )

    json.dump(report.to_dict(), sys.stdout, indent=2)
    sys.stdout.write("\n")


def cmd_generate(args: argparse.Namespace) -> None:
    report_data = json.loads(Path(args.report).read_text())
    source_urn = report_data.get("source_urn", "")
    changes = report_data.get("changes", [])
    catalog = resolve_catalog(getattr(args, "source", "fixture"), source_urn or None, args.fixture)
    models_dir = args.models_dir or "examples/models"
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    remediations = choose_and_rewrite(
        changes=changes,
        catalog=catalog,
        models_dir=models_dir,
        source_urn=source_urn,
    )
    report_data["remediations"] = remediations

    for rem in remediations:
        rewritten = rem.get("rewritten_sql")
        if rewritten:
            src = Path(rem["path"])
            dest = out_dir / src.name
            dest.write_text(rewritten)

    (out_dir / "impact_report.json").write_text(json.dumps(report_data, indent=2))
    json.dump(report_data, sys.stdout, indent=2)
    sys.stdout.write("\n")


def cmd_apply(args: argparse.Namespace) -> None:
    report_data = json.loads(Path(args.report).read_text())
    if args.generate or not report_data.get("remediations"):
        source_urn = report_data.get("source_urn", "")
        changes = report_data.get("changes", [])
        catalog = resolve_catalog(getattr(args, "source", "fixture"), source_urn or None, args.fixture)
        models_dir = args.models_dir or "examples/models"
        report_data["remediations"] = choose_and_rewrite(
            changes=changes,
            catalog=catalog,
            models_dir=models_dir,
            source_urn=source_urn,
        )

    summary = run_apply(
        report_data,
        out_dir=args.out,
        mark_lifecycle=args.mark_migrated,
        pr_number=args.pr_number,
    )
    json.dump(summary, sys.stdout, indent=2)
    sys.stdout.write("\n")


def cmd_demo(args: argparse.Namespace) -> None:
    result = run_demo(
        out_dir=args.out,
        urn=args.urn,
        diff=args.diff,
        models_dir=args.models_dir,
        fixture=args.fixture,
        source=args.source,
        mark_migrated=not args.skip_migrated,
    )
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cascade — schema change impact analyzer")
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    impact_p = sub.add_parser("impact", help="Build a blast-radius impact report")
    impact_p.add_argument("--urn", required=True, help="Source dataset URN")
    impact_p.add_argument("--diff", required=True, help="Path to JSON changes file")
    impact_p.add_argument("--fixture", help="Override fixture path")
    impact_p.add_argument(
        "--source",
        choices=["fixture", "live", "auto"],
        default="fixture",
        help="Data source: fixture (default), live (GMS, fail if down), auto (prefer live, fallback fixture)",
    )
    impact_p.add_argument("--generate", action="store_true", help="Run agent to produce remediations")
    impact_p.add_argument("--models-dir", help="Directory with downstream model SQL files")
    impact_p.add_argument("--out", help="Output directory for rewritten SQL files")
    impact_p.set_defaults(func=cmd_impact)

    gen_p = sub.add_parser("generate", help="Generate remediations from an existing impact report")
    gen_p.add_argument("--report", required=True, help="Path to impact report JSON")
    gen_p.add_argument("--out", required=True, help="Output directory for rewritten SQL files")
    gen_p.add_argument("--models-dir", help="Directory with downstream model SQL files")
    gen_p.add_argument("--fixture", help="Override fixture path")
    gen_p.add_argument(
        "--source",
        choices=["fixture", "live", "auto"],
        default="fixture",
        help="Catalog source for schema gate / rewrite (default fixture)",
    )
    gen_p.set_defaults(func=cmd_generate)

    apply_p = sub.add_parser(
        "apply",
        help="Act + write-back: PR comment, downstream artifacts, DataHub/ML tags (dry-run without secrets)",
    )
    apply_p.add_argument("--report", required=True, help="Path to impact report JSON")
    apply_p.add_argument("--out", required=True, help="Artifact output directory")
    apply_p.add_argument("--models-dir", help="Directory with downstream model SQL files")
    apply_p.add_argument("--fixture", help="Override fixture path")
    apply_p.add_argument(
        "--source",
        choices=["fixture", "live", "auto"],
        default="fixture",
        help="Catalog source when --generate / remediations missing (default fixture)",
    )
    apply_p.add_argument(
        "--generate",
        action="store_true",
        help="(Re)run agent remediations before apply",
    )
    apply_p.add_argument(
        "--mark-migrated",
        action="store_true",
        help="Also emit migrated lifecycle write-back (merge hook / stub)",
    )
    apply_p.add_argument("--pr-number", type=int, help="Source PR number for live comment")
    apply_p.set_defaults(func=cmd_apply)

    demo_p = sub.add_parser(
        "demo",
        help="One-command fixture path: impact → generate → apply dry-run",
    )
    demo_p.add_argument("--out", default="artifacts/demo", help="Demo artifact directory")
    demo_p.add_argument("--urn", default=DEFAULT_URN, help="Source dataset URN")
    demo_p.add_argument("--diff", default=DEFAULT_DIFF, help="Sample diff/changes path")
    demo_p.add_argument("--models-dir", default=DEFAULT_MODELS, help="Downstream SQL models")
    demo_p.add_argument("--fixture", help="Override fixture path")
    demo_p.add_argument(
        "--source",
        choices=["fixture", "live", "auto"],
        default="fixture",
        help="Catalog source (default fixture)",
    )
    demo_p.add_argument(
        "--skip-migrated",
        action="store_true",
        help="Skip migrated lifecycle artifact",
    )
    demo_p.set_defaults(func=cmd_demo)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
