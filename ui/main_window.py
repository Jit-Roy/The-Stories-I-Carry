from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QStackedWidget
from PySide6.QtCore import Qt
import database
import tmdb_api

from ui.pages.home_page import HomePage
from ui.pages.collection_page import CollectionPage
from ui.pages.wishlist_page import WishlistPage
from ui.pages.detail_page import MovieDetailPage
from ui.pages.grid_page import GridPage

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FrameVault")
        self.setMinimumSize(1200, 800)
        self.previous_page_index = 0
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QHBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        self.setup_left_sidebar()
        
        self.center_area = QWidget()
        self.center_layout = QVBoxLayout(self.center_area)
        self.center_layout.setContentsMargins(30, 20, 30, 20)
        
        self.setup_top_nav()
        
        self.stack = QStackedWidget()
        
        self.home_page = HomePage(self.change_status, self.show_movie_detail, self.show_grid_view)
        self.collection_page = CollectionPage(self.change_status, self.show_movie_detail)
        self.wishlist_page = WishlistPage(self.change_status, self.show_movie_detail)
        self.detail_page = MovieDetailPage(self.go_back_to_previous_page, self.change_status, self.show_movie_detail)
        self.grid_page = GridPage(self.go_back_to_previous_page, self.change_status, self.show_movie_detail)
        
        self.stack.addWidget(self.home_page)      # 0
        self.stack.addWidget(self.collection_page) # 1
        self.stack.addWidget(self.wishlist_page)   # 2
        self.stack.addWidget(self.detail_page)     # 3
        self.stack.addWidget(self.grid_page)       # 4
        
        self.center_layout.addWidget(self.stack)
        self.layout.addWidget(self.center_area, 1)
        
        # Load initial data for lists
        self.collection_page.load_lists()
        self.wishlist_page.load_lists()

    def setup_left_sidebar(self):
        self.left_sidebar = QWidget()
        self.left_sidebar.setStyleSheet("background-color: #11131A; border-right: 1px solid #1E202B;")
        self.left_sidebar.setFixedWidth(240)
        layout = QVBoxLayout(self.left_sidebar)
        layout.setAlignment(Qt.AlignTop)
        layout.setContentsMargins(20, 30, 20, 20)
        
        logo = QLabel("🎬 FrameVault\nYour Cinema Universe")
        logo.setStyleSheet("font-size: 16px; font-weight: bold; color: white; border: none;")
        layout.addWidget(logo)
        layout.addSpacing(30)
        
        nav_style = """
            QPushButton {
                background-color: transparent; color: #A0AEC0; text-align: left;
                padding: 12px 16px; border-radius: 8px; font-size: 14px; font-weight: 500; border: none;
            }
            QPushButton:hover {
                color: #FFFFFF; background-color: #1A1C23;
            }
            QPushButton:checked {
                color: #FFFFFF; background-color: #032541; border-left: 3px solid #1AE0A1;
                border-top-left-radius: 0px; border-bottom-left-radius: 0px;
            }
        """
        
        self.home_btn = QPushButton("🏠 Home")
        self.home_btn.setStyleSheet(nav_style)
        self.home_btn.setCheckable(True)
        self.home_btn.setChecked(True)
        self.home_btn.clicked.connect(lambda: self.switch_page(0, self.home_btn))
        layout.addWidget(self.home_btn)
        
        self.col_btn = QPushButton("📚 Collection")
        self.col_btn.setStyleSheet(nav_style)
        self.col_btn.setCheckable(True)
        self.col_btn.clicked.connect(lambda: self.switch_page(1, self.col_btn))
        layout.addWidget(self.col_btn)
        
        self.wish_btn = QPushButton("🔖 Wishlist")
        self.wish_btn.setStyleSheet(nav_style)
        self.wish_btn.setCheckable(True)
        self.wish_btn.clicked.connect(lambda: self.switch_page(2, self.wish_btn))
        layout.addWidget(self.wish_btn)
        
        layout.addStretch()
        self.layout.addWidget(self.left_sidebar)
        
    def switch_page(self, index, active_btn):
        self.stack.setCurrentIndex(index)
        self.previous_page_index = index
        self.home_btn.setChecked(False)
        self.col_btn.setChecked(False)
        self.wish_btn.setChecked(False)
        active_btn.setChecked(True)
        if index == 1:
            self.collection_page.load_lists()
        elif index == 2:
            self.wishlist_page.load_lists()

    def show_movie_detail(self, movie_data):
        self.previous_page_index = self.stack.currentIndex()
        self.detail_page.load_movie(movie_data)
        self.stack.setCurrentIndex(3)
        
    def show_grid_view(self, title, fetch_func, initial_params=None):
        self.previous_page_index = self.stack.currentIndex()
        self.grid_page.load_grid(title, fetch_func, initial_params)
        self.stack.setCurrentIndex(4)

    def setup_top_nav(self):
        from PySide6.QtWidgets import QLineEdit
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Search movies, actors, keywords...")
        self.search_bar.setStyleSheet("""
            QLineEdit {
                background-color: #11131A;
                border: 1px solid #1E202B;
                border-radius: 20px;
                padding: 12px 20px;
                color: white;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #1AE0A1;
            }
        """)
        self.search_bar.returnPressed.connect(self.perform_search)
        
        self.center_layout.addWidget(self.search_bar)
        self.center_layout.addSpacing(20)
        
    def perform_search(self):
        query = self.search_bar.text().strip()
        if not query:
            return
        
        self.show_grid_view(
            f"Search Results: '{query}'", 
            lambda page: tmdb_api.search_movies(query, page=page)
        )
        
    def go_back_to_previous_page(self):
        # We don't want to go back to detail or grid if we are escaping it
        if self.previous_page_index in [3, 4]:
            self.previous_page_index = 0
            self.home_btn.setChecked(True)
        self.stack.setCurrentIndex(self.previous_page_index)

    def change_status(self, movie_data, new_status):
        details = tmdb_api.get_movie_details(movie_data["id"])
        series_name = details.get("series_name") if details else None
        database.add_movie(
            movie_data["id"], 
            movie_data["title"], 
            movie_data["poster_path"], 
            new_status,
            series_name
        )
        # Update the dictionary so buttons reflect current state instantly
        movie_data["status"] = new_status
        
        self.collection_page.load_lists()
        self.wishlist_page.load_lists()
        if self.stack.currentIndex() == 3:
            # Refresh detail page if we are on it
            self.detail_page.load_movie(movie_data)
