"""Small read-only operator-status helpers shared by School50 presentation views."""
from __future__ import annotations

from enum import Enum

NOTICE_TTL_SECONDS = 60.0
HEADER_MARGIN = 2
SCIENTIFIC_NOTATION_BASE = 10
MAX_DISPLAY_INTEGER_ROOT = 100
PROFILE_ADOPTION_EVENTS = (
    "SCHOOL_EXECUTION_PROFILE_ADOPTED",
    "SCHOOL_SEMANTIC_CATALOG_PROFILE_ADOPTED",
)


class OperatorStatusError(str, Enum):
    NUMBER_SEMANTICS_INVALID = "DASHBOARD_NUMBER_SEMANTICS_INVALID"
    NOTIFICATION_INVALID = "DASHBOARD_NOTIFICATION_INVALID"
    PROFILE_ADOPTION_INVALID = "SCHOOL_TELEMETRY_PROFILE_ADOPTION_INVALID"


def clean(value):
    return str(value if value is not None else "-").replace("\n", " ").encode(
        "ascii", "replace").decode("ascii")


def cell(value, width, *, right=False):
    text = clean(value)
    if len(text) > width:
        text = text[:width - 1] + "~" if width > 1 else "~"
    return text.rjust(width) if right else text.ljust(width)


def header_table(fields):
    headings = " ".join(
        cell(label, width) for label, _value, width, _right in fields).rstrip()
    values = " ".join(
        cell(value, width, right=right)
        for _label, value, width, right in fields).rstrip()
    return headings, values


def human_duration(seconds):
    value = max(0, int(seconds))
    days, value = divmod(value, 86400)
    hours, value = divmod(value, 3600)
    minutes, seconds = divmod(value, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


def right_header(left, summary, width):
    if len(summary) > width - HEADER_MARGIN:
        return summary[:width]
    left = left[:max(0, width - len(summary) - HEADER_MARGIN)]
    return left + " " * max(HEADER_MARGIN, width - len(left) - len(summary)) + summary


def score_summary(progress, label, width):
    full = progress.summary(label)
    if label == "LATEST*":
        missing = progress.remaining_to_perfect()
        if missing is not None:
            overall = progress.current_means()["ALL"]
            full += (
                f' | TO100 {missing["total"]}/{getattr(progress,"question_count",616)} wrong '
                f'(G{missing["G"]} B{missing["B"]} N{missing["N"]}); '
                f'ALL +{100-overall:.1f}pp')
    if len(full) <= width:
        return full
    means = progress.start_means() if label == "START" else progress.current_means()
    compact = label + " " + " ".join(
        f"{group}{means[group]:.0f}%" if means[group] is not None else f"{group}-"
        for group in ("G", "B", "N", "ALL"))
    if label == "LATEST*":
        missing = progress.remaining_to_perfect()
        denominator = getattr(progress, "question_count", 616)
        if (missing is not None and
                len(compact) + len(f' TO100 {missing["total"]}/{denominator}') <= width):
            compact += f' TO100 {missing["total"]}/{denominator}'
    return compact


def display_metric(value, *, decimals=3):
    if type(value) in (float, int):
        if value and abs(value) < 0.5 * SCIENTIFIC_NOTATION_BASE ** (-decimals):
            return f"{value:.2e}"
        return f"{value:.{decimals}f}"
    return "-"


def normalize_number_semantics(values):
    if values in (None, ()):
        return ()
    if (isinstance(values, (list, tuple)) and values and
            all(isinstance(value, str) and value for value in values)):
        return tuple(values)
    raise ValueError(OperatorStatusError.NUMBER_SEMANTICS_INVALID.value)


def number_semantics_from_state(state):
    if not isinstance(state, dict):
        return ()
    heads = ((state.get("config") or {}).get("answer_heads") or {})
    values = (heads.get("numeric_active") or {}).get("values")
    try:
        return normalize_number_semantics(values)
    except ValueError:
        return ()


def number_semantics_from_profile(profile_id):
    if not isinstance(profile_id, str):
        return ()
    marker = "/numeric-0-"
    if marker not in profile_id:
        return ()
    suffix = profile_id.rsplit(marker, 1)[1]
    if not suffix.isdigit():
        return ()
    maximum = int(suffix)
    if maximum > MAX_DISPLAY_INTEGER_ROOT:
        return ()
    return tuple(str(value) for value in range(maximum + 1))


def number_semantics_text(values):
    return " ".join(values) if values else "-"


def add_notice(notifications, now, message, *, key=None,
               ttl_seconds=NOTICE_TTL_SECONDS):
    if (not isinstance(message, str) or not message.strip() or
            not isinstance(ttl_seconds, (int, float)) or ttl_seconds <= 0):
        raise ValueError(OperatorStatusError.NOTIFICATION_INVALID.value)
    identity = str(key if key is not None else message)
    current = [
        item for item in notifications
        if item["expires"] > now and item["key"] != identity
    ]
    notifications.clear()
    notifications.extend(current)
    notifications.append({
        "key": identity,
        "message": message.strip(),
        "expires": now + float(ttl_seconds),
    })


def active_notice(notifications, now):
    current = [item for item in notifications if item["expires"] > now]
    if len(current) != len(notifications):
        notifications.clear()
        notifications.extend(current)
    return current[-1]["message"] if current else None


def school_phase_notice(grade, phase):
    if not isinstance(grade, str) or not grade:
        return None
    return {
        "AWAITING_NEXT_GRADE":
            f"GRADE {grade} GRADUATED 100% > NEXT GRADE READY",
        "AWAITING_NEXT_GRADE_WITH_DEBT":
            f"GRADE {grade} PROMOTED WITH DEBT > NEXT GRADE READY",
        "WHOLE_SCHOOL_MASTERED":
            f"SCHOOL MASTERED THROUGH GRADE {grade} 100%",
    }.get(phase)


def notify_grade_admitted(board, grade, generation):
    if grade:
        board.notify(
            f"GRADE {grade} ADMITTED > CURRICULUM EXPANDED",
            key=f"grade-admitted:{grade}:{generation}")


def apply_profile_adoption(telemetry, grade, event):
    profile_id = event.get("profile_id")
    if not grade or not isinstance(profile_id, str) or not profile_id:
        raise ValueError(OperatorStatusError.PROFILE_ADOPTION_INVALID.value)
    telemetry._reset_score_era(reason=event["event"], grade=grade)
    numeric_changed = telemetry.board.set_numeric_profile(profile_id, notify=True)
    if event.get("transition_kind") == "APPEND_GRADE":
        notify_grade_admitted(telemetry.board, grade, event.get("generation", "-"))
    telemetry.board.push("system", {
        "kind": "CURRICULUM", "grade": grade,
        "detail": (
            f"Active profile {profile_id}" +
            (" | number scope updated" if numeric_changed else "")),
    }, redraw=False)
