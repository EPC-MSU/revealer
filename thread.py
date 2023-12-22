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
        self._task_in_process: threading.Event = threading.Event()
        self._task_queue: Queue = Queue()

    def add_task(self, task_func, *args, **kwargs) -> None:
        self._task_queue.put(lambda: task_func(*args, **kwargs))

    def run(self) -> None:
        while self._running:
            self._task_in_process.set()
            if self._task_queue.empty():
                self._task_in_process.clear()
                time.sleep(0.005)
                continue
            task = self._task_queue.get()
            if not self._running:
                self._task_in_process.clear()
                return
            task()
            self._task_in_process.clear()

    def empty(self):
        return self._task_queue.empty()

    def task_in_process(self):
        return self._task_in_process.is_set()

    def stop_thread(self) -> None:
        self._running = False
