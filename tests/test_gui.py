from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from gui.main_window import MainWindow


class TestGUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_window_creation(self):
        window = MainWindow()
        self.assertIsNotNone(window)
        window.close()

    def test_tabs_present(self):
        window = MainWindow()
        self.assertEqual(window.tabs.count(), 3)
        window.close()


if __name__ == "__main__":
    unittest.main()