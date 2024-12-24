import logging
from datetime import datetime


# Custom Formatter with Colors
class Logger(logging.Formatter):
    """Custom logging formatter to include colors and icons for log level."""

    # ANSI escape sequences for colors
    COLOR_CODES = {
        logging.DEBUG: "\033[94m",  # Blue
        logging.INFO: "\033[97m",  # White
        logging.WARNING: "\033[93m",  # Yellow
        logging.ERROR: "\033[91m",  # Red
        logging.CRITICAL: "\033[95m",  # Magenta
    }

    # Icons for each log level
    LOG_LEVEL_ICONS = {
        logging.DEBUG: "-",
        logging.INFO: "ℹ",
        logging.WARNING: "!",
        logging.ERROR: "⚠",
        logging.CRITICAL: "⚠",
    }

    def format(self, record):
        current_time = datetime.now().strftime('%m.%d %H:%M:%S')
        level_icon = self.LOG_LEVEL_ICONS.get(record.levelno, 'ℹ️')
        level_color = self.COLOR_CODES.get(record.levelno, "\033[0m")  # Default color if not found

        log_message = f"\033[92m\033[1m{level_icon}\033[0m\033[92m {current_time}\033[37m: {level_color}{record.getMessage()}\033[0m"
        return log_message


def get_custom_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        console_handler = logging.StreamHandler()
        formatter = Logger()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger
