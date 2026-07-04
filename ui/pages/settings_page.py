from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QHBoxLayout, 
                               QSpacerItem, QSizePolicy, QFrame)
from PySide6.QtCore import Qt, QTimer, Signal
import tmdb_api

class SettingsPage(QWidget):
    api_key_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsPage")
        self.setStyleSheet("""
            QWidget#settingsPage {
                background-color: #0B0D14;
            }
            QLabel {
                color: #FFFFFF;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLineEdit {
                background-color: #1A1C23;
                border: 1px solid #2D3243;
                border-radius: 8px;
                padding: 12px;
                color: #FFFFFF;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #1AE0A1;
            }
            QLineEdit[readOnly="true"] {
                background-color: transparent;
                border: 1px solid transparent;
                color: #A0AEC0;
            }
            QPushButton {
                font-weight: bold;
                font-size: 14px;
                border-radius: 8px;
                padding: 10px 20px;
                border: none;
            }
            QPushButton#saveBtn {
                background-color: #1AE0A1;
                color: #0B0D14;
            }
            QPushButton#saveBtn:hover {
                background-color: #14B884;
            }
            QPushButton#editBtn {
                background-color: rgba(255, 255, 255, 0.05);
                color: #FFFFFF;
                border: 1px solid #2D3243;
            }
            QPushButton#editBtn:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
            QPushButton#cancelBtn {
                background-color: transparent;
                color: #A0AEC0;
            }
            QPushButton#cancelBtn:hover {
                color: #FFFFFF;
                background-color: rgba(255, 255, 255, 0.05);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # Title
        title_label = QLabel("Settings")
        title_label.setStyleSheet("font-size: 28px; font-weight: bold; margin-bottom: 20px;")
        layout.addWidget(title_label)

        # Card container for API Key
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(16)

        section_title = QLabel("TMDB API Configuration")
        section_title.setStyleSheet("font-size: 18px; font-weight: 600; color: #1AE0A1;")
        card_layout.addWidget(section_title)

        desc = QLabel("Enter your TMDB API Key (v3 auth) below. This is required for fetching movie details, posters, and search results.")
        desc.setStyleSheet("color: #A0AEC0; font-size: 13px;")
        desc.setWordWrap(True)
        card_layout.addWidget(desc)

        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("Enter TMDB API Key...")
        
        # Initial State: Read-only and masked
        self.api_input.setReadOnly(True)
        self.api_input.setEchoMode(QLineEdit.Password)
        
        # Pre-fill with current key
        self.current_key = tmdb_api.get_api_key() or ""
        self.api_input.setText(self.current_key)
            
        card_layout.addWidget(self.api_input)

        # Buttons
        btn_layout = QHBoxLayout()
        
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setObjectName("editBtn")
        self.edit_btn.setCursor(Qt.PointingHandCursor)
        self.edit_btn.clicked.connect(self._on_edit_clicked)
        
        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("saveBtn")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self._on_save_clicked)
        self.save_btn.hide()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        self.cancel_btn.hide()
        
        self.status_msg = QLabel("")
        self.status_msg.setStyleSheet("color: #1AE0A1; font-weight: 500;")
        self.status_msg.hide()

        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.status_msg)
        btn_layout.addStretch()

        card_layout.addLayout(btn_layout)

        layout.addWidget(card)
        layout.addStretch()

    def _set_edit_mode(self, editing):
        self.api_input.setReadOnly(not editing)
        self.api_input.setEchoMode(QLineEdit.Normal if editing else QLineEdit.Password)
        
        self.edit_btn.setVisible(not editing)
        self.save_btn.setVisible(editing)
        self.cancel_btn.setVisible(editing)
        
        if editing:
            self.api_input.setFocus()
            self.status_msg.hide()
            # Force style re-evaluation for the readOnly state
            self.api_input.style().unpolish(self.api_input)
            self.api_input.style().polish(self.api_input)
        else:
            self.api_input.style().unpolish(self.api_input)
            self.api_input.style().polish(self.api_input)

    def _on_edit_clicked(self):
        self._set_edit_mode(True)

    def _on_cancel_clicked(self):
        self.api_input.setText(self.current_key)
        self._set_edit_mode(False)

    def _on_save_clicked(self):
        new_key = self.api_input.text().strip()
        if new_key:
            tmdb_api.set_api_key(new_key)
            self.current_key = new_key
            self._set_edit_mode(False)
            
            self.status_msg.setText("✓ Saved successfully!")
            self.status_msg.setStyleSheet("color: #1AE0A1; font-weight: 500;")
            
            # Emit signal to let MainWindow know it needs to refresh the app
            self.api_key_changed.emit()
        else:
            self.status_msg.setText("Error: API Key cannot be empty.")
            self.status_msg.setStyleSheet("color: #E53E3E; font-weight: 500;")
            
        self.status_msg.show()
        QTimer.singleShot(3000, self.status_msg.hide)
