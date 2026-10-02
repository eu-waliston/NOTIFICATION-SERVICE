import threading
import time
from collections import defaultdict, deque

from fastapi import Depends

from app.core.config import get_settings
from app.core.exceptions import TooManyRequests
from app.core.security import get_current_client
from app.models.user import ApiClient

_mem: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def _hits_last_minute(client_id: str) -> int:
    """Registra uma chamada e retorna quantas houve no último minuto.
    Redis (quando configurado) compartilha o contador entre instâncias; senão, memória local."""
    from app.queue import get_redis

    r = get_redis()
    if r is not None:
        key = f"rl:{client_id}:{int(time.time() // 60)}"
        n = r.incr(key)
        if n == 1:
            r.expire(key, 120)
        return int(n)
    now = time.time()
    with _lock:
        q = _mem[client_id]
        while q and q[0] <= now - 60:
            q.popleft()
        q.append(now)
        return len(q)


def rate_limited_client(client: ApiClient = Depends(get_current_client)) -> ApiClient:
    limit = client.rate_limit_per_minute
    if limit is None:
        limit = get_settings().rate_limit_per_minute
    if limit and _hits_last_minute(client.id) > limit:
        raise TooManyRequests(
            f"Limite de {limit} requisições por minuto excedido para '{client.name}'.",
            headers={"Retry-After": "60"},
        )
    return client
