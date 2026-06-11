import sys
import os
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
import database

def main():
    # Initialize the database
    database.init_db()
    
    app = QApplication(sys.argv)
    
    # Base global styles
    app.setStyleSheet("""
        QMainWindow { background-color: #0A0B10; }
        QWidget { font-family: 'Inter', 'Segoe UI', Arial, sans-serif; color: #FFFFFF; }
    """)
            
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
