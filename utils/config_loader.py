# utils/config_loader.py
"""
Загрузчик и валидатор конфигурационных файлов.
"""
import json
import os

def load_all_configs(config_dir, model, vendor):
    """Загружает все конфигурационные файлы."""
    configs = {}
    
    # Загрузка основных конфигов
    main_config_files = {
        'patterns': 'patterns.json',
        'credentials': 'credentials.json',
        'reset_commands': 'reset_commands.json',
        'timeouts': 'timeouts.json',
        'firmware_info': 'firmware_info.json',
    }
    
    for key, filename in main_config_files.items():
        file_path = os.path.join(config_dir, filename)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                configs[key] = json.load(f)
        else:
            configs[key] = {}
            print(f"⚠️ Файл конфигурации не найден: {file_path}")
    
    # Загрузка конфига устройства
    device_filename = f"{vendor}_{model}.json"
    device_file_path = os.path.join(config_dir, "devices", device_filename)
    if os.path.exists(device_file_path):
        with open(device_file_path, 'r', encoding='utf-8') as f:
            configs['device'] = json.load(f)
    else:
        raise FileNotFoundError(f"❌ Конфигурационный файл для устройства {vendor} {model} не найден: {device_file_path}")

    # Слияние таймаутов, если есть дефолты и специфичные для модели (пока просто используем общие)
    # ...
    return configs

def validate_configs(device_cfg, patterns):
    """Выполняет базовую валидацию конфигов."""
    required_device_keys = ['baudrate', 'recovery_combinations']
    for key in required_device_keys:
        if key not in device_cfg:
            raise ValueError(f"Отсутствует обязательный ключ в конфигурации устройства: {key}")

    required_pattern_keys = ['boot_indicators', 'recovery_indicators', 'USER_PROMPT', 'PRIVILEGED_PROMPT']
    for key in required_pattern_keys:
        if key not in patterns:
            raise ValueError(f"Отсутствует обязательный ключ в паттернах: {key}")
