import sys
import os
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
import database

def main():
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
    # Global AppData Setup
    import shutil
    app_data_dir = os.path.join(os.getenv('LOCALAPPDATA', os.path.expanduser('~')), 'TheStoriesICarry')
    os.makedirs(app_data_dir, exist_ok=True)
    
    # Copy assets to AppData if they don't exist
    target_assets_dir = os.path.join(app_data_dir, 'assets')
    if not os.path.exists(target_assets_dir):
        source_assets_dir = os.path.join(base_dir, 'assets')
        if os.path.exists(source_assets_dir):
            shutil.copytree(source_assets_dir, target_assets_dir)
            
    # Force copy the app icon to AppData so it can be used for the window icon
    try:
        shutil.copy2(os.path.join(base_dir, 'assets', 'icons', 'app_icon.svg'), os.path.join(app_data_dir, 'assets', 'icons', 'app_icon.svg'))
        shutil.copy2(os.path.join(base_dir, 'assets', 'icons', 'app_icon.ico'), os.path.join(app_data_dir, 'assets', 'icons', 'app_icon.ico'))
    except Exception:
        pass
        
    # Set the working directory to AppData so databases, SVGs, and downloads_history all map there
    os.chdir(app_data_dir)
    
    # Initialize the database
    database.init_db()
    
    import ctypes
    from PySide6.QtGui import QIcon
    
    # Set AppUserModelID so Windows taskbar correctly groups and uses the custom icon
    # myappid = 'jitroy.thestoriesihaveseen.app.1.0'
    # try:
    #     ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    # except Exception:
    #     pass
    app = QApplication(sys.argv)
    
    import ctypes
    myappid = 'JitRoy.TheStoriesIHaveSeen.app.1.0'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    
    # Pre-load themes to ensure SVGs are customized
    from ui.theme_manager import ThemeManager
    ThemeManager.load_theme()
    
    # Set the runtime window icon (using .ico ensures it renders correctly in Windows Taskbar)
    app.setWindowIcon(QIcon("assets/icons/app_icon.ico"))
    
    # Base global styles
    app.setStyleSheet("""
        QMainWindow { background-color: #0A0B10; }
        QWidget { font-family: 'Inter', 'Segoe UI', Arial, sans-serif; font-size: 14px; color: #FFFFFF; }
    """)
            
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
