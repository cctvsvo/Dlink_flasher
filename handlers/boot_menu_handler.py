# handlers/boot_menu_handler.py
"""
Обработчик для работы с Boot Configuration Menu.
"""
import time

class BootMenuHandler:
    def __init__(self, parent):
        self.parent = parent
        self.logger = parent.logger
        self.connection = parent.connection
        self.patterns = parent.patterns
        self.device_cfg = parent.device_cfg
        self.timeouts = parent.timeouts

    def attempt_boot_menu_entry(self):
        self.logger.step("⚠️ Блок 4: Попытка входа в Boot Configuration Menu (Аварийный режим)")
        self.logger.info("⚠️ Пожалуйста, ПЕРЕЗАГРУЗИТЕ устройство для входа в Boot Menu.")
        
        boot_menu_combo_hex = self.device_cfg.get("boot_menu_combination", "33")
        boot_menu_combo_bytes = bytes.fromhex(boot_menu_combo_hex)
        
        start_time = time.monotonic()
        timeout = self.timeouts['boot_menu_wait']
        
        while time.monotonic() - start_time < timeout:
            output = self.connection.read_available()
            if output:
                self.logger.debug(f"📥 Данные при ожидании Boot Menu: {output[:100]}...")
                if any(ind in output for ind in self.patterns['boot_indicators']):
                    self.logger.debug("📥 Обнаружен индикатор загрузки. Отправляем комбинацию для Boot Menu.")
                    self.connection.send_raw(boot_menu_combo_bytes)
                    time.sleep(0.5) # Небольшая пауза
                    
                    # Ждем индикаторы Boot Menu
                    menu_output = self.connection.read_until_pattern(
                        self.patterns['boot_menu_indicators'],
                        timeout=20
                    )
                    
                    if any(ind in menu_output for ind in self.patterns['boot_menu_indicators']):
                        self.logger.success("✅ Успешно вошли в Boot Configuration Menu!")
                        # TODO: Реализовать навигацию по меню и ZModem
                        # Это сложная часть, требующая эмуляции терминала и работы с ZModem
                        self.logger.info("ℹ️ Обнаружен Boot Menu. Требуется ручная настройка ZModem (пока не реализовано автоматически).")
                        self.logger.info("Пожалуйста, вручную выберите 'Download Protocol: [ZModem]' и передайте файлы через ZModem.")
                        input("Нажмите Enter после завершения ручной передачи и перезагрузки устройства...")
                        return True
                    else:
                        self.logger.warning("⚠️ Комбинация отправлена, но Boot Menu не обнаружен.")
                        
            time.sleep(0.5)
            
        self.logger.error("❌ Не удалось войти в Boot Configuration Menu!")
        return False
