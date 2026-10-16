from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from algorithms.search_and_sort import (
    IncidentIndex,
    binary_search,
    find_duplicate_ids,
    get_sorted_ids,
    quick_sort,
    sequential_search,
    sort_incidents,
)
from algorithms.review_queue import ActionStack, build_review_queue, select_next_report
from analytics.dashboard import IncidentAnalyzer
from analytics.data_files import DataRepository, QUIZ_STAGES, format_app_datetime
from auth.users import (
    get_current_user,
    is_admin,
    is_authenticated,
    login_session,
    login_user,
    register_user,
    require_admin,
    require_login,
)
from awareness.articles_and_quiz import ArticleService, QuizService
from core.incident import (
    AFFECTED_SCOPES,
    CATEGORIES,
    SEVERITY_LEVELS,
    STATUS_TRANSITIONS,
    STATUSES,
    URGENCY_LEVELS,
)
from services.startup import (
    PARTICIPANT_CODE,
    articles_as_objects,
    ids_for_user,
    load_manager,
    next_article_id,
    next_question_id,
    next_result_id,
    prepare_data,
    questions_as_objects,
    remember_owner,
    save_manager,
)

def login():
    prepare_data()

    st.title("Login")

    if is_authenticated():
        st.success("You are already logged in.")
        st.stop()

    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    if submitted:
        if not email.strip() or not password:
            st.error("Enter your email and password.")
        else:
            user = login_user(email, password)
            if user is None:
                st.error("Invalid email or password.")
            else:
                login_session(user)
                st.success("Welcome, " + user["username"] + ". Role: " + user["role"] + ".")
                st.rerun()

def register():
    prepare_data()

    st.title("Register")
    st.write("New accounts are regular users. Admin access is not granted here.")

    if is_authenticated():
        st.success("You are already logged in.")
        st.stop()

    with st.form("register_form"):
        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Create account")

    if submitted:
        if password != confirm:
            st.error("The two passwords do not match.")
        else:
            try:
                register_user(username, email, password)
                user = login_user(email, password)
            except ValueError as error:
                st.error(str(error))
            else:
                login_session(user)
                st.success("Account created. Role: " + user["role"] + ".")
                st.rerun()

def home():
    require_login()
    user = get_current_user()
    repository = prepare_data()

    st.title("CyberAware")
    st.write("Signed in as " + user["username"] + " (" + user["role"] + ").")

    if is_admin():
        analyzer = IncidentAnalyzer(repository)
        metrics = analyzer.get_dashboard_metrics(
            repository.load_incidents(),
            quiz_results=repository.load_quiz_results(),
        )
        kpis = metrics["kpis"]
        column_1, column_2, column_3, column_4 = st.columns(4)
        column_1.metric("Reports", kpis["total_incidents"])
        column_2.metric("Unresolved", kpis["unresolved_incidents"])
        column_3.metric("Unresolved %", kpis["unresolved_percent"])
        column_4.metric("Avg. hours to review", kpis["average_review_hours"])
        st.write(
            "Review changes report status. Dashboard is the full summary. "
            "Both are admin pages."
        )
    else:
        owned = ids_for_user(user["user_id"])
        st.metric("Your reports", len(owned))
        st.write(
            "You can submit a report, read the awareness notes, take the quiz, "
            "and open your dashboard. Status changes and the full dashboard are admin-only."
        )

    st.info(
        "Priority scores order the review. They do not confirm that an attack happened. "
        "The bundled reports are simulated."
    )

def report():
    require_login()
    repository = prepare_data()

    st.title("Report an Incident")
    st.write("Describe what you saw. The report is saved as Submitted.")

    with st.form("incident_form"):
        category = st.selectbox("Category", CATEGORIES)
        description = st.text_area(
            "What happened?",
            placeholder="Describe the suspicious activity. Do not include passwords.",
        )
        left, right = st.columns(2)
        with left:
            severity = st.selectbox("Severity", SEVERITY_LEVELS)
            urgency = st.selectbox("Urgency", URGENCY_LEVELS)
        with right:
            affected_scope = st.selectbox("Affected scope", AFFECTED_SCOPES)
        submitted = st.form_submit_button("Submit report")

    if submitted:
        try:
            manager = load_manager(repository)
            incident = manager.add_incident(
                {
                    "category": category,
                    "description": description,
                    "severity": severity,
                    "urgency": urgency,
                    "affected_scope": affected_scope,
                }
            )
            save_manager(manager, repository)
            remember_owner(incident.incident_id, get_current_user()["user_id"])
        except ValueError as error:
            st.error(str(error))
        else:
            st.success("Report saved.")
            st.write("Incident ID:", incident.incident_id)
            st.write("Priority score:", incident.priority_score)
            st.write("Status:", incident.status)
            st.warning(
                "This score helps decide which submitted report to review first. "
                "It is not a confirmation of an attack."
            )

