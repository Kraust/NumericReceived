import signal
import sys

from chatlog import ChatLogWidget
from PySide6.QtWidgets import QApplication


def main():
    """Main"""
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication([])

    widget = ChatLogWidget()
    widget.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
