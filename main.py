
import sys
import os
import ctypes
import subprocess
import time
from pathlib import Path

import a2s

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QPoint
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QFileDialog,
    QMessageBox,
    QVBoxLayout,
    QHBoxLayout,
    QInputDialog,
)

# ==================================================
# 1. НАСТРОЙКИ ЛАУНЧЕРА
# ==================================================

APP_TITLE = "SHINRY LAUNCHER"

BASE_DIR = Path(__file__).resolve().parent
BACKGROUND_PATH = BASE_DIR / "background.png"
SERVER_FILE = BASE_DIR / "Servers.txt"

SELECTED_SERVER_INTERVAL = 10
OTHER_SERVERS_INTERVAL = 60
SCHEDULER_INTERVAL = 500

BUILTIN_SERVERS = [
    {"address": "185.71.66.87:28021"},
    {"address": "185.71.66.223:28015"},
    {"address": "185.71.66.87:28015"},
    {"address": "185.71.66.87:28019"},
    {"address": "185.71.66.223:28019"},
    {"address": "185.71.66.223:28098"},
    {"address": "185.71.66.87:28024"},
    {"address": "185.71.66.87:28021"},
    {"address": "185.71.66.223:28100"},
    {"address": "185.71.66.87:28020"},
    {"address": "185.71.66.223:28102"},
    {"address": "185.71.66.87:28023"},
    {"address": "185.71.66.223:28017"},
]

ECON_CONFIG = """
joystick 0

mat_picmip 2
mat_antialias 0
mat_forceaniso 1
mat_hdr_level 0
mat_specular 0
mat_bumpmap 0
mat_colorcorrection 0

r_3dsky 0
r_shadows 0

mat_reduceparticles 1

r_cheapwaterstart 1
r_cheapwaterend 1
r_waterdrawreflection 0
r_waterforcereflectentities 0

fps_max 60
"""

ECON_TOOLTIP_TEXT = (
    "ЭКОНОМ-РЕЖИМ\n\n"
    "Снижает некоторые графические настройки "
    "Garry's Mod, чтобы уменьшить нагрузку "
    "на компьютер и повысить стабильность FPS.\n\n"
    "При выключенном режиме игра запускается "
    "без дополнительного эконом-конфига."
)


# ==================================================
# 2. АВТОМАТИЧЕСКИЙ ПОИСК STEAM
# ==================================================

def is_valid_steam_folder(folder):
    try:
        path = Path(folder).expanduser()

        if path.is_file() and path.name.lower() == "steam.exe":
            return path

        exe = path / "steam.exe"

        if exe.is_file():
            return exe

    except (OSError, ValueError):
        pass

    return None


def get_registry_steam_paths():
    paths = []

    if os.name != "nt":
        return paths

    try:
        import winreg

        registry_locations = [
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam"),
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\WOW6432Node\Valve\Steam"
            ),
        ]

        registry_views = [
            winreg.KEY_WOW64_64KEY,
            winreg.KEY_WOW64_32KEY,
        ]

        for hive, key_path in registry_locations:
            for view in registry_views:
                try:
                    with winreg.OpenKey(
                        hive,
                        key_path,
                        0,
                        winreg.KEY_READ | view
                    ) as key:

                        for value_name in ("SteamPath", "InstallPath"):
                            try:
                                value, _ = winreg.QueryValueEx(
                                    key,
                                    value_name
                                )

                                if value:
                                    paths.append(value)

                            except OSError:
                                pass

                except OSError:
                    pass

    except ImportError:
        pass

    return paths


def get_common_steam_paths():
    paths = []

    program_files = os.environ.get("ProgramFiles")
    program_files_x86 = os.environ.get("ProgramFiles(x86)")
    program_w6432 = os.environ.get("ProgramW6432")
    local_app_data = os.environ.get("LOCALAPPDATA")

    if program_files:
        paths.append(Path(program_files) / "Steam")

    if program_files_x86:
        paths.append(Path(program_files_x86) / "Steam")

    if program_w6432:
        paths.append(Path(program_w6432) / "Steam")

    if local_app_data:
        paths.append(
            Path(local_app_data) / "Programs" / "Steam"
        )

    paths.extend([
        Path("C:/Steam"),
        Path("D:/Steam"),
        Path("E:/Steam"),
    ])

    return paths


