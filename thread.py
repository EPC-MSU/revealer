"""
File to start application.
"""

import time
from queue import Queue
import threading

import logging as log


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


class ProcessSSDPThread(threading.Thread):
    """
    Base class for threads to perform tasks.
    """

    def __init__(self) -> None:
        super().__init__()
        self._running: bool = True
        self._task_in_process: threading.Event = threading.Event()
        self._task_queue: Queue = Queue()

        self.stop_flag: threading.Event = threading.Event()

    def ssdp_timer_task(self):
        """
        Thread task for timer for ssdp search.
        :return:
        """
        # ssdp timer is divided in two parts for more fast closing
        log.warning(f"start timer...")
        if self._running:
            time.sleep(1.25)
        if self._running:
            time.sleep(1.25)
        self.stop_flag.set()
        log.warning(f"stop timer.")

    def add_task(self, task_func, *args, **kwargs) -> None:
        self._task_queue.put(lambda: task_func(*args, **kwargs))

    def run(self) -> None:
        while self._running:
            if self._task_queue.empty():
                self._task_in_process.clear()
                time.sleep(0.005)
                continue
            self._task_in_process.set()
            task = self._task_queue.get()
            if not self._running:
                self._task_in_process.clear()
                return
            timer = threading.Thread(target=self.ssdp_timer_task)
            timer.start()
            # create
            task()
            self._task_in_process.clear()
            self.stop_thread()  # it is one time thread

    def empty(self):
        return self._task_queue.empty()

    def task_in_process(self):
        return self._task_in_process.is_set()

    def stop_thread(self) -> None:
        self._running = False


class SSDPSearchThread:
    """
    Class of the list of the threads for SSDP search on all interfaces.

    """

    def __init__(self):

        self._threads = []
        self._notify_flag = False

    def add_adapters(self, adapters):

        for adapter in adapters:
            for ip in adapter.ips:
                self._threads.append(ProcessSSDPThread())
                self._threads[-1].start()

    def __len__(self):
        return len(self._threads)

    def __getitem__(self, item):
        return self._threads[item]

    def stop_all(self):

        for thread in self._threads:
            thread.stop_thread()

        self.wait_all_to_end()

    def delete_all(self):

        self.stop_all()

        self._threads = []

    def wait_all_to_end(self):

        for thread in self._threads:
            while thread.task_in_process():
                log.warning(f"wait till thread {thread} is ended...")
                pass

    def start_notify(self):
        self._notify_flag = True

    def stop_notify(self):
        self._notify_flag = False

    def in_process(self):
        in_process = False

        for thread in self._threads:
            if thread.task_in_process():
                in_process = True

        if self._notify_flag:
            in_process = True

        return in_process

