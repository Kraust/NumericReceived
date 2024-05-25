""" Chat Log Processing Class """
import datetime
import json
import os
import re
import time
from typing import Iterator

from PySide6 import QtCore
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import (QClipboard, QKeySequence, QStandardItem,
                           QStandardItemModel)
from PySide6.QtWidgets import (QApplication, QFileDialog, QMenuBar, QTreeView,
                               QVBoxLayout, QWidget, QLabel)

# log_regex = r"\[.*,(.*T.*),.*,[.*]@,@,,,[.*]\](.*)"
log_regex = r"\[.*,(.*T.*),0,.*,.*,.*,.*,.*\](.*)"
reward_regex = r"You received ([\d,]+) (.*)"
reward_regex_2 = r"Items acquired: (.*) x ([\d,]+)"
reward_regex_3 = r"Item acquired: (.*)"


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
            "Copy",
            QKeySequence("Ctrl+C"),
            self.copy_summary,
        )
        self.file_menu.addAction(
            "Save",
            QKeySequence("Ctrl+S"),
            self.save_dialog,
        )
        self.file_menu.addAction(
            "Exit",
            QKeySequence("Ctrl+Q"),
            self.exit,
        )

        self.clipboard = QClipboard()

        self.worker_thread = None

        self.results_view = QTreeView()
        self.results_model = QStandardItemModel()
        self.results_view.setModel(self.results_model)

        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.addWidget(self.results_view)

        self.label = QLabel()
        self.label.setText("Numeric Received")

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.menu)
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.results_widget)

        self.filename = self.settings.value("filename")
        if self.filename:
            self.worker_thread = WorkerThread(self)
            self.worker_thread.set_filename(self.filename)
            self.worker_thread.start()

        self.restoreGeometry(self.settings.value("geometry"))

    @QtCore.Slot()
    def open_dialog(self):
        """Open Chat Log Dialog Box"""

        open_dir = self.settings.value("open_dir")
        fname, _ = QFileDialog.getOpenFileName(
            self,
            "Open Log File",
            dir=open_dir,
            options=QFileDialog.DontUseNativeDialog,
        )
        if fname:
            self.filename = fname
            self.settings.setValue("filename", self.filename)
            self.settings.setValue("open_dir", os.path.dirname(self.filename))
            if self.worker_thread:
                self.worker_thread.exit()
            self.worker_thread = WorkerThread(self)
            self.worker_thread.set_filename(self.filename)
            self.worker_thread.start()
        else:
            self.filename = None
            self.worker_thread = None

    @QtCore.Slot()
    def copy_summary(self):
        """Save Chat Log Metadata"""
        secs = self.results.get("duration")
        dil = self.results.get("rewards", {}).get("Dilithium Ore", 0)
        self.clipboard.setText(
            f"NR ({int(secs/3600):0>2}h {int(secs%3600/60):0>2}m {int(secs%60)}s) - {int(dil/secs):0>2} DPS",
            mode=QClipboard.Mode.Clipboard,
        )

    @QtCore.Slot()
    def save_dialog(self):
        """Save Chat Log Metadata"""

        save_dir = self.settings.value("save_dir")
        fname, _ = QFileDialog.getSaveFileName(
            self,
            "Save Log Metadata",
            dir=os.path.join(save_dir, f"{self.results['start']}.json"),
            options=QFileDialog.DontUseNativeDialog,
        )

        if fname:
            self.settings.setValue("save_dir", os.path.dirname(fname))
            with open(fname, "w") as file:
                file.write(json.dumps(self.results))

    @QtCore.Slot(dict)
    def populate(self, results):
        self.results_model.clear()
        self.results_model.setHorizontalHeaderLabels(["Item", "Amount"])
        self.results = results
        rewards = self.results.get("rewards", {})

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
            text = "Numeric Received (not running)"
        else:
            text = f"Numeric Received ({int(secs/3600):0>2}h {int(secs%3600/60):0>2}m {int(secs%60)}s) ({int(dil/secs):0>2} DPS)"

        self.setWindowTitle(text)
        self.label.setText(text)

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
            self.last = self.start
            self.delta = self.last - self.start

            if not self.filename:
                time.sleep(1)
                continue

            with open(self.filename, "r+") as file:
                for line in self.follow(file):
                    data = {
                        "start": self.start.timestamp(),
                        "end": self.last.timestamp(),
                        "duration": self.delta.total_seconds(),
                        "rewards": self.rewards,
                    }
                    match = re.match(log_regex, line)
                    if match:
                        at = datetime.datetime.strptime(
                            match.group(1),
                            "%Y%m%dT%H%M%S",
                        )
                        match2 = re.match(reward_regex, match.group(2))
                        match3 = re.match(reward_regex_2, match.group(2))
                        match4 = re.match(reward_regex_3, match.group(2))
                        if match2:
                            key = match2.group(2)
                            val = int(match2.group(1).replace(",", ""))
                            if self.rewards.get(key):
                                self.rewards[key] += val
                            else:
                                self.rewards[key] = val
                            self.signals.results.emit(data)
                        elif match3:
                            key = match3.group(1)
                            val = int(match3.group(2).replace(",", ""))
                            if self.rewards.get(key):
                                self.rewards[key] += val
                            else:
                                self.rewards[key] = val
                            self.signals.results.emit(data)
                        elif match4:
                            key = match4.group(1)
                            val = 1
                            if self.rewards.get(key):
                                self.rewards[key] += val
                            else:
                                self.rewards[key] = val
                            self.signals.results.emit(data)
                        elif "ChatLog ON" in match.group(2):
                            self.emit = True
                            self.start = at
                            self.rewards = {}
                            self.signals.results.emit(data)
                        elif "ChatLog OFF" in match.group(2):
                            self.emit = False

                    if self.emit:
                        self.last = at
                        self.delta = self.last - self.start
                        self.signals.seconds.emit(
                            (
                                self.rewards.get("Dilithium Ore", 0),
                                self.delta.total_seconds(),
                            ),
                        )

    @QtCore.Slot()
    def quit(self, event):
        self.running = False
