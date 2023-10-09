import threading

import threading
from datetime import datetime

class FileLogger:
    def __init__(self, log_file_path, info_file_path):
        self.log_file_path = log_file_path
        self.info_file_path = info_file_path
        self.lock = threading.Lock()

    def log(self, *args):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        message = " ".join(str(arg) for arg in args)
        log_line = f"[{timestamp}] {message}"

        with self.lock:
            with open(self.log_file_path, 'a') as file:
                file.write(log_line + '\n')

    def info(self, *args):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        message = " ".join(str(arg) for arg in args)
        log_line = f"[{timestamp}] {message}"

        with self.lock:
            with open(self.info_file_path, 'a') as file:
                file.write(log_line + '\n')

# Create a shared logger instance
logger = FileLogger('log.txt','info.txt')

if __name__ == '__main__':
    # Usage example
    # from logger import logger

    def worker():
        value1 = 10
        logger.log("Hello from thread", value1)

    # Create multiple threads
    threads = []
    for _ in range(5):
        thread = threading.Thread(target=worker)
        threads.append(thread)
        thread.start()

    # Wait for all threads to finish
    for thread in threads:
        thread.join()
