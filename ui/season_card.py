from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor

from ui.movie_card import ImageLoader

class SeasonCard(QWidget):
    def __init__(self, season, on_click_callback=None, width=150):
        super().__init__()
        self.season = season
        self.on_click_callback = on_click_callback
        self.setFixedWidth(width)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        from ui.movie_card import RoundedImage
        self.poster_lbl = RoundedImage()
        self.poster_lbl.setFixedSize(width, int(width * 1.5))
        self.poster_lbl.setStyleSheet("background-color: #2D3748; border-radius: 8px;")
        self.poster_lbl.setAlignment(Qt.AlignCenter)

        # Hover highlight overlay (hidden by default)
        self.hover_overlay = QWidget(self.poster_lbl)
        self.hover_overlay.setFixedSize(width, int(width * 1.5))
        self.hover_overlay.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(0,0,0,0.6), stop:0.25 rgba(0,0,0,0), stop:0.75 rgba(0,0,0,0), stop:1 rgba(0,0,0,0.6));
                border-radius: 8px;
            }
        """)
        self.hover_overlay.hide()
        self.hover_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        name = season.get("name", "Unknown")
        self.title_lbl = QLabel(name)
        self.title_lbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        self.title_lbl.setWordWrap(True)
        
        ep_count = season.get("episode_count", 0)
        year = season.get("air_date", "")[:4] if season.get("air_date") else "Unknown"
        self.info_lbl = QLabel(f"{ep_count} Episodes • {year}")
        self.info_lbl.setStyleSheet("color: #A0AEC0; font-size: 12px;")
        
        layout.addWidget(self.poster_lbl)
        layout.addWidget(self.title_lbl)
        layout.addWidget(self.info_lbl)
        layout.addStretch()
        
        self.load_poster()

    def load_poster(self):
        path = self.season.get("poster_path")
        if not path:
            self.poster_lbl.setText("No Image")
            return
            
        url = f"https://image.tmdb.org/t/p/w500{path}"
        
        from PySide6.QtCore import QThreadPool
        target_size = (self.poster_lbl.width(), self.poster_lbl.height())
        self.loader = ImageLoader(url, target_size=target_size)
        self.loader.signals.finished_img.connect(self.on_poster_loaded)
        QThreadPool.globalInstance().start(self.loader)
            
    def on_poster_loaded(self, img):
        if not img:
            self.poster_lbl.setText("No Image")
            return
            
        from PySide6.QtGui import QPixmap
        self.poster_lbl.setPixmap(QPixmap(img))
        
    def enterEvent(self, event):
        self.hover_overlay.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hover_overlay.hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.on_click_callback:
            self.on_click_callback(self.season)
        super().mousePressEvent(event)
