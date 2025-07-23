# handlers/connection.py
"""
Обработчик последовательного соединения.
"""
import serial
import time

class SerialConnection:
    def __init__(self, port, baudrate, logger):
        self.port = port
        self.baudrate = baudrate
        self.logger = logger
        self.conn = None
        self._last_output = ""

    def connect(self):
        """Устанавливает соединение."""
        try:
            self.conn = serial.Serial(self.port, self.baudrate, timeout=1)
            self.logger.debug(f"🔌 Попытка подключения к {self.port} ({self.baudrate} baud)...")
            time.sleep(1) # Стабилизация
            self.logger.info(f"✅ Подключение к {self.port} ({self.baudrate} baud) установлено.")
        except Exception as e:
            self.logger.critical(f"❌(CRITICAL) Ошибка: Не удалось подключиться к порту {self.port}: {e}")
            raise SystemExit(1)

    def disconnect(self):
        """Закрывает соединение."""
        if self.conn and self.conn.is_open:
            self.conn.close()
            self.logger.info(f"🔌 Соединение с {self.port} закрыто.")

    def send_raw(self, data_bytes):
        """Отправляет сырые байты."""
        if self.conn:
            self.conn.write(data_bytes)

    def read_available(self):
        """Читает все доступные данные."""
        if self.conn and self.conn.in_waiting > 0:
            data = self.conn.read(self.conn.in_waiting)
            decoded_data = data.decode('utf-8', errors='ignore')
            self.logger.debug(f"📥 Получены сырые данные: {repr(data)} -> '{decoded_data}'")
            return decoded_data
        return ""

    def read_until_pattern(self, patterns, timeout=10):
        """
        Читает данные до тех пор, пока не найдет один из паттернов или не истечет таймаут.
        """
        start_time = time.monotonic()
        buffer = ""
        while time.monotonic() - start_time < timeout:
            buffer += self.read_available()
            for pattern in patterns:
                import re
                if re.search(pattern, buffer, re.IGNORECASE):
                    self.logger.debug(f"🎯 Найден паттерн '{pattern}' в буфере.")
                    return buffer
            time.sleep(0.1)
        self.logger.debug(f"⏱️ Таймаут ожидания паттернов {patterns}. Буфер: {buffer[-200:]}...")
        return buffer

    def send_command_and_wait(self, command, expected_patterns, timeout=10):
        """
        Отправляет команду и ждет один из ожидаемых паттернов.
        """
        self.logger.debug(f"📤 Отправка команды: {command}")
        self.send_raw(f"{command}\r".encode())
        output = self.read_until_pattern(expected_patterns, timeout)
        self._last_output = output
        # Проверяем, какой паттерн найден
        import re
        for pattern in expected_patterns:
            if re.search(pattern, output, re.IGNORECASE):
                self.logger.debug(f"🎯 Команда '{command}' завершена с паттерном '{pattern}'.")
                return pattern
        self.logger.debug(f"⚠️ Команда '{command}' завершена, но ожидаемый паттерн не найден. Вывод: {output[-100:]}...")
        return None

    def get_last_output(self):
        """Возвращает вывод последней команды."""
        return getattr(self, '_last_output', "")
