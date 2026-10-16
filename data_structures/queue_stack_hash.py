class Queue:
    def __init__(self):
        self._items = []

    def enqueue(self, item):
        self._items.append(item)

    def dequeue(self):
        if self.is_empty():
            return None
        return self._items.pop(0)

    def peek(self):
        if self.is_empty():
            return None
        return self._items[0]

    def is_empty(self):
        return len(self._items) == 0

    def size(self):
        return len(self._items)

    def get_items(self):
        return self._items.copy()


class Stack:
    def __init__(self):
        self._items = []

    def push(self, item):
        self._items.append(item)

    def pop(self):
        if self.is_empty():
            return None
        return self._items.pop()

    def peek(self):
        if self.is_empty():
            return None
        return self._items[-1]

    def is_empty(self):
        return len(self._items) == 0

    def size(self):
        return len(self._items)

    def get_items(self):
        return self._items.copy()


class HashTable:
    def __init__(self, capacity=256):
        if type(capacity) is not int or capacity < 1:
            raise ValueError("Hash table capacity must be a whole number above 0.")

        self.capacity = capacity
        self.buckets = [[] for _ in range(capacity)]
        self.count = 0

    def _index(self, key):
        total = 0
        for character in str(key):
            total = (total * 33 + ord(character)) % self.capacity
        return total

    def insert(self, key, value):
        bucket = self.buckets[self._index(key)]

        for item in bucket:
            if item[0] == key:
                item[1] = value
                return

        bucket.append([key, value])
        self.count += 1

    def search(self, key):
        for item in self.buckets[self._index(key)]:
            if item[0] == key:
                return item[1]

        return None

    def delete(self, key):
        bucket = self.buckets[self._index(key)]

        for position, item in enumerate(bucket):
            if item[0] == key:
                bucket.pop(position)
                self.count -= 1
                return True

        return False

    def size(self):
        return self.count

    def is_empty(self):
        return self.count == 0
