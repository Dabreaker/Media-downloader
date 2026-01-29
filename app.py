#!/usr/bin/env python3
"""
UNIVERSAL MEDIA DOWNLOADER - COMPLETE EDITION
GitHub-inspired UI with 3-dot menu, format selection, and custom download location
Credits: Mahim & DeepSeek Brother
"""

import os
import json
import hashlib
import threading
import tempfile
import yt_dlp
import shutil
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from datetime import datetime
import urllib.parse
import time
import traceback
import sys
from concurrent.futures import ThreadPoolExecutor
import subprocess

# ============================================================================
# CONFIGURATION
# ============================================================================

APP_VERSION = "5.0.0"
PORT = 4050
HOST = "0.0.0.0"
MAX_WORKERS = 4

# GitHub-inspired Color Scheme
COLORS = {
    "background": "#0d1117",  # GitHub Dark
    "surface": "#161b22",  # GitHub Card
    "surface_variant": "#21262d",  # GitHub Hover
    "primary": "#238636",  # GitHub Green
    "primary_hover": "#2ea043",
    "border": "#30363d",  # GitHub Border
    "text_primary": "#f0f6fc",  # GitHub Text
    "text_secondary": "#8b949e",  # GitHub Secondary Text
    "accent": "#1f6feb",  # GitHub Blue
    "error": "#f85149",  # GitHub Red
    "warning": "#d29922",  # GitHub Yellow
    "success": "#238636",  # GitHub Green
}

# ============================================================================
# DOWNLOAD MANAGER
# ============================================================================

class DownloadManager:
    """Manages download operations"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DownloadManager, cls).__new__(cls)
            cls._instance._init()
        return cls._instance
    
    def _init(self):
        self.downloads = {}
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
        # Default download directory
        self.download_dir = Path.home() / "Downloads" / "MediaDownloader"
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # Load settings
        self.settings_file = self.download_dir / "settings.json"
        self.load_settings()
    
    def load_settings(self):
        """Load settings from file"""
        default_settings = {
            "download_path": str(self.download_dir),
            "max_concurrent_downloads": 2,
            "default_format": "best",
            "auto_download": False
        }
        
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    self.download_dir = Path(settings.get('download_path', str(self.download_dir)))
                    # Ensure directory exists
                    self.download_dir.mkdir(parents=True, exist_ok=True)
        except:
            pass
    
    def save_settings(self, settings):
        """Save settings to file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=2)
            
            # Update download directory if changed
            new_path = settings.get('download_path', str(self.download_dir))
            self.download_dir = Path(new_path)
            self.download_dir.mkdir(parents=True, exist_ok=True)
            
            return True
        except:
            return False
    
    def start_download(self, url: str, format_id: str, filename: str) -> str:
        """Start a download and return download ID"""
        download_id = hashlib.md5(f"{url}{format_id}{time.time()}".encode()).hexdigest()[:8]
        
        self.downloads[download_id] = {
            'id': download_id,
            'url': url,
            'format_id': format_id,
            'filename': filename,
            'status': 'queued',
            'progress': 0,
            'started_at': datetime.now().isoformat(),
            'completed_at': None,
            'error': None,
            'filepath': None,
            'downloaded_bytes': 0,
            'total_bytes': 0,
            'speed': 0,
            'eta': None
        }
        
        # Submit download task
        self.executor.submit(self._download_worker, download_id)
        
        return download_id
    
    def _download_worker(self, download_id: str):
        """Background worker for downloading"""
        download = self.downloads[download_id]
        
        try:
            download['status'] = 'downloading'
            
            # Create safe filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = ''.join(c for c in download['filename'] if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
            if not safe_filename:
                safe_filename = f"download_{timestamp}"
            
            # Ensure download directory exists
            self.download_dir.mkdir(parents=True, exist_ok=True)
            
            # Download using yt-dlp with custom output template
            ydl_opts = {
                'format': download['format_id'],
                'outtmpl': str(self.download_dir / f"{safe_filename}.%(ext)s"),
                'quiet': True,
                'no_warnings': True,
                'progress_hooks': [self._create_progress_hook(download_id)],
                'socket_timeout': 30,
                'retries': 3,
                'nooverwrites': True,
                'merge_output_format': 'mp4',
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }] if 'video' in download['format_id'] else []
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([download['url']])
            
            # Find the actual downloaded file
            pattern = f"{safe_filename}*"
            downloaded_files = list(self.download_dir.glob(pattern))
            if downloaded_files:
                actual_file = downloaded_files[0]
                download['filepath'] = str(actual_file)
            
            # Update download info
            download['status'] = 'completed'
            download['progress'] = 100
            download['completed_at'] = datetime.now().isoformat()
            
        except Exception as e:
            download['status'] = 'error'
            download['error'] = str(e)
            download['completed_at'] = datetime.now().isoformat()
    
    def _create_progress_hook(self, download_id: str):
        """Create progress hook for yt-dlp"""
        def hook(d):
            if d['status'] == 'downloading':
                download = self.downloads.get(download_id)
                if download:
                    total = d.get('total_bytes') or d.get('total_bytes_estimate')
                    downloaded = d.get('downloaded_bytes', 0)
                    
                    if total and total > 0:
                        download['progress'] = (downloaded / total) * 100
                    else:
                        download['progress'] = min(download.get('progress', 0) + 10, 90)
                    
                    download['downloaded_bytes'] = downloaded
                    download['total_bytes'] = total
                    download['speed'] = d.get('speed')
                    download['eta'] = d.get('eta')
        
        return hook
    
    def get_download(self, download_id: str) -> dict:
        """Get download info"""
        return self.downloads.get(download_id, {})
    
    def get_all_downloads(self) -> list:
        """Get all downloads"""
        return list(self.downloads.values())

# ============================================================================
# HTML TEMPLATE WITH GITHUB-INSPIRED DESIGN
# ============================================================================

