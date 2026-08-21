from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crawler.settings import Settings
from crawler.storage import FileManager
from gui.worker import CrawlerWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Advanced Web Crawler")
        self.resize(1200, 800)
        self.settings = Settings()
        self.bridge = None
        self.worker = None

        self._setup_tabs()
        self._connect_signals()

    def _setup_tabs(self) -> None:
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.controls_tab = QWidget()
        self.config_tab = QWidget()
        self.files_tab = QWidget()
        self.tabs.addTab(self.controls_tab, "Controls")
        self.tabs.addTab(self.config_tab, "Configuration")
        self.tabs.addTab(self.files_tab, "Files")

        self._setup_controls_tab()
        self._setup_config_tab()
        self._setup_files_tab()

    def _setup_controls_tab(self) -> None:
        layout = QVBoxLayout(self.controls_tab)

        self.url_input = QLabel("Seed URL:")
        self.url_edit = QPlainTextEdit()
        self.url_edit.setPlaceholderText("https://example.com")
        self.url_edit.setMaximumHeight(60)

        self.start_btn = QPushButton("Start Crawl")
        self.stop_btn = QPushButton("Stop Crawl")
        self.stop_btn.setEnabled(False)
        self.start_btn.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold;")

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)

        self.stats_label = QLabel("Processed: 0 | Queue: 0 | Active: 0 | Speed: 0.0 pages/s | Memory: 0%")
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["URL", "Title", "Quality", "Depth", "Domain"])
        self.table.horizontalHeader().setStretchLastSection(True)

        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumHeight(200)

        layout.addWidget(self.url_input)
        layout.addWidget(self.url_edit)
        layout.addLayout(btn_layout)
        layout.addWidget(self.stats_label)
        layout.addWidget(self.table)
        layout.addWidget(self.console)

    def _setup_config_tab(self) -> None:
        layout = QFormLayout(self.config_tab)
        self.max_depth_spin = QSpinBox()
        self.max_depth_spin.setRange(1, 20)
        self.max_depth_spin.setValue(3)

        self.max_pages_spin = QSpinBox()
        self.max_pages_spin.setRange(1, 1000000)
        self.max_pages_spin.setValue(500)

        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(0, 1000)
        self.concurrency_spin.setValue(0)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 120)
        self.timeout_spin.setValue(15)

        self.output_dir_input = QLabel("crawled_data")

        self.follow_external_checkbox = QLabel("False")
        self.use_proxy_checkbox = QLabel("False")

        self.zip_extract_checkbox = QLabel("True")
        self.dedup_checkbox = QLabel("True")

        layout.addRow("Max Depth", self.max_depth_spin)
        layout.addRow("Max Pages", self.max_pages_spin)
        layout.addRow("Concurrency (0=auto)", self.concurrency_spin)
        layout.addRow("Timeout (s)", self.timeout_spin)
        layout.addRow("Output Dir", self.output_dir_input)
        layout.addRow("Follow External", self.follow_external_checkbox)
        layout.addRow("Use Proxy", self.use_proxy_checkbox)
        layout.addRow("Zip Extract", self.zip_extract_checkbox)
        layout.addRow("Enable Dedup", self.dedup_checkbox)

    def _setup_files_tab(self) -> None:
        layout = QVBoxLayout(self.files_tab)
        self.files_list = QListWidget()
        self.refresh_files_btn = QPushButton("Refresh")
        self.preview_btn = QPushButton("Preview")
        self.compress_btn = QPushButton("Compress Output")
        self.delete_btn = QPushButton("Delete Selected")

        btn_layout = QHBoxLayout()
        for btn in [self.refresh_files_btn, self.preview_btn, self.compress_btn, self.delete_btn]:
            btn_layout.addWidget(btn)

        layout.addWidget(self.files_list)
        layout.addLayout(btn_layout)

    def _connect_signals(self) -> None:
        from crawler.signals import SignalBridge

        self.bridge = SignalBridge()
        self.bridge.stats.connect(self._on_stats)
        self.bridge.console.connect(self._on_console)
        self.bridge.page.connect(self._on_page)
        self.bridge.finished.connect(self._on_finished)

        self.start_btn.clicked.connect(self.start_crawl)
        self.stop_btn.clicked.connect(self.stop_crawl)
        self.refresh_files_btn.clicked.connect(self._refresh_files)
        self.preview_btn.clicked.connect(self._preview_file)
        self.compress_btn.clicked.connect(self._compress_files)
        self.delete_btn.clicked.connect(self._delete_selected)

    def start_crawl(self) -> None:
        urls = [u.strip() for u in self.url_edit.toPlainText().splitlines() if u.strip()]
        if not urls:
            QMessageBox.warning(self, "No URL", "Enter at least one seed URL.")
            return
        self.settings.seed_urls = urls
        self.settings.max_depth = self.max_depth_spin.value()
        self.settings.max_pages = self.max_pages_spin.value()
        self.settings.concurrency = self.concurrency_spin.value()
        self.settings.timeout = float(self.timeout_spin.value())
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.worker = CrawlerWorker(self.settings, self.bridge)
        self.worker.start()

    def stop_crawl(self) -> None:
        if self.worker:
            self.worker.stop()
        self.stop_btn.setEnabled(False)
        self.start_btn.setEnabled(True)

    def _on_stats(self, data: dict) -> None:
        self.stats_label.setText(
            f"Processed: {data.get('processed', 0)} | "
            f"Queue: {data.get('queue_size', 0)} | "
            f"Active: {data.get('active_requests', 0)} | "
            f"Speed: {data.get('speed', 0.0)} pages/s | "
            f"Memory: {data.get('memory_percent', 0)}% | "
            f"Workers: {data.get('workers', 0)}"
        )

    def _on_console(self, level: str, message: str) -> None:
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        color = QColor("#ffffff")
        if level == "error":
            color = QColor("#ff5555")
        elif level == "info":
            color = QColor("#55ff55")
        elif level == "warning":
            color = QColor("#ffff55")
        fmt.setForeground(color)
        cursor.insertText(message + "\n", fmt)
        self.console.setTextCursor(cursor)
        self.console.ensureCursorVisible()

    def _on_page(self, page: dict) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(page.get("url", "")))
        self.table.setItem(row, 1, QTableWidgetItem(page.get("title", "")))
        self.table.setItem(row, 2, QTableWidgetItem(str(page.get("quality_score", 0))))
        self.table.setItem(row, 3, QTableWidgetItem(str(page.get("depth", 0))))
        self.table.setItem(row, 4, QTableWidgetItem(page.get("domain", "")))
        self.table.scrollToBottom()

    def _on_finished(self, data: dict) -> None:
        self.stop_btn.setEnabled(False)
        self.start_btn.setEnabled(True)
        self._refresh_files()

    def _refresh_files(self) -> None:
        self.files_list.clear()
        try:
            fm = FileManager(self.settings)
            for f in fm.list_files():
                self.files_list.addItem(f)
        except Exception as exc:
            self._on_console("error", f"File refresh failed: {exc}")

    def _preview_file(self) -> None:
        item = self.files_list.currentItem()
        if not item:
            return
        fm = FileManager(self.settings)
        content = fm.preview_file(item.text())
        QMessageBox.information(self, "Preview", content[:2000] if content else "Empty or binary file")

    def _compress_files(self) -> None:
        fm = FileManager(self.settings)
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        import asyncio
        result = asyncio.run(fm.compress_output())
        self._on_console("info", f"Compressed to {result}")

    def _delete_selected(self) -> None:
        item = self.files_list.currentItem()
        if not item:
            return
        fm = FileManager(self.settings)
        fm.delete_file(item.text())
        self._refresh_files()