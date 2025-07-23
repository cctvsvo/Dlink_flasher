# handlers/ firmware_handler.py
"""
Обработчик для обновления PROM и прошивки.
"""
import time

class FirmwareHandler:
    def __init__(self, parent):
        self.parent = parent
        self.logger = parent.logger
        self.connection = parent.connection
        self.patterns = parent.patterns
        self.device_cfg = parent.device_cfg
        self.timeouts = parent.timeouts
        self.firmware_info = parent.firmware_info
        self.cli_handler = parent.cli_handler # Для повторного входа

    def update_prom(self):
        self.logger.step("💾 Блок 7: Проверка и обновление PROM")
        
        model_info = self.firmware_info.get(self.parent.model, {})
        prom_info = model_info.get("prom", {})
        
        if not prom_info or not prom_info.get("target_version"):
            self.logger.info("✅ Обновление PROM не требуется или не поддерживается для данной модели.")
            return "SKIP"
            
        # TODO: Получить текущую версию PROM через CLI (show switch)
        # current_prom_version = ...
        current_prom_version = "1.00.B004" # Заглушка
        target_prom_version = prom_info["target_version"]
        
        # Сравнение версий (простое строковое сравнение, в реальности может быть сложнее)
        if current_prom_version >= target_prom_version and not self.parent.force_reflash:
            self.logger.info(f"✅ PROM актуален ({current_prom_version}). Обновление не требуется.")
            return "SKIP"
            
        self.logger.info(f"🔄 Требуется обновление PROM с {current_prom_version} до {target_prom_version}.")
        
        tftp_ip = self.parent.report_data.get("tftp_ip_used")
        if not tftp_ip:
            # Пытаемся получить снова
            # tftp_status = self.cli_handler._check_tftp_connectivity()
            # tftp_ip = tftp_status.get("ip")
            tftp_ip = "192.168.1.100" # Заглушка
            
        if not tftp_ip:
            self.logger.error("❌ Не удалось определить IP адрес TFTP сервера для обновления PROM.")
            return "ERROR"
            
        prom_filename = prom_info["filename"]
        download_cmd = f"download firmware_fromTFTP {tftp_ip} {prom_filename}"
        
        self.logger.info(f"🔄 Обновление PROM: {download_cmd}")
        result = self.connection.send_command_and_wait(
            download_cmd,
            expected_patterns=[self.patterns['FIRMWARE_DOWNLOAD_SUCCESS'], self.patterns['FIRMWARE_DOWNLOAD_ERROR'], self.patterns['PRIVILEGED_PROMPT']],
            timeout=self.timeouts['firmware_download']
        )
        
        download_output = self.connection.get_last_output()
        if result == self.patterns['FIRMWARE_DOWNLOAD_SUCCESS'] or "Success" in download_output:
            self.logger.success("✅ PROM успешно загружен.")
        else:
            self.logger.error(f"❌ Ошибка загрузки PROM: {download_output}")
            return "ERROR"
            
        # Сохраняем
        save_result = self.connection.send_command_and_wait("save", expected_patterns=[self.patterns['SUCCESS_GENERIC'], self.patterns['PRIVILEGED_PROMPT']], timeout=self.timeouts['command_default'])
        if not save_result:
            self.logger.error("❌ Ошибка сохранения после загрузки PROM.")
            return "ERROR"
            
        # Перезагружаем
        self.logger.info("🔄 PROM обновлен. Перезагрузка устройства...")
        self.connection.send_raw(b'reboot\r')
        time.sleep(2)
        
        reboot_confirm_output = self.connection.read_available()
        if self.patterns['CONFIRM_YN'] in reboot_confirm_output:
             self.connection.send_raw(b'Y\r')
             time.sleep(1)
             self.connection.send_raw(b'\r')
             time.sleep(0.5)
             self.connection.send_raw(b'\r')

        self.connection.read_until_pattern([self.patterns['REBOOTING']], timeout=10)
        self.logger.success("✅ PROM обновлен, перезагрузка инициирована...")
        
        return "REBOOT_NEEDED"

    def update_firmware(self):
        self.logger.step("📀 Блок 8: Проверка и обновление основной прошивки")
        
        model_info = self.firmware_info.get(self.parent.model, {})
        firmware_cfg = model_info.get("firmware", {})
        
        if not firmware_cfg or not firmware_cfg.get("final_version"):
            self.logger.info("✅ Обновление прошивки не требуется или не указано в конфигурации.")
            return "SKIP"
            
        # TODO: Получить информацию о слотах через CLI (show firmware information)
        # firmware_info_output = self.parent._run_show_command("show firmware information")
        # slots_info = parse_firmware_slots(firmware_info_output) # Функция из utils
        
        # Для демонстрации симулируем
        slots_info = {
            "Slot 1": {"version": "1.21.B006", "status": "Boot"},
            "Slot 2": {"version": "empty", "status": "Empty"}
        }
        self.parent.report_data["firmware_slots_before_update"] = str(slots_info)
        
        active_slot = None
        empty_slot = None
        active_version = None
        for slot_name, slot_data in slots_info.items():
            if slot_data["status"] == "Boot":
                active_slot = slot_name
                active_version = slot_data["version"]
            elif slot_data["status"] == "Empty":
                empty_slot = slot_name
                
        if not active_slot:
            self.logger.error("❌ Не удалось определить активный слот прошивки.")
            return "ERROR"
            
        final_version = firmware_cfg["final_version"]
        
        # Сравнение версий
        if active_version == final_version and not self.parent.force_reflash:
            self.logger.info(f"✅ Активная прошивка актуальна ({active_version}). Обновление не требуется.")
            return "SKIP"
            
        self.logger.info(f"🔄 Требуется обновление прошивки с {active_version} до {final_version}.")
        
        tftp_ip = self.parent.report_data.get("tftp_ip_used", "192.168.1.100") # Используем сохраненный или дефолтный
        
        target_slot = empty_slot if empty_slot else ("Slot 2" if active_slot == "Slot 1" else "Slot 1")
        self.logger.info(f"Целевой слот для загрузки: {target_slot}")
        
        # --- Проверка необходимости промежуточной прошивки ---
        intermediate_needed = False
        intermediate_version = firmware_cfg.get("intermediate_version")
        final_filename = firmware_cfg["final_filename"]
        
        # Логика выбора файла (упрощена)
        if intermediate_version and active_version < intermediate_version and active_version < final_version:
            intermediate_needed = True
            filename_to_download = firmware_cfg["intermediate_filename"]
            self.logger.info(f"🔄 Требуется промежуточная прошивка: {intermediate_version}")
        else:
            filename_to_download = final_filename
            self.logger.info(f"🔄 Загрузка финальной прошивки: {final_version}")
            
        # --- Очистка целевого слота, если он не пуст ---
        if not empty_slot:
            self.logger.info(f"🗑️ Очистка целевого слота {target_slot}...")
            delete_cmd = f"config firmware image_id {target_slot.split()[1]} delete"
            self.connection.send_command_and_wait(delete_cmd, expected_patterns=[self.patterns['CONFIRM_YN'], self.patterns['SUCCESS_GENERIC'], self.patterns['PRIVILEGED_PROMPT']], timeout=self.timeouts['command_default'])
            delete_confirm = self.connection.get_last_output()
            if self.patterns['CONFIRM_YN'] in delete_confirm:
                self.connection.send_raw(b'Y\r')
                time.sleep(1)
                self.connection.send_raw(b'\r')
                time.sleep(0.5)
                self.connection.send_raw(b'\r')
                # Ждем завершения
                self.connection.read_until_pattern([self.patterns['SUCCESS_GENERIC'], self.patterns['PRIVILEGED_PROMPT']], timeout=10)
                self.logger.success(f"✅ Слот {target_slot} очищен.")
            else:
                self.logger.warning(f"⚠️ Очистка слота {target_slot} может не потребоваться или уже выполнена.")
        
        # --- Загрузка прошивки ---
        image_id = target_slot.split()[1]
        download_cmd = f"download firmware_fromTFTP {tftp_ip} {filename_to_download} image_id {image_id}"
        
        self.logger.info(f"🔄 Загрузка прошивки: {download_cmd}")
        result = self.connection.send_command_and_wait(
            download_cmd,
            expected_patterns=[self.patterns['FIRMWARE_DOWNLOAD_SUCCESS'], self.patterns['FIRMWARE_DOWNLOAD_ERROR'], self.patterns['PRIVILEGED_PROMPT']],
            timeout=self.timeouts['firmware_download']
        )
        
        download_output = self.connection.get_last_output()
        if result == self.patterns['FIRMWARE_DOWNLOAD_SUCCESS'] or "Success" in download_output:
            self.logger.success(f"✅ Прошивка {filename_to_download} успешно загружена в {target_slot}.")
        else:
            self.logger.error(f"❌ Ошибка загрузки прошивки: {download_output}")
            return "ERROR"
            
        # --- Установка загруженной прошивки как загрузочной ---
        bootup_cmd = f"config firmware image_id {image_id} boot_up"
        self.connection.send_command_and_wait(bootup_cmd, expected_patterns=[self.patterns['SUCCESS_GENERIC'], self.patterns['PRIVILEGED_PROMPT']], timeout=self.timeouts['command_default'])
        bootup_output = self.connection.get_last_output()
        if any(s in bootup_output for s in self.patterns['SUCCESS_GENERIC']) or self.patterns['PRIVILEGED_PROMPT'] in bootup_output:
            self.logger.success(f"✅ Прошивка в {target_slot} установлена как загрузочная.")
        else:
            self.logger.error(f"❌ Ошибка установки прошивки как загрузочной: {bootup_output}")
            return "ERROR"
            
        # --- Сохранение конфигурации ---
        save_result = self.connection.send_command_and_wait("save", expected_patterns=[self.patterns['SUCCESS_GENERIC'], self.patterns['PRIVILEGED_PROMPT']], timeout=self.timeouts['command_default'])
        if not save_result:
            self.logger.error("❌ Ошибка сохранения после загрузки прошивки.")
            return "ERROR"
            
        # --- Перезагрузка ---
        self.logger.info("🔄 Прошивка обновлена. Перезагрузка устройства...")
        self.connection.send_raw(b'reboot\r')
        time.sleep(2)
        
        reboot_confirm_output = self.connection.read_available()
        if self.patterns['CONFIRM_YN'] in reboot_confirm_output:
             self.connection.send_raw(b'Y\r')
             time.sleep(1)
             self.connection.send_raw(b'\r')
             time.sleep(0.5)
             self.connection.send_raw(b'\r')

        self.connection.read_until_pattern([self.patterns['REBOOTING']], timeout=10)
        self.logger.success("✅ Прошивка обновлена, перезагрузка инициирована...")
        
        # --- Если это была промежуточная прошивка, нужно будет снова обновить ---
        if intermediate_needed and filename_to_download == firmware_cfg["intermediate_filename"]:
            self.logger.info("ℹ️ Была загружена промежуточная прошивка. После перезагрузки потребуется загрузить финальную.")
            # При следующем входе в CLI будет снова вызван update_firmware
            
        return "REBOOT_NEEDED"