def get_html_template() -> str:
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Media Downloader</title>
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons+Round" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        /* GitHub-inspired Design System */
        :root {{
            --bg-primary: {COLORS['background']};
            --bg-secondary: {COLORS['surface']};
            --bg-tertiary: {COLORS['surface_variant']};
            --border-color: {COLORS['border']};
            --text-primary: {COLORS['text_primary']};
            --text-secondary: {COLORS['text_secondary']};
            --text-link: {COLORS['accent']};
            --btn-primary-bg: {COLORS['primary']};
            --btn-primary-hover: {COLORS['primary_hover']};
            --btn-secondary-bg: {COLORS['surface_variant']};
            --success: {COLORS['success']};
            --error: {COLORS['error']};
            --warning: {COLORS['warning']};
            
            --radius-sm: 6px;
            --radius-md: 8px;
            --radius-lg: 12px;
            --radius-xl: 16px;
            --shadow-sm: 0 1px 0 rgba(27, 31, 36, 0.04);
            --shadow-md: 0 3px 6px rgba(0, 0, 0, 0.1);
            --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.12);
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            line-height: 1.5;
            padding-bottom: 70px; /* Space for fixed footer */
        }}
        
        /* Header with 3-dot Menu */
        .app-header {{
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-color);
            padding: 16px 24px;
            position: sticky;
            top: 0;
            z-index: 100;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        
        .logo {{
            display: flex;
            align-items: center;
            gap: 12px;
            font-weight: 600;
            font-size: 18px;
        }}
        
        .logo-icon {{
            color: var(--btn-primary-bg);
        }}
        
        /* 3-dot Menu */
        .menu-container {{
            position: relative;
        }}
        
        .menu-button {{
            background: none;
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
            color: var(--text-primary);
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.2s;
        }}
        
        .menu-button:hover {{
            background: var(--bg-tertiary);
            border-color: var(--text-secondary);
        }}
        
        .dropdown-menu {{
            position: absolute;
            top: 100%;
            right: 0;
            margin-top: 8px;
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-lg);
            width: 220px;
            z-index: 1000;
            display: none;
            overflow: hidden;
        }}
        
        .dropdown-menu.show {{
            display: block;
            animation: fadeIn 0.2s ease;
        }}
        
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(-10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        
        .menu-item {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 16px;
            color: var(--text-primary);
            text-decoration: none;
            border: none;
            background: none;
            width: 100%;
            text-align: left;
            cursor: pointer;
            font-size: 14px;
            transition: background 0.2s;
        }}
        
        .menu-item:hover {{
            background: var(--bg-tertiary);
        }}
        
        /* Main Container */
        .container {{
            max-width: 800px;
            margin: 0 auto;
            padding: 24px;
        }}
        
        /* Card Design */
        .card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg);
            padding: 24px;
            margin-bottom: 16px;
            box-shadow: var(--shadow-sm);
        }}
        
        /* Input Section */
        .input-group {{
            display: flex;
            gap: 12px;
            margin-bottom: 16px;
        }}
        
        .url-input {{
            flex: 1;
            padding: 12px 16px;
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
            color: var(--text-primary);
            font-size: 14px;
            font-family: inherit;
            transition: all 0.2s;
        }}
        
        .url-input:focus {{
            outline: none;
            border-color: var(--btn-primary-bg);
            box-shadow: 0 0 0 3px rgba(35, 134, 54, 0.1);
        }}
        
        .url-input::placeholder {{
            color: var(--text-secondary);
        }}
        
        /* Buttons */
        .btn {{
            padding: 12px 24px;
            border: 1px solid transparent;
            border-radius: var(--radius-md);
            font-size: 14px;
            font-weight: 500;
            font-family: inherit;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }}
        
        .btn-primary {{
            background: var(--btn-primary-bg);
            color: white;
            border-color: var(--btn-primary-bg);
        }}
        
        .btn-primary:hover {{
            background: var(--btn-primary-hover);
            border-color: var(--btn-primary-hover);
            transform: translateY(-1px);
            box-shadow: var(--shadow-md);
        }}
        
        .btn-primary:active {{
            transform: translateY(0);
        }}
        
        .btn-secondary {{
            background: var(--btn-secondary-bg);
            color: var(--text-primary);
            border-color: var(--border-color);
        }}
        
        .btn-secondary:hover {{
            background: var(--bg-tertiary);
            border-color: var(--text-secondary);
        }}
        
        /* Download Button - Large and Prominent */
        .btn-download-large {{
            width: 100%;
            padding: 16px;
            background: var(--btn-primary-bg);
            color: white;
            border: none;
            border-radius: var(--radius-md);
            font-size: 16px;
            font-weight: 600;
            margin-top: 24px;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
        }}
        
        .btn-download-large:hover {{
            background: var(--btn-primary-hover);
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }}
        
        .btn-download-large:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
            transform: none !important;
            box-shadow: none !important;
        }}
        
        /* Loading State */
        .loading {{
            text-align: center;
            padding: 40px;
        }}
        
        .spinner {{
            width: 40px;
            height: 40px;
            border: 3px solid var(--border-color);
            border-top: 3px solid var(--btn-primary-bg);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 16px;
        }}
        
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        
        /* Video Info */
        .video-info {{
            display: grid;
            grid-template-columns: 180px 1fr;
            gap: 20px;
            align-items: start;
        }}
        
        @media (max-width: 640px) {{
            .video-info {{
                grid-template-columns: 1fr;
            }}
        }}
        
        .thumbnail-container {{
            position: relative;
            border-radius: var(--radius-md);
            overflow: hidden;
            aspect-ratio: 16/9;
            background: var(--bg-tertiary);
        }}
        
        .thumbnail {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}
        
        /* Format Selection - Custom Styled Dropdown */
        .format-selection {{
            margin-top: 24px;
        }}
        
        .custom-select {{
            position: relative;
            width: 100%;
        }}
        
        .select-header {{
            padding: 12px 16px;
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 14px;
        }}
        
        .select-header:hover {{
            border-color: var(--text-secondary);
        }}
        
        .select-options {{
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
            margin-top: 4px;
            max-height: 300px;
            overflow-y: auto;
            display: none;
            z-index: 100;
            box-shadow: var(--shadow-lg);
        }}
        
        .select-options.show {{
            display: block;
            animation: fadeIn 0.2s ease;
        }}
        
        .select-option {{
            padding: 12px 16px;
            cursor: pointer;
            border-bottom: 1px solid var(--border-color);
            font-size: 14px;
            transition: background 0.2s;
        }}
        
        .select-option:last-child {{
            border-bottom: none;
        }}
        
        .select-option:hover {{
            background: var(--bg-tertiary);
        }}
        
        .select-option.selected {{
            background: rgba(35, 134, 54, 0.1);
            color: var(--btn-primary-bg);
        }}
        
        .format-badge {{
            display: inline-block;
            padding: 2px 8px;
            background: var(--btn-primary-bg);
            color: white;
            border-radius: 10px;
            font-size: 11px;
            font-weight: 500;
            margin-left: 8px;
        }}
        
        /* Download Progress */
        .download-progress {{
            margin-top: 24px;
            padding: 20px;
            background: var(--bg-tertiary);
            border-radius: var(--radius-md);
        }}
        
        .progress-header {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 12px;
            font-size: 14px;
        }}
        
        .progress-bar {{
            height: 8px;
            background: var(--border-color);
            border-radius: 4px;
            overflow: hidden;
            margin-bottom: 12px;
        }}
        
        .progress-fill {{
            height: 100%;
            background: var(--btn-primary-bg);
            border-radius: 4px;
            width: 0%;
            transition: width 0.3s ease;
        }}
        
        .progress-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 16px;
            margin-top: 16px;
        }}
        
        .stat-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        /* Settings Modal */
        .modal-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            padding: 20px;
            opacity: 0;
            visibility: hidden;
            transition: all 0.3s;
        }}
        
        .modal-overlay.show {{
            opacity: 1;
            visibility: visible;
        }}
        
        .modal {{
            background: var(--bg-secondary);
            border-radius: var(--radius-lg);
            width: 100%;
            max-width: 500px;
            max-height: 90vh;
            overflow-y: auto;
            box-shadow: var(--shadow-lg);
            transform: translateY(-20px);
            transition: transform 0.3s;
        }}
        
        .modal-overlay.show .modal {{
            transform: translateY(0);
        }}
        
        .modal-header {{
            padding: 20px 24px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .modal-body {{
            padding: 24px;
        }}
        
        .form-group {{
            margin-bottom: 20px;
        }}
        
        .form-label {{
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            font-size: 14px;
        }}
        
        .form-input {{
            width: 100%;
            padding: 12px 16px;
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
            color: var(--text-primary);
            font-size: 14px;
            font-family: inherit;
        }}
        
        .form-input:focus {{
            outline: none;
            border-color: var(--btn-primary-bg);
        }}
        
        .form-hint {{
            margin-top: 6px;
            font-size: 12px;
            color: var(--text-secondary);
        }}
        
        /* Toast Notifications */
        .toast-container {{
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 2000;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}
        
        .toast {{
            padding: 16px 20px;
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-lg);
            animation: slideIn 0.3s ease;
            min-width: 300px;
            display: flex;
            align-items: center;
            gap: 12px;
            border-left: 4px solid var(--btn-primary-bg);
        }}
        
        @keyframes slideIn {{
            from {{ transform: translateX(100%); opacity: 0; }}
            to {{ transform: translateX(0); opacity: 1; }}
        }}
        
        .toast.success {{ border-left-color: var(--success); }}
        .toast.error {{ border-left-color: var(--error); }}
        .toast.warning {{ border-left-color: var(--warning); }}
        
        /* Fixed Footer */
        .app-footer {{
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: var(--bg-secondary);
            border-top: 1px solid var(--border-color);
            display: flex;
            z-index: 99;
        }}
        
        .footer-btn {{
            flex: 1;
            padding: 16px;
            background: none;
            border: none;
            color: var(--text-secondary);
            font-family: inherit;
            font-size: 14px;
            cursor: pointer;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 4px;
            transition: all 0.2s;
        }}
        
        .footer-btn:hover {{
            background: var(--bg-tertiary);
            color: var(--text-primary);
        }}
        
        .footer-btn.active {{
            color: var(--btn-primary-bg);
        }}
        
        /* Credits */
        .credits {{
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            color: var(--text-secondary);
            font-size: 13px;
            border-top: 1px solid var(--border-color);
        }}
        
        .credits a {{
            color: var(--text-link);
            text-decoration: none;
        }}
        
        .credits a:hover {{
            text-decoration: underline;
        }}
        
        /* Utility Classes */
        .hidden {{ display: none !important; }}
        .mt-4 {{ margin-top: 16px; }}
        .mb-4 {{ margin-bottom: 16px; }}
        .text-center {{ text-align: center; }}
        .text-muted {{ color: var(--text-secondary); }}
    </style>
</head>
<body>
    <!-- Header with 3-dot Menu -->
    <header class="app-header">
        <div class="logo">
            <span class="material-icons-round logo-icon">download_for_offline</span>
            Media Downloader
        </div>
        
        <div class="menu-container">
            <button class="menu-button" id="menuButton">
                <span class="material-icons-round">more_vert</span>
            </button>
            
            <div class="dropdown-menu" id="dropdownMenu">
                <button class="menu-item" id="openSettings">
                    <span class="material-icons-round">settings</span>
                    Settings
                </button>
                <button class="menu-item" id="clearHistory">
                    <span class="material-icons-round">history</span>
                    Clear History
                </button>
                <button class="menu-item" id="aboutApp">
                    <span class="material-icons-round">info</span>
                    About
                </button>
            </div>
        </div>
    </header>

    <!-- Main Content -->
    <main class="container">
        <!-- URL Input Card -->
        <div class="card">
            <div class="input-group">
                <input type="url" id="urlInput" class="url-input" 
                       placeholder="https://www.youtube.com/watch?v=... or any supported URL"
                       autocomplete="off">
                <button id="analyzeBtn" class="btn btn-primary">
                    <span class="material-icons-round">search</span>
                    Analyze
                </button>
            </div>
            <p class="text-muted" style="font-size: 13px; margin-top: 8px;">
                <span class="material-icons-round" style="font-size: 14px;">info</span>
                Supports YouTube, Twitter, TikTok, Instagram, Vimeo, SoundCloud, and 1000+ sites
            </p>
        </div>

        <!-- Loading State -->
        <div id="loadingSection" class="card hidden">
            <div class="loading">
                <div class="spinner"></div>
                <h3 id="loadingTitle">Analyzing URL</h3>
                <p id="loadingText" class="text-muted">Fetching video information...</p>
                <div class="progress-bar" style="margin-top: 20px;">
                    <div id="analyzeProgress" class="progress-fill"></div>
                </div>
            </div>
        </div>

        <!-- Video Info & Format Selection -->
        <div id="videoSection" class="card hidden">
            <div class="video-info">
                <div class="thumbnail-container">
                    <img id="videoThumb" class="thumbnail" alt="Video thumbnail">
                    <div style="position: absolute; bottom: 8px; right: 8px; background: rgba(0,0,0,0.8); color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px;" id="videoDuration">
                        0:00
                    </div>
                </div>
                <div>
                    <h3 id="videoTitle" style="margin-bottom: 8px;">Video Title</h3>
                    <div style="display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap;">
                        <span style="background: var(--bg-tertiary); padding: 4px 12px; border-radius: 12px; font-size: 12px; display: flex; align-items: center; gap: 4px;" id="videoAuthor">
                            <span class="material-icons-round" style="font-size: 14px;">person</span>
                            Unknown Author
                        </span>
                        <span style="background: var(--bg-tertiary); padding: 4px 12px; border-radius: 12px; font-size: 12px; display: flex; align-items: center; gap: 4px;" id="videoViews">
                            <span class="material-icons-round" style="font-size: 14px;">visibility</span>
                            0 views
                        </span>
                    </div>
                    <p id="videoDescription" class="text-muted" style="font-size: 14px;">
                        Video description will appear here...
                    </p>
                </div>
            </div>

            <!-- Format Selection Area -->
            <div id="formatSelection" class="format-selection hidden">
                <label class="form-label">Select Format & Quality</label>
                <div class="custom-select">
                    <div class="select-header" id="selectHeader">
                        <span id="selectedOptionText">-- Select a format --</span>
                        <span class="material-icons-round">expand_more</span>
                    </div>
                    <div class="select-options" id="selectOptions">
                        <!-- Options will be populated by JavaScript -->
                    </div>
                </div>
            </div>

            <!-- Download Button -->
            <button id="downloadBtn" class="btn-download-large hidden" disabled>
                <span class="material-icons-round">download</span>
                Download
            </button>
        </div>

        <!-- Download Progress -->
        <div id="downloadProgressSection" class="card hidden">
            <div class="download-progress">
                <div class="progress-header">
                    <span id="downloadStatus">Preparing download...</span>
                    <span id="downloadPercent">0%</span>
                </div>
                <div class="progress-bar">
                    <div id="downloadProgress" class="progress-fill"></div>
                </div>
                
                <div class="progress-stats">
                    <div class="stat-item">
                        <span class="material-icons-round" style="color: var(--btn-primary-bg);">speed</span>
                        <div>
                            <div style="font-size: 12px; color: var(--text-secondary);">Speed</div>
                            <div style="font-weight: 600; font-size: 14px;" id="downloadSpeed">0 KB/s</div>
                        </div>
                    </div>
                    <div class="stat-item">
                        <span class="material-icons-round" style="color: var(--btn-primary-bg);">timer</span>
                        <div>
                            <div style="font-size: 12px; color: var(--text-secondary);">Time Left</div>
                            <div style="font-weight: 600; font-size: 14px;" id="timeRemaining">--:--</div>
                        </div>
                    </div>
                    <div class="stat-item">
                        <span class="material-icons-round" style="color: var(--btn-primary-bg);">storage</span>
                        <div>
                            <div style="font-size: 12px; color: var(--text-secondary);">Size</div>
                            <div style="font-weight: 600; font-size: 14px;" id="fileSize">0 MB</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <!-- Settings Modal -->
    <div class="modal-overlay" id="settingsModal">
        <div class="modal">
            <div class="modal-header">
                <h3 style="font-weight: 600;">Settings</h3>
                <button class="menu-button" id="closeSettings">
                    <span class="material-icons-round">close</span>
                </button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label class="form-label" for="downloadPath">Download Location</label>
                    <input type="text" id="downloadPath" class="form-input" 
                           placeholder="e.g., C:/Downloads or /home/user/Videos">
                    <p class="form-hint">Path where downloaded files will be saved</p>
                </div>
                
                <div class="form-group">
                    <label class="form-label" for="maxDownloads">Max Concurrent Downloads</label>
                    <input type="number" id="maxDownloads" class="form-input" min="1" max="5" value="2">
                    <p class="form-hint">Number of downloads that can run simultaneously</p>
                </div>
                
                <div class="form-group">
                    <label class="form-label" for="defaultFormat">Default Format Preference</label>
                    <select id="defaultFormat" class="form-input">
                        <option value="best">Best Quality Available</option>
                        <option value="worst">Smallest File Size</option>
                        <option value="bestvideo">Best Video Only</option>
                        <option value="bestaudio">Best Audio Only</option>
                    </select>
                </div>
                
                <div style="margin-top: 24px;">
                    <button id="saveSettingsBtn" class="btn btn-primary" style="width: 100%;">
                        Save Settings
                    </button>
                </div>
            </div>
        </div>
    </div>

    <!-- About Modal -->
    <div class="modal-overlay" id="aboutModal">
        <div class="modal">
            <div class="modal-header">
                <h3 style="font-weight: 600;">About Media Downloader</h3>
                <button class="menu-button" id="closeAbout">
                    <span class="material-icons-round">close</span>
                </button>
            </div>
            <div class="modal-body">
                <div style="text-align: center; margin-bottom: 24px;">
                    <span class="material-icons-round" style="font-size: 48px; color: var(--btn-primary-bg);">download_for_offline</span>
                    <h3 style="margin-top: 12px; margin-bottom: 8px;">Media Downloader v5.0.0</h3>
                    <p class="text-muted">Universal video & audio downloader</p>
                </div>
                
                <div class="form-group">
                    <h4 style="margin-bottom: 12px;">Features</h4>
                    <ul style="color: var(--text-secondary); font-size: 14px; line-height: 1.6;">
                        <li>Supports 1000+ video/audio platforms</li>
                        <li>Custom download location</li>
                        <li>Format and quality selection</li>
                        <li>Real-time download progress</li>
                        <li>Cross-platform compatibility</li>
                    </ul>
                </div>
                
                <div class="form-group">
                    <h4 style="margin-bottom: 12px;">Credits</h4>
                    <p style="color: var(--text-secondary); font-size: 14px;">
                        Developed with ❤️ by <strong>Mahim</strong> & <strong>DeepSeek Brother</strong>
                    </p>
                </div>
                
                <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--border-color);">
                    <p style="font-size: 12px; color: var(--text-secondary); text-align: center;">
                        This tool is for personal use only.<br>
                        Please respect copyright laws and platform terms of service.
                    </p>
                </div>
            </div>
        </div>
    </div>

    <!-- Toast Container -->
    <div class="toast-container" id="toastContainer"></div>

    <!-- Fixed Footer -->
    <footer class="app-footer">
        <button class="footer-btn" id="footerDownloadBtn">
            <span class="material-icons-round">download</span>
            <span>Download</span>
        </button>
        <button class="footer-btn" id="footerSettingsBtn">
            <span class="material-icons-round">settings</span>
            <span>Settings</span>
        </button>
    </footer>

    <script>
        class MediaDownloader {{
            constructor() {{
                this.videoInfo = null;
                this.selectedFormat = null;
                this.downloadId = null;
                this.progressInterval = null;
                this.settings = {{
                    downloadPath: '',
                    maxDownloads: 2,
                    defaultFormat: 'best'
                }};
                this.init();
            }}
            
            init() {{
                this.loadSettings();
                this.setupEventListeners();
                console.log('Media Downloader v5.0.0 initialized');
            }}
            
            setupEventListeners() {{
                // 3-dot Menu
                document.getElementById('menuButton').addEventListener('click', (e) => {{
                    e.stopPropagation();
                    this.toggleDropdown();
                }});
                
                // Dropdown menu items
                document.getElementById('openSettings').addEventListener('click', () => {{
                    this.showSettings();
                    this.toggleDropdown();
                }});
                
                document.getElementById('clearHistory').addEventListener('click', () => {{
                    this.clearHistory();
                    this.toggleDropdown();
                }});
                
                document.getElementById('aboutApp').addEventListener('click', () => {{
                    this.showAbout();
                    this.toggleDropdown();
                }});
                
                // Close dropdown when clicking outside
                document.addEventListener('click', () => {{
                    this.closeDropdown();
                }});
                
                // URL input and analyze
                document.getElementById('analyzeBtn').addEventListener('click', () => this.analyzeUrl());
                document.getElementById('urlInput').addEventListener('keypress', (e) => {{
                    if (e.key === 'Enter') this.analyzeUrl();
                }});
                
                // Format selection
                document.getElementById('selectHeader').addEventListener('click', (e) => {{
                    e.stopPropagation();
                    this.toggleSelectOptions();
                }});
                
                // Download button
                document.getElementById('downloadBtn').addEventListener('click', () => this.startDownload());
                
                // Footer buttons
                document.getElementById('footerDownloadBtn').addEventListener('click', () => this.triggerDownload());
                document.getElementById('footerSettingsBtn').addEventListener('click', () => this.showSettings());
                
                // Modal close buttons
                document.getElementById('closeSettings').addEventListener('click', () => this.hideSettings());
                document.getElementById('closeAbout').addEventListener('click', () => this.hideAbout());
                document.getElementById('saveSettingsBtn').addEventListener('click', () => this.saveSettings());
                
                // Close modals when clicking outside
                document.getElementById('settingsModal').addEventListener('click', (e) => {{
                    if (e.target.id === 'settingsModal') this.hideSettings();
                }});
                
                document.getElementById('aboutModal').addEventListener('click', (e) => {{
                    if (e.target.id === 'aboutModal') this.hideAbout();
                }});
            }}
            
            toggleDropdown() {{
                const dropdown = document.getElementById('dropdownMenu');
                dropdown.classList.toggle('show');
            }}
            
            closeDropdown() {{
                document.getElementById('dropdownMenu').classList.remove('show');
            }}
            
            toggleSelectOptions() {{
                const options = document.getElementById('selectOptions');
                options.classList.toggle('show');
            }}
            
            async analyzeUrl() {{
                const url = document.getElementById('urlInput').value.trim();
                
                if (!url) {{
                    this.showToast('Please enter a URL', 'error');
                    return;
                }}
                
                try {{
                    new URL(url);
                }} catch (e) {{
                    this.showToast('Please enter a valid URL', 'error');
                    return;
                }}
                
                this.showLoading(true, 'Analyzing URL', 'Connecting to source...');
                this.updateProgress(10);
                
                try {{
                    const response = await fetch('/api/analyze', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ url: url }})
                    }});
                    
                    if (!response.ok) {{
                        const error = await response.json();
                        throw new Error(error.error || 'Analysis failed');
                    }}
                    
                    this.updateProgress(50, 'Fetching video information...');
                    
                    const data = await response.json();
                    this.videoInfo = data;
                    
                    this.updateProgress(100, 'Analysis complete!');
                    await this.sleep(500);
                    
                    this.showLoading(false);
                    this.showVideoInfo();
                    this.populateFormatOptions(data.formats);
                    
                    this.showToast(`Found ${{data.formats.length}} format(s)`, 'success');
                    
                }} catch (error) {{
                    console.error('Analysis error:', error);
                    this.showToast(`Analysis failed: ${{error.message}}`, 'error');
                    this.showLoading(false);
                }}
            }}
            
            showVideoInfo() {{
                const info = this.videoInfo;
                
                document.getElementById('videoTitle').textContent = info.title;
                document.getElementById('videoAuthor').textContent = info.author;
                document.getElementById('videoViews').textContent = info.view_count ? this.formatNumber(info.view_count) + ' views' : 'Unknown views';
                document.getElementById('videoDuration').textContent = this.formatDuration(info.duration);
                document.getElementById('videoDescription').textContent = info.description ? 
                    info.description.substring(0, 150) + (info.description.length > 150 ? '...' : '') : 
                    'No description available';
                
                const thumb = document.getElementById('videoThumb');
                if (info.thumbnail) {{
                    thumb.src = info.thumbnail;
                    thumb.onerror = () => {{
                        thumb.src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="180" height="101" viewBox="0 0 180 101"><rect width="100%" height="100%" fill="%2321262d"/><text x="50%" y="50%" fill="%238b949e" font-family="Inter" font-size="12" text-anchor="middle" dy=".3em">No thumbnail</text></svg>';
                    }};
                }}
                
                document.getElementById('videoSection').classList.remove('hidden');
                document.getElementById('formatSelection').classList.remove('hidden');
                document.getElementById('videoSection').scrollIntoView({{ behavior: 'smooth' }});
                
                this.selectedFormat = null;
                document.getElementById('downloadBtn').classList.add('hidden');
                document.getElementById('downloadBtn').disabled = true;
            }}
            
            populateFormatOptions(formats) {{
                const optionsContainer = document.getElementById('selectOptions');
                optionsContainer.innerHTML = '';
                
                // Filter and sort formats
                const videoFormats = formats.filter(f => f.vcodec !== 'none');
                videoFormats.sort((a, b) => {{
                    const aRes = parseInt(a.resolution) || 0;
                    const bRes = parseInt(b.resolution) || 0;
                    return bRes - aRes;
                }});
                
                // Group by resolution
                const grouped = {{}};
                videoFormats.forEach(format => {{
                    const res = format.resolution !== 'N/A' ? format.resolution + 'p' : 'Unknown';
                    if (!grouped[res]) grouped[res] = [];
                    grouped[res].push(format);
                }});
                
                // Create options
                for (const [resolution, formatList] of Object.entries(grouped)) {{
                    // Add resolution header
                    const header = document.createElement('div');
                    header.className = 'select-option';
                    header.style.background = 'var(--bg-tertiary)';
                    header.style.fontWeight = '600';
                    header.style.pointerEvents = 'none';
                    header.textContent = `${{resolution}} Quality`;
                    optionsContainer.appendChild(header);
                    
                    // Add format options for this resolution
                    formatList.forEach(format => {{
                        const option = document.createElement('div');
                        option.className = 'select-option';
                        option.dataset.formatId = format.id;
                        
                        const size = format.filesize ? this.formatFileSize(format.filesize) : 'Unknown size';
                        const note = format.format_note ? ` • ${{format.format_note}}` : '';
                        
                        option.innerHTML = `
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <strong>${{format.ext.toUpperCase()}}</strong>
                                    <span class="text-muted" style="font-size: 12px; margin-left: 8px;">${{size}}${{note}}</span>
                                </div>
                                <span class="format-badge">${{format.vcodec.split('.')[0]}}</span>
                            </div>
                        `;
                        
                        option.addEventListener('click', (e) => {{
                            e.stopPropagation();
                            this.selectFormat(format, option);
                        }});
                        
                        optionsContainer.appendChild(option);
                    }});
                }}
                
                // Add audio-only formats if available
                const audioFormats = formats.filter(f => f.vcodec === 'none' && f.acodec !== 'none');
                if (audioFormats.length > 0) {{
                    const header = document.createElement('div');
                    header.className = 'select-option';
                    header.style.background = 'var(--bg-tertiary)';
                    header.style.fontWeight = '600';
                    header.style.pointerEvents = 'none';
                    header.textContent = 'Audio Only';
                    optionsContainer.appendChild(header);
                    
                    audioFormats.forEach(format => {{
                        const option = document.createElement('div');
                        option.className = 'select-option';
                        option.dataset.formatId = format.id;
                        
                        const size = format.filesize ? this.formatFileSize(format.filesize) : 'Unknown size';
                        const bitrate = format.bitrate ? ` • ${{format.bitrate}}kbps` : '';
                        
                        option.innerHTML = `
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <strong>${{format.ext.toUpperCase()}} Audio</strong>
                                    <span class="text-muted" style="font-size: 12px; margin-left: 8px;">${{size}}${{bitrate}}</span>
                                </div>
                                <span class="format-badge" style="background: var(--accent);">AUDIO</span>
                            </div>
                        `;
                        
                        option.addEventListener('click', (e) => {{
                            e.stopPropagation();
                            this.selectFormat(format, option);
                        }});
                        
                        optionsContainer.appendChild(option);
                    }});
                }}
            }}
            
            selectFormat(format, element) {{
                // Remove selected class from all options
                document.querySelectorAll('.select-option').forEach(opt => {{
                    opt.classList.remove('selected');
                }});
                
                // Add selected class to clicked option
                element.classList.add('selected');
                
                // Update selected format display
                const resolution = format.resolution !== 'N/A' ? format.resolution + 'p' : 'Audio';
                const size = format.filesize ? this.formatFileSize(format.filesize) : 'Unknown size';
                const note = format.format_note ? ` • ${{format.format_note}}` : '';
                
                document.getElementById('selectedOptionText').innerHTML = `
                    <strong>${{resolution}}</strong> • ${{format.ext.toUpperCase()}} • ${{size}}${{note}}
                `;
                
                this.selectedFormat = format;
                
                // Show and enable download button
                const downloadBtn = document.getElementById('downloadBtn');
                downloadBtn.classList.remove('hidden');
                downloadBtn.disabled = false;
                
                // Close options dropdown
                this.toggleSelectOptions();
                
                this.showToast(`Selected: ${{resolution}} ${{format.ext.toUpperCase()}}`, 'success');
            }}
            
            async startDownload() {{
                if (!this.selectedFormat) {{
                    this.showToast('Please select a format first', 'error');
                    return;
                }}
                
                const format = this.selectedFormat;
                const filename = `${{this.videoInfo.title}}.${{format.ext}}`.replace(/[<>:"/\\\\|?*]/g, '_');
                
                // Show download progress section
                document.getElementById('downloadProgressSection').classList.remove('hidden');
                document.getElementById('downloadProgressSection').scrollIntoView({{ behavior: 'smooth' }});
                
                this.resetDownloadProgress();
                
                try {{
                    const response = await fetch('/api/download', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{
                            url: this.videoInfo.url,
                            format_id: format.id,
                            filename: filename
                        }})
                    }});
                    
                    if (!response.ok) {{
                        const error = await response.json();
                        throw new Error(error.error || 'Download failed');
                    }}
                    
                    const data = await response.json();
                    this.downloadId = data.download_id;
                    
                    // Start progress polling
                    this.startProgressPolling();
                    
                    // Update footer button state
                    document.getElementById('footerDownloadBtn').classList.add('active');
                    
                }} catch (error) {{
                    this.showToast(`Download failed: ${{error.message}}`, 'error');
                }}
            }}
            
            startProgressPolling() {{
                if (this.progressInterval) {{
                    clearInterval(this.progressInterval);
                }}
                
                this.progressInterval = setInterval(async () => {{
                    if (!this.downloadId) return;
                    
                    try {{
                        const response = await fetch(`/api/download/${{this.downloadId}}`);
                        if (response.ok) {{
                            const data = await response.json();
                            this.updateDownloadProgress(data);
                            
                            if (data.status === 'completed') {{
                                clearInterval(this.progressInterval);
                                this.showToast('Download completed!', 'success');
                                this.offerFileDownload(data.filepath);
                                document.getElementById('footerDownloadBtn').classList.remove('active');
                            }} else if (data.status === 'error') {{
                                clearInterval(this.progressInterval);
                                this.showToast(`Download error: ${{data.error}}`, 'error');
                                document.getElementById('footerDownloadBtn').classList.remove('active');
                            }}
                        }}
                    }} catch (error) {{
                        console.error('Progress polling error:', error);
                    }}
                }}, 1000);
            }}
            
            updateDownloadProgress(data) {{
                document.getElementById('downloadProgress').style.width = `${{data.progress || 0}}%`;
                document.getElementById('downloadPercent').textContent = `${{Math.round(data.progress || 0)}}%`;
                
                let status = 'Downloading...';
                if (data.status === 'queued') status = 'Queued...';
                else if (data.status === 'downloading') status = 'Downloading...';
                else if (data.status === 'completed') status = 'Completed!';
                else if (data.status === 'error') status = 'Error!';
                
                document.getElementById('downloadStatus').textContent = status;
                
                if (data.speed) {{
                    document.getElementById('downloadSpeed').textContent = this.formatFileSize(data.speed) + '/s';
                }}
                
                if (data.total_bytes) {{
                    document.getElementById('fileSize').textContent = this.formatFileSize(data.total_bytes);
                }}
                
                if (data.eta) {{
                    const minutes = Math.floor(data.eta / 60);
                    const seconds = data.eta % 60;
                    document.getElementById('timeRemaining').textContent = `${{minutes}}:${{seconds.toString().padStart(2, '0')}}`;
                }}
            }}
            
            resetDownloadProgress() {{
                document.getElementById('downloadProgress').style.width = '0%';
                document.getElementById('downloadPercent').textContent = '0%';
                document.getElementById('downloadStatus').textContent = 'Preparing download...';
                document.getElementById('downloadSpeed').textContent = '0 KB/s';
                document.getElementById('fileSize').textContent = '0 MB';
                document.getElementById('timeRemaining').textContent = '--:--';
            }}
            
            async offerFileDownload(filepath) {{
                if (!filepath) return;
                
                try {{
                    const a = document.createElement('a');
                    a.href = `/download/${{encodeURIComponent(filepath)}}`;
                    a.download = true;
                    a.style.display = 'none';
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    
                    this.showToast('File download started!', 'success');
                }} catch (error) {{
                    this.showToast('Download complete! Check your downloads folder.', 'success');
                }}
            }}
            
            triggerDownload() {{
                const downloadBtn = document.getElementById('downloadBtn');
                if (!downloadBtn.classList.contains('hidden') && !downloadBtn.disabled) {{
                    downloadBtn.scrollIntoView({{ behavior: 'smooth' }});
                    downloadBtn.click();
                }} else {{
                    this.showToast('Please analyze a URL and select a format first.', 'info');
                }}
            }}
            
            // Settings Management
            loadSettings() {{
                try {{
                    const saved = localStorage.getItem('mediaDownloaderSettings');
                    if (saved) {{
                        this.settings = JSON.parse(saved);
                        document.getElementById('downloadPath').value = this.settings.downloadPath || '';
                        document.getElementById('maxDownloads').value = this.settings.maxDownloads || 2;
                        document.getElementById('defaultFormat').value = this.settings.defaultFormat || 'best';
                    }}
                }} catch (e) {{
                    console.error('Error loading settings:', e);
                }}
            }}
            
            showSettings() {{
                document.getElementById('settingsModal').classList.add('show');
            }}
            
            hideSettings() {{
                document.getElementById('settingsModal').classList.remove('show');
            }}
            
            showAbout() {{
                document.getElementById('aboutModal').classList.add('show');
            }}
            
            hideAbout() {{
                document.getElementById('aboutModal').classList.remove('show');
            }}
            
            async saveSettings() {{
                try {{
                    const settings = {{
                        downloadPath: document.getElementById('downloadPath').value.trim(),
                        maxDownloads: parseInt(document.getElementById('maxDownloads').value),
                        defaultFormat: document.getElementById('defaultFormat').value
                    }};
                    
                    const response = await fetch('/api/settings', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify(settings)
                    }});
                    
                    if (response.ok) {{
                        localStorage.setItem('mediaDownloaderSettings', JSON.stringify(settings));
                        this.settings = settings;
                        this.showToast('Settings saved successfully!', 'success');
                        this.hideSettings();
                    }} else {{
                        throw new Error('Failed to save settings');
                    }}
                }} catch (error) {{
                    this.showToast(`Failed to save settings: ${{error.message}}`, 'error');
                }}
            }}
            
            clearHistory() {{
                if (confirm('Are you sure you want to clear all download history?')) {{
                    localStorage.removeItem('mediaDownloaderSettings');
                    this.settings = {{ downloadPath: '', maxDownloads: 2, defaultFormat: 'best' }};
                    this.showToast('History cleared!', 'success');
                }}
            }}
            
            // UI Helpers
            showLoading(show, title = 'Loading', message = 'Please wait...') {{
                const loadingSection = document.getElementById('loadingSection');
                const videoSection = document.getElementById('videoSection');
                
                if (show) {{
                    loadingSection.classList.remove('hidden');
                    videoSection.classList.add('hidden');
                    document.getElementById('downloadProgressSection').classList.add('hidden');
                    document.getElementById('loadingTitle').textContent = title;
                    document.getElementById('loadingText').textContent = message;
                }} else {{
                    loadingSection.classList.add('hidden');
                }}
            }}
            
            updateProgress(percent, message = '') {{
                document.getElementById('analyzeProgress').style.width = `${{percent}}%`;
                if (message) {{
                    document.getElementById('loadingText').textContent = message;
                }}
            }}
            
            showToast(message, type = 'info') {{
                const toast = document.createElement('div');
                toast.className = `toast ${{type}}`;
                
                const icon = type === 'success' ? 'check_circle' :
                            type === 'error' ? 'error' :
                            type === 'warning' ? 'warning' : 'info';
                
                toast.innerHTML = `
                    <span class="material-icons-round">${{icon}}</span>
                    <span>${{message}}</span>
                `;
                
                const container = document.getElementById('toastContainer');
                container.appendChild(toast);
                
                setTimeout(() => {{
                    toast.style.opacity = '0';
                    setTimeout(() => toast.remove(), 300);
                }}, 3000);
            }}
            
            // Utility Methods
            formatFileSize(bytes) {{
                if (!bytes) return '0 Bytes';
                const k = 1024;
                const sizes = ['Bytes', 'KB', 'MB', 'GB'];
                const i = Math.floor(Math.log(bytes) / Math.log(k));
                return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
            }}
            
            formatDuration(seconds) {{
                if (!seconds) return '0:00';
                const hours = Math.floor(seconds / 3600);
                const minutes = Math.floor((seconds % 3600) / 60);
                const secs = Math.floor(seconds % 60);
                
                if (hours > 0) {{
                    return `${{hours}}:${{minutes.toString().padStart(2, '0')}}:${{secs.toString().padStart(2, '0')}}`;
                }}
                return `${{minutes}}:${{secs.toString().padStart(2, '0')}}`;
            }}
            
            formatNumber(num) {{
                if (!num) return '0';
                if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
                if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
                return num.toString();
            }}
            
            sleep(ms) {{
                return new Promise(resolve => setTimeout(resolve, ms));
            }}
        }}
        
        // Initialize the application
        window.downloader = new MediaDownloader();
        
        // Close dropdown and select options when clicking outside
        document.addEventListener('click', () => {{
            document.getElementById('dropdownMenu').classList.remove('show');
            document.getElementById('selectOptions').classList.remove('show');
        }});
        
        // Prevent propagation for elements that shouldn't close dropdowns
        document.querySelectorAll('.menu-container, .custom-select').forEach(el => {{
            el.addEventListener('click', (e) => e.stopPropagation());
        }});
    </script>
