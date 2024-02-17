""" Chat Log Processing Class """
import datetime
import re
import time
from typing import Iterator

from PySide6 import QtCore
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QKeySequence, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (QApplication, QFileDialog, QMenuBar, QTreeView,
                               QVBoxLayout, QWidget)

# log_regex = r"\[.*,(.*T.*),.*,[.*]@,@,,,[.*]\](.*)"
log_regex = r"\[.*,(.*T.*),0,.*,.*,.*,.*,.*\](.*)"
reward_regex = r"You received ([\d,]+) (.*)"
reward_regex_2 = r"Items acquired: (.*) x ([\d,]+)"


class ChatLogWidget(QWidget):
    def __init__(self):
        """Initialize a chat log instance."""
        super().__init__()

        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        # self.setWindowFlag(Qt.FramelessWindowHint, True)

        self.settings = QSettings("Numeric Received", "Numeric Received")
        self.setWindowTitle("Numeric Received")

        self.file = None

        self.menu = QMenuBar()
        self.file_menu = self.menu.addMenu("File")
        self.file_menu.addAction(
            "Open",
            QKeySequence("Ctrl+O"),
            self.open_dialog,
        )
        self.file_menu.addAction(
            "Exit",
            QKeySequence("Ctrl+Q"),
            self.exit,
        )

        self.worker_thread = None

        self.results_view = QTreeView()
        self.results_model = QStandardItemModel()
        self.results_view.setModel(self.results_model)

        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.addWidget(self.results_view)

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.menu)
        self.layout.addWidget(self.results_widget)

        self.filename = self.settings.value("filename")
        if self.filename:
            self.worker_thread = WorkerThread(self)
            self.worker_thread.set_filename(self.filename)
            self.worker_thread.start()

        self.restoreGeometry(self.settings.value("geometry"))

    @QtCore.Slot()
    def open_dialog(self):
        """Open Combat Log Dialog Box"""

        fname, _ = QFileDialog.getOpenFileName(
            self,
            "Open Log File",
            "",
            "Chat Log (*.log)",
        )
        if fname:
            self.filename = fname
            self.settings.setValue("filename", self.filename)
            if self.worker_thread:
                self.worker_thread.exit()
            self.worker_thread = WorkerThread(self)
            self.worker_thread.set_filename(self.filename)
            self.worker_thread.start()
        else:
            self.filename = None
            self.worker_thread = None

    @QtCore.Slot(dict)
    def populate(self, rewards):
        self.results_model.clear()
        self.results_model.setHorizontalHeaderLabels(["Item", "Amount"])

        for k, v in rewards.items():
            row_item = QStandardItem(k)
            row_item.setEditable(False)

            row_amount = QStandardItem(f"{v:,}")
            row_item.setEditable(False)

            self.results_model.appendRow([row_item, row_amount])

        self.results_view.resizeColumnToContents(0)

    @QtCore.Slot(int)
    def update_title(self, tup):
        dil = tup[0]
        secs = tup[1]
        if not secs:
            self.setWindowTitle("Numeric Received (not running)")
            return

        self.setWindowTitle(
            f"Numeric Received ({int(secs/3600):0>2,.0f}h {int(secs%3600/60)}m {int(secs%60)}s) ({int(dil/secs)} DPS)"
        )

    @QtCore.Slot()
    def exit(self):
        """Close Application"""
        QApplication.closeAllWindows()

    def closeEvent(self, event):
        """Close Event"""
        self.settings.setValue("geometry", self.saveGeometry())


class WorkerSignals(QtCore.QObject):
    """Signals"""

    results = QtCore.Signal(dict)
    seconds = QtCore.Signal(tuple)


class WorkerThread(QtCore.QThread):
    """Worker thread to update Popout Widget"""

    def __init__(self, parent=None):
        QtCore.QThread.__init__(self, parent)

        self.settings = QSettings("Numeric Received", "Numeric Received")
        self.running = True
        self.rewards = {}

        self.signals = WorkerSignals()
        self.signals.results.connect(parent.populate)
        self.signals.seconds.connect(parent.update_title)

    def set_filename(self, filename):
        self.filename = filename

    def follow(self, file, sleep_sec=0.1) -> Iterator[str]:
        line = ""
        while True:
            tmp = file.readline()
            if tmp is not None and tmp != "":
                line += tmp
                if line.endswith("\n"):
                    yield line
                    line = ""
            elif sleep_sec:
                if self.start:
                    if self.emit:
                        delta = datetime.datetime.utcnow() - self.start
                        self.signals.seconds.emit(
                            (
                                self.rewards.get("Dilithium Ore", 0),
                                delta.total_seconds(),
                            ),
                        )
                time.sleep(sleep_sec)

    def run(self):
        while self.running:
            self.start = datetime.datetime.utcnow()
            self.emit = False

            if not self.filename:
                time.sleep(1)
                continue

            with open(self.filename, "r+") as file:
                for line in self.follow(file):
                    match = re.match(log_regex, line)
                    if match:
                        at = datetime.datetime.strptime(
                            match.group(1),
                            "%Y%m%dT%H%M%S",
                        )
                        match2 = re.match(reward_regex, match.group(2))
                        match3 = re.match(reward_regex_2, match.group(2))
                        if match2:
                            key = match2.group(2)
                            val = int(match2.group(1).replace(",", ""))
                            if self.rewards.get(key):
                                self.rewards[key] += val
                            else:
                                self.rewards[key] = val
                            self.signals.results.emit(self.rewards)
                        elif match3:
                            key = match3.group(1)
                            val = int(match3.group(2).replace(",", ""))
                            if self.rewards.get(key):
                                self.rewards[key] += val
                            else:
                                self.rewards[key] = val
                            self.signals.results.emit(self.rewards)
                        elif "ChatLog ON" in match.group(2):
                            self.emit = True
                            self.start = at
                            self.rewards = {}
                            self.signals.results.emit(self.rewards)
                        elif "ChatLog OFF" in match.group(2):
                            self.emit = False

                    if self.emit:
                        self.last = at
                        delta = self.last - self.start
                        self.signals.seconds.emit(
                            (
                                self.rewards.get("Dilithium Ore", 0),
                                delta.total_seconds(),
                            ),
                        )

    @QtCore.Slot()
    def quit(self, event):
        self.running = False
