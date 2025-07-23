# utils/stats_manager.py
"""
Менеджер статистики для сортировки и обновления данных.
"""
import json
import os

class StatsManager:
    def __init__(self, stats_dir):
        self.stats_dir = stats_dir
        self.stats_files = {
            "credentials": "credentials_stats.json",
            "reset_commands": "reset_commands_stats.json",
            "recovery_keys": "recovery_keys_stats.json",
        }
        self.stats_data = {}
        self._load_all_stats()

    def _load_all_stats(self):
        """Загружает всю статистику из файлов."""
        for stat_type, filename in self.stats_files.items():
            file_path = os.path.join(self.stats_dir, filename)
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    self.stats_data[stat_type] = json.load(f)
            else:
                self.stats_data[stat_type] = {}

    def _save_stats_to_file(self, stat_type):
        """Сохраняет статистику определенного типа в файл."""
        if stat_type in self.stats_files:
            file_path = os.path.join(self.stats_dir, self.stats_files[stat_type])
            with open(file_path, 'w') as f:
                json.dump(self.stats_data[stat_type], f, indent=4)

    def sort_by_stats(self, items, stat_type):
        """
        Сортирует список элементов (словарей с ключом 'id') по убыванию успехов.
        Элементы без статистики помещаются в конец.
        """
        if stat_type not in self.stats_data:
            return items
            
        def sort_key(item):
            item_id = item.get('id')
            if item_id and item_id in self.stats_data[stat_type]:
                stats = self.stats_data[stat_type][item_id]
                # Сортируем по успехам (по убыванию), затем по общему кол-ву (по возрастанию, чтобы новые были в начале)
                return (-stats.get('success', 0), stats.get('total', 0))
            return (0, float('inf')) # Элементы без статистики в конец
        
        return sorted(items, key=sort_key)

    def update_stats(self, stat_type, item_id, success):
        """Обновляет статистику для элемента."""
        if stat_type not in self.stats_data:
            self.stats_data[stat_type] = {}
            
        if item_id not in self.stats_data[stat_type]:
            self.stats_data[stat_type][item_id] = {"success": 0, "total": 0}
            
        self.stats_data[stat_type][item_id]["total"] += 1
        if success:
            self.stats_data[stat_type][item_id]["success"] += 1

    def save_stats(self, stat_type):
        """Сохраняет статистику определенного типа."""
        self._save_stats_to_file(stat_type)
