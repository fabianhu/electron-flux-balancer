import threading
import time
from datetime import datetime
from logger import logger
import traceback


class TaskController:
    def __init__(self):
        self.tasks = {}
        self.lock = threading.Lock()

    def add_task(self, name, func, interval, watchdog_timeout):
        t = threading.Thread(target=self._run_task, args=(name,))
        self.tasks[name] = {'func': func, 'interval': interval, 'watchdog_timeout': watchdog_timeout, 'thread': t}
        t.start()

    def is_task_running(self, name):
        return self.tasks[name]['thread'].is_alive()

    def _run_task(self, name):
        task_data = self.tasks[name]
        func = task_data['func']
        interval = task_data['interval']
        watchdog_timeout = task_data['watchdog_timeout']

        while True:
            next_run = time.time() + interval
            watchdog = threading.Timer(watchdog_timeout, self._restart_task, args=(name,))
            watchdog.start()

            start_time = datetime.now()

            if not callable(func):
                logger.log("Task not callable: ", func, self.tasks[name])
            else:
                try:
                    func()
                except Exception as e:
                    tb = traceback.extract_tb(e.__traceback__)
                    filename, line, func, text = tb[-1]
                    logger.log(f"Exception occurred in task {name} in file {filename} at line {line}: Exception : {e}")


                end_time = datetime.now()

                #logger.info(f"Task {name} started at {start_time} and finished at {end_time}")

            watchdog.cancel()

            time_to_next_run = next_run - time.time()
            if time_to_next_run > 0:
                time.sleep(time_to_next_run)

    def _restart_task(self, name):
        with self.lock:
            logger.log(f"Watchdog activated for task {name}.")
            task_data = self.tasks[name]
            if self.is_task_running(name): # check if task is still running
                logger.log(f"Task {name} is still running and the timout of {self.tasks[name]['watchdog_timeout']}s is over")
            else:
                logger.log(f"Task {name} died on the way - restarting")
                t = threading.Thread(target=self._run_task, args=(name,))
                self.tasks[name]['thread'] = t
                t.start()


# Example usage
def task1():
    logger.info("Task1 running")
    time.sleep(2)


def task2():
    logger.info("Task2 running")
    time.sleep(4)


if __name__ == '__main__':
    controller = TaskController()
    controller.add_task('Task1', task1, 2, 5)
    controller.add_task('Task2', task2, 1, 3)
