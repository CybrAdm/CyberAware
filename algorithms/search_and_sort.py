from datetime import datetime

from core.incident import SEVERITY_LEVELS, Incident
from data_structures.queue_stack_hash import HashTable


def _check_incidents(incidents):
    if not isinstance(incidents, (list, tuple)):
        raise ValueError("Incidents must be a list.")


def _check_incident(incident):
    if not isinstance(incident, Incident):
        raise ValueError("Each incident must be an Incident object.")


DATE_FORMAT = "%d/%m/%Y %I:%M %p"
EPOCH = datetime(1970, 1, 1)


def incident_number(incident_id):
    if (
        not isinstance(incident_id, str)
        or not incident_id.startswith("INC-")
        or not incident_id[4:].isdecimal()
    ):
        raise ValueError("Incident ID must look like INC-1001.")

    return int(incident_id[4:])

def date_to_number(value):
    try:
        parsed = datetime.strptime(value, DATE_FORMAT)
    except (TypeError, ValueError):
        raise ValueError(
            "Date and time must use DD/MM/YYYY HH:MM AM/PM format."
        )

    return int((parsed - EPOCH).total_seconds())


SORT_FIELDS = ("priority", "date", "severity", "id")


def _partition(pairs, low, high, stats):
    middle = (low + high) // 2
    pairs[middle], pairs[high] = pairs[high], pairs[middle]
    stats["swaps"] += 1
    pivot = pairs[high][0]

    border = low

    for index in range(low, high):
        stats["comparisons"] += 1
        if pairs[index][0] < pivot:
            pairs[index], pairs[border] = pairs[border], pairs[index]
            stats["swaps"] += 1
            border += 1

    pairs[border], pairs[high] = pairs[high], pairs[border]
    stats["swaps"] += 1
    return border


def _quick_sort(pairs, low, high, stats):
    stats["recursive_calls"] += 1
    while low < high:
        pivot_index = _partition(pairs, low, high, stats)

        if pivot_index - low < high - pivot_index:
            _quick_sort(pairs, low, pivot_index - 1, stats)
            low = pivot_index + 1
        else:
            _quick_sort(pairs, pivot_index + 1, high, stats)
            high = pivot_index - 1

def quick_sort(items, key):
    if not isinstance(items, (list, tuple)):
        raise ValueError("Items must be a list.")

    if not callable(key):
        raise ValueError("Key must be a function.")

    pairs = [(key(item), item) for item in items]
    stats = {"comparisons": 0, "swaps": 0, "recursive_calls": 0}
    _quick_sort(pairs, 0, len(pairs) - 1, stats)
    quick_sort.last_stats = stats

    return [item for _, item in pairs]


quick_sort.last_stats = {"comparisons": 0, "swaps": 0, "recursive_calls": 0}

def get_sort_key(incident, sort_by, descending=True):
    _check_incident(incident)

    if sort_by not in SORT_FIELDS:
        raise ValueError("Choose a valid sort field.")

    id_number = incident_number(incident.incident_id)
    date_number = date_to_number(incident.reported_at)

    if sort_by == "priority":
        if type(incident.priority_score) is not int:
            raise ValueError("Priority score must be a whole number.")

        main_value = incident.priority_score
    elif sort_by == "severity":
        if incident.severity not in SEVERITY_LEVELS:
            raise ValueError("Choose a valid severity.")

        main_value = SEVERITY_LEVELS.index(incident.severity)
    elif sort_by == "date":
        main_value = date_number
    else:
        main_value = id_number

    if descending:
        main_value = -main_value

    return (main_value, date_number, id_number)


def sort_incidents(incidents, sort_by="priority", descending=True):
    _check_incidents(incidents)

    if sort_by not in SORT_FIELDS:
        raise ValueError("Choose a valid sort field.")

    if not isinstance(descending, bool):
        raise ValueError("Descending must be True or False.")

    return quick_sort(
        incidents,
        lambda incident: get_sort_key(incident, sort_by, descending),
    )

def get_sorted_ids(incidents):
    _check_incidents(incidents)

    ids = []

    for incident in incidents:
        _check_incident(incident)
        ids.append(incident.incident_id)

    return quick_sort(ids, incident_number)


def sequential_search(incidents, incident_id):
    _check_incidents(incidents)

    if not isinstance(incident_id, str) or not incident_id.strip():
        return None

    incident_id = incident_id.strip()

    for incident in incidents:
        _check_incident(incident)

        if incident.incident_id == incident_id:
            return incident

    return None

def binary_search(sorted_ids, target_id):
    if not isinstance(sorted_ids, (list, tuple)):
        raise ValueError("Sorted IDs must be a list.")

    if not isinstance(target_id, str):
        raise ValueError("Incident ID must look like INC-1001.")

    target = incident_number(target_id.strip())

    low = 0
    high = len(sorted_ids) - 1

    while low <= high:
        middle = (low + high) // 2
        current = incident_number(sorted_ids[middle])

        if current == target:
            return True, middle

        if current < target:
            low = middle + 1
        else:
            high = middle - 1

    return False, low


def find_duplicate_ids(incidents):
    _check_incidents(incidents)

    seen = set()
    duplicates = []

    for incident in incidents:
        _check_incident(incident)

        if incident.incident_id in seen:
            if incident.incident_id not in duplicates:
                duplicates.append(incident.incident_id)
        else:
            seen.add(incident.incident_id)

    return duplicates


class IncidentIndex:
    def __init__(self, incidents=None):
        self.lookup = HashTable()

        if incidents is not None:
            _check_incidents(incidents)

            for incident in incidents:
                self.add(incident)

    def add(self, incident):
        _check_incident(incident)

        if self.lookup.search(incident.incident_id) is not None:
            raise ValueError(
                "Duplicate incident ID: " + incident.incident_id
            )

        self.lookup.insert(incident.incident_id, incident)

    def find(self, incident_id):
        if not isinstance(incident_id, str) or not incident_id.strip():
            return None

        return self.lookup.search(incident_id.strip())

    def size(self):
        return self.lookup.size()
