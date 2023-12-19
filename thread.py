"""
File to start application.
"""

import time
from queue import Queue
import threading


class ProcessThread(threading.Thread):
    """
    Base class for threads to perform tasks.
    """

    def __init__(self) -> None:
        super().__init__()
        self._running: bool = True
        self._task_queue: Queue = Queue()

    def add_task(self, task_func, *args, **kwargs) -> None:
        self._task_queue.put(lambda: task_func(*args, **kwargs))

    def run(self) -> None:
        while self._running:
            if self._task_queue.empty():
                time.sleep(0.005)
                continue
            task = self._task_queue.get()
            if not self._running:
                return
            task()

    def stop_thread(self) -> None:
        self._running = False
