import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from core.incident import (
    ACTION_FIELDS,
    AFFECTED_SCOPES,
    CATEGORIES,
    INCIDENT_FIELDS,
    Incident,
    SEVERITY_LEVELS,
    STATUSES,
    URGENCY_LEVELS,
)


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DEFAULT_DATA_DIR = DATA_DIR


class CyberAwareError(Exception):
    """Base error for storage and analytics"""


class StorageError(CyberAwareError):
    """Raised when a data file cannot be read or written safely"""


APP_DATETIME_FORMAT = "%d/%m/%Y %I:%M %p"
INCIDENT_ID_PATTERN = re.compile(r"^INC-\d+$")
RESULT_ID_PATTERN = re.compile(r"^RES-\d+$")

UNRESOLVED_STATUSES = ("Submitted", "Under Review")
QUIZ_STAGES = ("pre-training", "post-training")

ARTICLE_FIELDS = (
    "article_id",
    "title",
    "category",
    "summary",
    "content",
    "source_name",
    "source_url",
    "published_at",
)

QUIZ_QUESTION_FIELDS = (
    "question_id",
    "topic",
    "question",
    "options",
    "correct_option",
    "explanation",
)

QUIZ_RESULT_FIELDS = (
    "result_id",
    "participant_code",
    "quiz_stage",
    "quiz_date",
    "score",
    "total_questions",
)

REQUIRED_INCIDENT_FIELDS = (
    "incident_id",
    "reported_at",
    "category",
    "description",
    "severity",
    "urgency",
    "affected_scope",
    "status",
)


SYNTHETIC_SEED = 42


def _is_blank(value):
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    if isinstance(value, str) and not value.strip():
        return True
    text = str(value).strip()
    return text.lower() in {"nan", "nat", "none", "null"}


def _as_text(value):
    if _is_blank(value):
        return ""
    return str(value).strip()


def format_app_datetime(value):
    """Format a datetime using English AM/PM"""
    hour = value.hour % 12
    if hour == 0:
        hour = 12
    suffix = "AM" if value.hour < 12 else "PM"
    return (
        f"{value.day:02d}/{value.month:02d}/{value.year} "
        f"{hour:02d}:{value.minute:02d} {suffix}"
    )


def parse_app_datetime(value):
    """Parse DD/MM/YYYY HH:MM AM/PM"""
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if _is_blank(value):
        return None
    text = _as_text(value)
    try:
        return datetime.strptime(text, APP_DATETIME_FORMAT)
    except ValueError:
        return None


def parse_filter_datetime(value, end_of_day=False):
    if value is None or _is_blank(value):
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    parsed = parse_app_datetime(value)
    if parsed is not None:
        return parsed
    try:
        parsed = datetime.strptime(_as_text(value), "%d/%m/%Y")
    except ValueError as error:
        raise ValueError(
            "Filter dates must use DD/MM/YYYY or DD/MM/YYYY HH:MM AM/PM."
        ) from error
    if end_of_day:
        return parsed.replace(hour=23, minute=59, second=59)
    return parsed


def expected_priority(severity, urgency):
    if severity not in SEVERITY_LEVELS or urgency not in URGENCY_LEVELS:
        raise ValueError("Severity and urgency must be valid before scoring.")
    return SEVERITY_LEVELS.index(severity) + 1 + URGENCY_LEVELS.index(urgency) + 1


def to_int_priority(value):
    if _is_blank(value):
        raise ValueError("Priority score is missing.")
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError) as error:
        raise ValueError("Priority score must be a whole number.") from error
    if number != int(number):
        raise ValueError("Priority score must be a whole number.")
    return int(number)


def serialize_incidents(incidents, allow_invalid=False):
    rows = []
    for item in incidents:
        if hasattr(item, "to_dict"):
            record = item.to_dict()
        elif isinstance(item, dict):
            record = item
        else:
            raise TypeError("Each incident must be a dictionary or Incident.")
        row = {}
        for field in INCIDENT_FIELDS:
            value = record.get(field, "")
            if field == "priority_score":
                try:
                    row[field] = to_int_priority(value)
                except ValueError:
                    if not allow_invalid:
                        raise
                    row[field] = "" if _is_blank(value) else value
            else:
                row[field] = _as_text(value)
        rows.append(row)
    return rows


