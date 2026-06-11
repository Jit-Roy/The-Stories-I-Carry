from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton
import database
from ui.movie_card import MovieCard, SeriesFolderCard
from ui.components import FlowLayout, ResizableScrollArea

class WishlistPage(QWidget):
    def __init__(self, change_status_callback, on_movie_click_callback):
        super().__init__()
        self.change_status = change_status_callback
        self.on_movie_click = on_movie_click_callback
        self.current_series = None
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.back_btn = QPushButton("← Back to All Watch Later")
        self.back_btn.setProperty("class", "primary-btn")
        self.back_btn.clicked.connect(lambda: self.set_series_view(None))
        self.back_btn.hide()
        self.layout.addWidget(self.back_btn)
        
        self.flow = FlowLayout()
        container = QWidget()
        container.setLayout(self.flow)
        scroll = ResizableScrollArea(self.flow)
        scroll.setWidget(container)
        self.layout.addWidget(scroll)
        
    def set_series_view(self, series_name):
        self.current_series = series_name
        self.back_btn.setVisible(series_name is not None)
        self.load_lists()
        
    def clear_layout(self):
        while self.flow.count():
            item = self.flow.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
    def load_lists(self):
        self.clear_layout()
        movies = database.get_movies("watch_later")
        
        series_groups = {}
        standalone = []
        
        for m in movies:
            s_name = m.get("series_name")
            if s_name:
                if s_name not in series_groups:
                    series_groups[s_name] = []
                series_groups[s_name].append(m)
            else:
                standalone.append(m)
                
        if self.current_series:
            for m in series_groups.get(self.current_series, []):
                self.flow.add_widget(MovieCard(m, self.change_status, self.on_movie_click))
        else:
            for s_name, s_movies in series_groups.items():
                folder = SeriesFolderCard(s_name, len(s_movies), self.set_series_view)
                self.flow.add_widget(folder)
            for m in standalone:
                self.flow.add_widget(MovieCard(m, self.change_status, self.on_movie_click))
