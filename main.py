"""
OCR PDF - Huvudapplikation
Windows desktop-applikation för automatisk extraktion av strukturerad data från fakturor.
"""

import sys
from PySide6.QtWidgets import QApplication
from src.main_window import MainWindow

def main():
    """Startar applikationen."""
    app = QApplication(sys.argv)
    app.setApplicationName("OCR PDF")
    app.setOrganizationName("OCR Mapping")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
