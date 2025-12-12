"""Custom logging setup for the playout system."""

import logging
from datetime import datetime

from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with timestamp and level normalization."""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        if not log_record.get("timestamp"):
            # this doesn't use record.created, so it is slightly off
            now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            log_record["timestamp"] = now
        if log_record.get("level"):
            log_record["level"] = log_record["level"].upper()
        else:
            log_record["level"] = record.levelname


def setup_logger(name=__name__):
    """Setup and return a logger with JSON formatting."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    log_handler = logging.StreamHandler()
    formatter = CustomJsonFormatter("%(timestamp)s %(level)s %(name)s:%(lineno)s %(message)s")
    log_handler.setFormatter(formatter)
    logger.addHandler(log_handler)

    return logger


# Default logger instance
logger = setup_logger()
