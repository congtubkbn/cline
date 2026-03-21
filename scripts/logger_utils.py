import logging
import sys
from datetime import datetime
from pathlib import Path
from enum import Enum, auto

# 1. Define Destinations using Enum to avoid magic strings
class LogDest(Enum):
    FILE = auto()
    CONSOLE = auto()
    BOTH = auto()

class ScriptLogger:
    def __init__(self, script_name: str):
        self.script_name = script_name
        
        # Folder Setup: /process/log/
        log_dir = Path("process/log")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # File Setup: log_YYYYMMDD_HHMMSS_name.log
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = log_dir / f"log_{timestamp}_{self.script_name}.log"

        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 2. Setup Internal Loggers
        # File-only logger
        self._file_logger = logging.getLogger(f"{script_name}_f")
        self._file_logger.setLevel(logging.DEBUG)
        if not self._file_logger.handlers:
            fh = logging.FileHandler(self.log_path)
            fh.setFormatter(formatter)
            self._file_logger.addHandler(fh)

        # Console-only logger
        self._console_logger = logging.getLogger(f"{script_name}_c")
        self._console_logger.setLevel(logging.DEBUG)
        if not self._console_logger.handlers:
            ch = logging.StreamHandler(sys.stdout)
            ch.setFormatter(formatter)
            self._console_logger.addHandler(ch)

    def _dispatch(self, level_name: str, msg: str, dest: LogDest):
        """Routes the message to the correct destination based on Enum."""
        # Mapping level name to the actual logging method
        if dest == LogDest.FILE or dest == LogDest.BOTH:
            getattr(self._file_logger, level_name)(msg)
        
        if dest == LogDest.CONSOLE or dest == LogDest.BOTH:
            getattr(self._console_logger, level_name)(msg)

    # --- Public API ---
    def info(self, msg: str, dest: LogDest = LogDest.BOTH):
        self._dispatch("info", msg, dest)

    def error(self, msg: str, dest: LogDest = LogDest.BOTH):
        self._dispatch("error", msg, dest)

    def debug(self, msg: str, dest: LogDest = LogDest.BOTH):
        self._dispatch("debug", msg, dest)

    def warning(self, msg: str, dest: LogDest = LogDest.BOTH):
        self._dispatch("warning", msg, dest)

# Factory function
def get_logger(name: str):
    return ScriptLogger(name)