from collections import defaultdict

from fastapi import BackgroundTasks

from app import queue


class FakeRedis:
    def __init__(self):
        self.lists, self.z, self.counters = defaultdict(list), {}, defaultdict(int)

    def rpush(self, k, v): self.lists[k].append(v)

    def blpop(self, keys, timeout=0):
        for k in keys:
            if self.lists[k]:
                return k, self.lists[k].pop(0)
        return None

    def zadd(self, k, m): self.z.update(m)
    def zrangebyscore(self, k, lo, hi): return [m for m, s in self.z.items() if lo <= s <= hi]
    def zrem(self, k, m): return 1 if self.z.pop(m, None) is not None else 0
    def incr(self, k): self.counters[k] += 1; return self.counters[k]
    def expire(self, k, s): pass


def test_priority_order():
    r = FakeRedis()
    for nid, p in [("l", "low"), ("n", "normal"), ("h", "high")]:
        queue.enqueue(r, nid, p)
    order = [r.blpop(queue.QUEUE_ORDER)[1] for _ in range(3)]
    assert order == ["h", "n", "l"]


def test_dispatch_uses_redis(monkeypatch):
    r = FakeRedis()
    monkeypatch.setattr(queue, "get_redis", lambda: r)
    queue.dispatch("abc", "high", BackgroundTasks())
    assert r.lists[queue.QUEUES["high"]] == ["abc"]


def test_retry_keeps_priority():
    r = FakeRedis()
    queue.schedule_retry(r, "x", -1, "high")
    queue.schedule_retry(r, "y", 3600, "low")  # ainda não venceu
    queue.promote_due(r)
    assert r.lists[queue.QUEUES["high"]] == ["x"] and not r.lists[queue.QUEUES["low"]]
    assert queue.priority_of_queue(queue.QUEUES["high"]) == "high"


def test_rate_limit_counter_uses_redis(monkeypatch):
    from app.core import rate_limit
    r = FakeRedis()
    monkeypatch.setattr(queue, "get_redis", lambda: r)
    assert [rate_limit._hits_last_minute("c1") for _ in range(3)] == [1, 2, 3]
