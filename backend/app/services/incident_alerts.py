"""Shared, transparent burst rules for early-warning incident alerts."""

def incident_burst_metrics(recent_reports):
    """Summarize a rolling 24-hour window using distinct citizens.

    Multiple submissions by one person still appear in the report count, but
    cannot alone create a community-level alert. Critical priority is evaluated
    only for reports in this same time window.
    """
    reports = list(recent_reports or [])
    reporter_ids = {row.citizen_id for row in reports if row.citizen_id is not None}
    critical = [row for row in reports if (row.priority or "").casefold() == "critical"]
    critical_reporter_ids = {
        row.citizen_id for row in critical if row.citizen_id is not None
    }
    priorities = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    recent_priority = max(
        (row.priority for row in reports if row.priority),
        key=lambda value: priorities.get(value.casefold(), 0),
        default=None,
    )
    return {
        "reports_last_24h": len(reports),
        "distinct_reporters_last_24h": len(reporter_ids),
        "critical_reports_last_24h": len(critical),
        "critical_reporters_last_24h": len(critical_reporter_ids),
        "highest_priority_last_24h": recent_priority,
    }


def should_raise_incident_alert(metrics):
    """Raise at three independent reporters, or two including a Critical case."""
    reporters = metrics["distinct_reporters_last_24h"]
    critical_reporters = metrics["critical_reporters_last_24h"]
    return reporters >= 3 or (reporters >= 2 and critical_reporters >= 1)


def incident_alert_reason(metrics):
    reports = metrics["reports_last_24h"]
    reporters = metrics["distinct_reporters_last_24h"]
    critical = metrics["critical_reports_last_24h"]
    if reporters >= 3:
        return (
            f"{reporters} different citizens submitted {reports} linked reports in the last 24 hours. "
            "Review whether this is a growing local incident."
        )
    return (
        f"{reporters} different citizens submitted {reports} linked reports in the last 24 hours, "
        f"including {critical} Critical report(s). Triage promptly."
    )
