# src/db/log_handler.py
"""
Non-blocking PostgreSQL logging handler.
Uses a background daemon thread + queue so the main agent is never stalled by DB writes.
Add to any logger via: logger.addHandler(PostgreSQLLogHandler())
"""
import json
import logging
import queue
import threading
import traceback
from datetime import datetime, timezone


class PostgreSQLLogHandler(logging.Handler):
    """
    Logging handler that writes records to the system_logs table.
    Writes are queued and processed by a single background thread — never blocks the caller.
    """

    def __init__(self, level=logging.DEBUG, max_queue_size: int = 5000):
        super().__init__(level)
        self._queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._worker, daemon=True, name="pg-log-handler")
        self._thread.start()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            # Build extra context (exclude standard LogRecord fields)
            _SKIP = {
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "message", "module",
                "msecs", "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName", "exc_info", "exc_text"
            }
            extra = {k: v for k, v in record.__dict__.items() if k not in _SKIP}
            if record.exc_info:
                extra["traceback"] = "".join(traceback.format_exception(*record.exc_info))

            entry = {
                "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
                "level": record.levelname,
                "logger_name": record.name,
                "message": self.format(record),
                "extra": extra or None,
            }
            self._queue.put_nowait(entry)
        except queue.Full:
            pass  # drop silently if queue is full to avoid cascading failures
        except Exception:
            self.handleError(record)

    def _worker(self) -> None:
        """Background thread: drains the queue and writes to PostgreSQL in batches."""
        # Import here to avoid circular import at module level
        from src.db.connection import get_conn, is_available

        while not self._stop_event.is_set():
            batch = []
            try:
                # Block until at least one item arrives
                entry = self._queue.get(timeout=2.0)
                batch.append(entry)
                # Drain up to 99 more items without blocking
                while len(batch) < 100:
                    try:
                        batch.append(self._queue.get_nowait())
                    except queue.Empty:
                        break
            except queue.Empty:
                continue

            if not batch or not is_available():
                continue

            try:
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        cur.executemany(
                            "INSERT INTO system_logs (timestamp, level, logger_name, message, extra) "
                            "VALUES (%s, %s, %s, %s, %s)",
                            [
                                (
                                    e["timestamp"],
                                    e["level"],
                                    e["logger_name"],
                                    e["message"],
                                    json.dumps(e["extra"]) if e["extra"] else None,
                                )
                                for e in batch
                            ],
                        )
            except Exception:
                pass  # never crash the logging thread

    def close(self) -> None:
        self._stop_event.set()
        super().close()


def attach_to_root_logger(level=logging.INFO) -> PostgreSQLLogHandler:
    """
    Convenience function: attach a PostgreSQLLogHandler to the root 'trading_agent' logger.
    Returns the handler so callers can remove it on shutdown.
    """
    handler = PostgreSQLLogHandler(level=level)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    root = logging.getLogger("trading_agent")
    root.addHandler(handler)
    return handler
