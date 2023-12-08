import logging
import inspect

class Logger:
    def __init__(self, log_level=logging.ERROR, log_path='log.log'):
        # Retrieve the caller's module name using inspect
        #caller_frame = inspect.stack()[1]
        #module_name = inspect.getmodule(caller_frame[0]).__name__
        caller_frame = inspect.currentframe().f_back
        module_name = caller_frame.f_globals['__name__']

        self.logger = logging.getLogger(module_name)
        self.logger.setLevel(logging.DEBUG)  # Set to the lowest level to capture all messages by default

        self.log_handler = logging.FileHandler(log_path)
        self.log_handler.setLevel(log_level)

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.log_handler.setFormatter(formatter)

        self.logger.addHandler(self.log_handler)

    def get_logger(self, module_name, log_level=logging.ERROR):
        module_logger = logging.getLogger(module_name)
        module_logger.setLevel(log_level)
        module_logger.propagate = False  # Prevent logs from propagating up the hierarchy

        if not any(isinstance(handler, logging.FileHandler) for handler in module_logger.handlers):
            module_logger.addHandler(self.log_handler)  # Add the file handler if not already present

        return module_logger

    def debug(self, message):
        self.logger.debug(message)

    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def log(self, message):  # legacy support
        self.logger.error(message)

    def error(self, message):
        self.logger.error(message)

    def critical(self, message):
        self.logger.critical(message)




# Usage example:
if __name__ == "__main__":
    logger_debug = Logger(log_path='debug.log', log_level=logging.DEBUG)
    logger_debug.log("Debug message")

    logger_info = Logger(log_path='info.log', log_level=logging.INFO)
    logger_info.log("Info message")

    logger_warning = Logger(log_path='warning.log', log_level=logging.WARNING)
    logger_warning.log("Warning message")

    logger_error = Logger(log_path='error.log', log_level=logging.ERROR)
    logger_error.log("Error message")

    logger_critical = Logger(log_path='critical.log', log_level=logging.CRITICAL)
    logger_critical.log("Critical message")


# Initialize the logging setup when the module is imported
#logger = Logger()
