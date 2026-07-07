import os
import sys
import subprocess
import asyncio
import threading
import urllib.parse
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, 
    QLabel, QWidget
)
from PySide6.QtCore import Qt, Signal, QThread, QEvent
from playwright.async_api import async_playwright

def force_foreground_chrome(target_pid=None):
    import ctypes
    try:
        def enum_windows_callback(hwnd, lParam):
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value
                
                if "Google Chrome" in title or "Stream Preview" in title:
                    is_match = False
                    
                    if target_pid is not None:
                        # Check if this window belongs to the exact Chrome process we launched
                        window_pid = ctypes.c_ulong()
                        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
                        if window_pid.value == target_pid:
                            is_match = True
                    else:
                        # Fallback for "Stream Preview" which has a highly unique title
                        if "Stream Preview" in title:
                            is_match = True
                            
                    if is_match:
                        if ctypes.windll.user32.IsIconic(hwnd):
                            ctypes.windll.user32.ShowWindow(hwnd, 9) # SW_RESTORE
                        ctypes.windll.user32.SetForegroundWindow(hwnd)
                        return False # Stop enumerating
            return True
        
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
        ctypes.windll.user32.EnumWindows(EnumWindowsProc(enum_windows_callback), 0)
    except:
        pass

class ChromeSnifferThread(QThread):
    stream_found = Signal(str, dict)
    log_msg = Signal(str)
    
    preview_requested = Signal(str, dict)
    cookies_fetched = Signal(list)
    
    def __init__(self, movie_url):
        super().__init__()
        self.movie_url = movie_url
        self.is_running = True
        self.chrome_proc = None
        self.loop = None
        self.context = None

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.preview_requested.connect(self._handle_preview_request)
        try:
            self.loop.run_until_complete(self._sniff_loop())
        finally:
            self.loop.close()
            
    def _handle_preview_request(self, stream_url, headers):
        if self.loop and self.context:
            asyncio.run_coroutine_threadsafe(self._open_preview_tab(stream_url, headers), self.loop)
            
    def fetch_cookies(self):
        if self.loop and self.context:
            asyncio.run_coroutine_threadsafe(self._do_fetch_cookies(), self.loop)
            
    async def _do_fetch_cookies(self):
        try:
            cookies = await self.context.cookies()
            self.cookies_fetched.emit(cookies)
        except Exception as e:
            self.log_msg.emit(f"Cookie fetch error: {e}")
            self.cookies_fetched.emit([])

    async def _open_preview_tab(self, stream_url, headers):
        try:
            self.log_msg.emit("Opening preview tab in Chrome...")
            page = await self.context.new_page()
            
            orig_referer = headers.get('referer', headers.get('Referer', 'https://vidsrc.sbs/'))
            await page.set_extra_http_headers({'referer': orig_referer})
            
            actual_stream_url = stream_url
            
            parsed_stream = urllib.parse.urlparse(actual_stream_url)
            base_url = f"{parsed_stream.scheme}://{parsed_stream.netloc}"
            fake_url = f"{base_url}/__local_preview_player__"
            
            is_mp4 = '.mp4' in stream_url.lower()
            
            async def route_handler(route):
                if is_mp4:
                    script_logic = f"""
                        video.src = '{actual_stream_url}';
                        video.addEventListener('loadedmetadata', function() {{ player.play(); }});
                    """
                else:
                    script_logic = f"""
                        if (Hls.isSupported()) {{
                            const hls = new Hls({{
                                debug: false,
                                enableWorker: true
                            }});
                            hls.loadSource('{actual_stream_url}');
                            hls.attachMedia(video);
                            hls.on(Hls.Events.MANIFEST_PARSED, function() {{ 
                                player.play(); 
                            }});
                        }} else if (video.canPlayType('application/vnd.apple.mpegurl')) {{
                            video.src = '{actual_stream_url}';
                            video.addEventListener('loadedmetadata', function() {{ player.play(); }});
                        }}
                    """

                html = f'''<!DOCTYPE html>
<html>
<head>
    <title>Stream Preview</title>
    <link rel="stylesheet" href="https://cdn.plyr.io/3.7.8/plyr.css" />
    <script src="https://cdn.jsdelivr.net/npm/hls.js@1"></script>
    <script src="https://cdn.plyr.io/3.7.8/plyr.polyfilled.js"></script>
    <style>
        body {{ background: black; margin: 0; padding: 0; overflow: hidden; display: flex; align-items: center; justify-content: center; height: 100vh; width: 100vw; }}
        video {{ width: 100%; height: 100%; }}
        :root {{ --plyr-color-main: #1AE0A1; }}
    </style>
</head>
<body>
    <video id="player" controls playsinline></video>
    <script>
      const video = document.getElementById('player');
      
      const defaultOptions = {{
          controls: ['play-large', 'play', 'progress', 'current-time', 'duration', 'mute', 'volume', 'captions', 'settings', 'pip', 'airplay', 'fullscreen'],
          seekTime: 10,
          keyboard: {{ focused: true, global: true }}
      }};

        const player = new Plyr(video, defaultOptions);
        
        {script_logic}
    </script>
</body>
</html>'''
                await route.fulfill(content_type="text/html", body=html)

            await page.route(fake_url, route_handler)
            
            # Bring Chrome to the front instantly before the page even loads
            await page.bring_to_front()
            try:
                force_foreground_chrome(self.chrome_proc.pid)
            except Exception as e:
                print(f"Foreground Error: {e}")
                
            await page.goto(fake_url)
            
        except Exception as e:
            self.log_msg.emit(f"Preview Error: {str(e)}")

    async def _sniff_loop(self):
        chrome_path = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
        if not os.path.exists(chrome_path):
            chrome_path = r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'
            if not os.path.exists(chrome_path):
                self.log_msg.emit("Error: Could not find Google Chrome installed.")
                return

        user_data_dir = os.path.join(os.getcwd(), 'chrome_debug_profile')
        self.chrome_proc = subprocess.Popen([
            chrome_path, 
            '--remote-debugging-port=9222', 
            f'--user-data-dir={user_data_dir}',
            '--no-default-browser-check',
            '--no-first-run',
            self.movie_url
        ])

        await asyncio.sleep(2)
        if not self.is_running: return

        try:
            force_foreground_chrome(self.chrome_proc.pid)
        except:
            pass

        async with async_playwright() as p:
            try:
                browser = await p.chromium.connect_over_cdp('http://localhost:9222')
                contexts = browser.contexts
                if not contexts: return
                    
                self.context = contexts[0]
                pages = self.context.pages
                if not pages:
                    await asyncio.sleep(2)
                    pages = self.context.pages
                
                page = pages[0]
                async def on_response(response):
                    url = response.url
                    if response.status < 200 or response.status >= 300: return
                    headers = response.headers
                    content_type = headers.get('content-type', '').lower()
                    is_hls = 'mpegurl' in content_type or 'application/x-mpegurl' in content_type
                    is_mp4 = 'video/mp4' in content_type
                    if is_hls or is_mp4 or '.m3u8' in url:
                        req_headers = await response.request.all_headers()
                        # Filter out caching headers that cause yt-dlp to fail with 304 Not Modified
                        filtered_headers = {k: v for k, v in req_headers.items() if k.lower() not in ['if-none-match', 'if-modified-since']}
                        self.stream_found.emit(url, filtered_headers)

                page.on('response', on_response)
                self.context.on('page', lambda new_page: new_page.on('response', on_response))
                
                # Auto-refresh the page once after 2 seconds to fix the iframe timeout glitch
                async def auto_refresh():
                    await asyncio.sleep(2)
                    try:
                        await page.reload()
                    except:
                        pass
                asyncio.create_task(auto_refresh())
                
                while self.is_running:
                    if page.is_closed(): break
                    await asyncio.sleep(0.5)
                await browser.close()
            finally:
                if self.chrome_proc: self.chrome_proc.terminate()

    def stop(self):
        self.is_running = False
        if self.chrome_proc:
            try: self.chrome_proc.terminate()
            except: pass

