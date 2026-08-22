"""Minimal policy checks for Cascade Act (stdlib only)."""

from __future__ import annotations

from typing import Any


def evaluate_policy(
    report: dict[str, Any],
    *,
    remediation_open: bool = False,
    stack_requested: bool = False,
) -> dict[str, Any]:
    """Return ok/fail for production gates.

    Comment-first is ok. Opening a stacked PR for severity=high must succeed.
    """
    severity = str(report.get("severity") or "").lower()
    if stack_requested and severity == "high" and not remediation_open:
        return {
            "ok": False,
            "code": "high_without_remediation",
            "message": "severity=high but no stacked PR is open",
            "severity": severity,
            "remediation_open": False,
            "stack_requested": True,
        }
    return {
        "ok": True,
        "code": "pass",
        "message": "policy ok",
        "severity": severity or "unknown",
        "remediation_open": remediation_open,
        "stack_requested": stack_requested,
    }
