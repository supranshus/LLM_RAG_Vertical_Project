import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from app.rag.vectorstore.base import VectorStore
from app.repositories.health_repo import HealthRepository

logger = logging.getLogger(__name__)

# Shared so a hung vector store ping (e.g. a firewalled network) is reused by later health
# checks instead of piling up new threads.
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="health-ping")
_inflight: dict[int, Future[bool]] = {}
_inflight_lock = threading.Lock()


class HealthService:
    def __init__(
        self, repo: HealthRepository, vector_store: VectorStore, ping_timeout: float = 2.0
    ):
        self.repo = repo
        self.vector_store = vector_store
        self.ping_timeout = ping_timeout

    def check(self) -> dict[str, str]:
        database_ok = self._database_ok()
        return {
            "status": "ok" if database_ok else "degraded",
            "database": "ok" if database_ok else "error",
            # The vector store only affects document features, so it never degrades status.
            "vector_store": "ok" if self._vector_store_ok() else "error",
        }

    def _database_ok(self) -> bool:
        try:
            self.repo.ping()
            return True
        except Exception:
            logger.exception("Health check: database unreachable")
            return False

    def _vector_store_ok(self) -> bool:
        key = id(self.vector_store)
        with _inflight_lock:
            future = _inflight.get(key)
            if future is None or future.done():
                future = _executor.submit(self.vector_store.ping)
                _inflight[key] = future
        try:
            return bool(future.result(timeout=self.ping_timeout))
        except FutureTimeout:
            logger.warning(
                "Health check: vector store did not answer within %.0fs", self.ping_timeout
            )
            return False
        except Exception:
            return False
