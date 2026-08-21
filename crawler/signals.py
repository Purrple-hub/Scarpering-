from PyQt6.QtCore import QObject, pyqtSignal


class SignalBridge(QObject):
    stats = pyqtSignal(dict)
    console = pyqtSignal(str, str)
    page = pyqtSignal(dict)
    finished = pyqtSignal(dict)