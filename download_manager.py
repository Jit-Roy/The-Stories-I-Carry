import os
import asyncio
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool

import threading

class WorkerSignals(QObject):
    progress = Signal(int, dict)
    finished = Signal(int, bool, str)

class DownloadWorker(QRunnable):
    def __init__(self, tmdb_id, url, download_path, abort_event=None, filename_prefix=None):
        super().__init__()
        self.tmdb_id = tmdb_id
        self.url = url
        self.download_path = download_path
        self.abort_event = abort_event
        self.filename_prefix = filename_prefix
        self.signals = WorkerSignals()

    def run(self):
        try:
            import sys
            if sys.platform == 'win32':
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                
            import downloader
            def progress_cb(data):
                self.signals.progress.emit(self.tmdb_id, data)

            asyncio.run(downloader.intercept_media(self.url, progress_callback=progress_cb, download_path=self.download_path, abort_event=self.abort_event, filename_prefix=self.filename_prefix))
            self.signals.finished.emit(self.tmdb_id, True, None)
        except Exception as e:
            self.signals.finished.emit(self.tmdb_id, False, str(e))

class DownloadManager(QObject):
    _instance = None
    progress_updated = Signal(int, dict)
    status_updated = Signal(int, str)
    download_finished = Signal(int, bool, str)
    download_started = Signal(int, dict)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DownloadManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        self._initialized = True
        self.active_downloads = {} # tmdb_id -> { "movie_data": ..., "status": ... }
        self.download_path = os.path.join(os.getcwd(), "Downloads")
        self.history_file = os.path.join(os.getcwd(), "downloads_history.json")
        os.makedirs(self.download_path, exist_ok=True)
        self.load_history()

    def load_history(self):
        import json
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)
                for k, v in history.items():
                    self.active_downloads[int(k)] = {
                        "movie_data": v.get("movie_data", {}),
                        "status": v.get("status", "Unknown"),
                        "percent": v.get("percent", 0.0)
                    }
                    if self.active_downloads[int(k)]["status"] not in ("Completed", "Download Failed", "Error") and not self.active_downloads[int(k)]["status"].startswith("Error"):
                        self.active_downloads[int(k)]["status"] = "Paused"
            except Exception as e:
                print(f"Error loading download history: {e}")

    def save_history(self):
        import json
        history = {}
        for k, v in self.active_downloads.items():
            history[str(k)] = {
                "movie_data": v.get("movie_data", {}),
                "status": v.get("status", "Unknown"),
                "percent": v.get("percent", 0.0)
            }
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=4)
        except Exception as e:
            print(f"Error saving download history: {e}")

    def start_download(self, movie_data):
        tmdb_id = movie_data["id"]
        if tmdb_id in self.active_downloads:
            dl_info = self.active_downloads[tmdb_id]
            if not dl_info.get("status", "").startswith("Error") and dl_info.get("status") not in ("Completed", "Paused"):
                return # Already downloading active stream
        
        url = f"https://vidsrc.sbs/movie/{tmdb_id}"
        abort_event = threading.Event()
        filename_prefix = f"movie_{tmdb_id}"
        worker = DownloadWorker(tmdb_id, url, self.download_path, abort_event=abort_event, filename_prefix=filename_prefix)
        
        if tmdb_id not in self.active_downloads:
            self.active_downloads[tmdb_id] = {
                "movie_data": movie_data,
                "status": "Initializing...",
                "percent": 0.0,
                "speed": 0,
                "eta": 0,
            }
            
        self.active_downloads[tmdb_id].update({
            "status": "Initializing...",
            "worker": worker, # Prevent garbage collection
            "abort_event": abort_event
        })
        
        worker.signals.progress.connect(self._on_worker_progress)
        worker.signals.finished.connect(self._on_worker_finished)
        QThreadPool.globalInstance().start(worker)
        self.download_started.emit(tmdb_id, self.active_downloads[tmdb_id])
        self.status_updated.emit(tmdb_id, "Initializing...")
        self.save_history()

    def pause_download(self, tmdb_id):
        if tmdb_id in self.active_downloads:
            dl_info = self.active_downloads[tmdb_id]
            abort_event = dl_info.get("abort_event")
            if abort_event:
                abort_event.set()
                dl_info["status"] = "Pausing..."
                self.status_updated.emit(tmdb_id, "Pausing...")
                self.save_history()

    def resume_download(self, tmdb_id):
        if tmdb_id in self.active_downloads:
            movie_data = self.active_downloads[tmdb_id]["movie_data"]
            self.start_download(movie_data)

    def _on_worker_progress(self, tmdb_id, data):
        if tmdb_id not in self.active_downloads:
            return
        
        dl_info = self.active_downloads[tmdb_id]
        if data["type"] == "log":
            # Extract status from log
            msg = data["message"]
            if "Intercepting" in msg or "Starting" in msg:
                dl_info["status"] = "Intercepting stream..."
            elif "Injecting player iframe" in msg:
                dl_info["status"] = "Bypassing anti-bot..."
            elif "Downloading:" in msg or "started..." in msg:
                dl_info["status"] = "Downloading..."
            elif "completed successfully" in msg:
                dl_info["status"] = "Finalizing..."
            self.status_updated.emit(tmdb_id, dl_info["status"])
        elif data["type"] == "progress":
            dl_info["status"] = "Downloading..."
            dl_info["percent"] = data.get("percent") or dl_info.get("percent", 0.0)
            dl_info["speed"] = data.get("speed") or dl_info.get("speed", 0)
            dl_info["eta"] = data.get("eta") or dl_info.get("eta", 0)
            self.progress_updated.emit(tmdb_id, dl_info)

    def _on_worker_finished(self, tmdb_id, success, error_msg):
        if tmdb_id in self.active_downloads:
            dl_info = self.active_downloads[tmdb_id]
            if not success and "Download was paused" in str(error_msg):
                dl_info["status"] = "Paused"
                self.status_updated.emit(tmdb_id, "Paused")
                self.save_history()
                return
                
            dl_info["status"] = "Completed" if success else f"Error: {error_msg}"
            if not success:
                import traceback
                with open("download_error.log", "w") as f:
                    f.write(f"Download Error for {tmdb_id}:\n{error_msg}\n")
            if success:
                dl_info["percent"] = 100.0
                import glob
                prefix = f"movie_{tmdb_id}"
                for p in glob.glob(os.path.join(self.download_path, f"{prefix}*.part*")) + glob.glob(os.path.join(self.download_path, f"{prefix}*.ytdl*")):
                    try:
                        os.remove(p)
                    except:
                        pass
                        
            self.status_updated.emit(tmdb_id, dl_info["status"])
            self.download_finished.emit(tmdb_id, success, error_msg or "")
            self.save_history()
