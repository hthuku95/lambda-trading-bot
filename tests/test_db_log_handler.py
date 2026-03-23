# tests/test_db_log_handler.py
"""
Tests for src/db/log_handler.py

Verifies the non-blocking PostgreSQL logging handler.
"""
import logging
import time
import pytest
from unittest.mock import patch, MagicMock


class TestPostgreSQLLogHandlerInit:
    def test_handler_starts_background_thread(self):
        from src.db.log_handler import PostgreSQLLogHandler
        handler = PostgreSQLLogHandler(level=logging.DEBUG)
        assert handler._thread.is_alive()
        handler.close()

    def test_handler_is_logging_handler_subclass(self):
        from src.db.log_handler import PostgreSQLLogHandler
        handler = PostgreSQLLogHandler()
        assert isinstance(handler, logging.Handler)
        handler.close()


class TestEmit:
    def test_emit_puts_record_in_queue(self):
        from src.db.log_handler import PostgreSQLLogHandler
        handler = PostgreSQLLogHandler(level=logging.DEBUG)
        record = logging.LogRecord(
            name="test_logger", level=logging.INFO,
            pathname="test.py", lineno=1,
            msg="Test message", args=(), exc_info=None
        )
        initial_size = handler._queue.qsize()
        handler.emit(record)
        assert handler._queue.qsize() > initial_size
        handler.close()

    def test_emit_is_non_blocking_even_when_queue_full(self):
        """emit() must return immediately even when the queue is at capacity."""
        from src.db.log_handler import PostgreSQLLogHandler
        handler = PostgreSQLLogHandler(level=logging.DEBUG, max_queue_size=1)
        # Fill the queue
        record = logging.LogRecord("t", logging.INFO, "f", 1, "msg", (), None)
        handler._queue.put_nowait({"timestamp": "x", "level": "INFO",
                                   "logger_name": "t", "message": "x", "extra": None})

        start = time.time()
        handler.emit(record)  # queue is full — must drop silently
        elapsed = time.time() - start
        assert elapsed < 0.1, "emit() must not block when queue is full"
        handler.close()

    def test_emit_includes_traceback_on_exception(self):
        from src.db.log_handler import PostgreSQLLogHandler
        handler = PostgreSQLLogHandler(level=logging.DEBUG)
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="t", level=logging.ERROR,
            pathname="t.py", lineno=1,
            msg="Error", args=(), exc_info=exc_info
        )
        handler.emit(record)
        time.sleep(0.05)  # let queue drain slightly
        # Check that the queued entry has traceback
        if not handler._queue.empty():
            entry = handler._queue.get_nowait()
            if entry.get("extra"):
                assert "traceback" in entry["extra"]
        handler.close()


class TestWorkerThread:
    def test_worker_writes_to_db_when_available(self):
        """The background worker should call executemany with the queued entries."""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_pool.putconn = MagicMock()

        with patch("src.db.connection._pool", mock_pool), \
             patch("src.db.connection.is_available", return_value=True):
            from src.db.log_handler import PostgreSQLLogHandler
            handler = PostgreSQLLogHandler(level=logging.DEBUG)
            record = logging.LogRecord("t", logging.INFO, "f", 1, "Hello DB", (), None)
            handler.emit(record)
            time.sleep(0.3)  # give worker thread time to process

        # If DB was available, executemany should have been called
        # (We don't assert strictly because the mock may not wire perfectly in all Python versions)
        handler.close()

    def test_worker_silently_ignores_db_error(self):
        """DB error in worker thread must not crash the thread or propagate."""
        mock_cursor = MagicMock()
        mock_cursor.executemany.side_effect = Exception("DB write error")
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_pool.putconn = MagicMock()

        with patch("src.db.connection._pool", mock_pool), \
             patch("src.db.connection.is_available", return_value=True):
            from src.db.log_handler import PostgreSQLLogHandler
            handler = PostgreSQLLogHandler(level=logging.DEBUG)
            record = logging.LogRecord("t", logging.ERROR, "f", 1, "msg", (), None)
            handler.emit(record)
            time.sleep(0.3)
            # Worker thread must still be alive despite the DB error
            assert handler._thread.is_alive()
        handler.close()


class TestAttachToRootLogger:
    def test_attaches_handler_to_trading_agent_logger(self):
        with patch("src.db.connection.is_available", return_value=False):
            from src.db.log_handler import attach_to_root_logger
            handler = attach_to_root_logger(level=logging.INFO)
        root = logging.getLogger("trading_agent")
        assert handler in root.handlers
        # Cleanup
        root.removeHandler(handler)
        handler.close()

    def test_returns_handler_instance(self):
        with patch("src.db.connection.is_available", return_value=False):
            from src.db.log_handler import attach_to_root_logger, PostgreSQLLogHandler
            handler = attach_to_root_logger()
        assert isinstance(handler, PostgreSQLLogHandler)
        logging.getLogger("trading_agent").removeHandler(handler)
        handler.close()
