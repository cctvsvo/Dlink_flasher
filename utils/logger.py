# utils/logger.py
"""
Настройка и кастомизация логгера.
"""
import logging
import os
from datetime import datetime
import queue

# Определим кастомные уровни логирования и методы
def step(self, message, *args, **kws):
    if self.isEnabledFor(logging.INFO):
        self._log(logging.INFO, f"📍 {message}", args, **kws)

def success(self, message, *args, **kws):
    if self.isEnabledFor(logging.INFO):
        self._log(logging.INFO, f"✅ {message}", args, **kws)

logging.addLevelName(logging.INFO, "INFO")
logging.addLevelName(logging.DEBUG, "DEBUG")
logging.addLevelName(logging.WARNING, "WARNING")
logging.addLevelName(logging.ERROR, "ERROR")
logging.addLevelName(logging.CRITICAL, "CRITICAL")

logging.Logger.step = step
logging.Logger.success = success

def setup_logger(logs_dir, debug=False):
    """Настраивает и возвращает логгер."""
    logger = logging.getLogger(f"DLinkReset_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    if not logger.handlers:
        log_filename = f"dlink_reset_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(os.path.join(logs_dir, log_filename), encoding='utf-8')
        file_formatter = logging.Formatter('%(asctime)s [%(levelname)-8s] %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger

# --- Обработчик для очереди логов GUI ---
class QueueLogHandler(logging.Handler):
    """Обработчик логов, отправляющий записи в очередь."""
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        try:
            msg = self.format(record)
            clean_msg = msg.split(']', 1)[-1].strip() if ']' in msg else msg
            self.log_queue.put((record.levelname, clean_msg))
        except Exception:
            self.handleError(record)
# ---
