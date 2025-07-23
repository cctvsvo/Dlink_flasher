# handlers/cli_handler.py
"""
Обработчик для работы с CLI.
"""
import time
import re

class CLIHandler:
    def __init__(self, parent):
        self.parent = parent
        self.logger = parent.logger
        self.connection = parent.connection
        self.patterns = parent.patterns
        self.device_cfg = parent.device_cfg
        self.timeouts = parent.timeouts
        self.stats_manager = parent.stats_manager
        self.credentials = parent.credentials
        self.reset_commands = parent.reset_commands
        self.firmware_info = parent.firmware_info

    def init_cli_handler_config(self):
        """Инициализация конфигурации CLI хендлера."""
        # Пока пусто, можно добавить инициализацию специфичных для CLI параметров
        pass

    def attempt_cli_entry(self):
        self.logger.step("🖥️ Блок 5: Попытка входа в CLI")
        
        start_time = time.monotonic()
        timeout = self.timeouts['reboot_wait']
        
        while time.monotonic() - start_time < timeout:
            # Отправляем Enter для активации промпта
            self.connection.send_raw(b'\r')
            time.sleep(0.5)
            
            output = self.connection.read_available()
            if output:
                self.logger.debug(f"📥 Получены данные при попытке входа в CLI: {output[:100]}...")
                
                if self.patterns['PRIVILEGED_PROMPT'] in output:
                    self.logger.success("✅ Успешный вход в CLI ('#')!")
                    return "SUCCESS_PRIVILEGED"
                elif self.patterns['USER_PROMPT'] in output:
                    self.logger.info("ℹ️ Обнаружен пользовательский промпт '>'. Попытка перейти в привилегированный режим...")
                    # Попробуем enable
                    self.connection.send_raw(b'enable\r')
                    time.sleep(1)
                    enable_output = self.connection.read_available()
                    if self.patterns['PRIVILEGED_PROMPT'] in enable_output:
                        self.logger.success("✅ Успешный вход в CLI ('#') после 'enable'!")
                        return "SUCCESS_PRIVILEGED"
                    elif self.patterns['PASSWORD_PROMPT'] in enable_output:
                        # Нужен пароль для enable, обработаем как обычный логин
                        pass
                    else:
                        self.logger.warning("⚠️ Не удалось перейти в привилегированный режим.")
                        
                if self.patterns['LOGIN_PROMPT'] in output or self.patterns['PASSWORD_PROMPT'] in output:
                    self.logger.info("ℹ️ Обнаружен запрос логина/пароля в CLI.")
                    login_result = self._handle_login(output)
                    if login_result == "SUCCESS_PRIVILEGED":
                        return login_result
                    elif login_result == "SUCCESS_USER":
                        # Нужно выполнить enable
                        self.connection.send_raw(b'enable\r')
                        time.sleep(1)
                        enable_prompt = self.connection.read_until_pattern(
                            [self.patterns['PASSWORD_PROMPT'], self.patterns['PRIVILEGED_PROMPT']],
                            timeout=self.timeouts['prompt_wait']
                        )
                        if self.patterns['PRIVILEGED_PROMPT'] in enable_prompt:
                            self.logger.success("✅ Успешный переход в привилегированный режим!")
                            return "SUCCESS_PRIVILEGED"
                        elif self.patterns['PASSWORD_PROMPT'] in enable_prompt:
                            # TODO: Обработка пароля для enable, если он есть
                            self.logger.warning("⚠️ Требуется пароль для 'enable', который не поддерживается в этой версии.")
                            return "FAILED" # Или продолжить с пользовательским промптом?
                        else:
                            self.logger.warning("⚠️ Неожиданный ответ после 'enable'.")
                            return "FAILED"
                    else: # "FAILED"
                        return login_result
                        
                if "Please set a new password" in output:
                    self.logger.info("ℹ️ Требуется установка нового пароля.")
                    if self._handle_initial_password():
                        # После установки пароля снова пытаемся войти
                        return self.attempt_cli_entry() # Рекурсивный вызов, но с ограничением итераций в run()
                        
            time.sleep(0.5)
            
        self.logger.error("❌ Не удалось войти в CLI!")
        return "FAILED"

    def _handle_login(self, initial_output=""):
        """Обрабатывает логин в CLI."""
        credentials_list = self.credentials.get("cli", [])
        sorted_credentials = self.stats_manager.sort_by_stats(credentials_list, "credentials")
        
        # Если уже есть вывод с запросом, используем его
        output_buffer = initial_output
        
        for cred in sorted_credentials:
            login = cred['login']
            password = cred['password']
            cred_id = cred['id']
            
            self.logger.debug(f"Пробуем учетные данные CLI: {cred_id}")
            
            # Если логин требуется
            if self.patterns['LOGIN_PROMPT'] in output_buffer or "UserName:" in output_buffer:
                self.connection.send_command_and_wait(login, expected_patterns=[self.patterns['PASSWORD_PROMPT']], timeout=self.timeouts['login_attempt'])
                output_buffer = self.connection.get_last_output()
            
            # Отправляем пароль
            self.connection.send_command_and_wait(password, expected_patterns=[self.patterns['USER_PROMPT'], self.patterns['PRIVILEGED_PROMPT'], self.patterns['LOGIN_FAILED_INDICATOR']], timeout=self.timeouts['login_attempt'])
            final_output = self.connection.get_last_output()
            
            if self.patterns['PRIVILEGED_PROMPT'] in final_output and not any(err in final_output for err in self.patterns['LOGIN_FAILED_INDICATOR']):
                self.logger.success(f"✅ Успешный вход в CLI с привилегиями '#' используя {cred_id}!")
                self.stats_manager.update_stats("credentials", cred_id, success=True)
                return "SUCCESS_PRIVILEGED"
            elif self.patterns['USER_PROMPT'] in final_output and not any(err in final_output for err in self.patterns['LOGIN_FAILED_INDICATOR']):
                self.logger.success(f"✅ Успешный вход в CLI с пользовательскими правами '>' используя {cred_id}!")
                self.stats_manager.update_stats("credentials", cred_id, success=True)
                return "SUCCESS_USER"
            else:
                self.logger.debug(f"Попытка входа с {cred_id} не удалась.")
                self.stats_manager.update_stats("credentials", cred_id, success=False)
                # Сброс буфера для следующей попытки
                output_buffer = ""
                
        self.logger.error("❌ Учетные данные для CLI не подошли.")
        return "FAILED"
        
    def _handle_initial_password(self):
        """Обрабатывает установку нового пароля при первом входе."""
        try:
            # Вводим новый пароль
            self.connection.send_raw(b'admin\r') # Предполагаем стандартный пароль
            time.sleep(1)
            # Подтверждаем пароль
            self.connection.send_raw(b'admin\r')
            time.sleep(1)
            # Сохраняем
            self.connection.send_raw(b'save\r')
            time.sleep(2)
            # Несколько Enter для выхода из диалога
            for _ in range(3):
                self.connection.send_raw(b'\r')
                time.sleep(0.5)
            
            self.logger.success("✅ Новый пароль установлен и сохранен.")
            return True
        except Exception as e:
            self.logger.error(f"❌ Ошибка при установке нового пароля: {e}")
            return False

    def execute_cli_reset(self):
        self.logger.step("🗑️ Блок 5: Выполнение дополнительного сброса через CLI")
        self.parent.report_data["reset_was_performed"] = True
        
        commands = self.reset_commands.get(self.device_cfg.get("cli_commands", "cli"), [])
        sorted_commands = self.stats_manager.sort_by_stats(commands, "reset_commands")
        
        if not sorted_commands:
             self.logger.error("❌ Нет команд сброса CLI в конфигурации.")
             return False
        
        success_count = 0
        for cmd_data in sorted_commands:
            cmd = cmd_data['command']
            cmd_id = cmd_data['id']
            
            result = self.connection.send_command_and_wait(
                cmd,
                expected_patterns=[
                    self.patterns['SUCCESS_GENERIC'],
                    self.patterns['PRIVILEGED_PROMPT'],
                    self.patterns['ERROR_GENERIC'],
                    self.patterns['CONFIRM_YN']
                ],
                timeout=self.timeouts['command_default']
            )
            
            if result == self.patterns['CONFIRM_YN']:
                self.logger.debug("Обнаружено подтверждение (Y/N), отправляем Y...")
                self.connection.send_raw(b'Y\r')
                time.sleep(1)
                # Ждем приглашение и отправляем Enter
                self.connection.read_until_pattern([self.patterns['PRIVILEGED_PROMPT'], self.patterns['USER_PROMPT']], timeout=5)
                self.connection.send_raw(b'\r')

            final_output = self.connection.get_last_output()
            success_found = any(s in final_output for s in self.patterns['SUCCESS_GENERIC']) or self.patterns['PRIVILEGED_PROMPT'] in final_output
            error_found = any(e in final_output for e in self.patterns['ERROR_GENERIC'])
            
            if success_found and not error_found:
                self.logger.success(f"✅ Команда сброса '{cmd}' выполнена успешно!")
                self.stats_manager.update_stats("reset_commands", cmd_id, success=True)
                success_count += 1
            else:
                self.logger.warning(f"⚠️ Команда сброса '{cmd}' не выполнена или выполнена с ошибкой.")
                self.stats_manager.update_stats("reset_commands", cmd_id, success=False)
        
        self.stats_manager.save_stats("reset_commands")
        
        if success_count == 0:
            self.logger.error("❌ Ни одна команда сброса CLI не была выполнена успешно.")
            return False
            
        # Сохраняем конфигурацию
        self.connection.send_command_and_wait("save", expected_patterns=[self.patterns['SUCCESS_GENERIC'], self.patterns['PRIVILEGED_PROMPT']], timeout=self.timeouts['command_default'])
        save_output = self.connection.get_last_output()
        if any(s in save_output for s in self.patterns['SUCCESS_GENERIC']) or self.patterns['PRIVILEGED_PROMPT'] in save_output:
            self.logger.success("✅ Конфигурация сброса сохранена.")
        else:
            self.logger.warning("⚠️ Возможная ошибка при сохранении конфигурации сброса.")
            
        # Перезагружаем
        self.logger.info("Перезагрузка устройства после сброса CLI...")
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
        self.logger.success("✅ Дополнительный сброс через CLI выполнен, перезагрузка инициирована...")
        
        self.parent.report_data["reset_method"] = "CLI"
        self.parent.report_data["reset_status"] = "Success"
        return True

    def perform_cli_checks(self):
        self.logger.step("🔍 Блок 6: Проверки состояния устройства в CLI")
        
        # --- Проверка 'show switch' ---
        show_switch_output = self.parent._run_show_command("show switch")
        # Здесь должна быть функция парсинга, например, из utils
        # Для демонстрации просто логируем
        self.logger.info(f"ℹ️ 'show switch' вывод: {show_switch_output[:200]}...")
        # TODO: Реализовать парсинг и запись в report_data
        
        # --- Проверка TFTP ---
        tftp_status = self._check_tftp_connectivity()
        self.parent.report_data["tftp_ping_status"] = tftp_status.get("status")
        self.parent.report_data["tftp_ip_used"] = tftp_status.get("ip")
        
        if tftp_status.get("status") != "Success":
            self.logger.warning("⚠️ TFTP недоступен. Попытка настройки IP...")
            # TODO: Реализовать настройку IP, как в Плане V7.2
            # self._setup_default_ip_config()
            # После настройки снова проверяем
            # tftp_status = self._check_tftp_connectivity()
            
        return True # Пока всегда успех для демонстрации

    def _check_tftp_connectivity(self):
        """Проверяет доступность TFTP сервера."""
        tftp_ips = self.device_cfg.get("tftp_ip_candidates", ["192.168.1.100"])
        
        for ip in tftp_ips:
            self.logger.debug(f"Пингуем TFTP сервер: {ip}")
            self.connection.send_raw(b'\r') # Очистка
            time.sleep(0.5)
            ping_cmd = f"ping {ip}"
            result = self.connection.send_command_and_wait(
                ping_cmd,
                expected_patterns=[self.patterns['PING_SUCCESS'], self.patterns['PING_FAIL'], self.patterns['PRIVILEGED_PROMPT']],
                timeout=self.timeouts['ping_wait']
            )
            
            # Прерываем, если команда зависла
            self.connection.send_raw(b'\x03') # Ctrl+C
            time.sleep(1)
            self.connection.send_raw(b'\r') # Очистка
            
            final_output = self.connection.get_last_output()
            
            import re
            if result and re.search(self.patterns['PING_SUCCESS'], final_output):
                self.logger.success(f"✅ TFTP-сервер доступен по адресу: {ip}")
                return {"status": "Success", "ip": ip}
            else:
                self.logger.debug(f"Пинг {ip} не удался.")
                
        self.logger.error("❌ TFTP-сервер недоступен!")
        return {"status": "Fail", "ip": None}

    def perform_final_checks(self):
        self.logger.step("🏁 Блок 9: Финальные проверки и завершение")
        
        # --- Вход в CLI ---
        # В Плане V7.2 это делается внутри, но мы уже вошли
        # cli_result = self.attempt_cli_entry()
        # if cli_result != "SUCCESS_PRIVILEGED":
        #     self.logger.error("❌ Не удалось войти в CLI для финальных проверок!")
        #     return False
        
        # --- Проверка Активной Прошивки ---
        # show_firmware_output = self.parent._run_show_command("show firmware information")
        # TODO: Парсинг и проверка версии
        
        # --- Очистка Старого Слота ---
        # TODO: config firmware ... delete
        
        # --- Проверка Сети ---
        # TODO: Определение IP, пинги, проверка портов, telnet логин
        
        # --- Проверка Файловой Системы ---
        dir_output = self.parent._run_show_command("dir")
        self.parent.report_data["dir_output"] = dir_output
        # TODO: Парсинг dir_output
        
        # --- Пост-Настройка ---
        post_commands = self.device_cfg.get("post_config_commands", [])
        for cmd in post_commands:
            self.logger.info(f"🔧 Выполнение пост-команды: {cmd}")
            self.connection.send_command_and_wait(cmd, expected_patterns=[self.patterns['SUCCESS_GENERIC'], self.patterns['PRIVILEGED_PROMPT']], timeout=self.timeouts['command_default'])
            # TODO: Проверка результата
        
        # --- Финальное Сохранение ---
        save_result = self.connection.send_command_and_wait("save", expected_patterns=[self.patterns['SUCCESS_GENERIC'], self.patterns['PRIVILEGED_PROMPT']], timeout=self.timeouts['command_default'])
        save_output = self.connection.get_last_output()
        if save_result and (self.patterns['SUCCESS_GENERIC'] in save_output or self.patterns['PRIVILEGED_PROMPT'] in save_output):
            self.logger.success("💾 Финальное сохранение выполнено успешно.")
        else:
            self.logger.error("❌ Ошибка при финальном сохранении.")
            return False
            
        return True