def mine():
    require_login()
    user = get_current_user()
    manager = load_manager(prepare_data())
    owned_ids = ids_for_user(user["user_id"])
    rows = [
        incident.to_dict()
        for incident in manager.incidents
        if incident.incident_id in owned_ids
    ]

    st.title("My Reports")
    st.write("These are the reports submitted from this account.")

    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else:
        st.info("You have not submitted a report yet.")

def review():
    require_admin()

    repository = prepare_data()
    manager = load_manager(repository)

    st.title("Review Incidents")
    st.write(
        "Search uses the list, a sorted ID list, or the hash table. "
        "Sorting uses Quick Sort. The queue is arrival order. "
        "Greedy selection is the highest priority among submitted reports."
    )

    search_id = st.text_input("Incident ID")
    search_method = st.radio(
        "Search method",
        ["Sequential search", "Binary search", "Hash table lookup"],
        horizontal=True,
    )

    if st.button("Search"):
        try:
            if search_method == "Sequential search":
                found = sequential_search(manager.incidents, search_id)
            elif search_method == "Binary search":
                sorted_ids = get_sorted_ids(manager.incidents)
                exists, position = binary_search(sorted_ids, search_id)
                found = (
                    manager.find_incident(sorted_ids[position]) if exists else None
                )
            else:
                found = IncidentIndex(manager.incidents).find(search_id)
        except ValueError as error:
            st.error(str(error))
        else:
            if found is None:
                st.warning("No incident was found with this ID.")
            else:
                st.dataframe(
                    pd.DataFrame([found.to_dict()]),
                    width="stretch",
                    hide_index=True,
                )

    st.divider()
    st.subheader("All incidents")

    sort_labels = {
        "Priority": "priority",
        "Reported date": "date",
        "Severity": "severity",
        "Incident ID": "id",
    }
    sort_label = st.selectbox("Sort by", list(sort_labels))
    descending = st.checkbox("Descending", value=True)

    try:
        ordered = sort_incidents(
            manager.incidents,
            sort_labels[sort_label],
            descending,
        )
    except ValueError as error:
        st.error(str(error))
        ordered = []
    else:
        st.session_state["sort_stats"] = dict(quick_sort.last_stats)
        st.dataframe(
            pd.DataFrame([incident.to_dict() for incident in ordered]),
            width="stretch",
            hide_index=True,
        )
        stats = st.session_state["sort_stats"]
        stat_1, stat_2, stat_3 = st.columns(3)
        stat_1.metric("Quick Sort comparisons", stats["comparisons"])
        stat_2.metric("Quick Sort swaps", stats["swaps"])
        stat_3.metric("Quick Sort recursive calls", stats["recursive_calls"])

    duplicates = find_duplicate_ids(manager.incidents)
    if duplicates:
        st.error("Duplicate IDs: " + ", ".join(duplicates))

    st.divider()
    st.subheader("Update status")

    if ordered:
        selected_id = st.selectbox(
            "Incident",
            [incident.incident_id for incident in ordered],
        )
        selected = manager.find_incident(selected_id)
        allowed = STATUS_TRANSITIONS.get(selected.status, ())
        st.write("Current status:", selected.status)

        if not allowed:
            st.info("A closed incident cannot change status.")
        else:
            new_status = st.selectbox("New status", allowed)
            note = st.text_input("Note")
            resolution = ""
            if new_status == "Resolved":
                resolution = st.text_area("Resolution")
            if st.button("Save status"):
                try:
                    manager.update_status(
                        selected_id,
                        new_status,
                        note=note,
                        resolution=resolution,
                    )
                    save_manager(manager, repository)
                except ValueError as error:
                    st.error(str(error))
                else:
                    st.success(selected_id + " is now " + new_status + ".")
                    st.rerun()

    st.divider()
    left, right = st.columns(2)

    with left:
        st.subheader("Submitted queue")
        st.caption("First in, first out. Oldest submitted report leaves first.")
        queue = build_review_queue(manager.incidents)
        st.write("Waiting:", queue.size())
        waiting = queue.to_list()
        if waiting:
            st.dataframe(
                pd.DataFrame([incident.to_dict() for incident in waiting[:15]]),
                width="stretch",
                hide_index=True,
            )
        if st.button("Review oldest submitted report"):
            chosen = queue.peek()
            if chosen is None:
                st.info("The queue is empty.")
            else:
                try:
                    manager.update_status(
                        chosen.incident_id,
                        "Under Review",
                        note="Taken from the arrival queue.",
                    )
                    save_manager(manager, repository)
                except ValueError as error:
                    st.error(str(error))
                else:
                    st.success(chosen.incident_id + " moved to Under Review.")
                    st.rerun()

    with right:
        st.subheader("Greedy next report")
        st.caption("Highest priority, then older report, then smaller ID.")
        chosen = select_next_report(manager.incidents)
        if chosen is None:
            st.info("There is no submitted report.")
        else:
            st.write(chosen.incident_id)
            st.write("Priority:", chosen.priority_score)
            st.write("Reported:", chosen.reported_at)
        if st.button("Review highest-priority report"):
            if chosen is None:
                st.info("There is no submitted report.")
            else:
                try:
                    manager.update_status(
                        chosen.incident_id,
                        "Under Review",
                        note="Selected by greedy priority.",
                    )
                    save_manager(manager, repository)
                except ValueError as error:
                    st.error(str(error))
                else:
                    st.success(chosen.incident_id + " moved to Under Review.")
                    st.rerun()

    st.divider()
    st.subheader("Latest actions")
    recent = ActionStack(manager.actions).recent(8)
    if recent:
        st.dataframe(pd.DataFrame(recent), width="stretch", hide_index=True)
    else:
        st.info("No review actions have been recorded yet.")