def get_local_drives():
    drives = []

    if os.name != "nt":
        return drives

    try:
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()

        for letter_index in range(26):
            if not (bitmask & (1 << letter_index)):
                continue

            drive_letter = chr(ord("A") + letter_index)
            drive = f"{drive_letter}:\\"

            drive_type = ctypes.windll.kernel32.GetDriveTypeW(
                ctypes.c_wchar_p(drive)
            )

            if drive_type in (2, 3):
                drives.append(drive)

    except Exception as error:
        print(f"[STEAM SEARCH] Ошибка получения дисков: {error}")

    return drives


class SteamSearchWorker(QThread):
    found = Signal(str)
    search_finished = Signal(bool)

    def run(self):
        print("[STEAM SEARCH] Начинаю поиск Steam...")

        checked = set()

        for folder in get_registry_steam_paths():
            try:
                normalized = str(Path(folder).resolve()).lower()

                if normalized in checked:
                    continue

                checked.add(normalized)

                steam_exe = is_valid_steam_folder(folder)

                if steam_exe:
                    print(f"[STEAM SEARCH] Найден через реестр: {steam_exe}")
                    self.found.emit(str(steam_exe.parent))
                    self.search_finished.emit(True)
                    return

            except (OSError, ValueError):
                pass

        for folder in get_common_steam_paths():
            try:
                normalized = str(folder.resolve()).lower()

                if normalized in checked:
                    continue

                checked.add(normalized)

                steam_exe = is_valid_steam_folder(folder)

                if steam_exe:
                    print(f"[STEAM SEARCH] Найден в стандартной папке: {steam_exe}")
                    self.found.emit(str(steam_exe.parent))
                    self.search_finished.emit(True)
                    return

            except (OSError, ValueError):
                pass

        drives = get_local_drives()

        if not drives:
            print("[STEAM SEARCH] Не удалось получить список дисков.")
            self.search_finished.emit(False)
            return

        print(f"[STEAM SEARCH] Найдено дисков для проверки: {len(drives)}")

        for drive in drives:
            print(f"[STEAM SEARCH] Сканирую диск {drive}")

            try:
                for root, directories, files in os.walk(
                    drive,
                    topdown=True,
                    followlinks=False,
                    onerror=lambda error: None
                ):
                    for filename in files:
                        if filename.lower() == "steam.exe":
                            steam_exe = Path(root) / filename

                            if steam_exe.is_file():
                                print(f"[STEAM SEARCH] Найден Steam: {steam_exe}")
                                self.found.emit(str(steam_exe.parent))
                                self.search_finished.emit(True)
                                return

            except (PermissionError, OSError) as error:
                print(f"[STEAM SEARCH] Не удалось просканировать {drive}: {error}")

        print("[STEAM SEARCH] Steam не найден.")
        self.search_finished.emit(False)


# ==================================================
# 3. РАБОТА С АДРЕСАМИ СЕРВЕРОВ
# ==================================================

def parse_address(address):
    if not address:
        return None

    address = str(address).strip()

    if not address or "ВСТАВЬ" in address.upper():
        return None

    if any(character.isspace() for character in address):
        return None

    try:
        ip, port = address.rsplit(":", 1)
        port = int(port)

        if not ip or not (1 <= port <= 65535):
            return None

        return ip, port

    except (ValueError, TypeError):
        return None


def normalize_address(address):
    return str(address).strip().lower()


# ==================================================
# 4. ПОДСКАЗКА ЭКОНОМ-РЕЖИМА
# ==================================================

class HoverTooltip(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("economyTooltip")

        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            False
        )

        self.setAutoFillBackground(True)

        self.setStyleSheet("""
            QFrame#economyTooltip {
                background-color: #111111;
                border: 2px solid #A56BD2;
                border-radius: 10px;
            }
        """)

        self.text_label = QLabel(ECON_TOOLTIP_TEXT)
        self.text_label.setWordWrap(True)
        self.text_label.setFixedWidth(296)

        self.text_label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: transparent;
                border: none;
                font-size: 13px;
                font-weight: 500;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(0)
        layout.addWidget(self.text_label)

        self.setFixedWidth(330)

        self.adjust_tooltip_size()
        self.hide()

    def adjust_tooltip_size(self):
        self.text_label.setFixedWidth(296)
        self.text_label.adjustSize()

        self.layout().activate()

        text_height = self.text_label.heightForWidth(296)

        if text_height < 0:
            text_height = self.text_label.sizeHint().height()

        margins = self.layout().contentsMargins()

        total_height = (
            text_height
            + margins.top()
            + margins.bottom()
        )

        self.resize(330, total_height + 4)

    def show_for(self, widget):
        self.adjust_tooltip_size()

        button_position = widget.mapToGlobal(QPoint(0, 0))

        x = button_position.x() - self.width() - 12
        y = button_position.y()

        screen = widget.screen()

        if screen:
            available = screen.availableGeometry()

            x = max(available.left() + 5, x)

            max_y = max(
                available.top() + 5,
                available.bottom() - self.height() - 5
            )

            y = max(
                available.top() + 5,
                min(y, max_y)
            )

        self.move(x, y)
        self.show()
        self.raise_()


