import random
from datetime import datetime, timedelta

from analytics.data_files import (
    AFFECTED_SCOPES,
    CATEGORIES,
    INCIDENT_FIELDS,
    SEVERITY_LEVELS,
    STATUSES,
    SYNTHETIC_SEED,
    URGENCY_LEVELS,
    DataRepository,
    expected_priority,
    format_app_datetime,
)

DESCRIPTION_TEMPLATES = {
    "Phishing / Suspicious Message": (
        "[SIMULATED] A message claimed to be from campus IT and asked the user to confirm a student portal password on an unfamiliar page.",
        "[SIMULATED] An email used the university name and asked the recipient to click a button to prevent mailbox closure.",
        "[SIMULATED] A chat message offered a scholarship form and asked for a login code. No live link was opened.",
        "[SIMULATED] A notice said a library fine must be paid immediately through a page that did not match the usual library address.",
        "[SIMULATED] A message impersonated a lecturer and asked students to share a one-time sign-in code.",
    ),
    "Account Security": (
        "[SIMULATED] The user received a login alert for a campus account from an unrecognized city.",
        "[SIMULATED] Password reset emails arrived repeatedly although the user did not request a reset.",
        "[SIMULATED] A shared lab computer still had a previous student session open.",
        "[SIMULATED] Multi-factor prompts appeared at night when the user was not signing in.",
        "[SIMULATED] An old personal email still listed as the account recovery address looked unused.",
    ),
    "Malware": (
        "[SIMULATED] A coursework file from a classmate triggered a browser warning before it was opened.",
        "[SIMULATED] A USB classroom file installer asked for permission to run an unknown program. It was not run.",
        "[SIMULATED] A downloaded notes archive had a double file extension that did not match a normal document.",
        "[SIMULATED] A pop-up claimed the laptop was infected and demanded a call to a support number.",
        "[SIMULATED] An email attachment named invoice.pdf.exe was reported and not opened.",
    ),
    "Unauthorized Access": (
        "[SIMULATED] Coursework files in a shared folder were renamed overnight without a known editor.",
        "[SIMULATED] A lab account showed last-access times outside booked hours.",
        "[SIMULATED] An unknown device appeared in the campus account session list.",
        "[SIMULATED] A shared department mailbox sent mail that the usual owners did not write.",
        "[SIMULATED] A locker-room camera account password was still the default word from setup notes.",
    ),
    "Other": (
        "[SIMULATED] A public Wi-Fi hotspot at a cafe asked the user to install a certificate to continue.",
        "[SIMULATED] A caller claimed to be from campus finance and asked for a one-time payment code.",
        "[SIMULATED] A social-media page copied the student union name and asked for event registration details.",
        "[SIMULATED] A QR poster on a noticeboard pointed to a shortened address that did not match the official site. It was not opened.",
        "[SIMULATED] A job offer chat asked for copies of a national ID photo before any interview.",
    ),
}

RESOLUTION_TEMPLATES = (
    "Synthetic review: user advised not to open the message and to keep the original report. Not a confirmed attack.",
    "Synthetic review: password reset and MFA check were recommended. No live investigation was performed.",
    "Synthetic review: report classified for awareness follow-up. Priority score is not a decision that an attack occurred.",
    "Synthetic review: closed after guidance was recorded. Dataset row is simulated.",
)


INCIDENT_COUNT = 24
QUIZ_PARTICIPANT_COUNT = 6


def generate_synthetic_incidents(count=INCIDENT_COUNT, seed=SYNTHETIC_SEED):
    rng = random.Random(seed)
    start = datetime(2026, 5, 4, 8, 15)
    latest_report = datetime(2026, 10, 12, 16, 40)
    span_seconds = int((latest_report - start).total_seconds())
    incidents = []
    actions = []
    action_number = 1

    for index in range(count):
        reported = start + timedelta(seconds=rng.randint(0, span_seconds))
        reported = reported.replace(second=0, microsecond=0)
        category = rng.choices(
            CATEGORIES,
            weights=(40, 20, 15, 15, 10),
            k=1,
        )[0]
        severity = rng.choices(SEVERITY_LEVELS, weights=(20, 40, 30, 10), k=1)[0]
        urgency = rng.choices(URGENCY_LEVELS, weights=(30, 45, 25), k=1)[0]
        scope = rng.choices(AFFECTED_SCOPES, weights=(45, 30, 15, 10), k=1)[0]
        status = rng.choices(STATUSES, weights=(22, 28, 35, 15), k=1)[0]
        description = rng.choice(DESCRIPTION_TEMPLATES[category])
        incident_id = "INC-" + str(1001 + index)
        reviewed_at = ""
        resolution = ""
        reviewed_time = None

        if status != "Submitted":
            delay_minutes = rng.randint(20, 48 * 60)
            reviewed_time = reported + timedelta(minutes=delay_minutes)
            if reviewed_time > datetime(2026, 10, 13, 12, 0):
                reviewed_time = datetime(2026, 10, 13, 12, 0)
            if reviewed_time <= reported:
                reviewed_time = reported + timedelta(minutes=25)
            reviewed_time = reviewed_time.replace(second=0, microsecond=0)
            reviewed_at = format_app_datetime(reviewed_time)
            actions.append(
                {
                    "action_id": "ACT-" + str(action_number).zfill(4),
                    "incident_id": incident_id,
                    "action_type": "Status changed: Submitted -> Under Review",
                    "action_time": reviewed_at,
                    "note": "Synthetic review started. No live suspicious link was opened.",
                }
            )
            action_number += 1

        if status in {"Resolved", "Closed"} and reviewed_time is not None:
            close_time = reviewed_time + timedelta(minutes=rng.randint(30, 36 * 60))
            if close_time > datetime(2026, 10, 13, 16, 0):
                close_time = datetime(2026, 10, 13, 16, 0)
            if close_time <= reviewed_time:
                close_time = reviewed_time + timedelta(minutes=35)
            close_time = close_time.replace(second=0, microsecond=0)
            close_stamp = format_app_datetime(close_time)
            if status == "Resolved":
                resolution = rng.choice(RESOLUTION_TEMPLATES)
                action_type = "Status changed: Under Review -> Resolved"
                note = "Synthetic resolution recorded for demonstration."
            else:
                action_type = "Status changed: Under Review -> Closed"
                note = "Synthetic closure recorded for demonstration."
            actions.append(
                {
                    "action_id": "ACT-" + str(action_number).zfill(4),
                    "incident_id": incident_id,
                    "action_type": action_type,
                    "action_time": close_stamp,
                    "note": note,
                }
            )
            action_number += 1

        incidents.append(
            {
                "incident_id": incident_id,
                "reported_at": format_app_datetime(reported),
                "category": category,
                "description": description,
                "severity": severity,
                "urgency": urgency,
                "affected_scope": scope,
                "priority_score": expected_priority(severity, urgency),
                "status": status,
                "reviewed_at": reviewed_at,
                "resolution": resolution,
            }
        )
    return incidents, actions


