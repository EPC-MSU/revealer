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


class ProcessSSDPThread(threading.Thread):
    """
    Base class for threads to perform tasks.
    """

    # time for listening for SSDP answers
    # we send M-SEARCH request with MX = 2 sec so all devicces should answer in 2 sec, but we add a little additional
    # timeout for program parsing
    SSDP_TIMEOUT_SEC = 2.2

    def __init__(self) -> None:
        super().__init__()
        self._running: bool = True
        self._task_in_process: threading.Event = threading.Event()
        self._task_queue: Queue = Queue()

        self.stop_flag: threading.Event = threading.Event()
        self.stop_flag.set()

    def ssdp_timer_task(self):
        """
        Thread task for timer for ssdp search. Search will be stopped when this time sleep will be done.
        :return:
        """
        # ssdp timer is divided in two parts for more fast closing
        if self._running:
            time.sleep(self.SSDP_TIMEOUT_SEC / 2)
        if self._running:
            time.sleep(self.SSDP_TIMEOUT_SEC / 2)
        self.stop_flag.set()

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
        return self._task_in_process.is_set() or not self.stop_flag.is_set()

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
        """
        Add raw thread for each ip in adapter.

        :param adapters:
        :return:
        """

        for adapter in adapters:
            for ip in adapter.ips:
                self._threads.append(ProcessSSDPThread())
                # self._threads[-1].start()

    def __len__(self):
        return len(self._threads)

    def __getitem__(self, item):
        return self._threads[item]

    def stop_all(self):
        """
        Stop all threads and wait till they really stop.

        :return:
        """

        for thread in self._threads:
            thread.stop_thread()

        self.wait_all_to_end()

    def delete_all(self):
        """
        Stop and delete all threads from the list.

        :return:
        """

        self.stop_all()

        self._threads = []

    def wait_all_to_end(self):
        """
        Wait all threads to end.

        :return:
        """

        for thread in self._threads:
            while thread.task_in_process():
                pass

    def start_notify(self):
        """
        Set notify flag to indicate that we have started some searching process.

        :return:
        """
        self._notify_flag = True

    def stop_notify(self):
        """
        Reset notify flag to indicate that notify listening has stopped or its presence is not now important since
        the real search has started and we now know that we are in the process of searching.

        :return:
        """
        self._notify_flag = False

    def in_process(self):
        """
        Checks if the search is now in process.

        :return:
        """
        in_process = False

        for thread in self._threads:
            if thread.task_in_process():
                in_process = True

        if self._notify_flag:
            in_process = True

        return in_process
