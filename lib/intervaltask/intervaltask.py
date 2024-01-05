import functools
import logging
import threading
import time
from ..logger import Logger
logger = Logger(log_level=logging.DEBUG, log_path="tasks.log")

import traceback

# fixme think about multiprocessing

def thread_alert(func):
    """
    Check, if methods of class are executed in same thread.
    Add self.init_thread_id = None to the class you want to check.
    add @lib.intervaltask.intervaltask.thread_alert decorator to method. and import lib.intervaltask
    :param func:
    :return:
    """
    @functools.wraps(func)
    def wrapper(instance, *args, **kwargs):
        class_name = instance.__class__.__name__
        current_thread_id = threading.get_ident()
        if instance.init_thread_id is None:
            instance.init_thread_id = current_thread_id
            logger.info(f"Initialising '{func.__name__}()' for class {class_name} in thread '{threading.current_thread().name}'.")
        if instance.init_thread_id != current_thread_id:
            logger.error(f"Alarm: Method '{func.__name__}()' in class {class_name} executed in another Thread '{threading.current_thread().name}' than the Initialisation thread.")

        return func(instance, *args, **kwargs)

    return wrapper

class TaskController:
    def __init__(self):
        self.tasks = {}
        self.lock = threading.Lock()

    def add_task(self, name, func, interval, watchdog_timeout):
        t = threading.Thread(target=self._run_task, name=name, args=(name,))
        self.tasks[name] = {
            'func': func,
            'original_func': func,  # Store a copy of the original function
            'interval': interval,
            'watchdog_timeout': watchdog_timeout,
            'thread': t,
            'runtime': 0.0}
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

            start_time = time.time()

            if not callable(func):
                logger.error(f"Task {name} not callable: {func}, {self.tasks[name]}") # fixme check, how to recover
                self.log_func_details(func, name)
                self.tasks[name]['func'] = self.tasks[name]['original_func']  # Restore original function
            else:
                try:
                    func()
                except Exception as e:
                    tb = traceback.extract_tb(e.__traceback__)
                    filename, line, func, text = tb[-1]
                    logger.error(f"Exception occurred in task {name} in file {filename} at line {line}: Exception : {e}")
                    logger.debug(f"Traceback: {traceback.format_exc()}")


                end_time = time.time()
                self.tasks[name]['runtime'] = end_time - start_time
                #logger.info(f"Task {name} took {end_time - start_time} s")

            watchdog.cancel()

            time_to_next_run = next_run - time.time()
            if time_to_next_run > 0:
                time.sleep(time_to_next_run)

    def _restart_task(self, name):
        with self.lock:
            logger.error(f"Watchdog activated for task {name}.")
            task_data = self.tasks[name]
            if self.is_task_running(name): # check if task is still running
                logger.error(f"Task {name} is still running and the timeout of {self.tasks[name]['watchdog_timeout']}s is over")
                # fixme we did not kill it!
                raise Exception(f"Task {name} is hanging with data: {task_data}")
            else:
                logger.error(f"Task {name} died on the way - restarting")
                t = threading.Thread(target=self._run_task, args=(name,))
                self.tasks[name]['thread'] = t
                t.start()

    @staticmethod
    def log_func_details(func, task_name):
        logger.debug(f"Details of non-callable task '{task_name}':")
        logger.debug(f"Type: {type(func)}")
        logger.debug(f"String representation: {func}")
        logger.debug(f"Attributes: {dir(func)}")
        if hasattr(func, '__dict__'):
            logger.debug(f"Object dictionary: {func.__dict__}")

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