class ChromeSnifferDialog(QDialog):
    def __init__(self, movie_id, parent=None, media_type="movie", season_number=1, episode_number=1):
        super().__init__(parent.window() if parent else None)
        self.movie_id = movie_id
        self.media_type = media_type
        self.selected_m3u8 = None
        self.embed_url = f"https://vidsrc.sbs/embed/tv/{self.movie_id}/{season_number}/{episode_number}" if self.media_type == "tv" else f"https://vidsrc.sbs/embed/movie/{self.movie_id}"
        self.stream_headers = {}
        self.setWindowTitle("Chrome Stream Sniffer")
        self.resize(500, 300)
        flags = self.windowFlags()
        flags &= ~Qt.WindowContextHelpButtonHint
        flags |= Qt.WindowMinimizeButtonHint
        flags |= Qt.WindowCloseButtonHint
        self.setWindowFlags(flags)
        self.setModal(True)
        
        from ui.theme_manager import ThemeManager
        primary = ThemeManager.get_color("primary")
        complementary = ThemeManager.get_color("complementary")
        
        self.setStyleSheet(f"""
            QDialog {{ 
                background-color: #1A1C23; 
                color: white;
            }}
            QLabel {{ 
                font-size: 14px; 
                color: #E2E8F0;
                font-weight: bold;
            }}
            QComboBox {{ 
                background-color: #2D3748; 
                color: white; 
                border: 1px solid #4A5568; 
                border-radius: 4px; 
                padding: 6px 10px; 
                font-size: 13px;
                combobox-popup: 0;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 35px;
            }}
            QComboBox::down-arrow {{
                image: url(assets/icons/down_arrow.svg);
                width: 16px;
                height: 16px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #2D3748;
                color: white;
                selection-background-color: {primary};
                selection-color: #0F172A;
                border: 1px solid #4A5568;
                outline: none;
            }}
            QPushButton {{ 
                background-color: {primary}; 
                color: #0F172A; 
                border: none; 
                border-radius: 6px; 
                padding: 10px 16px; 
                font-weight: bold; 
                font-size: 14px;
                margin: 2px;
            }}
            QPushButton:hover {{
                margin: 0px;
            }}
            QPushButton:disabled {{ 
                background-color: #334155; 
                color: #94A3B8; 
            }}
            QPushButton#btnPreview {{ 
                background-color: {complementary}; 
                color: white; 
            }}
            QPushButton#btnPreview:hover {{
                margin: 0px;
            }}
            #statusLabel {{ 
                color: {primary}; 
                font-style: italic; 
                font-weight: normal;
                margin-top: 10px;
                margin-bottom: 20px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)
        
        lbl_inst = QLabel("Chrome is opening. Please play the video to capture the stream.")
        lbl_inst.setWordWrap(True)
        layout.addWidget(lbl_inst)
        
        self.lbl_status = QLabel("Status: Starting...")
        self.lbl_status.setObjectName("statusLabel")
        layout.addWidget(self.lbl_status)
        
        layout.addWidget(QLabel("Detected Streams:"))
        self.combo_streams = QComboBox()
        self.combo_streams.setMaxVisibleItems(8)
        self.combo_streams.currentIndexChanged.connect(self._on_combo_changed)
        layout.addWidget(self.combo_streams)
        
        layout.addStretch()
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        self.btn_preview = QPushButton("▶ Preview")
        self.btn_preview.setObjectName("btnPreview")
        self.btn_preview.setEnabled(False)
        self.btn_preview.clicked.connect(self._on_preview)
        
        self.btn_proceed = QPushButton("Download")
        self.btn_proceed.setEnabled(False)
        self.btn_proceed.clicked.connect(self._on_proceed)
        
        btn_layout.addWidget(self.btn_preview)
        btn_layout.addWidget(self.btn_proceed)
        layout.addLayout(btn_layout)
        
        self.thread = ChromeSnifferThread(self.embed_url)
        self.thread.stream_found.connect(self._on_stream_found)
        self.thread.log_msg.connect(self._on_log)
        self.thread.cookies_fetched.connect(self._on_cookies_fetched)
        self.thread.start()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized():
                if self.parentWidget():
                    self.parentWidget().showMinimized()
            elif self.windowState() == Qt.WindowNoState:
                if self.parentWidget() and self.parentWidget().isMinimized():
                    self.parentWidget().showNormal()
        super().changeEvent(event)

    def _on_log(self, msg):
        self.lbl_status.setText(f"Status: {msg}")

    def _on_stream_found(self, url, headers):
        for i in range(self.combo_streams.count()):
            if self.combo_streams.itemText(i) == url:
                return
                
        self.stream_headers[url] = headers
        self.combo_streams.addItem(url)
        self.lbl_status.setText(f"Status: Sniffed {self.combo_streams.count()} streams!")

    def _on_combo_changed(self, index):
        if index >= 0:
            self.btn_proceed.setEnabled(True)
            self.btn_preview.setEnabled(True)
        else:
            self.btn_proceed.setEnabled(False)
            self.btn_preview.setEnabled(False)

    def _on_preview(self):
        current_text = self.combo_streams.currentText()
        if not current_text: return
        
        headers = self.stream_headers.get(current_text, {})
        # Instead of ffplay, tell the Playwright thread to open a new tab 
        # with our hls.js player, completely bypassing CORS natively!
        self.thread.preview_requested.emit(current_text, headers)

    def _on_proceed(self):
        current_text = self.combo_streams.currentText()
        if current_text:
            self.selected_m3u8 = current_text
            self.btn_proceed.setText("Fetching cookies...")
            self.btn_proceed.setEnabled(False)
            self.thread.fetch_cookies()

    def _on_cookies_fetched(self, cookies):
        self.sniffed_cookies = cookies
        self.accept()

    def get_selection(self):
        return {
            'm3u8_url': self.selected_m3u8,
            'embed_url': self.embed_url,
            'cookies': getattr(self, 'sniffed_cookies', []),
            'headers': self.stream_headers.get(self.selected_m3u8, {})
        }

    def closeEvent(self, event):
        self.thread.stop()
        self.thread.wait(2000)
        super().closeEvent(event)

    def reject(self):
        self.thread.stop()
        self.thread.wait(2000)
        super().reject()