def serialize_actions(actions):
    rows = []
    for item in actions:
        if not isinstance(item, dict):
            raise TypeError("Each action must be a dictionary.")
        rows.append({field: _as_text(item.get(field, "")) for field in ACTION_FIELDS})
    return rows


def records_to_dataframe(records, fields=INCIDENT_FIELDS):
    """Convert records for analysis"""
    rows = []
    for item in records:
        if hasattr(item, "to_dict"):
            record = item.to_dict()
        elif isinstance(item, dict):
            record = item
        else:
            raise TypeError("Each incident must be a dictionary or Incident.")
        row = {}
        for field in fields:
            value = record.get(field, "")
            if field == "priority_score":
                try:
                    row[field] = to_int_priority(value)
                except ValueError:
                    row[field] = "" if _is_blank(value) else value
            else:
                row[field] = _as_text(value)
        rows.append(row)
    return pd.DataFrame(rows, columns=list(fields))


def incidents_from_records(records):
    objects = []
    for record in serialize_incidents(records):
        objects.append(Incident(**{field: record[field] for field in INCIDENT_FIELDS}))
    return objects


def _read_table(path, fields):
    path = Path(path)
    suffix = path.suffix.lower()
    try:
        if suffix == ".json":
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                raise StorageError(path.name + " must contain a JSON list.")
            frame = pd.DataFrame(raw)
        elif suffix in {".csv", ".txt"}:
            frame = pd.read_csv(
                path, dtype=str, keep_default_na=False, encoding="utf-8"
            )
        else:
            raise StorageError("Supported data files are CSV and JSON.")
    except json.JSONDecodeError as error:
        raise StorageError("The file is not valid JSON: " + path.name) from error
    except pd.errors.EmptyDataError:
        frame = pd.DataFrame(columns=list(fields))
    except OSError as error:
        raise StorageError("Could not read " + path.name + ".") from error

    for field in fields:
        if field not in frame.columns:
            frame[field] = ""
    frame = frame.loc[:, list(fields)]
    for field in fields:
        if field != "priority_score":
            frame[field] = frame[field].map(_as_text)
    return frame


