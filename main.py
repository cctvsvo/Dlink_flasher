# main.py
"""
Точка входа в скрипт.
Обрабатывает аргументы командной строки и запускает основной процесс.
"""
import argparse
import sys
import os

# Добавляем текущую директорию в путь поиска модулей
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dlink_reset import DLinkReset


def parse_arguments():
    """Парсит аргументы командной строки."""
    parser = argparse.ArgumentParser(description="Сброс и прошивка коммутаторов D-Link.")
    parser.add_argument("--port", required=True, help="COM-порт (например, COM3)")
    parser.add_argument("--model", required=True, help="Модель устройства (например, DES-3200-28)")
    parser.add_argument("--vendor", default="D-Link", help="Производитель (по умолчанию D-Link)")
    parser.add_argument("--force-reflash", action="store_true", help="Принудительно перепрошить, даже если версия совпадает")
    parser.add_argument("--debug", action="store_true", help="Включить подробное логирование")
    # Можно добавить другие аргументы по необходимости
    return parser.parse_args()

def main():
    """Основная точка входа."""
    args = parse_arguments()
    
    # Передаем аргументы в основной класс
    reset_tool = DLinkReset(
        port=args.port,
        model=args.model,
        vendor=args.vendor,
        force_reflash=args.force_reflash,
        debug=args.debug
    )
    
    try:
        reset_tool.run()
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