def learn():
    require_login()
    repository = prepare_data()
    service = ArticleService(articles_as_objects(repository.load_articles()))
    articles = service.get_all_articles()

    st.title("Awareness")
    if is_admin():
        st.write("Add a note. It is stored in the articles JSON file.")
        with st.form("add_article"):
            title = st.text_input("Title")
            category_new = st.selectbox("Category", CATEGORIES)
            summary = st.text_area("Summary")
            content = st.text_area("Content")
            source_name = st.text_input("Source name")
            source_url = st.text_input("Source URL")
            saved_article = st.form_submit_button("Save article")
        if saved_article:
            if not title.strip() or not summary.strip() or not content.strip():
                st.error("Title, summary, and content are required.")
            else:
                records = repository.load_articles()
                records.append(
                    {
                        "article_id": next_article_id(records),
                        "title": title.strip(),
                        "category": category_new,
                        "summary": summary.strip(),
                        "content": content.strip(),
                        "source_name": source_name.strip(),
                        "source_url": source_url.strip(),
                        "published_at": str(datetime.now().date()),
                    }
                )
                repository.save_articles(records)
                st.success("Article saved.")
                st.rerun()
        st.divider()
        st.write("Saved notes")
    else:
        st.write("Short guidance for the same categories used on incident reports.")

    categories = ["All"] + sorted({article.category for article in articles})
    category = st.selectbox("Category", categories, key="article_filter")
    keyword = st.text_input("Search")

    if keyword.strip():
        displayed = service.search_articles(keyword.strip())
        if category != "All":
            displayed = [
                article for article in displayed if article.category == category
            ]
    else:
        displayed = service.get_by_category(category)

    if not displayed:
        st.info("No articles match this filter.")

    for article in displayed:
        with st.expander(article.label()):
            st.caption(article.category)
            st.write(article.summary)
            st.write(article.content)
            if article.source_name:
                st.caption("Source: " + article.source_name)