def _atomic_write_csv(frame, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        frame.to_csv(tmp, index=False, encoding="utf-8")
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def _atomic_write_json(records, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


class DataRepository:

    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR
        self.incidents_path = self.data_dir / "incidents.csv"
        self.actions_path = self.data_dir / "incident_actions.csv"
        self.articles_path = self.data_dir / "articles.json"
        self.quiz_questions_path = self.data_dir / "quiz_questions.json"
        self.quiz_results_path = self.data_dir / "quiz_results.csv"

    def _prepare_empty_file(self, path, fields, json_file=False):
        path.parent.mkdir(parents=True, exist_ok=True)
        if json_file:
            _atomic_write_json([], path)
        else:
            _atomic_write_csv(pd.DataFrame(columns=list(fields)), path)

    def _load_records(self, path, fields, json_file=False):
        if not path.exists():
            self._prepare_empty_file(path, fields, json_file=json_file)
            return []
        try:
            frame = _read_table(path, fields)
        except StorageError:
            raise
        except Exception as error:
            raise StorageError("Could not read " + path.name + ".") from error
        records = frame.to_dict(orient="records")
        if "priority_score" in fields:
            normalized = []
            for record in records:
                if not _is_blank(record.get("priority_score")):
                    record["priority_score"] = to_int_priority(record["priority_score"])
                else:
                    record["priority_score"] = ""
                normalized.append(record)
            return normalized
        return records

    def load_incidents(self, path=None):
        target = Path(path) if path is not None else self.incidents_path
        return self._load_records(
            target, INCIDENT_FIELDS, json_file=target.suffix.lower() == ".json"
        )

    def save_incidents(self, incidents, path=None, allow_invalid=False):
        target = Path(path) if path is not None else self.incidents_path
        rows = serialize_incidents(incidents, allow_invalid=allow_invalid)
        frame = pd.DataFrame(rows, columns=list(INCIDENT_FIELDS))
        try:
            if target.suffix.lower() == ".json":
                _atomic_write_json(rows, target)
            else:
                _atomic_write_csv(frame, target)
        except OSError as error:
            raise StorageError("Could not save incidents.") from error
        return target

    def load_actions(self, path=None):
        target = Path(path) if path is not None else self.actions_path
        return self._load_records(
            target, ACTION_FIELDS, json_file=target.suffix.lower() == ".json"
        )

    def save_actions(self, actions, path=None):
        target = Path(path) if path is not None else self.actions_path
        rows = serialize_actions(actions)
        frame = pd.DataFrame(rows, columns=list(ACTION_FIELDS))
        try:
            if target.suffix.lower() == ".json":
                _atomic_write_json(rows, target)
            else:
                _atomic_write_csv(frame, target)
        except OSError as error:
            raise StorageError("Could not save actions.") from error
        return target

    def load_articles(self, path=None):
        target = Path(path) if path is not None else self.articles_path
        return self._load_records(target, ARTICLE_FIELDS, json_file=True)

    def save_articles(self, articles, path=None):
        target = Path(path) if path is not None else self.articles_path
        rows = []
        for item in articles:
            if not isinstance(item, dict):
                raise TypeError("Each article must be a dictionary.")
            rows.append({field: item.get(field, "") for field in ARTICLE_FIELDS})
        try:
            if target.suffix.lower() == ".json":
                _atomic_write_json(rows, target)
            else:
                _atomic_write_csv(
                    pd.DataFrame(rows, columns=list(ARTICLE_FIELDS)), target
                )
        except OSError as error:
            raise StorageError("Could not save articles.") from error
        return target

    def load_quiz_questions(self, path=None):
        target = Path(path) if path is not None else self.quiz_questions_path
        if not target.exists():
            self._prepare_empty_file(target, QUIZ_QUESTION_FIELDS, json_file=True)
            return []
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise StorageError("The file is not valid JSON: " + target.name) from error
        if not isinstance(raw, list):
            raise StorageError(target.name + " must contain a JSON list.")
        return raw

    def save_quiz_questions(self, questions, path=None):
        target = Path(path) if path is not None else self.quiz_questions_path
        if not isinstance(questions, list):
            raise TypeError("Quiz questions must be a list.")
        try:
            _atomic_write_json(questions, target)
        except OSError as error:
            raise StorageError("Could not save quiz questions.") from error
        return target

    def load_quiz_results(self, path=None):
        target = Path(path) if path is not None else self.quiz_results_path
        records = self._load_records(
            target, QUIZ_RESULT_FIELDS, json_file=target.suffix.lower() == ".json"
        )
        for record in records:
            if not _is_blank(record.get("score")):
                record["score"] = int(float(record["score"]))
            if not _is_blank(record.get("total_questions")):
                record["total_questions"] = int(float(record["total_questions"]))
        return records

    def save_quiz_results(self, results, path=None):
        target = Path(path) if path is not None else self.quiz_results_path
        rows = []
        for item in results:
            if not isinstance(item, dict):
                raise TypeError("Each quiz result must be a dictionary.")
            row = {field: item.get(field, "") for field in QUIZ_RESULT_FIELDS}
            row["result_id"] = _as_text(row["result_id"])
            row["participant_code"] = _as_text(row["participant_code"])
            row["quiz_stage"] = _as_text(row["quiz_stage"])
            row["quiz_date"] = _as_text(row["quiz_date"])
            row["score"] = int(row["score"])
            row["total_questions"] = int(row["total_questions"])
            rows.append(row)
        frame = pd.DataFrame(rows, columns=list(QUIZ_RESULT_FIELDS))
        try:
            if target.suffix.lower() == ".json":
                _atomic_write_json(rows, target)
            else:
                _atomic_write_csv(frame, target)
        except OSError as error:
            raise StorageError("Could not save quiz results.") from error
        return target

    def export_incidents(self, incidents, path):
        return self.save_incidents(incidents, path)
