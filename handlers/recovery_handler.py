# handlers/recovery_handler.py
"""
Обработчик для работы с режимом Password Recovery.
"""
import time
import re

class RecoveryHandler:
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

    def attempt_recovery_entry(self):
        self.logger.step("🔄 Блок 2: Попытка входа в Password Recovery Mode")
        self.logger.info("⚠️ Пожалуйста, ПЕРЕЗАГРУЗИТЕ устройство сейчас.")
        
        boot_detected = self._monitor_boot_and_send_combinations()
        
        if not boot_detected:
            self.logger.warning("⚠️ Индикаторы загрузки не найдены... Переход к CLI.")
            return "CLI_FALLBACK"

        output = self.connection.read_until_pattern(
            [p for p in self.patterns['recovery_indicators']],
            timeout=60
        )
        
        if any(ind in output for ind in self.patterns['recovery_indicators']):
            self.logger.success("✅ Успешно вошли в Password Recovery Mode!")
            
            self.connection.send_raw(b'\r')
            time.sleep(1)
            
            prompt_output = self.connection.read_until_pattern(
                [self.patterns['USER_PROMPT'], self.patterns['LOGIN_PROMPT'], self.patterns['PASSWORD_PROMPT']],
                timeout=self.timeouts['prompt_wait']
            )
            
            if self.patterns['USER_PROMPT'] in prompt_output:
                self.logger.info("✅ Доступ получен (пароля нет)!")
                self.parent.report_data["reset_method"] = "Recovery (No Password)"
                return "SUCCESS"
            elif self.patterns['LOGIN_PROMPT'] in prompt_output or self.patterns['PASSWORD_PROMPT'] in prompt_output:
                self.logger.info("ℹ️ Обнаружен запрос логина/пароля.")
                return "AUTH_NEEDED"
            else:
                self.logger.warning("⚠️ Recovery Mode не отвечает после входа.")
                return "CLI_FALLBACK"
        else:
            self.logger.warning("⚠️ Не удалось войти в Recovery Mode. Переход к CLI.")
            return "CLI_FALLBACK"

    def _monitor_boot_and_send_combinations(self):
        combinations = self.device_cfg.get("recovery_combinations", [])
        sorted_combinations = self.stats_manager.sort_by_stats(combinations, "recovery_keys")
        
        start_time = time.monotonic()
        timeout = self.timeouts['reboot_wait']
        
        while time.monotonic() - start_time < timeout:
            output = self.connection.read_available()
            if output:
                if any(ind in output for ind in self.patterns['boot_indicators']):
                    self.logger.debug(f"📥 Получен индикатор загрузки.")
                    if self.parent.interaction_start_time is None:
                        self.parent.interaction_start_time = time.monotonic()
                        self.parent.report_data["interaction_start_time"] = self.parent.interaction_start_time
                    
                    self._check_model_indicator(output)

                    for combo_data in sorted_combinations:
                        combo_bytes = bytes.fromhex(combo_data['hex'])
                        self.logger.debug(f"📤 Отправлена комбинация: {combo_data['id']} (HEX: {combo_data['hex']})")
                        self.connection.send_raw(combo_bytes)
                        time.sleep(0.5)
                    return True
            time.sleep(0.1)
        return False

    def _check_model_indicator(self, output):
        base_model_indicator = self.device_cfg.get("base_model_indicator")
        if base_model_indicator and base_model_indicator not in output:
            self.logger.error(f"❌ ОБНАРУЖЕНО НЕСООТВЕТСТВИЕ! Ожидалась модель с индикатором '{base_model_indicator}'")
            # В реальной реализации запрос (Y/N) и возможное завершение
            # answer = input("Продолжить? (Y/N): ")
            # if answer.upper() != 'Y':
            #     raise SystemExit(1)
            self.logger.warning("Продолжаем, несмотря на несоответствие (симуляция).")

    def authorize_in_recovery(self):
        self.logger.step("🔑 Блок 2.А: Авторизация в Password Recovery Mode")
        credentials_list = self.credentials.get("recovery", [])
        sorted_credentials = self.stats_manager.sort_by_stats(credentials_list, "credentials")
        
        for cred in sorted_credentials:
            login = cred['login']
            password = cred['password']
            cred_id = cred['id']
            
            self.logger.debug(f"Пробуем учетные данные: {cred_id}")
            
            self.connection.send_command_and_wait(login, expected_patterns=[self.patterns['PASSWORD_PROMPT']], timeout=self.timeouts['login_attempt'])
            self.connection.send_command_and_wait(password, expected_patterns=[self.patterns['USER_PROMPT'], self.patterns['LOGIN_FAILED_INDICATOR']], timeout=self.timeouts['login_attempt'])
            
            final_output = self.connection.get_last_output()
            if self.patterns['USER_PROMPT'] in final_output and not any(err in final_output for err in self.patterns['LOGIN_FAILED_INDICATOR']):
                self.logger.success(f"✅ Успешный вход в Recovery с учетными данными {cred_id}!")
                self.stats_manager.update_stats("credentials", cred_id, success=True)
                return True
            else:
                self.logger.debug(f"Попытка с {cred_id} не удалась.")
                self.stats_manager.update_stats("credentials", cred_id, success=False)
        
        self.logger.error("❌ Пароли для Recovery Mode не подошли.")
        return False

    def execute_recovery_reset(self):
        self.logger.step("🗑️ Блок 3: Выполнение сброса через Password Recovery Mode")
        self.parent.report_data["reset_was_performed"] = True
        
        commands = self.reset_commands.get(self.device_cfg.get("recovery_commands", "recovery"), [])
        sorted_commands = self.stats_manager.sort_by_stats(commands, "reset_commands")
        
        success_count = 0
        for cmd_data in sorted_commands:
            cmd = cmd_data['command']
            cmd_id = cmd_data['id']
            
            result = self.connection.send_command_and_wait(
                cmd,
                expected_patterns=[
                    self.patterns['SUCCESS_GENERIC'],
                    self.patterns['USER_PROMPT'],
                    self.patterns['ERROR_GENERIC'],
                    self.patterns['CONFIRM_YN']
                ],
                timeout=self.timeouts['command_default']
            )
            
            if result == self.patterns['CONFIRM_YN']:
                self.logger.debug("Обнаружено подтверждение (Y/N), отправляем Y...")
                self.connection.send_raw(b'Y\r')
                time.sleep(1)
                self.connection.send_raw(b'\r')
                time.sleep(0.5)
                self.connection.send_raw(b'\r')

            final_output = self.connection.get_last_output()
            success_found = any(s in final_output for s in self.patterns['SUCCESS_GENERIC']) or self.patterns['USER_PROMPT'] in final_output
            error_found = any(e in final_output for e in self.patterns['ERROR_GENERIC'])
            
            if success_found and not error_found:
                self.logger.success(f"✅ Команда '{cmd}' выполнена успешно!")
                self.stats_manager.update_stats("reset_commands", cmd_id, success=True)
                success_count += 1
            else:
                self.logger.warning(f"⚠️ Команда '{cmd}' не выполнена или выполнена с ошибкой.")
                self.stats_manager.update_stats("reset_commands", cmd_id, success=False)
        
        self.stats_manager.save_stats("reset_commands")
        self.stats_manager.save_stats("credentials")
        
        if success_count == 0:
            return False
            
        self.logger.info("Перезагрузка устройства после сброса...")
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
        self.logger.success("✅ Сброс выполнен, перезагрузка инициирована...")
        return True