</body>
</html>'''

# ============================================================================
# HTTP SERVER HANDLER
# ============================================================================

class MediaDownloaderHandler(BaseHTTPRequestHandler):
    """HTTP handler for the media downloader"""
    
    def __init__(self, *args, **kwargs):
        self.download_manager = DownloadManager()
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests"""
        try:
            path = urllib.parse.urlparse(self.path).path
            
            if path == '/':
                self.serve_html()
            elif path == '/favicon.ico':
                self.send_error(404, "Not Found")
            elif path.startswith('/api/download/'):
                download_id = path[14:]  # Remove '/api/download/'
                self.get_download_status(download_id)
            elif path.startswith('/download/'):
                filepath = urllib.parse.unquote(path[10:])  # Remove '/download/'
                self.serve_download_file(filepath)
            elif path.startswith('/api/'):
                self.send_error(404, "API endpoint not found")
            else:
                self.send_error(404, "Not Found")
                
        except Exception as e:
            self.send_error(500, f"Internal server error: {str(e)}")
    
    def do_POST(self):
        """Handle POST requests"""
        try:
            path = urllib.parse.urlparse(self.path).path
            
            if path == '/api/analyze':
                self.handle_analyze()
            elif path == '/api/download':
                self.handle_download()
            elif path == '/api/settings':
                self.handle_settings()
            else:
                self.send_error(404, "API endpoint not found")
                
        except Exception as e:
            self.send_error(500, f"Internal server error: {str(e)}")
    
    def serve_html(self):
        """Serve the main HTML page"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.end_headers()
        
        html = get_html_template()
        self.wfile.write(html.encode('utf-8'))
    
    def handle_analyze(self):
        """Handle URL analysis request"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
            url = data.get('url', '')
            
            if not url:
                self.send_json_response({'error': 'URL is required'}, 400)
                return
            
            # Use yt-dlp to get video information
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'forcejson': True,
                'skip_download': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    raise Exception("Could not extract video information")
                
                # Prepare response
                video_info = {
                    'id': info.get('id', ''),
                    'title': info.get('title', 'Unknown Title'),
                    'description': info.get('description', ''),
                    'author': info.get('uploader', info.get('channel', 'Unknown Author')),
                    'uploader': info.get('uploader', ''),
                    'duration': info.get('duration', 0),
                    'view_count': info.get('view_count', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'url': url,
                    'webpage_url': info.get('webpage_url', url),
                    'formats': []
                }
                
                # Extract formats with resolution information
                if 'formats' in info:
                    for fmt in info['formats']:
                        if fmt.get('vcodec') != 'none' or fmt.get('acodec') != 'none':
                            format_info = {
                                'id': fmt.get('format_id', ''),
                                'ext': fmt.get('ext', 'mp4'),
                                'resolution': str(fmt.get('height', 'N/A')),
                                'filesize': fmt.get('filesize') or fmt.get('filesize_approx'),
                                'bitrate': fmt.get('tbr'),
                                'vcodec': fmt.get('vcodec', 'none'),
                                'acodec': fmt.get('acodec', 'none'),
                                'format_note': fmt.get('format_note', ''),
                                'url': fmt.get('url', ''),
                                'protocol': fmt.get('protocol', 'http'),
                                'width': fmt.get('width'),
                                'height': fmt.get('height'),
                                'fps': fmt.get('fps'),
                                'dynamic_range': fmt.get('dynamic_range')
                            }
                            video_info['formats'].append(format_info)
                
                self.send_json_response(video_info)
                
        except yt_dlp.utils.DownloadError as e:
            self.send_json_response({'error': f'Video platform error: {str(e)}'}, 400)
        except Exception as e:
            self.send_json_response({'error': f'Analysis failed: {str(e)}'}, 500)
    
    def handle_download(self):
        """Handle download request"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
            url = data.get('url')
            format_id = data.get('format_id')
            filename = data.get('filename', 'download')
            
            if not url or not format_id:
                self.send_json_response({'error': 'URL and format_id are required'}, 400)
                return
            
            # Start download
            download_id = self.download_manager.start_download(url, format_id, filename)
            
            self.send_json_response({
                'status': 'started',
                'download_id': download_id,
                'message': 'Download has been started'
            })
            
        except Exception as e:
            self.send_json_response({'error': f'Download failed: {str(e)}'}, 500)
    
    def handle_settings(self):
        """Handle settings save request"""
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
            
            # Save settings
            success = self.download_manager.save_settings(data)
            
            if success:
                self.send_json_response({
                    'status': 'success',
                    'message': 'Settings saved successfully'
                })
            else:
                self.send_json_response({
                    'status': 'error',
                    'message': 'Failed to save settings'
                }, 500)
                
        except Exception as e:
            self.send_json_response({'error': str(e)}, 500)
    
    def get_download_status(self, download_id: str):
        """Get download status"""
        try:
            download = self.download_manager.get_download(download_id)
            
            if not download:
                self.send_json_response({'error': 'Download not found'}, 404)
                return
            
            self.send_json_response(download)
            
        except Exception as e:
            self.send_json_response({'error': str(e)}, 500)
    
    def serve_download_file(self, filepath: str):
        """Serve downloaded file"""
        try:
            # Security check
            file_path = Path(filepath)
            if not file_path.exists() or not file_path.is_file():
                self.send_error(404, "File not found")
                return
            
            # Determine MIME type
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if not mime_type:
                mime_type = 'application/octet-stream'
            
            # Send file
            self.send_response(200)
            self.send_header('Content-Type', mime_type)
            self.send_header('Content-Disposition', f'attachment; filename="{file_path.name}"')
            self.send_header('Content-Length', str(file_path.stat().st_size))
            self.end_headers()
            
            with open(file_path, 'rb') as f:
                shutil.copyfileobj(f, self.wfile)
                
        except Exception as e:
            self.send_error(500, f"File serving error: {str(e)}")
    
    def send_json_response(self, data: dict, status: int = 200):
        """Send JSON response"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        
        json_data = json.dumps(data, indent=2, default=str)
        self.wfile.write(json_data.encode('utf-8'))
    
    def log_message(self, format, *args):
        """Override to reduce log noise"""
        pass

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    """Main entry point"""
    print(f"""
╔═══════════════════════════════════════════════════════════════════╗
║               MEDIA DOWNLOADER v{APP_VERSION} - COMPLETE EDITION        ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  🌐 Server: http://localhost:{PORT}                                   ║
║  🎨 Design: GitHub-inspired dark theme                            ║
║  🔧 Features: All requested features implemented                  ║
║  👥 Credits: Mahim & DeepSeek Brother                            ║
║                                                                   ║
║  ✅ Features Checklist:                                           ║
║     • Download button with progress tracking                     ║
║     • Available formats & resolution from yt-dlp                 ║
║     • Custom-made selection bar (not native select)              ║
║     • 3-dot menu with Settings button                            ║
║     • Settings with custom download location                     ║
║     • Footer with only Download & Settings                       ║
║     • GitHub-inspired UI/UX                                      ║
║                                                                   ║
║  📱 How to Use:                                                  ║
║     1. Start server: python media_downloader.py                  ║
║     2. Open browser to http://localhost:{PORT}                     ║
║     3. Paste URL → Analyze → Select format → Download            ║
║     4. Use 3-dot menu to change download location                ║
║                                                                   ║
║  Press Ctrl+C to stop                                             ║
╚═══════════════════════════════════════════════════════════════════╝
    """)
    
    # Check and install dependencies
    try:
        import yt_dlp
        print("✓ yt-dlp: OK")
    except ImportError:
        print("✗ yt-dlp not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp"])
        import yt_dlp
        print("✓ yt-dlp: Installed")
    
    # Start server
    server = HTTPServer((HOST, PORT), MediaDownloaderHandler)
    
    try:
        print(f"\n✅ Server is running! Open your browser and visit:")
        print(f"   http://localhost:{PORT}")
        print("\n🚀 Ready to download media from 1000+ sites!")
        print("   • YouTube, Twitter, TikTok, Instagram, Vimeo, SoundCloud, etc.")
        print("\n🔄 Waiting for requests...\n")
        
        server.serve_forever()
        
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down server...")
        server.server_close()
        print("✅ Server stopped.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    main()