import json
import re
from pathlib import Path

from analytics.synthetic_data import generate_and_save_synthetic_dataset
from analytics.data_files import DATA_DIR, DataRepository, incidents_from_records
from auth.users import seed_admin
from awareness.articles_and_quiz import Article, ArticleService, QuizQuestion
from awareness.starter_content import ARTICLES, QUIZ_QUESTIONS
from core.incident import IncidentManager

def owners_path(path=None):
    if path is None:
        return DATA_DIR / "owners.json"
    return Path(path)


def load_owners(path=None):
    target = owners_path(path)
    if not target.exists():
        return []
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    return data


def save_owners(rows, path=None):
    target = owners_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    temporary.replace(target)


def remember_owner(incident_id, user_id, path=None):
    rows = load_owners(path)
    rows.append({"incident_id": incident_id, "user_id": user_id})
    save_owners(rows, path)


def ids_for_user(user_id, path=None):
    return {
        row.get("incident_id")
        for row in load_owners(path)
        if row.get("user_id") == user_id
    }


PARTICIPANT_CODE = re.compile(r"^[A-Za-z0-9-]{2,20}$")


def prepare_data():
    repository = DataRepository()
    if not repository.incidents_path.exists():
        generate_and_save_synthetic_dataset(repository.data_dir)

    if not repository.load_articles():
        repository.save_articles(ARTICLES)

    if not repository.load_quiz_questions():
        repository.save_quiz_questions(QUIZ_QUESTIONS)

    seed_admin()
    return repository


def load_manager(repository=None):
    repository = repository or DataRepository()
    return IncidentManager(
        incidents_from_records(repository.load_incidents()),
        repository.load_actions(),
    )


def save_manager(manager, repository=None):
    repository = repository or DataRepository()
    repository.save_incidents(manager.incidents)
    repository.save_actions(manager.actions)
    return repository


def articles_as_objects(records):
    return [Article(**record) for record in records]


def questions_as_objects(records):
    questions = []
    for record in records:
        options = record.get("options", [])
        if isinstance(options, str):
            options = [options]
        questions.append(
            QuizQuestion(
                question_id=record["question_id"],
                topic=record.get("topic", ""),
                question=record["question"],
                options=list(options),
                correct_option=record["correct_option"],
                explanation=record.get("explanation", ""),
            )
        )
    return questions


def next_result_id(results):
    highest = 0
    for result in results:
        result_id = str(result.get("result_id", ""))
        if result_id.startswith("RES-") and result_id[4:].isdigit():
            highest = max(highest, int(result_id[4:]))
    return "RES-" + str(highest + 1).zfill(4)


def next_article_id(articles):
    highest = 0
    for article in articles:
        article_id = str(article.get("article_id", ""))
        if article_id.startswith("ART-") and article_id[4:].isdigit():
            highest = max(highest, int(article_id[4:]))
    return "ART-" + str(highest + 1).zfill(3)


def next_question_id(questions):
    highest = 0
    for question in questions:
        question_id = str(question.get("question_id", ""))
        if question_id.startswith("Q") and question_id[1:].isdigit():
            highest = max(highest, int(question_id[1:]))
    return "Q" + str(highest + 1)


def article_service(repository):
    return ArticleService(articles_as_objects(repository.load_articles()))
