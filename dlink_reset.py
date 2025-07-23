# dlink_reset.py
"""
Основной класс оркестровки процесса сброса и прошивки.
Реализует логику переходов между состояниями согласно Плану V7.2.
"""
import time
import os
import sys
import queue
from pathlib import Path

# Импорты обработчиков и утилит
from handlers.connection import SerialConnection
from handlers import recovery_handler, cli_handler, boot_menu_handler, firmware_handler
from utils import logger, config_loader, stats_manager


class DLinkReset:
    """
    Основной класс для управления процессом сброса и прошивки.
    """
    def __init__(self, port, model, vendor="D-Link", force_reflash=False, debug=False, log_queue=None):
        self.port = port
        self.model = model
        self.vendor = vendor
        self.force_reflash = force_reflash
        self.debug = debug
        self.log_queue = log_queue # Для GUI

        # --- Инициализация путей и папок ---
        self.base_dir = Path(__file__).resolve().parent
        self.logs_dir = self.base_dir / "logs"
        self.reports_dir = self.base_dir / "reports"
        self.config_dir = self.base_dir / "config"
        self.stats_dir = self.base_dir / "stats"
        for d in [self.logs_dir, self.reports_dir, self.config_dir, self.stats_dir]:
            d.mkdir(exist_ok=True)

        # --- Инициализация логгера ---
        self.logger = logger.setup_logger(self.logs_dir, debug=self.debug)
        
        # Добавляем обработчик для очереди, если она предоставлена (для GUI)
        if self.log_queue:
            from utils.logger import QueueLogHandler
            gui_handler = QueueLogHandler(self.log_queue)
            gui_handler.setFormatter(logger.logging.Formatter('%(message)s'))
            self.logger.addHandler(gui_handler)
            if not self.debug:
                self.logger.setLevel(logger.logging.INFO)

        self.logger.info(f"--- Запуск скрипта для {self.vendor} {self.model} на порту {self.port} ---")

        # --- Загрузка конфигураций ---
        self._load_configs()

        # --- Инициализация данных отчета и статистики ---
        self.report_data = {
            "port": self.port,
            "model_requested": self.model,
            "vendor": self.vendor,
            "interaction_start_time": None,
            "interaction_duration": None,
            "reset_method": None,
            "reset_status": "Not Started",
            "reset_was_performed": False,
            "prom_reboot_initiated": False,
            "firmware_reboot_initiated": False,
            "overall_status": "Unknown",
            "model_detected": None,
            "mac_address": None,
            "prom_initial": None,
            "prom_final": None,
            "firmware_initial": None,
            "firmware_final": None,
            "firmware_slots_before_update": None,
            "tftp_ping_status": None,
            "tftp_ip_used": None,
            "active_ip": None,
            "telnet_port_status": None,
            "web_port_status": None,
            "telnet_login_status": None,
            "dir_output": None,
            "dir_parsed": None,
        }
        self.stats_manager = stats_manager.StatsManager(self.stats_dir)

        # --- Инициализация подключения ---
        self.connection = SerialConnection(self.port, self.device_cfg['baudrate'], self.logger)
        self.interaction_start_time = None 

        # --- Инициализация обработчиков ---
        self.cli_handler = cli_handler.CLIHandler(self)
        self.recovery_handler = recovery_handler.RecoveryHandler(self)
        self.boot_menu_handler = boot_menu_handler.BootMenuHandler(self)
        self.firmware_handler = firmware_handler.FirmwareHandler(self)

    def _load_configs(self):
        """Загружает все необходимые конфигурации."""
        try:
            configs = config_loader.load_all_configs(self.config_dir, self.model, self.vendor)
            
            self.device_cfg = configs['device']
            self.patterns = configs['patterns']
            self.credentials = configs['credentials']
            self.reset_commands = configs['reset_commands']
            self.timeouts = configs['timeouts']
            self.firmware_info = configs['firmware_info']
            
            config_loader.validate_configs(self.device_cfg, self.patterns)
            self.logger.info("✅ Конфигурация успешно загружена и проверена.")
        except Exception as e:
            self.logger.critical(f"❌(CRITICAL) Ошибка конфигурации: {e}")
            raise SystemExit(1)

    def run(self):
        """Основной цикл выполнения, управляющий переходами между состояниями."""
        current_state = "START"
        max_iterations = 30 # Предотвращает бесконечные циклы
        iteration = 0

        try:
            while current_state != "FINISHED" and iteration < max_iterations:
                iteration += 1
                self.logger.info(f"--- Текущее состояние: {current_state} ---")
                
                if current_state == "START":
                    self.connection.connect()
                    self.cli_handler.init_cli_handler_config()
                    current_state = "RECOVERY_ENTRY"

                elif current_state == "RECOVERY_ENTRY":
                    result = self.recovery_handler.attempt_recovery_entry()
                    if result == "SUCCESS":
                        current_state = "RECOVERY_RESET"
                    elif result == "AUTH_NEEDED":
                        current_state = "RECOVERY_AUTH"
                    elif result == "CLI_FALLBACK":
                        current_state = "CLI_ENTRY"
                    else:
                        current_state = "CLI_ENTRY"

                elif current_state == "RECOVERY_AUTH":
                    if self.recovery_handler.authorize_in_recovery():
                        self.report_data["reset_method"] = "Recovery (Password)"
                        current_state = "RECOVERY_RESET"
                    else:
                        current_state = "CLI_ENTRY"

                elif current_state == "RECOVERY_RESET":
                    if self.recovery_handler.execute_recovery_reset():
                        self.report_data["reset_status"] = "Success"
                        self.report_data["reset_was_performed"] = True
                        current_state = "CLI_ENTRY"
                    else:
                        current_state = "ERROR"

                elif current_state == "CLI_ENTRY":
                    cli_result = self.cli_handler.attempt_cli_entry()
                    if cli_result == "SUCCESS_PRIVILEGED":
                        if not self.report_data["reset_was_performed"]:
                            current_state = "CLI_RESET"
                        else:
                            current_state = "CLI_CHECKS"
                    elif cli_result == "BOOT_MENU_FALLBACK":
                        current_state = "BOOT_MENU_ENTRY"
                    else: # "FAILED"
                        current_state = "BOOT_MENU_ENTRY"

                elif current_state == "CLI_RESET":
                    if self.cli_handler.execute_cli_reset():
                        self.report_data["reset_method"] = "CLI"
                        self.report_data["reset_status"] = "Success"
                        self.report_data["reset_was_performed"] = True
                        current_state = "CLI_ENTRY"
                    else:
                        current_state = "ERROR"

                elif current_state == "BOOT_MENU_ENTRY":
                    if self.boot_menu_handler.attempt_boot_menu_entry():
                        current_state = "CLI_ENTRY"
                    else:
                        current_state = "ERROR"

                elif current_state == "CLI_CHECKS":
                    if self.cli_handler.perform_cli_checks():
                        current_state = "PROM_UPDATE"
                    else:
                        current_state = "ERROR"

                elif current_state == "PROM_UPDATE":
                    prom_result = self.firmware_handler.update_prom()
                    if prom_result == "REBOOT_NEEDED":
                        self.report_data["prom_reboot_initiated"] = True
                        current_state = "CLI_ENTRY"
                    elif prom_result == "SKIP" or prom_result == "SUCCESS":
                        current_state = "FIRMWARE_UPDATE"
                    else: # "ERROR"
                        current_state = "ERROR"

                elif current_state == "FIRMWARE_UPDATE":
                    firmware_result = self.firmware_handler.update_firmware()
                    if firmware_result == "REBOOT_NEEDED":
                        self.report_data["firmware_reboot_initiated"] = True
                        current_state = "CLI_ENTRY"
                    elif firmware_result == "SKIP" or firmware_result == "SUCCESS":
                        current_state = "FINAL_CHECKS"
                    else: # "ERROR"
                        current_state = "ERROR"

                elif current_state == "FINAL_CHECKS":
                    if self.cli_handler.perform_final_checks():
                        self.report_data["overall_status"] = "Success"
                        self.logger.info("🎉 Процесс успешно завершен!")
                    else:
                        self.report_data["overall_status"] = "Fail"
                        self.logger.warning("⚠️ Процесс завершен с ошибками.")
                    current_state = "FINISHED"

                elif current_state == "ERROR":
                    self.report_data["overall_status"] = "Fail"
                    self.logger.error("❌ Процесс прерван из-за ошибки.")
                    current_state = "FINISHED"

                elif current_state == "FINISHED":
                    pass

                else:
                    self.logger.critical(f"❌ Неизвестное состояние: {current_state}")
                    current_state = "ERROR"

        except Exception as e:
            self.logger.exception(f"❌ Необработанная ошибка в состоянии {current_state}: {e}")
            self.report_data["overall_status"] = "Fail"
            current_state = "FINISHED"
        finally:
            if self.interaction_start_time:
                self.report_data["interaction_duration"] = time.monotonic() - self.interaction_start_time

            if self.log_queue:
                try:
                    self.log_queue.put(("REPORT_DATA", self.report_data))
                except Exception as e:
                    self.logger.error(f"❌ Ошибка отправки отчета в очередь: {e}")

            # self._generate_reports()
            try:
                self.connection.disconnect()
            except:
                pass
            self.logger.info("--- Скрипт завершен ---")

    def _run_show_command(self, command):
        """Универсальный метод для выполнения команд 'show ...'."""
        self.logger.debug(f"🔍 Выполнение команды: {command}")
        result = self.connection.send_command_and_wait(
            command, 
            expected_patterns=[self.patterns['USER_PROMPT']], 
            timeout=self.timeouts['command_default']
        )
        output = self.connection.get_last_output()
        self.logger.debug(f"🔍 Вывод '{command}': {output[:100]}...")
        return output