# ==================================================
# 5. КНОПКА С ПОДСКАЗКОЙ
# ==================================================

class HelpButton(QPushButton):
    def __init__(self, tooltip):
        super().__init__("?")

        self.tooltip = tooltip

        self.setFixedSize(38, 38)

        self.setStyleSheet("""
            QPushButton {
                color: white;
                background: #39234f;
                border: 1px solid #9871bb;
                border-radius: 19px;
                font-size: 19px;
                font-weight: bold;
            }

            QPushButton:hover {
                background: #68418a;
            }
        """)

    def enterEvent(self, event):
        self.tooltip.show_for(self)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.tooltip.hide()
        super().leaveEvent(event)


# ==================================================
# 6. ПРОВЕРКА СЕРВЕРА
# ==================================================

class ServerWorker(QThread):
    result_ready = Signal(int, object)

    def __init__(self, index, server):
        super().__init__()

        self.index = index
        self.server = server

    def run(self):
        result = None

        try:
            parsed = parse_address(self.server["address"])

            if parsed is not None:
                ip, port = parsed

                info = a2s.info(
                    (ip, port),
                    timeout=3.0
                )

                server_name = str(
                    getattr(info, "server_name", "") or ""
                ).strip()

                players = info.player_count
                maximum = info.max_players

                result = (
                    server_name,
                    players,
                    maximum
                )

        except Exception as error:
            print(f"[SERVER {self.index}] Ошибка: {error}")

        self.result_ready.emit(self.index, result)


# ==================================================
# 7. ФОНОВОЕ ИЗОБРАЖЕНИЕ
# ==================================================

class BackgroundWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.background = QPixmap(str(BACKGROUND_PATH))

    def paintEvent(self, event):
        painter = QPainter(self)

        if not self.background.isNull():
            painter.setRenderHint(
                QPainter.RenderHint.SmoothPixmapTransform
            )

            painter.drawPixmap(
                self.rect(),
                self.background
            )

        else:
            painter.fillRect(
                self.rect(),
                Qt.GlobalColor.darkGray
            )


# ==================================================
# 8. ГЛАВНОЕ ОКНО
# ==================================================

class ShinryLauncher(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(APP_TITLE)

        self.resize(1366, 768)
        self.setMinimumSize(1000, 600)

        self.workers = {}
        self.next_check = {}
        self.server_results = {}
        self.server_names = {}

        self.servers = [
            server.copy()
            for server in BUILTIN_SERVERS
        ]

        self.steam_path_manually_changed = False

        self.steam_path = QLineEdit()
        self.steam_path.setPlaceholderText(
            "Автоматический поиск Steam..."
        )

        self.economy = QCheckBox("Эконом")
        self.server_box = QComboBox()

        self.economy_tooltip = HoverTooltip()

        self.load_extra_servers()

        self.create_interface()
        self.load_servers()

        self.server_box.currentIndexChanged.connect(
            self.on_server_changed
        )

        self.steam_path.textEdited.connect(
            self.on_steam_path_edited
        )

        self.start_steam_search()

        current_time = time.monotonic()

        for index in range(len(self.servers)):
            self.next_check[index] = current_time

        self.refresh_servers()

        self.server_timer = QTimer(self)
        self.server_timer.timeout.connect(
            self.refresh_servers
        )

        self.server_timer.start(SCHEDULER_INTERVAL)

    # ==================================================
    # ЗАГРУЗКА ДОПОЛНИТЕЛЬНЫХ СЕРВЕРОВ
    # ==================================================

    def load_extra_servers(self):
        print(f"[SERVERS] Файл серверов: {SERVER_FILE}")

        try:
            if not SERVER_FILE.exists():
                SERVER_FILE.write_text("", encoding="utf-8")

            content = SERVER_FILE.read_text(encoding="utf-8-sig")

        except OSError as error:
            print(f"[SERVERS] Не удалось прочитать файл: {error}")
            return

        existing_addresses = {
            normalize_address(server["address"])
            for server in self.servers
        }

        loaded_count = 0

        for line_number, line in enumerate(content.splitlines(), start=1):
            address = line.strip()

            if not address or address.startswith("#"):
                continue

            if parse_address(address) is None:
                print(
                    f"[SERVERS] Пропущена неправильная строка "
                    f"{line_number}: {address}"
                )
                continue

            normalized = normalize_address(address)

            if normalized in existing_addresses:
                print(f"[SERVERS] Дубликат пропущен: {address}")
                continue

            self.servers.append({"address": address})
            existing_addresses.add(normalized)
            loaded_count += 1

        print(f"[SERVERS] Загружено дополнительных серверов: {loaded_count}")
        print(f"[SERVERS] Всего серверов: {len(self.servers)}")

    # ==================================================
    # ДОБАВЛЕНИЕ НОВОГО СЕРВЕРА
    # ==================================================

    def add_server(self):
        address, accepted = QInputDialog.getText(
            self,
            "Добавить сервер",
            "Введи адрес сервера в формате IP:PORT:",
            QLineEdit.EchoMode.Normal
        )

        if not accepted:
            return

        address = address.strip()

        if not address:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Ты не ввёл адрес сервера."
            )
            return

        if parse_address(address) is None:
            QMessageBox.warning(
                self,
                "Неправильный адрес",
                "Проверь адрес сервера.\n\n"
                "Нужен формат IP:PORT.\n"
                "Например: 185.71.66.87:28021"
            )
            return

        normalized = normalize_address(address)

        for server in self.servers:
            if normalize_address(server["address"]) == normalized:
                QMessageBox.information(
                    self,
                    "Сервер уже существует",
                    "Этот сервер уже есть в списке."
                )
                return

        try:
            with SERVER_FILE.open("a", encoding="utf-8") as file:
                file.write(address + "\n")

        except OSError as error:
            QMessageBox.critical(
                self,
                "Ошибка сохранения",
                "Не удалось сохранить сервер в файл Servers.txt.\n\n"
                f"Причина: {error}"
            )
            return

        new_index = len(self.servers)

        self.servers.append({"address": address})
        self.next_check[new_index] = time.monotonic()

        self.server_box.addItem(
            f"Сервер №{new_index + 1} — проверка...",
            new_index
        )

        self.server_box.setCurrentIndex(new_index)

        self.refresh_servers()

        QMessageBox.information(
            self,
            "Сервер добавлен",
            "Сервер успешно добавлен!\n\n"
            "Он сохранён в Servers.txt и останется "
            "в списке после перезапуска лаунчера."
        )

        print(f"[SERVERS] Добавлен новый сервер: {address}")

    # ==================================================
    # АВТОМАТИЧЕСКИЙ ПОИСК STEAM
    # ==================================================

    def start_steam_search(self):
        self.steam_search_worker = SteamSearchWorker()

        self.steam_search_worker.found.connect(
            self.on_steam_found
        )

        self.steam_search_worker.search_finished.connect(
            self.on_steam_search_finished
        )

        self.steam_search_worker.start()

    def on_steam_found(self, folder):
        if self.steam_path_manually_changed:
            return

        self.steam_path.setText(folder)

        print(f"[STEAM] Автоматически выбран путь: {folder}")

    def on_steam_search_finished(self, success):
        if success:
            print("[STEAM] Поиск завершён. Steam найден.")
        else:
            print("[STEAM] Steam автоматически найти не удалось.")

            if not self.steam_path_manually_changed:
                self.steam_path.setPlaceholderText(
                    "Steam не найден. Укажи путь вручную."
                )

    def on_steam_path_edited(self, text):
        self.steam_path_manually_changed = True

    # ==================================================
    # СОЗДАНИЕ ИНТЕРФЕЙСА
    # ==================================================

    def create_interface(self):
        background = BackgroundWidget()
        self.setCentralWidget(background)

        main_layout = QVBoxLayout(background)
        main_layout.setContentsMargins(40, 25, 40, 20)
        main_layout.setSpacing(12)

        title_layout = QHBoxLayout()

        title = QLabel("SHINRY LAUNCHER")
        title.setStyleSheet("""
            color: white;
            font-size: 36px;
            font-weight: bold;
        """)

        title_layout.addWidget(title)
        title_layout.addStretch()

        self.add_server_button = QPushButton("+ ДОБАВИТЬ СЕРВЕР")
        self.add_server_button.setMinimumHeight(42)

        self.add_server_button.setStyleSheet("""
            QPushButton {
                color: white;
                background: #39234f;
                border: 1px solid #9871bb;
                border-radius: 9px;
                padding: 8px 18px;
                font-size: 14px;
                font-weight: bold;
            }

            QPushButton:hover {
                background: #68418a;
                border: 1px solid #c69ae8;
            }

            QPushButton:pressed {
                background: #281737;
            }
        """)

        self.add_server_button.clicked.connect(self.add_server)
        title_layout.addWidget(self.add_server_button)

        main_layout.addLayout(title_layout)

        subtitle = QLabel("Community Launcher  •  1.0")
        subtitle.setStyleSheet("""
            color: #d4c5e7;
            font-size: 14px;
        """)

        main_layout.addWidget(subtitle)

        steam_label = QLabel("Путь к Steam:")
        steam_label.setStyleSheet("""
            color: white;
            font-size: 17px;
            font-weight: bold;
        """)

        self.steam_path.setMinimumHeight(42)
        self.steam_path.setStyleSheet("""
            QLineEdit {
                color: white;
                background: rgba(15, 12, 27, 220);
                border: 1px solid #76549b;
                border-radius: 9px;
                padding: 8px;
                font-size: 15px;
            }
        """)

        browse_button = QPushButton("Обзор")
        browse_button.setMinimumHeight(42)
        browse_button.clicked.connect(self.choose_steam)

        browse_button.setStyleSheet("""
            QPushButton {
                color: white;
                background: #39234f;
                border: 1px solid #76549b;
                border-radius: 9px;
                padding: 8px 18px;
                font-size: 15px;
            }

            QPushButton:hover {
                background: #583477;
            }
        """)

        steam_layout = QHBoxLayout()
        steam_layout.addWidget(self.steam_path)
        steam_layout.addWidget(browse_button)

        main_layout.addWidget(steam_label)
        main_layout.addLayout(steam_layout)

        controls_layout = QHBoxLayout()

        self.play_button = QPushButton("▶   ЗАПУСК")
        self.play_button.setMinimumHeight(100)

        self.play_button.setStyleSheet("""
            QPushButton {
                color: white;
                background: #873ac4;
                border: none;
                border-radius: 14px;
                font-size: 30px;
                font-weight: bold;
            }

            QPushButton:hover {
                background: #9b50d7;
            }

            QPushButton:pressed {
                background: #64269b;
            }
        """)

        self.play_button.clicked.connect(self.launch_game)
        controls_layout.addWidget(self.play_button, 4)

        economy_layout = QVBoxLayout()

        self.question_button = HelpButton(self.economy_tooltip)

        self.economy.setMinimumHeight(65)
        self.economy.setStyleSheet("""
            QCheckBox {
                color: white;
                background: rgba(15, 12, 27, 225);
                border: 1px solid #76549b;
                border-radius: 10px;
                padding: 12px;
                font-size: 20px;
                font-weight: bold;
            }

            QCheckBox::indicator {
                width: 24px;
                height: 24px;
            }

            QCheckBox::indicator:unchecked {
                background: #554465;
                border-radius: 12px;
            }

            QCheckBox::indicator:checked {
                background: #a44be0;
                border-radius: 12px;
            }
        """)

        economy_layout.addWidget(
            self.question_button,
            alignment=Qt.AlignmentFlag.AlignRight
        )

        economy_layout.addWidget(self.economy)
        controls_layout.addLayout(economy_layout, 1)

        main_layout.addLayout(controls_layout)

        server_label = QLabel("Выбор сервера:")
        server_label.setStyleSheet("""
            color: white;
            font-size: 19px;
            font-weight: bold;
        """)

        self.server_box.setMinimumHeight(55)
        self.server_box.setStyleSheet("""
            QComboBox {
                color: white;
                background: rgba(15, 12, 27, 235);
                border: 1px solid #76549b;
                border-radius: 10px;
                padding: 10px;
                font-size: 17px;
            }

            QComboBox:hover {
                border: 1px solid #a56bd2;
            }

            QComboBox QAbstractItemView {
                color: white;
                background: #171322;
                selection-background-color: #873ac4;
                border: 1px solid #76549b;
                padding: 5px;
            }
        """)

        main_layout.addWidget(server_label)
        main_layout.addWidget(self.server_box)
        main_layout.addStretch()

        footer = QLabel(
            "Shinry Launcher v1.0"
            "   |   Performance Edition"
        )

        footer.setStyleSheet("""
            color: #d4c5e7;
            font-size: 13px;
        """)

        main_layout.addWidget(footer)

    # ==================================================
    # РУЧНОЙ ВЫБОР STEAM
    # ==================================================

    def choose_steam(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Выбери папку Steam",
            self.steam_path.text()
        )

        if folder:
            self.steam_path_manually_changed = True
            self.steam_path.setText(folder)

    # ==================================================
    # НАЗВАНИЕ СЕРВЕРА
    # ==================================================

    def get_server_name(self, index):
        name = self.server_names.get(index)

        if name:
            return name

        return f"Сервер №{index + 1}"

    # ==================================================
    # ЗАГРУЗКА СПИСКА СЕРВЕРОВ
    # ==================================================

    def load_servers(self):
        self.server_box.clear()

        for index, server in enumerate(self.servers):
            address = server["address"]
            name = self.get_server_name(index)

            if parse_address(address) is None:
                status = "Адрес не задан"
            else:
                status = "ожидание проверки..."

            self.server_box.addItem(
                f"{name} — {status}",
                index
            )

    # ==================================================
    # СМЕНА ВЫБРАННОГО СЕРВЕРА
    # ==================================================

    def on_server_changed(self, selected_index):
        if selected_index < 0:
            return

        current_time = time.monotonic()

        self.next_check[selected_index] = current_time

        for index in range(len(self.servers)):
            if index != selected_index:
                self.next_check[index] = (
                    current_time + OTHER_SERVERS_INTERVAL
                )

        print(
            f"[SERVER] Приоритет: "
            f"{self.get_server_name(selected_index)}"
        )

        self.refresh_servers()

    # ==================================================
    # ПЛАНИРОВЩИК ПРОВЕРКИ СЕРВЕРОВ
    # ==================================================

    def refresh_servers(self):
        current_time = time.monotonic()
        selected_index = self.server_box.currentIndex()

        for index, server in enumerate(self.servers):
            if index in self.workers:
                continue

            check_time = self.next_check.get(
                index,
                current_time
            )

            if current_time < check_time:
                continue

            if index == selected_index:
                interval = SELECTED_SERVER_INTERVAL
            else:
                interval = OTHER_SERVERS_INTERVAL

            self.next_check[index] = current_time + interval

            self.start_server_check(index, server)

    # ==================================================
    # ЗАПУСК ОТДЕЛЬНОЙ ПРОВЕРКИ
    # ==================================================

    def start_server_check(self, index, server):
        if index in self.workers:
            return

        parsed = parse_address(server["address"])

        if parsed is None:
            self.server_results[index] = None
            self.set_server_text(
                index,
                f"{self.get_server_name(index)} — Адрес не задан"
            )
            return

        self.set_server_text(
            index,
            f"{self.get_server_name(index)} — проверка..."
        )

        print(f"[SERVER] Проверка: {server['address']}")

        worker = ServerWorker(index, server)
        self.workers[index] = worker

        worker.result_ready.connect(self.update_server_info)

        worker.finished.connect(
            lambda idx=index, current_worker=worker:
            self.worker_finished(idx, current_worker)
        )

        worker.start()

    # ==================================================
    # ПОЛУЧЕНИЕ РЕЗУЛЬТАТА
    # ==================================================

    def update_server_info(self, index, result):
        if index < 0 or index >= len(self.servers):
            return

        self.server_results[index] = result

        if result is None:
            name = self.get_server_name(index)
            text = f"{name} — Информация недоступна"

            print(f"[SERVER] {name}: информация недоступна")

        else:
            server_name, players, maximum = result

            if server_name:
                self.server_names[index] = server_name

            name = self.get_server_name(index)

            text = f"{name} — {players} / {maximum} игроков"

            print(f"[SERVER] Получено название: {name}")
            print(f"[SERVER] Онлайн: {players}/{maximum}")

        self.set_server_text(index, text)

    # ==================================================
    # ОБНОВЛЕНИЕ ТЕКСТА
    # ==================================================

    def set_server_text(self, index, text):
        if 0 <= index < self.server_box.count():
            self.server_box.setItemText(index, text)

    # ==================================================
    # ЗАВЕРШЕНИЕ ПОТОКА СЕРВЕРА
    # ==================================================

    def worker_finished(self, index, worker):
        if self.workers.get(index) is worker:
            self.workers.pop(index, None)

        worker.deleteLater()

        print(
            f"[SERVER] Проверка завершена: "
            f"{self.get_server_name(index)}"
        )

    # ==================================================
    # ЗАПУСК GARRY'S MOD
    # ==================================================

    def launch_game(self):
        steam_folder = Path(
            self.steam_path.text().strip().strip('"')
        )

        if (
            steam_folder.is_file()
            and steam_folder.name.lower() == "steam.exe"
        ):
            steam_exe = steam_folder
            steam_folder = steam_folder.parent
        else:
            steam_exe = steam_folder / "steam.exe"

        if not steam_exe.is_file():
            QMessageBox.warning(
                self,
                "Ошибка",
                "Не найден steam.exe.\n\n"
                f"Проверенный путь:\n{steam_exe}\n\n"
                "Дождись окончания автоматического поиска "
                "или укажи папку Steam вручную."
            )
            return

        selected_index = self.server_box.currentIndex()

        if selected_index < 0:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Выбери сервер."
            )
            return

        server = self.servers[selected_index]
        address = server["address"]

        parsed = parse_address(address)

        if parsed is None:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Адрес выбранного сервера "
                "не заполнен или имеет неправильный формат.\n\n"
                "Нужен формат IP:PORT."
            )
            return

        gmod_folder = (
            steam_folder
            / "steamapps"
            / "common"
            / "GarrysMod"
        )

        cfg_folder = (
            gmod_folder
            / "garrysmod"
            / "cfg"
        )

        if not gmod_folder.exists():
            QMessageBox.warning(
                self,
                "Garry's Mod не найден",
                "Не удалось найти Garry's Mod "
                "в стандартной библиотеке Steam.\n\n"
                "Если игра находится в другой "
                "библиотеке, пока запуск невозможен "
                "через этот путь."
            )
            return

        # ==================================================
        # ПАРАМЕТРЫ ЗАПУСКА
        # ==================================================

        arguments = [
            str(steam_exe),
            "-applaunch",
            "4000",

            # Включаем консоль разработчика.
            "-console",

            # Разрешаем ввод команд в консоль.
            "+con_enable",
            "1",

            # Подключаемся к выбранному серверу.
            "+connect",
            address
        ]

        if self.economy.isChecked():
            if not cfg_folder.exists():
                QMessageBox.warning(
                    self,
                    "Ошибка",
                    "Не найдена папка cfg Garry's Mod."
                )
                return

            config_file = cfg_folder / "shinry_econom.cfg"

            try:
                config_file.write_text(
                    ECON_CONFIG.strip(),
                    encoding="utf-8"
                )

            except OSError as error:
                QMessageBox.critical(
                    self,
                    "Ошибка записи конфига",
                    str(error)
                )
                return

            arguments += [
                "+exec",
                "shinry_econom.cfg"
            ]

        print("[LAUNCH] Команда запуска:")
        print(arguments)

        try:
            subprocess.Popen(
                arguments,
                cwd=str(steam_folder)
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Ошибка запуска",
                str(error)
            )

    # ==================================================
    # ЗАКРЫТИЕ ПРИЛОЖЕНИЯ
    # ==================================================

    def closeEvent(self, event):
        if hasattr(self, "steam_search_worker"):
            if self.steam_search_worker.isRunning():
                self.steam_search_worker.wait()

        for worker in list(self.workers.values()):
            if worker.isRunning():
                worker.wait(3500)

        event.accept()


# ==================================================
# 9. ЗАПУСК ПРИЛОЖЕНИЯ
# ==================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)

    app.setApplicationName(APP_TITLE)

    window = ShinryLauncher()
    window.show()

    sys.exit(app.exec())
