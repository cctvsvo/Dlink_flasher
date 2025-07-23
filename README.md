# Dlink_flasher

Программное обеспечение разрабатывается администратором канала Хроники Связи СВО - Душнилой.
Предназначено для массовой проверки и прошивки коммутаторов D-link (и других производителей в следующих версиях)

<img width="1004" height="735" alt="1" src="https://github.com/user-attachments/assets/c5e7454d-a205-4d12-9ff0-4a77fb077bb0" />

## Timeline

23.07.2025: выложена версия 0.01 c с базовым функционалом.

---

### Аннотация на русском языке

**v0.01 - Начальная реализация инструмента сброса и прошивки коммутаторов D-Link**

Этот релиз представляет собой первую рабочую версию консольного и графического инструмента, предназначенного для автоматизации процесса сброса настроек и обновления прошивки коммутаторов D-Link (таких как DES-3200, DES-3526, DES-1228, DWS-3160 и другие).

**Основные возможности:**

*   **Универсальная архитектура:** Проект построен на модульной структуре, позволяющей легко добавлять поддержку новых моделей и производителей.
*   **Многоуровневый подход к сбросу:**
    *   Попытка сброса через **Password Recovery Mode** (с подбором комбинаций и учетных данных).
    *   Альтернативный сброс и настройка через **CLI** (с подбором учетных данных).
    *   Аварийный вход через **Boot Configuration Menu** (с заглушкой для ручной настройки ZModem).
*   **Автоматическое обновление:** Проверка и обновление **PROM** и основной **прошивки** через TFTP, включая обработку промежуточных версий.
*   **Динамическая конфигурация:** Параметры для каждой модели (скорость порта, комбинации клавиш, команды сброса, информация о прошивках) хранятся в отдельных JSON-файлах.
*   **Интеллектуальное управление:** Использование статистики успеха для сортировки комбинаций, команд и учетных данных, повышая эффективность последующих попыток.
*   **Два интерфейса:** Поддержка запуска как из **командной строки (CLI)**, так и через **графический интерфейс пользователя (GUI)** на базе Tkinter.
*   **Подробное логирование:** Все этапы процесса логируются для последующего анализа.

**Цель проекта** – обеспечить надежный и автоматизированный способ восстановления коммутаторов D-Link к заводскому состоянию и загрузки целевой прошивки, минимизируя ручное вмешательство.

---

### Annotation in English

**v0.01 - Initial Implementation of the D-Link Switch Reset and Firmware Tool**

This release represents the first working version of a console and graphical tool designed to automate the process of resetting configurations and updating firmware on D-Link switches (such as DES-3200, DES-3526, DES-1228, DWS-3160, and others).

**Key Features:**

*   **Universal Architecture:** The project is built on a modular structure, making it easy to add support for new models and vendors.
*   **Multi-Level Reset Approach:**
    *   Attempt reset via **Password Recovery Mode** (with combination and credential brute-forcing).
    *   Fallback reset and configuration via **CLI** (with credential brute-forcing).
    *   Emergency entry via **Boot Configuration Menu** (with a stub for manual ZModem setup).
*   **Automatic Updates:** Verification and updating of **PROM** and main **firmware** via TFTP, including handling intermediate versions.
*   **Dynamic Configuration:** Parameters for each model (port speed, key combinations, reset commands, firmware info) are stored in separate JSON files.
*   **Smart Management:** Uses success statistics to sort combinations, commands, and credentials, increasing the efficiency of subsequent attempts.
*   **Dual Interfaces:** Supports execution from the **Command Line Interface (CLI)** as well as via a **Graphical User Interface (GUI)** based on Tkinter.
*   **Detailed Logging:** All stages of the process are logged for later analysis.

**The goal of the project** is to provide a reliable and automated way to restore D-Link switches to their factory state and upload the target firmware, minimizing manual intervention.
