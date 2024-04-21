import datetime
import logging
import inspect

class Logger:
    count = 0

    def __init__(self, log_level=logging.ERROR, log_path='log.log'):
        """
        Initializes a Logger object for module-specific logging.
        This method configures a logger with a file handler, suitable for logging messages from the calling module. The logger
        captures all messages (level DEBUG), while the file handler records messages based on `log_level`.
        The logger's name is automatically set to the calling module's name, allowing distinct log outputs for different modules.
        Log messages are formatted to include timestamp, logger name, level, and message.

        Parameters:
        - log_level (logging.Level, optional): Minimum level of log messages to be recorded. Defaults to logging.ERROR.
        - log_path (str, optional): File path for the log output. Defaults to 'log.log'.

        Note:
        - The logger level and file handler level are independent; the file handler may filter out lower-severity messages.
        """

        # Retrieve the caller's module name using inspect
        caller_frame = inspect.currentframe().f_back
        module_name = caller_frame.f_globals['__name__']

        self.log_handler = logging.FileHandler(log_path)

        self.logger = logging.getLogger(module_name)
        self.logger.setLevel(logging.DEBUG)  # Set to the lowest level to capture all messages by default

        self.log_handler.setLevel(log_level)

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.log_handler.setFormatter(formatter)

        self.logger.addHandler(self.log_handler)

        if Logger.count == 0:
            self.logint("############### LOGGER START ############################################")
        Logger.count += 1

        self.logint(f"Logger created from {module_name} logging to {log_path}")

        self.logger.info("############### START ############################################")




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

    @staticmethod
    def logint(message):
        with open("logger_internal.log", "a") as f: f.write(f"{datetime.datetime.now()} {message}\n")



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
