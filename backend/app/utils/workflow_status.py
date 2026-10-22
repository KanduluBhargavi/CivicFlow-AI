
def complaint_display_status(status: str, has_officer: bool, viewer_role: str | None = None) -> str:
    """Human-facing workflow label without changing the persisted state machine.

    The database uses ``Assigned`` to mean the complaint has been routed to a
    department. The UI should not imply that an individual officer has already
    been assigned when no ComplaintAssignment exists.
    """
    status = (status or "Submitted").strip()
    if status == "Assigned":
        if has_officer:
            return "Assigned to You" if (viewer_role or "").lower() == "officer" else "Officer Assigned"
        return "Received by Department"
    return status


def assignee_display(name: str | None) -> str:
    return name or "Awaiting Officer"