def generate_synthetic_quiz_results(participant_count=QUIZ_PARTICIPANT_COUNT, seed=SYNTHETIC_SEED):
    rng = random.Random(seed + 7)
    results = []
    result_number = 1
    start = datetime(2026, 6, 1, 9, 0)
    for index in range(participant_count):
        participant = "P-" + str(index + 1).zfill(4)
        pre_date = start + timedelta(days=rng.randint(0, 40), hours=rng.randint(0, 8))
        post_date = pre_date + timedelta(
            days=rng.randint(5, 20), hours=rng.randint(0, 5)
        )
        pre_score = rng.randint(3, 7)
        post_score = min(10, pre_score + rng.randint(0, 4))
        for stage, score, when in (
            ("pre-training", pre_score, pre_date),
            ("post-training", post_score, post_date),
        ):
            results.append(
                {
                    "result_id": "RES-" + str(result_number).zfill(4),
                    "participant_code": participant,
                    "quiz_stage": stage,
                    "quiz_date": format_app_datetime(
                        when.replace(second=0, microsecond=0)
                    ),
                    "score": score,
                    "total_questions": 10,
                }
            )
            result_number += 1
    return results


def generate_dirty_incidents():
    """Rows used only to prove cleaning. Do not load this file into IncidentManager."""
    valid = {
        "incident_id": "INC-9001",
        "reported_at": "01/09/2026 10:00 AM",
        "category": "Phishing / Suspicious Message",
        "description": "[SIMULATED] Valid dirty-set control row.",
        "severity": "High",
        "urgency": "Medium",
        "affected_scope": "One user",
        "priority_score": 5,
        "status": "Submitted",
        "reviewed_at": "",
        "resolution": "",
    }
    rows = [
        valid,
        dict(valid),
        {
            **valid,
            "incident_id": "INC-9002",
            "reported_at": "2026-09-01",
            "description": "[SIMULATED] Invalid ISO date on purpose.",
        },
        {
            **valid,
            "incident_id": "INC-9003",
            "description": "",
        },
        {
            **valid,
            "incident_id": "INC-9004",
            "category": "Hacking",
            "description": "[SIMULATED] Invalid category on purpose.",
        },
        {
            **valid,
            "incident_id": "INC-9005",
            "priority_score": 99,
            "severity": "Low",
            "urgency": "Low",
            "description": "[SIMULATED] Wrong priority on purpose.",
        },
        {
            **valid,
            "incident_id": "INC-9006",
            "status": "Done",
            "description": "[SIMULATED] Invalid status on purpose.",
        },
        {
            **valid,
            "incident_id": "",
            "description": "[SIMULATED] Missing ID on purpose.",
        },
        {
            **valid,
            "incident_id": "INC-9008",
            "status": "Under Review",
            "reviewed_at": "not-a-date",
            "description": "[SIMULATED] Invalid review timestamp on purpose.",
            "priority_score": 5,
        },
        {field: "" for field in INCIDENT_FIELDS},
    ]
    return rows


def generate_and_save_synthetic_dataset(data_dir=None, incident_count=INCIDENT_COUNT):
    repository = DataRepository(data_dir)
    repository.data_dir.mkdir(parents=True, exist_ok=True)
    incidents, actions = generate_synthetic_incidents(incident_count)
    quiz_results = generate_synthetic_quiz_results()
    dirty = generate_dirty_incidents()

    repository.save_incidents(incidents)
    repository.save_incidents(incidents, repository.data_dir / "incidents.json")
    repository.save_actions(actions)
    repository.save_actions(actions, repository.data_dir / "incident_actions.json")
    repository.save_quiz_results(quiz_results)
    repository.save_quiz_results(
        quiz_results, repository.data_dir / "quiz_results.json"
    )
    repository.save_incidents(
        dirty,
        repository.data_dir / "dirty_incidents.csv",
        allow_invalid=True,
    )
    repository.save_articles([])
    repository.save_quiz_questions([])
    return {
        "incidents": len(incidents),
        "actions": len(actions),
        "quiz_results": len(quiz_results),
        "dirty_incidents": len(dirty),
        "data_dir": str(repository.data_dir),
    }
