# CyberAware

CyberAware is a Streamlit application for reporting suspicious cyber activity, reviewing those reports, reading short guidance, and summarizing the saved records.

The bundled incidents, actions, and quiz attempts are simulated. A priority score orders review. It does not confirm that an attack happened.

## Users

- A regular account reports incidents, reads the awareness notes, takes the quiz, and sees only its own reports.
- An admin does that work and also reviews every report and opens the dashboard.
- Registration always creates a regular user. The first empty user file creates one admin.

Local demo admin: `admin@cyberaware.local` / `Admin@12345`

## Run

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The first launch writes a 24-row simulated dataset under `data/` if `data/incidents.csv` is missing. Later reports and quiz attempts are added to those files.

## Tests

```bash
python -m unittest -v tests.test_algorithms tests.test_analytics tests.test_users_and_structures
```

## Data structures

- List: the incident records and sorted results.
- Dictionary: action records, quiz answers, and the category-by-severity counts on the dashboard.
- Set: duplicate incident IDs, and IDs already inside the review queue.
- Queue: `data_structures/queue_stack_hash.py` has a plain FIFO queue. `ReviewQueue` uses it for Submitted reports, oldest first.
- Stack: the same file has a plain LIFO stack. `ActionStack` uses it to show the latest review actions first.
- Hash table: `IncidentIndex` stores incidents in the hand-written hash table in that file. Built-in `dict` is not the lookup used by the index.
- 2D structure: the dashboard matrix is a dictionary of dictionaries, category then severity.

## Algorithms

- Sequential search walks the unsorted incident list. Use it when the list is not ordered.
- Binary search runs only on IDs already sorted by incident number.
- Quick Sort orders the table by priority, date, severity, or ID. The middle element is the pivot. The review page shows comparisons, swaps, and recursive calls for the last sort.
- Greedy selection picks the Submitted report with the highest priority, then the older report, then the smaller ID. It looks at the current list only, which matches a reviewer who must choose the next report now.

Dates are stored as `DD/MM/YYYY HH:MM AM/PM` and compared as dates, not as text.

## Files

- `core/incident.py`: incident rules, the record, and status changes.
- `algorithms/search_and_sort.py`: search, Quick Sort, and the hash index.
- `algorithms/review_queue.py`: the review queue, the action stack, and greedy choice.
- `data_structures/queue_stack_hash.py`: plain queue, plain stack, and the hash table.
- `analytics/data_files.py`: file storage and cleaning helpers.
- `analytics/dashboard.py`: Pandas metrics.
- `analytics/synthetic_data.py`: the simulated dataset.
- `awareness/articles_and_quiz.py` and `awareness/starter_content.py`: articles, quiz, and the seeded text.
- `auth/users.py`: passwords, registration, login, and the admin check.
- `services/startup.py`: startup and report ownership.
- `ui/pages.py`: Streamlit screens. `app.py` shows a different menu for a user and an admin.
- `tests/`: automated checks.
- `docs/`: the original member notes.

Map view, deployment, and an in-app AI feature are not included.
