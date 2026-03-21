# src/agent/file_lock.py
"""
A simple file-based locking mechanism to prevent race conditions
when reading/writing the agent_state.json file.
"""
import os
import time
import logging

logger = logging.getLogger(__name__)

class FileLock:
    def __init__(self, lock_file_path, timeout=10, delay=0.05):
        """
        Initializes the FileLock.
        :param lock_file_path: Path to the lock file.
        :param timeout: Maximum time in seconds to wait for the lock.
        :param delay: Time in seconds to wait between lock acquisition attempts.
        """
        self.lock_file_path = lock_file_path
        self.timeout = timeout
        self.delay = delay
        self._is_locked = False

    def acquire(self):
        """
        Acquire the lock. If the lock is not available, it will wait
        until the timeout is reached.
        """
        start_time = time.time()
        while True:
            try:
                # Attempt to create the file exclusively.
                # This is an atomic operation on most OSes.
                self.fd = os.open(self.lock_file_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                self._is_locked = True
                break
            except FileExistsError:
                if time.time() - start_time >= self.timeout:
                    raise TimeoutError(f"Could not acquire lock on {self.lock_file_path} within {self.timeout} seconds.")
                time.sleep(self.delay)

    def release(self):
        """
        Release the lock by closing and deleting the lock file.
        """
        if self._is_locked:
            os.close(self.fd)
            os.remove(self.lock_file_path)
            self._is_locked = False

    def __enter__(self):
        """
        Context manager entry. Acquires the lock.
        """
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit. Releases the lock.
        """
        self.release()

# Helper function to create a lock for our specific state file
def get_state_lock():
    """
    Returns a FileLock instance for the agent_state.json file.
    Lock file is placed next to agent_state.json using an absolute path
    derived from this module's location, so it works regardless of CWD.
    """
    # Resolve project root from this file's location (src/agent/file_lock.py → ../../)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    lock_file = os.path.join(project_root, "agent_state.json.lock")
    return FileLock(lock_file)