def quiz():
    require_login()
    repository = prepare_data()
    records = repository.load_quiz_questions()

    if is_admin():
        st.title("Quiz questions")
        st.write("Add a question. It is stored in the quiz JSON file.")
        with st.form("add_question"):
            topic = st.selectbox("Topic", CATEGORIES)
            question_text = st.text_area("Question")
            option_1 = st.text_input("Option 1")
            option_2 = st.text_input("Option 2")
            option_3 = st.text_input("Option 3")
            option_4 = st.text_input("Option 4")
            correct_label = st.selectbox(
                "Correct option",
                ["Option 1", "Option 2", "Option 3", "Option 4"],
            )
            explanation = st.text_area("Explanation")
            saved_question = st.form_submit_button("Save question")
        if saved_question:
            options = [
                option_1.strip(),
                option_2.strip(),
                option_3.strip(),
                option_4.strip(),
            ]
            correct_text = options[int(correct_label[-1]) - 1]
            if not question_text.strip():
                st.error("The question is required.")
            elif any(option == "" for option in options):
                st.error("Enter all four options.")
            elif len(set(options)) != 4:
                st.error("The four options must be different.")
            else:
                records.append(
                    {
                        "question_id": next_question_id(records),
                        "topic": topic,
                        "question": question_text.strip(),
                        "options": options,
                        "correct_option": correct_text,
                        "explanation": explanation.strip(),
                    }
                )
                repository.save_quiz_questions(records)
                st.success("Question saved.")
                st.rerun()
        st.subheader("Saved questions")
        if records:
            st.dataframe(pd.DataFrame(records), width="stretch", hide_index=True)
        else:
            st.info("No quiz questions are stored yet.")
        return

    questions = questions_as_objects(records)
    service = QuizService(questions)

    st.title("Awareness Quiz")
    st.write(
        "The score is saved as a pre-training or post-training attempt. "
        "It does not measure whether incidents decreased."
    )

    if not questions:
        st.warning("No quiz questions are available.")
        st.stop()

    with st.form("quiz_form"):
        participant_code = st.text_input("Participant code")
        quiz_stage = st.selectbox("Stage", QUIZ_STAGES)
        answers = {}
        for question in questions:
            st.write("**" + question.label() + "**")
            answers[question.question_id] = st.radio(
                "Answer",
                question.options,
                key=question.question_id,
                index=None,
            )
        submitted = st.form_submit_button("Submit quiz")

    if submitted:
        if PARTICIPANT_CODE.fullmatch(participant_code.strip()) is None:
            st.error("Participant code must be 2 to 20 letters, numbers, or hyphens.")
        elif any(answer is None for answer in answers.values()):
            st.error("Answer every question.")
        else:
            graded = service.calculate_score(answers)
            saved = repository.load_quiz_results()
            record = {
                "result_id": next_result_id(saved),
                "participant_code": participant_code.strip(),
                "quiz_stage": quiz_stage,
                "quiz_date": format_app_datetime(
                    datetime.now().replace(second=0, microsecond=0)
                ),
                "score": graded["score"],
                "total_questions": graded["total_questions"],
            }
            saved.append(record)
            repository.save_quiz_results(saved)
            st.success("Quiz saved as " + record["result_id"] + ".")
            st.metric(
                "Score",
                str(graded["score"]) + " / " + str(graded["total_questions"]),
            )
            st.write("Percentage:", round(graded["percentage"], 2))
            with st.expander("Review"):
                for item in graded["feedback"]:
                    st.write("**" + item["question"] + "**")
                    if item["is_correct"]:
                        st.write("Correct.")
                    else:
                        st.write("Your answer: " + str(item["user_answer"]))
                        st.write("Correct answer: " + str(item["correct_option"]))
                    if item["explanation"]:
                        st.caption(item["explanation"])

def user_board():
    require_login()
    user = get_current_user()
    if is_admin():
        st.error("Open Dashboard for the full summary.")
        st.stop()

    manager = load_manager(prepare_data())
    owned_ids = ids_for_user(user["user_id"])
    rows = [
        incident.to_dict()
        for incident in manager.incidents
        if incident.incident_id in owned_ids
    ]

    st.title("My Dashboard")
    st.write("Counts cover reports submitted from this account.")

    frame = pd.DataFrame(rows)
    total = len(rows)
    status_counts = {status: 0 for status in STATUSES}
    if total:
        for status, count in frame["status"].value_counts().items():
            status_counts[status] = int(count)

    metric_1, metric_2, metric_3, metric_4 = st.columns(4)
    metric_1.metric("Your reports", total)
    metric_2.metric("Submitted", status_counts.get("Submitted", 0))
    metric_3.metric("Under Review", status_counts.get("Under Review", 0))
    metric_4.metric("Resolved", status_counts.get("Resolved", 0))

    if frame.empty:
        st.info("You have not submitted a report yet.")
        return

    category_tab, status_tab, severity_tab = st.tabs(
        ["Category", "Status", "Severity"]
    )
    with category_tab:
        by_category = (
            frame.groupby("category").size().reset_index(name="count")
        )
        st.bar_chart(by_category, x="category", y="count")
    with status_tab:
        by_status = frame.groupby("status").size().reset_index(name="count")
        st.bar_chart(by_status, x="status", y="count")
    with severity_tab:
        by_severity = (
            frame.groupby("severity").size().reset_index(name="count")
        )
        st.bar_chart(by_severity, x="severity", y="count")

    st.subheader("Your reports")
    st.dataframe(frame, width="stretch", hide_index=True)


