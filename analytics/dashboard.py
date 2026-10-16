from pathlib import Path

import pandas as pd

from analytics.data_files import (
    AFFECTED_SCOPES,
    CATEGORIES,
    INCIDENT_FIELDS,
    INCIDENT_ID_PATTERN,
    QUIZ_RESULT_FIELDS,
    QUIZ_STAGES,
    REQUIRED_INCIDENT_FIELDS,
    RESULT_ID_PATTERN,
    SEVERITY_LEVELS,
    STATUSES,
    UNRESOLVED_STATUSES,
    URGENCY_LEVELS,
    _as_text,
    _atomic_write_csv,
    _is_blank,
    expected_priority,
    format_app_datetime,
    parse_app_datetime,
    parse_filter_datetime,
    records_to_dataframe,
    to_int_priority,
)

class IncidentAnalyzer:
    """Clean incident records and calculate dashboard KPIs with Pandas"""

    def __init__(self, repository=None):
        self.repository = repository

    def _to_frame(self, records=None):
        if records is None:
            if self.repository is None:
                raise ValueError("No incident records were provided.")
            records = self.repository.load_incidents()
        if isinstance(records, pd.DataFrame):
            frame = records.copy()
            for field in INCIDENT_FIELDS:
                if field not in frame.columns:
                    frame[field] = ""
            return frame.loc[:, list(INCIDENT_FIELDS)]
        return records_to_dataframe(records)

    def _datetime_series(self, series):
        parsed = [parse_app_datetime(value) for value in series]
        return pd.Series(
            [pd.Timestamp(value) if value is not None else pd.NaT for value in parsed],
            index=series.index,
        )

    def clean_data(self, records=None):
        """Clean missing values, duplicates, and invalid dates

        same incident_id. The first row is kept
        Invalid reported_at rows are dropped so review-time math is not wrong
        """
        frame = self._to_frame(records)
        report = {
            "rows_in": int(len(frame)),
            "rows_out": 0,
            "dropped_empty_rows": 0,
            "dropped_missing_required": 0,
            "dropped_invalid_id": 0,
            "dropped_invalid_dates": 0,
            "dropped_invalid_category": 0,
            "dropped_invalid_status": 0,
            "dropped_invalid_severity": 0,
            "dropped_invalid_urgency": 0,
            "dropped_invalid_scope": 0,
            "dropped_duplicate_ids": 0,
            "priority_recalculated": 0,
            "cleared_invalid_reviewed_at": 0,
            "excluded_negative_review_times": 0,
        }

        if frame.empty:
            report["rows_out"] = 0
            return frame.reset_index(drop=True), report

        working = frame.copy()
        for field in INCIDENT_FIELDS:
            if field != "priority_score":
                working[field] = working[field].map(_as_text)

        empty_mask = working.apply(
            lambda row: all(_is_blank(value) for value in row), axis=1
        )
        report["dropped_empty_rows"] = int(empty_mask.sum())
        working = working.loc[~empty_mask].copy()

        required_blank = pd.Series(False, index=working.index)
        for field in REQUIRED_INCIDENT_FIELDS:
            required_blank = required_blank | working[field].map(_is_blank)
        report["dropped_missing_required"] = int(required_blank.sum())
        working = working.loc[~required_blank].copy()

        invalid_id = ~working["incident_id"].map(
            lambda value: bool(INCIDENT_ID_PATTERN.match(value))
        )
        report["dropped_invalid_id"] = int(invalid_id.sum())
        working = working.loc[~invalid_id].copy()

        reported = self._datetime_series(working["reported_at"])
        invalid_reported = reported.isna()
        report["dropped_invalid_dates"] = int(invalid_reported.sum())
        working = working.loc[~invalid_reported].copy()
        reported = reported.loc[~invalid_reported]
        working["reported_at"] = [
            format_app_datetime(value.to_pydatetime()) for value in reported
        ]

        reviewed = self._datetime_series(working["reviewed_at"])
        invalid_reviewed = (
            working["reviewed_at"].map(lambda value: not _is_blank(value))
            & reviewed.isna()
        )
        report["cleared_invalid_reviewed_at"] = int(invalid_reviewed.sum())
        working.loc[invalid_reviewed, "reviewed_at"] = ""
        reviewed.loc[invalid_reviewed] = pd.NaT
        formatted_reviewed = []
        for value in reviewed:
            if pd.isna(value):
                formatted_reviewed.append("")
            else:
                formatted_reviewed.append(format_app_datetime(value.to_pydatetime()))
        working["reviewed_at"] = formatted_reviewed

        invalid_category = ~working["category"].isin(CATEGORIES)
        report["dropped_invalid_category"] = int(invalid_category.sum())
        working = working.loc[~invalid_category].copy()

        invalid_status = ~working["status"].isin(STATUSES)
        report["dropped_invalid_status"] = int(invalid_status.sum())
        working = working.loc[~invalid_status].copy()

        invalid_severity = ~working["severity"].isin(SEVERITY_LEVELS)
        report["dropped_invalid_severity"] = int(invalid_severity.sum())
        working = working.loc[~invalid_severity].copy()

        invalid_urgency = ~working["urgency"].isin(URGENCY_LEVELS)
        report["dropped_invalid_urgency"] = int(invalid_urgency.sum())
        working = working.loc[~invalid_urgency].copy()

        invalid_scope = ~working["affected_scope"].isin(AFFECTED_SCOPES)
        report["dropped_invalid_scope"] = int(invalid_scope.sum())
        working = working.loc[~invalid_scope].copy()

        priorities = []
        recalculated = 0
        for _, row in working.iterrows():
            expected = expected_priority(row["severity"], row["urgency"])
            try:
                current = to_int_priority(row["priority_score"])
            except ValueError:
                current = expected
                recalculated += 1
            if current != expected:
                current = expected
                recalculated += 1
            priorities.append(int(current))
        working["priority_score"] = priorities
        report["priority_recalculated"] = recalculated

        duplicate_count = int(working["incident_id"].duplicated(keep="first").sum())
        report["dropped_duplicate_ids"] = duplicate_count
        working = working.drop_duplicates(subset=["incident_id"], keep="first")

        working["resolution"] = working["resolution"].map(_as_text)
        working = working.reset_index(drop=True)
        report["rows_out"] = int(len(working))
        return working, report

    def apply_filters(self, frame, filters=None):
        if frame.empty:
            return frame.copy()
        filters = filters or {}
        selected = frame.copy()
        reported = self._datetime_series(selected["reported_at"])

        date_from = parse_filter_datetime(filters.get("date_from"))
        date_to = parse_filter_datetime(filters.get("date_to"), end_of_day=True)
        if date_from is not None:
            selected = selected.loc[reported >= pd.Timestamp(date_from)]
            reported = reported.loc[selected.index]
        if date_to is not None:
            selected = selected.loc[reported <= pd.Timestamp(date_to)]

        for field, key in (
            ("category", "categories"),
            ("status", "statuses"),
            ("severity", "severities"),
        ):
            values = filters.get(key)
            if values:
                selected = selected.loc[selected[field].isin(list(values))]
        return selected.reset_index(drop=True)

    def group_by_category(self, frame):
        if frame.empty:
            return pd.DataFrame(columns=["category", "count"])
        return (
            frame.groupby("category", dropna=False)
            .size()
            .reset_index(name="count")
            .sort_values(["count", "category"], ascending=[False, True])
            .reset_index(drop=True)
        )

    def group_by_status(self, frame):
        if frame.empty:
            return pd.DataFrame(columns=["status", "count"])
        counts = (
            frame.groupby("status", dropna=False)
            .size()
            .reindex(list(STATUSES), fill_value=0)
            .reset_index(name="count")
        )
        counts.columns = ["status", "count"]
        return counts

    def group_by_severity(self, frame):
        if frame.empty:
            return pd.DataFrame(columns=["severity", "count"])
        counts = (
            frame.groupby("severity", dropna=False)
            .size()
            .reindex(list(SEVERITY_LEVELS), fill_value=0)
            .reset_index(name="count")
        )
        counts.columns = ["severity", "count"]
        return counts

    def analyze_trends(self, frame, freq="M"):
        empty = pd.DataFrame(columns=["period", "count"])
        if frame.empty:
            return empty
        reported = self._datetime_series(frame["reported_at"]).dropna()
        if reported.empty:
            return empty
        if freq == "D":
            grouped = reported.dt.floor("D")
            trend = grouped.value_counts().sort_index()
            result = trend.reset_index()
            result.columns = ["period_dt", "count"]
            result["period"] = result["period_dt"].dt.strftime("%d/%m/%Y")
            return result[["period", "count"]]
        if freq == "W":
            periods = reported.dt.to_period("W").astype(str)
        else:
            periods = reported.dt.to_period("M").astype(str)
        trend = periods.value_counts().sort_index()
        result = trend.reset_index()
        result.columns = ["period", "count"]
        return result

    def _review_hours(self, frame):
        if frame.empty:
            return pd.Series(dtype="float64"), 0
        reported = self._datetime_series(frame["reported_at"])
        reviewed = self._datetime_series(frame["reviewed_at"])
        usable = reported.notna() & reviewed.notna()
        hours = (
            reviewed.loc[usable] - reported.loc[usable]
        ).dt.total_seconds() / 3600.0
        negative = int((hours < 0).sum())
        hours = hours.loc[hours >= 0]
        return hours, negative

    def calculate_metrics(self, frame):
        total = int(len(frame))
        unresolved = (
            int(frame["status"].isin(UNRESOLVED_STATUSES).sum()) if total else 0
        )
        hours, negative = self._review_hours(frame)
        average_hours = round(float(hours.mean()), 2) if not hours.empty else None
        return {
            "total_incidents": total,
            "unresolved_incidents": unresolved,
            "unresolved_percent": (
                round((unresolved / total) * 100, 2) if total else None
            ),
            "average_review_hours": average_hours,
            "reviewed_with_timestamp": int(len(hours)),
            "excluded_negative_review_times": negative,
        }

    def clean_quiz_results(self, results=None):
        if results is None:
            if self.repository is None:
                return pd.DataFrame(columns=list(QUIZ_RESULT_FIELDS)), {
                    "rows_in": 0,
                    "rows_out": 0,
                }
            results = self.repository.load_quiz_results()
        if isinstance(results, pd.DataFrame):
            frame = results.copy()
        else:
            frame = pd.DataFrame(results)
        for field in QUIZ_RESULT_FIELDS:
            if field not in frame.columns:
                frame[field] = ""
        frame = frame.loc[:, list(QUIZ_RESULT_FIELDS)]
        report = {"rows_in": int(len(frame)), "rows_out": 0, "dropped_invalid": 0}
        if frame.empty:
            return frame, report

        keep = []
        for _, row in frame.iterrows():
            valid = True
            if not RESULT_ID_PATTERN.match(_as_text(row["result_id"])):
                valid = False
            if _is_blank(row["participant_code"]):
                valid = False
            if _as_text(row["quiz_stage"]) not in QUIZ_STAGES:
                valid = False
            if parse_app_datetime(row["quiz_date"]) is None:
                valid = False
            try:
                score = int(float(row["score"]))
                total = int(float(row["total_questions"]))
            except (TypeError, ValueError):
                valid = False
                score = 0
                total = 0
            if valid and (total <= 0 or score < 0 or score > total):
                valid = False
            keep.append(valid)
        cleaned = frame.loc[keep].copy()
        if not cleaned.empty:
            cleaned["score"] = cleaned["score"].map(lambda value: int(float(value)))
            cleaned["total_questions"] = cleaned["total_questions"].map(
                lambda value: int(float(value))
            )
            cleaned["quiz_stage"] = cleaned["quiz_stage"].map(_as_text)
            cleaned["quiz_date"] = [
                format_app_datetime(parse_app_datetime(value))
                for value in cleaned["quiz_date"]
            ]
        report["dropped_invalid"] = int((~pd.Series(keep)).sum())
        report["rows_out"] = int(len(cleaned))
        return cleaned.reset_index(drop=True), report

    def _quiz_metrics(self, quiz_results):
        frame, report = self.clean_quiz_results(quiz_results)
        empty = pd.DataFrame(columns=["quiz_stage", "average_score", "attempts"])
        if frame.empty:
            return {
                "average_quiz_score": None,
                "attempts": 0,
                "by_stage": empty,
                "cleaning_report": report,
            }
        percent = (frame["score"] / frame["total_questions"]) * 100
        by_stage = (
            frame.assign(percent=percent)
            .groupby("quiz_stage", dropna=False)["percent"]
            .agg(["mean", "size"])
            .reset_index()
        )
        by_stage.columns = ["quiz_stage", "average_score", "attempts"]
        by_stage["average_score"] = by_stage["average_score"].round(2)
        return {
            "average_quiz_score": round(float(percent.mean()), 2),
            "attempts": int(len(frame)),
            "by_stage": by_stage,
            "cleaning_report": report,
        }

    def _insights(self, frame, kpis, quiz_metrics):
        if frame.empty:
            return [
                "No incidents match the selected filters.",
            ]
        insights = []
        by_category = self.group_by_category(frame)
        top = by_category.iloc[0]
        insights.append(
            f"{top['category']} is the most reported category in the filtered dataset "
            f"({int(top['count'])} of {kpis['total_incidents']} reports, "
            f"{round((int(top['count']) / kpis['total_incidents']) * 100, 1)}%)."
        )
        unresolved = kpis["unresolved_incidents"]
        percent = kpis["unresolved_percent"]
        insights.append(
            f"{unresolved} reports are unresolved (Submitted or Under Review"
            + (
                f", {percent}% of the filtered dataset)."
                if percent is not None
                else ")."
            )
        )
        if kpis["average_review_hours"] is None:
            insights.append(
                "Average review time is not available because no filtered report has a valid review timestamp."
            )
        else:
            insights.append(
                f"Average time from submission to first recorded review is "
                f"{kpis['average_review_hours']} hours "
                f"({kpis['reviewed_with_timestamp']} reports with a valid review timestamp)."
            )
        trend = self.analyze_trends(frame, freq="M")
        if not trend.empty:
            peak = trend.sort_values("count", ascending=False).iloc[0]
            insights.append(
                f"The month with the most reports in this filter is {peak['period']} "
                f"({int(peak['count'])} reports)."
            )
        if quiz_metrics["attempts"]:
            insights.append(
                f"Average quiz score is {quiz_metrics['average_quiz_score']}% "
                f"across {quiz_metrics['attempts']} attempts. "
                "A score change is not proof that real-world incidents decreased."
            )
        return insights

    def get_dashboard_metrics(
        self, records=None, filters=None, quiz_results=None, trend_freq="M"
    ):
        cleaned, cleaning_report = self.clean_data(records)
        filtered = self.apply_filters(cleaned, filters)
        kpis = self.calculate_metrics(filtered)
        quiz_metrics = self._quiz_metrics(quiz_results)
        empty_message = ""
        if filtered.empty:
            empty_message = "No incidents match the selected filters."
        return {
            "kpis": kpis,
            "by_category": self.group_by_category(filtered),
            "by_status": self.group_by_status(filtered),
            "by_severity": self.group_by_severity(filtered),
            "trend": self.analyze_trends(filtered, freq=trend_freq),
            "recurring_categories": self.group_by_category(filtered),
            "quiz": quiz_metrics,
            "insights": self._insights(filtered, kpis, quiz_metrics),
            "is_empty": bool(filtered.empty),
            "message": empty_message,
            "cleaning_report": cleaning_report,
            "filters_applied": filters or {},
            "filtered_incidents": filtered,
        }

    def export_summary(self, metrics, path):
        kpis = metrics["kpis"]
        rows = [
            {"metric": "total_incidents", "value": kpis["total_incidents"]},
            {"metric": "unresolved_incidents", "value": kpis["unresolved_incidents"]},
            {"metric": "unresolved_percent", "value": kpis["unresolved_percent"]},
            {"metric": "average_review_hours", "value": kpis["average_review_hours"]},
            {
                "metric": "reviewed_with_timestamp",
                "value": kpis["reviewed_with_timestamp"],
            },
            {
                "metric": "average_quiz_score",
                "value": metrics["quiz"]["average_quiz_score"],
            },
        ]
        _atomic_write_csv(pd.DataFrame(rows), path)
        return Path(path)
