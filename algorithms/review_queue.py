from algorithms.search_and_sort import _check_incident, _check_incidents, get_sort_key, sort_incidents
from core.incident import ACTION_FIELDS
from data_structures.queue_stack_hash import Queue, Stack


PENDING_STATUSES = ("Submitted",)


class ReviewQueue:
    def __init__(self, incidents=None):
        self._items = Queue()
        self._ids = set()

        if incidents is not None:
            _check_incidents(incidents)

            for incident in incidents:
                self.enqueue(incident)

    def enqueue(self, incident):
        _check_incident(incident)

        if incident.incident_id in self._ids:
            raise ValueError(
                "Incident is already in the queue: " + incident.incident_id
            )

        self._items.enqueue(incident)
        self._ids.add(incident.incident_id)

    def dequeue(self):
        incident = self._items.dequeue()
        if incident is None:
            return None

        self._ids.remove(incident.incident_id)
        return incident

    def peek(self):
        return self._items.peek()

    def is_empty(self):
        return self._items.is_empty()

    def size(self):
        return self._items.size()

    def to_list(self):
        return self._items.get_items()

def get_pending_incidents(incidents):
    _check_incidents(incidents)

    pending = []

    for incident in incidents:
        _check_incident(incident)

        if incident.status in PENDING_STATUSES:
            pending.append(incident)

    return pending

def build_review_queue(incidents):
    pending = get_pending_incidents(incidents)
    arrival_order = sort_incidents(pending, "date", descending=False)

    return ReviewQueue(arrival_order)


class ActionStack:
    def __init__(self, actions=None):
        self._items = Stack()

        if actions is not None:
            if not isinstance(actions, (list, tuple)):
                raise ValueError("Actions must be a list.")

            for action in actions:
                self.push(action)

    def push(self, action):
        if not isinstance(action, dict):
            raise ValueError("Each action must be a dictionary.")

        for field in ACTION_FIELDS:
            if field not in action:
                raise ValueError("Missing action field: " + field)

        self._items.push(action)

    def pop(self):
        return self._items.pop()

    def peek(self):
        return self._items.peek()

    def is_empty(self):
        return self._items.is_empty()

    def size(self):
        return self._items.size()

    def to_list(self):
        return self._items.get_items()[::-1]

    def recent(self, count):
        if type(count) is not int or count < 0:
            raise ValueError("Count must be a whole number, 0 or more.")

        return self.to_list()[:count]


def select_next_report(incidents):
    best = None
    best_key = None

    for incident in get_pending_incidents(incidents):
        key = get_sort_key(incident, "priority", True)

        if best is None or key < best_key:
            best = incident
            best_key = key

    return best