def board():
    require_admin()

    repository = prepare_data()
    analyzer = IncidentAnalyzer(repository)

    st.title("Dashboard")
    st.write(
        "Figures describe saved reports after cleaning. "
        "They do not prove that an attack occurred."
    )

    st.sidebar.subheader("Filters")
    date_from = st.sidebar.text_input("From (DD/MM/YYYY)", "")
    date_to = st.sidebar.text_input("To (DD/MM/YYYY)", "")
    categories = st.sidebar.multiselect("Categories", CATEGORIES, default=list(CATEGORIES))
    statuses = st.sidebar.multiselect("Statuses", STATUSES, default=list(STATUSES))
    severities = st.sidebar.multiselect(
        "Severities", SEVERITY_LEVELS, default=list(SEVERITY_LEVELS)
    )
    trend_label = st.sidebar.radio("Trend", ["Month", "Week", "Day"], horizontal=True)
    trend_freq = {"Month": "M", "Week": "W", "Day": "D"}[trend_label]

    filters = {
        "date_from": date_from.strip() or None,
        "date_to": date_to.strip() or None,
        "categories": categories,
        "statuses": statuses,
        "severities": severities,
    }

    try:
        metrics = analyzer.get_dashboard_metrics(
            repository.load_incidents(),
            filters=filters,
            quiz_results=repository.load_quiz_results(),
            trend_freq=trend_freq,
        )
    except ValueError as error:
        st.error(str(error))
        st.stop()

    kpis = metrics["kpis"]
    quiz = metrics["quiz"]

    metric_1, metric_2, metric_3 = st.columns(3)
    metric_1.metric("Reports", kpis["total_incidents"])
    metric_2.metric("Unresolved", kpis["unresolved_incidents"])
    metric_3.metric("Unresolved %", kpis["unresolved_percent"])

    metric_4, metric_5, metric_6 = st.columns(3)
    metric_4.metric("Avg. hours to review", kpis["average_review_hours"])
    metric_5.metric("Quiz average %", quiz["average_quiz_score"])
    metric_6.metric("Quiz attempts", quiz["attempts"])

    st.subheader("Insights")
    for line in metrics["insights"]:
        st.write("- " + line)

    if metrics["is_empty"]:
        st.info(metrics["message"])
        st.stop()

    category_tab, status_tab, severity_tab, trend_tab, matrix_tab = st.tabs(
        ["Category", "Status", "Severity", "Trend", "Category by severity"]
    )

    with category_tab:
        st.bar_chart(metrics["by_category"], x="category", y="count")
    with status_tab:
        st.bar_chart(metrics["by_status"], x="status", y="count")
    with severity_tab:
        st.bar_chart(metrics["by_severity"], x="severity", y="count")
    with trend_tab:
        st.line_chart(metrics["trend"], x="period", y="count")
    with matrix_tab:
        filtered = metrics["filtered_incidents"]
        nested = {}
        for _, row in filtered.iterrows():
            nested.setdefault(row["category"], {})
            bucket = nested[row["category"]]
            bucket[row["severity"]] = bucket.get(row["severity"], 0) + 1
        matrix = (
            pd.DataFrame(nested)
            .reindex(list(SEVERITY_LEVELS))
            .fillna(0)
            .astype(int)
            .T
        )
        st.dataframe(matrix, width="stretch")
        st.caption(
            "Each cell is a count. The structure is a dictionary of dictionaries: "
            "category, then severity."
        )

    st.subheader("Filtered reports")
    st.dataframe(metrics["filtered_incidents"], width="stretch", hide_index=True)

    if not quiz["by_stage"].empty:
        st.subheader("Quiz by stage")
        st.bar_chart(quiz["by_stage"], x="quiz_stage", y="average_score")

    summary_path = Path(repository.data_dir) / "dashboard_summary.csv"
    if st.button("Export summary CSV"):
        analyzer.export_summary(metrics, summary_path)
        st.session_state["summary_ready"] = str(summary_path)

    if st.session_state.get("summary_ready"):
        exported = Path(st.session_state["summary_ready"])
        if exported.exists():
            st.download_button(
                "Download summary",
                exported.read_bytes(),
                file_name="dashboard_summary.csv",
            )

    with st.expander("Cleaning report for the loaded file"):
        st.json(metrics["cleaning_report"])
        dirty_path = DataRepository(repository.data_dir).data_dir / "dirty_incidents.csv"
        if dirty_path.exists():
            dirty_frame, dirty_report = analyzer.clean_data(
                DataRepository(repository.data_dir).load_incidents(dirty_path)
            )
            st.write("Dirty sample rows in:", dirty_report["rows_in"])
            st.write("Dirty sample rows kept:", dirty_report["rows_out"])
            st.dataframe(dirty_frame, width="stretch", hide_index=True)
