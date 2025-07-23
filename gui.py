# gui.py
"""
Графический интерфейс пользователя для скрипта сброса и прошивки D-Link.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import sys
import os
import serial.tools.list_ports
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dlink_reset import DLinkReset


class DLinkResetGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Сброс и прошивка коммутаторов D-Link")
        self.root.geometry("1000x700")

        # --- Переменные GUI ---
        self.selected_port = tk.StringVar()
        self.selected_vendor = tk.StringVar(value="D-Link")
        self.selected_model = tk.StringVar()
        self.firmware_path = tk.StringVar() # Не используется напрямую, но можно для выбора папки конфигов
        self.tftp_ip = tk.StringVar(value="192.168.1.100")
        self.force_reflash = tk.BooleanVar()
        
        # --- Состояние выполнения ---
        self.dlink_reset_instance = None
        self.is_running = False
        self.log_queue = queue.Queue()

        # --- Создание виджетов ---
        self.create_widgets()
        self.populate_initial_data()
        self.update_model_list()

    def create_widgets(self):
        # --- Заголовок ---
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill=tk.X, padx=10, pady=5)

        title_label = ttk.Label(header_frame, text="Сброс и прошивка коммутаторов D-Link", font=("Arial", 14, "bold"))
        title_label.pack(side=tk.LEFT)

        info_label = ttk.Label(header_frame,
                               text="ПО разработано для нужд Армии России\nБоец с позывным «Душнила»\nПоддержка: @zas_svo",
                               font=('Arial', 9),
                               foreground='blue', justify=tk.RIGHT)
        info_label.pack(side=tk.RIGHT)

        # --- Основной контент ---
        main_paned_window = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        main_paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # --- Верхняя панель: Настройки и Управление ---
        top_frame = ttk.Frame(main_paned_window)
        main_paned_window.add(top_frame, weight=1)

        # --- Секция Настройки ---
        settings_frame = ttk.LabelFrame(top_frame, text="Настройки", padding="10")
        settings_frame.pack(fill=tk.X, side=tk.LEFT, padx=(0, 5))

        port_frame = ttk.Frame(settings_frame)
        port_frame.pack(fill=tk.X, pady=2)
        ttk.Label(port_frame, text="COM-порт:", width=20, anchor=tk.W).pack(side=tk.LEFT)
        port_combo_frame = ttk.Frame(port_frame)
        port_combo_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.port_combo = ttk.Combobox(port_combo_frame, textvariable=self.selected_port, state="readonly")
        self.port_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(port_combo_frame, text="Обновить", command=self.update_port_list).pack(side=tk.LEFT, padx=(5, 0))

        vendor_frame = ttk.Frame(settings_frame)
        vendor_frame.pack(fill=tk.X, pady=2)
        ttk.Label(vendor_frame, text="Производитель:", width=20, anchor=tk.W).pack(side=tk.LEFT)
        self.vendor_combo = ttk.Combobox(vendor_frame, textvariable=self.selected_vendor, values=["D-Link"], state="readonly")
        self.vendor_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.vendor_combo.bind('<<ComboboxSelected>>', self.on_vendor_selected)

        model_frame = ttk.Frame(settings_frame)
        model_frame.pack(fill=tk.X, pady=2)
        ttk.Label(model_frame, text="Модель:", width=20, anchor=tk.W).pack(side=tk.LEFT)
        self.model_combo = ttk.Combobox(model_frame, textvariable=self.selected_model, state="readonly")
        self.model_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Убран выбор папки прошивок, так как конфиги встроены
        # tftp_frame = ttk.Frame(settings_frame)
        # tftp_frame.pack(fill=tk.X, pady=2)
        # ttk.Label(tftp_frame, text="IP TFTP:", width=20, anchor=tk.W).pack(side=tk.LEFT)
        # ttk.Entry(tftp_frame, textvariable=self.tftp_ip, width=20).pack(side=tk.LEFT)

        force_frame = ttk.Frame(settings_frame)
        force_frame.pack(fill=tk.X, pady=2)
        ttk.Checkbutton(force_frame, text="Принудительная перепрошивка", variable=self.force_reflash).pack(side=tk.LEFT)

        # --- Секция Управление ---
        control_frame = ttk.LabelFrame(top_frame, text="Управление", padding="10")
        control_frame.pack(fill=tk.BOTH, side=tk.RIGHT, padx=(5, 0))

        self.run_button = ttk.Button(control_frame, text="Запустить", command=self.start_process)
        self.run_button.pack(pady=5, fill=tk.X)

        self.stop_button = ttk.Button(control_frame, text="Остановить", command=self.stop_process, state='disabled')
        self.stop_button.pack(pady=5, fill=tk.X)

        self.status_label = ttk.Label(control_frame, text="Готов", foreground='blue')
        self.status_label.pack(pady=5)

        self.progress = ttk.Progressbar(control_frame, mode='indeterminate')
        self.progress.pack(pady=5, fill=tk.X)

        # --- Нижняя панель: Лог и Отчет ---
        bottom_frame = ttk.Frame(main_paned_window)
        main_paned_window.add(bottom_frame, weight=3)

        log_frame = ttk.LabelFrame(bottom_frame, text="Лог выполнения", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=(0, 5))

        self.log_text = tk.Text(log_frame, state='disabled', wrap=tk.WORD)
        log_scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)

        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        report_frame = ttk.LabelFrame(bottom_frame, text="Отчет", padding="5")
        report_frame.pack(fill=tk.BOTH, expand=True, side=tk.RIGHT, padx=(5, 0))

        self.report_text = tk.Text(report_frame, state='disabled', wrap=tk.WORD)
        report_scrollbar = ttk.Scrollbar(report_frame, orient="vertical", command=self.report_text.yview)
        self.report_text.configure(yscrollcommand=report_scrollbar.set)

        self.report_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        report_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def populate_initial_data(self):
        """Заполняет начальные данные в выпадающих списках."""
        self.update_port_list()
        self.vendor_combo['values'] = ["D-Link"]
        self.selected_vendor.set("D-Link")

    def update_port_list(self):
        """Обновляет список доступных COM-портов."""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports and not self.selected_port.get():
            self.selected_port.set(ports[0])

    def on_vendor_selected(self, event=None):
        """Обработчик выбора производителя."""
        vendor = self.selected_vendor.get()
        self.update_model_list(vendor)

    def update_model_list(self, vendor="D-Link"):
        """Обновляет список моделей в зависимости от выбранного производителя."""
        # Заглушка, в реальном проекте можно загружать из конфига
        model_map = {
            "D-Link": [
                "DES-3200-28", "DWS-3160-24TC" # Добавьте остальные поддерживаемые модели
            ]
        }
        models = model_map.get(vendor, [])
        self.model_combo['values'] = models
        if models:
            self.model_combo.set(models[0])
        else:
            self.model_combo.set("")

    def start_process(self):
        """Запускает основной процесс в отдельном потоке."""
        if self.is_running:
            messagebox.showwarning("Предупреждение", "Процесс уже запущен!")
            return

        if not self.selected_port.get():
            messagebox.showerror("Ошибка", "Не выбран COM-порт.")
            return
        if not self.selected_model.get():
            messagebox.showerror("Ошибка", "Не выбрана модель.")
            return

        self.is_running = True
        self.run_button.config(state='disabled')
        self.stop_button.config(state='normal')
        self.status_label.config(text="Запуск...", foreground='orange')
        self.progress.start()

        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state='disabled')
        self.report_text.config(state='normal')
        self.report_text.delete(1.0, tk.END)
        self.report_text.config(state='disabled')

        try:
            # Создаем экземпляр с параметрами из GUI
            self.dlink_reset_instance = DLinkReset(
                port=self.selected_port.get(),
                model=self.selected_model.get(),
                vendor=self.selected_vendor.get(),
                force_reflash=self.force_reflash.get(),
                debug=True,
                log_queue=self.log_queue
            )
        except Exception as e:
            self.log_message(f"❌ Ошибка инициализации: {e}\n", "error")
            self.on_process_finished()
            return

        threading.Thread(target=self._run_dlink_reset, daemon=True).start()
        self.check_log_queue()

    def _run_dlink_reset(self):
        """Фактический запуск процесса в потоке."""
        try:
            self.dlink_reset_instance.run()
        except Exception as e:
            self.log_queue.put(("ERROR", f"Критическая ошибка в потоке: {e}"))
        finally:
            self.log_queue.put(("FINISHED", "Процесс завершен"))

    def stop_process(self):
        """Пытается остановить процесс."""
        # TODO: Реализовать механизм остановки в DLinkReset
        self.log_message("⚠️ Попытка остановки процесса... (Функционал остановки требует реализации)\n", "warning")

    def check_log_queue(self):
        """Проверяет очередь логов и обновляет GUI."""
        try:
            while True:
                record = self.log_queue.get_nowait()
                if record[0] == "FINISHED":
                    self.on_process_finished()
                    break
                elif record[0] == "REPORT_DATA":
                    self.display_report(record[1])
                else:
                    self.log_message(record[1], record[0].lower())
        except queue.Empty:
            pass
        if self.is_running:
            self.root.after(100, self.check_log_queue)

    def log_message(self, message, level="info"):
        """Добавляет сообщение в текстовое поле лога."""
        self.log_text.config(state='normal')
        tag = level
        if tag not in self.log_text.tag_names():
            if tag == "error":
                self.log_text.tag_config(tag, foreground="red")
            elif tag == "warning":
                self.log_text.tag_config(tag, foreground="orange")
            elif tag == "success":
                self.log_text.tag_config(tag, foreground="green")
            elif tag == "step":
                self.log_text.tag_config(tag, foreground="blue", font=("Arial", 10, "bold"))

        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        self.log_text.insert(tk.END, formatted_message, (tag,))
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def display_report(self, report_data):
        """Отображает данные отчета в соответствующем поле."""
        self.report_text.config(state='normal')
        self.report_text.delete(1.0, tk.END)
        
        if not report_
            self.report_text.insert(tk.END, "Отчет отсутствует.")
            self.report_text.config(state='disabled')
            return

        report_lines = ["--- Отчет ---"]
        for key, value in report_data.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                report_lines.append(f"{key}: {value}")
            else:
                report_lines.append(f"{key}: <object>")

        self.report_text.insert(tk.END, "\n".join(report_lines))
        self.report_text.see(tk.END)
        self.report_text.config(state='disabled')

    def on_process_finished(self):
        """Вызывается при завершении процесса."""
        self.is_running = False
        self.run_button.config(state='normal')
        self.stop_button.config(state='disabled')
        self.progress.stop()
        self.status_label.config(text="Завершено", foreground='green')
        self.log_message("--- Процесс завершен ---\n", "info")


def main():
    """Точка входа для GUI."""
    root = tk.Tk()
    app = DLinkResetGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
