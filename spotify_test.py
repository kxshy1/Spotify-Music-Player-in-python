import json
import os
import random
import time
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
import mutagen
import pygame


BACKGROUND = "#10110f"
SIDEBAR = "#151714"
SURFACE = "#1b1e1a"
SURFACE_HOVER = "#252923"
TEXT = "#f5f5f0"
MUTED = "#9a9e96"
GREEN = "#b5f36b"
GREEN_DARK = "#26351d"
RED = "#ff8378"
def format_time(milliseconds):
    seconds = max(0, int(milliseconds or 0) // 1000)
    return f"{seconds // 60}:{seconds % 60:02}"


def track_artists(track):
    return ", ".join(artist["name"] for artist in track.get("artists", []))


class MusicPlayer:
    def __init__(self, root):
        self.root = root
        self.current_track = None
        self.current_duration = 0
        self.is_playing = False
        self.page = "Your Music"
        self.local_tracks = []
        self.local_track_index = None
        self.local_shuffle_enabled = False
        self.local_repeat_enabled = False
        self.local_started_at = 0.0
        self.local_position = 0
        self.local_progress_after_id = None
        data_home = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        self.data_directory = data_home / "kaustubh-music-player"
        self.local_library_path = self.data_directory / "library.json"
        self.liked_library_path = self.data_directory / "liked.json"
        self.recent_library_path = self.data_directory / "recent.json"
        self.favorite_paths = set()
        self.recent_paths = []
        self._load_local_library()
        self._load_local_collections()
        self.playback_source = "local"

        self.audio_available = False
        try:
            pygame.mixer.init()
            self.audio_available = True
        except pygame.error as error:
            self.audio_error = str(error)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")
        self.root.title("Kaustubh Music Player")
        self.root.geometry("1180x800")
        self.root.minsize(900, 640)
        self.root.configure(fg_color=BACKGROUND)

        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_workspace()
        self._build_player()
        self._set_local_volume(self.volume_slider.get())
        self._update_like_button()
        self.navigate("Your Music")
        if not self.audio_available:
            self._set_status(f"Audio output unavailable: {self.audio_error}", error=True)
        self.root.protocol("WM_DELETE_WINDOW", self._close)


    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(
            self.root, width=225, corner_radius=0, fg_color=SIDEBAR
        )
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(12, weight=1)

        ctk.CTkLabel(
            sidebar,
            text="♫  music player",
            font=("Arial", 23, "bold"),
            text_color=TEXT,
        ).grid(row=0, column=0, sticky="w", padx=23, pady=(27, 38))

        ctk.CTkLabel(
            sidebar,
            text="YOUR SPACE",
            font=("Arial", 10, "bold"),
            text_color="#72776d",
        ).grid(row=1, column=0, sticky="w", padx=25, pady=(0, 10))

        self.nav_buttons = {}
        for row, (label, icon) in enumerate(
            (
                ("Your Music", "♫"),
                ("Search", "⌕"),
                ("Liked Songs", "♡"),
                ("Recently Played", "◷"),
                ("Queue", "≡"),
                ("About", "ⓘ"),
            ),
            start=2,
        ):
            button = ctk.CTkButton(
                sidebar,
                text=f"{icon}    {label}",
                anchor="w",
                height=43,
                corner_radius=10,
                fg_color="transparent",
                hover_color=SURFACE_HOVER,
                text_color=MUTED,
                font=("Arial", 14, "bold"),
                command=lambda page=label: self.navigate(page),
            )
            button.grid(row=row, column=0, sticky="ew", padx=12, pady=2)
            self.nav_buttons[label] = button

        ctk.CTkLabel(
            sidebar,
            text="OFFLINE LIBRARY",
            text_color="#777d73",
            font=("Arial", 9, "bold"),
        ).grid(row=10, column=0, sticky="w", padx=25, pady=(14, 18))

    def _build_workspace(self):
        workspace = ctk.CTkFrame(self.root, fg_color=BACKGROUND, corner_radius=0)
        workspace.grid(row=0, column=1, sticky="nsew")
        workspace.grid_rowconfigure(1, weight=1)
        workspace.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(workspace, fg_color=BACKGROUND, height=76)
        header.grid(row=0, column=0, sticky="ew", padx=31)
        header.grid_columnconfigure(0, weight=1)
        self.page_title = ctk.CTkLabel(
            header, text="Home", font=("Arial", 22, "bold"), text_color=TEXT
        )
        self.page_title.grid(row=0, column=0, sticky="w", pady=(20, 15))
        self.status_label = ctk.CTkLabel(
            header, text="", text_color=MUTED, font=("Arial", 11)
        )
        self.status_label.grid(row=0, column=1, padx=(10, 17), pady=(20, 15))
        self.add_music_button = ctk.CTkButton(
            header,
            text="Add music",
            width=112,
            height=37,
            corner_radius=10,
            fg_color=GREEN,
            hover_color="#c9ff91",
            text_color="#17200f",
            font=("Arial", 12, "bold"),
            command=self._add_local_files,
        )
        self.add_music_button.grid(row=0, column=2, pady=(17, 15))

        self.content = ctk.CTkFrame(workspace, fg_color=BACKGROUND, corner_radius=0)
        self.content.grid(row=1, column=0, sticky="nsew", padx=26, pady=(0, 17))
        self.content.grid_columnconfigure(0, weight=1)

    def _build_player(self):
        dock = ctk.CTkFrame(
            self.root, height=114, corner_radius=0, fg_color="#181a17"
        )
        dock.grid(row=1, column=0, columnspan=2, sticky="ew")
        dock.grid_propagate(False)
        dock.grid_columnconfigure(1, weight=1)
        dock.grid_columnconfigure(2, weight=1)

        self.dock_cover = ctk.CTkLabel(
            dock,
            text="♫",
            width=58,
            height=58,
            corner_radius=9,
            fg_color=SURFACE,
            text_color=GREEN,
            font=("Arial", 25, "bold"),
        )
        self.dock_cover.grid(row=0, column=0, rowspan=2, padx=(20, 12), pady=16)

        song_info = ctk.CTkFrame(dock, fg_color="transparent")
        song_info.grid(row=0, column=1, rowspan=2, sticky="w", pady=14)
        self.dock_title = ctk.CTkLabel(
            song_info,
            text="Nothing playing",
            text_color=TEXT,
            font=("Arial", 13, "bold"),
            anchor="w",
            width=200,
        )
        self.dock_title.pack(anchor="w")
        self.dock_artist = ctk.CTkLabel(
            song_info,
            text="Choose music from your library",
            text_color=MUTED,
            font=("Arial", 11),
            anchor="w",
            width=250,
        )
        self.dock_artist.pack(anchor="w", pady=(2, 0))

        center = ctk.CTkFrame(dock, fg_color="transparent")
        center.grid(row=0, column=2, sticky="ew", padx=16, pady=(8, 0))
        center.grid_columnconfigure(1, weight=1)

        self.shuffle_button = self._dock_button(center, "⤨", self.toggle_shuffle)
        self.shuffle_button.grid(row=0, column=0, padx=5)
        self.previous_button = self._dock_button(center, "|◀", self.previous_track)
        self.previous_button.grid(row=0, column=1, padx=5)
        self.play_button = ctk.CTkButton(
            center,
            text="▶",
            width=42,
            height=42,
            corner_radius=22,
            fg_color=TEXT,
            hover_color="#dfe3d8",
            text_color="#161814",
            font=("Arial", 16, "bold"),
            command=self.toggle_play,
        )
        self.play_button.grid(row=0, column=2, padx=7)
        self.next_button = self._dock_button(center, "▶|", self.next_track)
        self.next_button.grid(row=0, column=3, padx=5)
        self.repeat_button = self._dock_button(center, "↻", self.toggle_repeat)
        self.repeat_button.grid(row=0, column=4, padx=5)

        progress_row = ctk.CTkFrame(center, fg_color="transparent")
        progress_row.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(1, 0))
        self.current_time_label = ctk.CTkLabel(
            progress_row, text="0:00", width=39, text_color=MUTED, font=("Arial", 10)
        )
        self.current_time_label.pack(side="left")
        self.progress_slider = ctk.CTkSlider(
            progress_row,
            from_=0,
            to=100,
            height=14,
            button_length=11,
            progress_color=GREEN,
            button_color=TEXT,
            button_hover_color="#d9ffd0",
            fg_color="#3b3e39",
            command=self._preview_seek,
        )
        self.progress_slider.set(0)
        self.progress_slider.pack(side="left", fill="x", expand=True, padx=7)
        self.progress_slider.bind("<ButtonRelease-1>", self._seek)
        self.total_time_label = ctk.CTkLabel(
            progress_row, text="0:00", width=39, text_color=MUTED, font=("Arial", 10)
        )
        self.total_time_label.pack(side="right")

        right = ctk.CTkFrame(dock, fg_color="transparent")
        right.grid(row=0, column=3, rowspan=2, sticky="e", padx=(12, 20))
        self.like_button = self._dock_button(right, "♡", self.toggle_like)
        self.like_button.grid(row=0, column=0, padx=(0, 9))
        self.volume_slider = ctk.CTkSlider(
            right,
            from_=0,
            to=100,
            width=94,
            height=14,
            progress_color=GREEN,
            button_color=TEXT,
            button_hover_color="#d9ffd0",
            fg_color="#3b3e39",
            command=self._schedule_volume,
        )
        self.volume_slider.set(55)
        self.volume_slider.grid(row=0, column=1)

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=0)

    @staticmethod
    def _dock_button(parent, text, command):
        return ctk.CTkButton(
            parent,
            text=text,
            width=30,
            height=34,
            corner_radius=9,
            fg_color="transparent",
            hover_color=SURFACE_HOVER,
            text_color=MUTED,
            font=("Arial", 16, "bold"),
            command=command,
        )

    def _clear_content(self):
        for child in self.content.winfo_children():
            child.destroy()

    def _set_status(self, message, error=False):
        self.status_label.configure(
            text=message, text_color=RED if error else MUTED
        )

    def _close(self):
        if self.local_progress_after_id:
            self.root.after_cancel(self.local_progress_after_id)
        if self.audio_available:
            pygame.mixer.quit()
        self.root.destroy()

    def navigate(self, page):
        if page in self.nav_buttons:
            self.page = page
            for label, button in self.nav_buttons.items():
                active = label == page
                button.configure(
                    fg_color=GREEN_DARK if active else "transparent",
                    text_color=GREEN if active else MUTED,
                )
        else:
            self.page = page

        self.page_title.configure(text=page)
        if page in ("Your Music", "Local Music", "Your Library", "Home"):
            self._show_local_music()
        elif page == "Search":
            self._show_search()
        elif page == "Liked Songs":
            self._show_track_collection(
                "Liked Songs",
                [track for track in self.local_tracks if track["local_path"] in self.favorite_paths],
                "No liked songs yet. Use the heart beside a track to save it.",
            )
        elif page == "Recently Played":
            by_path = {track["local_path"]: track for track in self.local_tracks}
            self._show_track_collection(
                "Recently Played",
                [by_path[path] for path in self.recent_paths if path in by_path],
                "Your listening history will appear here.",
            )
        elif page == "Queue":
            self._show_track_collection(
                "Up Next", self.local_tracks, "Add music to build your queue."
            )
        elif page == "About":
            self._show_about()

    def _show_search(self):
        self._clear_content()
        ctk.CTkLabel(
            self.content,
            text="Find it in your music",
            text_color=TEXT,
            font=("Arial", 29, "bold"),
        ).pack(anchor="w", padx=8, pady=(15, 5))
        ctk.CTkLabel(
            self.content,
            text="Search the songs you have added to this player.",
            text_color=MUTED,
            font=("Arial", 13),
        ).pack(anchor="w", padx=8, pady=(0, 17))
        search_row = ctk.CTkFrame(self.content, fg_color="transparent")
        search_row.pack(fill="x", padx=7)
        self.search_entry = ctk.CTkEntry(
            search_row,
            height=45,
            placeholder_text="Song or artist",
            fg_color=SURFACE,
            border_color="#343830",
            text_color=TEXT,
            corner_radius=12,
            font=("Arial", 14),
        )
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.search_entry.bind("<Return>", lambda _event: self.search())
        ctk.CTkButton(
            search_row,
            text="Search",
            width=100,
            height=43,
            corner_radius=12,
            fg_color=GREEN,
            hover_color="#c9ff91",
            text_color="#17200f",
            font=("Arial", 12, "bold"),
            command=self.search,
        ).pack(side="left", padx=(9, 0))
        self.search_results = ctk.CTkScrollableFrame(
            self.content, fg_color="transparent", scrollbar_button_color="#42463f"
        )
        self.search_results.pack(fill="both", expand=True, pady=(17, 0))
        self._empty_message(self.search_results, "Add music, then search by song or artist.")

    def _show_local_music(self):
        self._clear_content()
        heading = ctk.CTkFrame(self.content, fg_color="transparent")
        heading.pack(fill="x", padx=8, pady=(12, 5))
        ctk.CTkLabel(
            heading, text="Your music", text_color=TEXT, font=("Arial", 27, "bold")
        ).pack(side="left")
        ctk.CTkButton(
            heading,
            text="Add folder",
            width=105,
            height=34,
            corner_radius=17,
            fg_color=SURFACE,
            hover_color=SURFACE_HOVER,
            text_color=TEXT,
            command=self._add_local_folder,
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            heading,
            text="Add songs",
            width=105,
            height=34,
            corner_radius=17,
            fg_color=GREEN,
            hover_color="#c9ff91",
            text_color="#17200f",
            command=self._add_local_files,
        ).pack(side="right")
        ctk.CTkLabel(
            self.content,
            text=f"{len(self.local_tracks)} tracks  ·  stored on this device",
            text_color=MUTED,
            font=("Arial", 11),
        ).pack(anchor="w", padx=9, pady=(0, 12))
        self.local_track_list = ctk.CTkScrollableFrame(
            self.content, fg_color="transparent", scrollbar_button_color="#42463f"
        )
        self.local_track_list.pack(fill="both", expand=True)
        self._render_local_tracks()

    def _show_about(self):
        self._clear_content()
        panel = ctk.CTkFrame(self.content, fg_color=SURFACE, corner_radius=20)
        panel.pack(fill="both", expand=True, padx=8, pady=8)
        ctk.CTkLabel(
            panel, text="A SMALL, PERSONAL PLAYER", text_color=GREEN, font=("Arial", 10, "bold")
        ).pack(anchor="w", padx=32, pady=(34, 14))
        ctk.CTkLabel(
            panel,
            text="Built by hand. Made to play the music you already have.",
            text_color=TEXT,
            font=("Arial", 25, "bold"),
            justify="left",
            wraplength=650,
        ).pack(anchor="w", padx=32, pady=(0, 17))
        ctk.CTkLabel(
            panel,
            text="This music player is made by - Kaustubh Mishra on python with tkinter whole hand written code",
            text_color="#d9ddd4",
            font=("Arial", 14, "bold"),
            justify="left",
            wraplength=650,
        ).pack(anchor="w", padx=32, pady=(0, 18))
        ctk.CTkLabel(
            panel,
            text="No account or other device is needed. Add music files from your computer and playback stays inside this player.",
            text_color=MUTED,
            font=("Arial", 13),
            justify="left",
            wraplength=650,
        ).pack(anchor="w", padx=32)
        ctk.CTkLabel(
            panel,
            text="Python  ·  Tkinter / CustomTkinter  ·  pygame-ce",
            text_color="#777d73",
            font=("Arial", 11),
        ).pack(anchor="w", padx=32, pady=(24, 0))

    def _add_local_files(self):
        paths = filedialog.askopenfilenames(
            title="Choose music files",
            filetypes=[("Audio files", "*.mp3 *.wav *.ogg"), ("All files", "*.*")],
        )
        self._add_local_paths(paths)

    def _add_local_folder(self):
        folder = filedialog.askdirectory(title="Choose a music folder")
        if folder:
            supported = {".mp3", ".wav", ".ogg"}
            paths = sorted(
                str(path)
                for path in Path(folder).rglob("*")
                if path.is_file() and path.suffix.lower() in supported
            )
            self._add_local_paths(paths)

    def _load_local_library(self):
        try:
            paths = json.loads(self.local_library_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return
        if isinstance(paths, list):
            self._add_local_paths(paths, notify=False, persist=False)

    def _load_local_collections(self):
        try:
            favorites = json.loads(self.liked_library_path.read_text(encoding="utf-8"))
            recent = json.loads(self.recent_library_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return
        if isinstance(favorites, list):
            self.favorite_paths = set(favorites)
        if isinstance(recent, list):
            self.recent_paths = recent

    def _save_local_collections(self):
        try:
            self.data_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.liked_library_path.write_text(
                json.dumps(sorted(self.favorite_paths), indent=2), encoding="utf-8"
            )
            self.recent_library_path.write_text(
                json.dumps(self.recent_paths, indent=2), encoding="utf-8"
            )
        except OSError as error:
            self._set_status(f"Could not save your music history: {error}", error=True)

    def _save_local_library(self):
        try:
            self.local_library_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.local_library_path.write_text(
                json.dumps([track["local_path"] for track in self.local_tracks], indent=2),
                encoding="utf-8",
            )
        except OSError as error:
            self._set_status(f"Could not save your library: {error}", error=True)

    def _add_local_paths(self, paths, notify=True, persist=True):
        known_paths = {track["local_path"] for track in self.local_tracks}
        supported = {".mp3", ".wav", ".ogg"}
        added = 0
        for path in paths:
            file_path = Path(path).expanduser()
            if (
                file_path.suffix.lower() not in supported
                or not file_path.is_file()
                or str(file_path.resolve()) in known_paths
            ):
                continue
            file_path = file_path.resolve()
            try:
                metadata = mutagen.File(str(file_path), easy=True)
            except (OSError, mutagen.MutagenError):
                metadata = None
            tags = metadata or {}
            title = str((tags.get("title") or [file_path.stem])[0])
            artist = str((tags.get("artist") or ["Local file"])[0])
            duration = getattr(getattr(metadata, "info", None), "length", 0) or 0
            self.local_tracks.append(
                {
                    "name": title,
                    "artists": [{"name": artist}],
                    "duration_ms": int(duration * 1000),
                    "uri": str(file_path),
                    "local_path": str(file_path),
                }
            )
            known_paths.add(str(file_path))
            added += 1
        if persist and added:
            self._save_local_library()
        if notify:
            self._set_status(f"Added {added} local song{'s' if added != 1 else ''}.")
        if hasattr(self, "content"):
            self._refresh_current_page()

    def _render_local_tracks(self):
        parent = getattr(self, "local_track_list", None)
        if not parent or not parent.winfo_exists():
            return
        self._clear_frame(parent)
        if not self.local_tracks:
            self._empty_message(parent, "Add audio files or a folder to build your local library.")
            return
        for index, track in enumerate(self.local_tracks):
            self._track_row(parent, track, show_like=True, local_index=index)

    def _show_track_collection(self, title, tracks, empty_text):
        self._clear_content()
        ctk.CTkLabel(
            self.content,
            text=title,
            text_color=TEXT,
            font=("Arial", 27, "bold"),
        ).pack(anchor="w", padx=8, pady=(12, 12))
        parent = ctk.CTkScrollableFrame(
            self.content, fg_color="transparent", scrollbar_button_color="#42463f"
        )
        parent.pack(fill="both", expand=True)
        if not tracks:
            self._empty_message(parent, empty_text)
            return
        indexes = {track["local_path"]: index for index, track in enumerate(self.local_tracks)}
        for track in tracks:
            index = indexes.get(track["local_path"])
            if index is not None:
                self._track_row(parent, track, show_like=True, local_index=index)

    def _refresh_current_page(self):
        if self.page in ("Your Music", "Local Music", "Your Library", "Home"):
            self._show_local_music()
        elif self.page == "Liked Songs":
            self.navigate(self.page)
        elif self.page == "Recently Played":
            self.navigate(self.page)
        elif self.page == "Queue":
            self.navigate(self.page)
        elif self.page == "Search":
            self.search()

    def _toggle_favorite_path(self, path):
        if path in self.favorite_paths:
            self.favorite_paths.remove(path)
        else:
            self.favorite_paths.add(path)
        self._save_local_collections()
        self._update_like_button()
        if hasattr(self, "content"):
            self._refresh_current_page()

    def _play_local_index(self, index):
        if not self.local_tracks:
            return
        if not self.audio_available:
            self._set_status("Audio output is not available on this device.", error=True)
            return
        index %= len(self.local_tracks)
        track = self.local_tracks[index]
        try:
            pygame.mixer.music.load(track["local_path"])
            pygame.mixer.music.play()
        except pygame.error as error:
            self._set_status(f"Could not play {track['name']}: {error}", error=True)
            return
        self.playback_source = "local"
        self.local_track_index = index
        self.current_track = track
        self.current_duration = track["duration_ms"]
        self.local_position = 0
        self.local_started_at = time.monotonic()
        path = track["local_path"]
        self.recent_paths = [path] + [item for item in self.recent_paths if item != path]
        self.recent_paths = self.recent_paths[:100]
        self._save_local_collections()
        self.is_playing = True
        self.dock_title.configure(text=track["name"])
        self.dock_artist.configure(text=track_artists(track))
        self.dock_cover.configure(image=None, text="♫")
        self.play_button.configure(text="Ⅱ")
        self.current_time_label.configure(text="0:00")
        self.total_time_label.configure(text=format_time(self.current_duration))
        self.progress_slider.set(0)
        self._update_modes()
        self._update_like_button()
        self._schedule_local_progress()
        self._set_status(f"Playing {track['name']} locally")

    def _schedule_local_progress(self):
        if self.local_progress_after_id:
            self.root.after_cancel(self.local_progress_after_id)
        self.local_progress_after_id = self.root.after(400, self._update_local_progress)

    def _update_local_progress(self):
        self.local_progress_after_id = None
        if self.playback_source != "local" or not self.current_track:
            return
        if self.is_playing:
            if not pygame.mixer.music.get_busy():
                self._advance_local_track()
                return
            position = self.local_position + int((time.monotonic() - self.local_started_at) * 1000)
            self.current_time_label.configure(text=format_time(position))
            if self.current_duration:
                self.progress_slider.set(min(100, position * 100 / self.current_duration))
        self._schedule_local_progress()

    def _advance_local_track(self):
        if self.local_repeat_enabled:
            self._play_local_index(self.local_track_index)
        elif self.local_shuffle_enabled and len(self.local_tracks) > 1:
            choices = [
                index
                for index in range(len(self.local_tracks))
                if index != self.local_track_index
            ]
            self._play_local_index(random.choice(choices))
        elif self.local_track_index + 1 < len(self.local_tracks):
            self._play_local_index(self.local_track_index + 1)
        else:
            self.is_playing = False
            self.local_position = self.current_duration
            self.play_button.configure(text="▶")
            self.progress_slider.set(100)
            self.current_time_label.configure(text=format_time(self.current_duration))

    def _toggle_local_play(self):
        if self.local_track_index is None:
            if self.local_tracks:
                self._play_local_index(0)
            else:
                self.navigate("Local Music")
            return
        if self.is_playing:
            pygame.mixer.music.pause()
            self.local_position += int((time.monotonic() - self.local_started_at) * 1000)
            self.is_playing = False
            self.play_button.configure(text="▶")
        elif self.current_duration and self.local_position >= self.current_duration:
            self._play_local_index(self.local_track_index)
        else:
            pygame.mixer.music.unpause()
            self.local_started_at = time.monotonic()
            self.is_playing = True
            self.play_button.configure(text="Ⅱ")

    def _skip_local(self, offset):
        if self.local_track_index is not None:
            position = self.local_position
            if self.is_playing:
                position += int((time.monotonic() - self.local_started_at) * 1000)
            if offset < 0 and position > 3000:
                self.progress_slider.set(0)
                self._seek_local()
                return
            if self.local_shuffle_enabled and len(self.local_tracks) > 1:
                choices = [
                    index
                    for index in range(len(self.local_tracks))
                    if index != self.local_track_index
                ]
                self._play_local_index(random.choice(choices))
                return
            next_index = self.local_track_index + offset
            if self.local_repeat_enabled or 0 <= next_index < len(self.local_tracks):
                self._play_local_index(next_index)

    def _seek_local(self):
        if self.playback_source != "local" or not self.current_duration:
            return False
        target = int(self.current_duration * self.progress_slider.get() / 100)
        try:
            pygame.mixer.music.play(start=target / 1000)
        except pygame.error:
            self._set_status("Seeking is not supported for this audio file.", error=True)
            return True
        self.local_position = target
        self.local_started_at = time.monotonic()
        self.is_playing = True
        self.play_button.configure(text="Ⅱ")
        return True

    def _set_local_volume(self, volume):
        if self.audio_available:
            pygame.mixer.music.set_volume(max(0, min(1, volume / 100)))

    def search(self):
        query = self.search_entry.get().strip()
        filtered = [
            track
            for track in self.local_tracks
            if query.casefold() in track["name"].casefold()
            or query.casefold() in track_artists(track).casefold()
        ]
        self._clear_frame(self.search_results)
        if not filtered:
            self._empty_message(
                self.search_results,
                "No matches in your music." if query else "Add music, then search by song or artist.",
            )
            return
        indexes = {track["local_path"]: index for index, track in enumerate(self.local_tracks)}
        for track in filtered:
            self._track_row(
                self.search_results,
                track,
                show_like=True,
                local_index=indexes[track["local_path"]],
            )
        self._set_status(f"{len(filtered)} tracks")

    @staticmethod
    def _clear_frame(frame):
        for child in frame.winfo_children():
            child.destroy()

    def _track_row(self, parent, track, show_like=False, subtitle=None, local_index=None):
        title = track.get("name", "Unknown track")
        artist = subtitle or track_artists(track) or "Unknown artist"
        row = ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=11)
        row.pack(fill="x", padx=4, pady=3)
        ctk.CTkLabel(
            row,
            text="♫",
            width=42,
            height=42,
            fg_color="#2b3026",
            corner_radius=8,
            text_color=GREEN,
            font=("Arial", 16, "bold"),
        ).pack(side="left", padx=(9, 10), pady=7)
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, pady=7)
        ctk.CTkLabel(
            info,
            text=title,
            text_color=TEXT,
            font=("Arial", 12, "bold"),
            anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            info, text=artist, text_color=MUTED, font=("Arial", 10), anchor="w"
        ).pack(anchor="w", pady=(1, 0))
        ctk.CTkLabel(
            row,
            text=format_time(track.get("duration_ms")),
            text_color=MUTED,
            font=("Arial", 10),
        ).pack(side="right", padx=8)
        if show_like and track.get("local_path"):
            liked = track["local_path"] in self.favorite_paths
            ctk.CTkButton(
                row,
                text="♥" if liked else "♡",
                width=31,
                height=31,
                corner_radius=15,
                fg_color="transparent",
                hover_color=SURFACE_HOVER,
                text_color=GREEN if liked else MUTED,
                command=lambda path=track["local_path"]: self._toggle_favorite_path(path),
            ).pack(side="right", padx=2)
        if local_index is None and track.get("local_path"):
            local_index = next(
                (
                    index
                    for index, item in enumerate(self.local_tracks)
                    if item["local_path"] == track["local_path"]
                ),
                None,
            )
        if local_index is None:
            play_command = lambda: None
        else:
            play_command = lambda index=local_index: self._play_local_index(index)
        ctk.CTkButton(
            row,
            text="▶",
            width=32,
            height=31,
            corner_radius=16,
            fg_color=GREEN_DARK,
            hover_color="#35472a",
            text_color=GREEN,
            command=play_command,
        ).pack(side="right", padx=(4, 5))

    def _empty_message(self, parent, message):
        ctk.CTkLabel(
            parent,
            text=message,
            text_color=MUTED,
            font=("Arial", 13),
        ).pack(padx=15, pady=26)

    def toggle_play(self):
        self._toggle_local_play()

    def next_track(self):
        self._skip_local(1)

    def previous_track(self):
        self._skip_local(-1)

    def toggle_shuffle(self):
        self.local_shuffle_enabled = not self.local_shuffle_enabled
        if self.local_shuffle_enabled:
            self.local_repeat_enabled = False
        self._update_modes()
        self._set_status("Shuffle on" if self.local_shuffle_enabled else "Shuffle off")

    def toggle_repeat(self):
        self.local_repeat_enabled = not self.local_repeat_enabled
        if self.local_repeat_enabled:
            self.local_shuffle_enabled = False
        self._update_modes()
        self._set_status("Repeat track on" if self.local_repeat_enabled else "Repeat off")

    def toggle_like(self):
        if not self.current_track or not self.current_track.get("local_path"):
            return
        self._toggle_favorite_path(self.current_track["local_path"])

    def _update_like_button(self):
        path = (self.current_track or {}).get("local_path")
        liked = path in self.favorite_paths if path else False
        self.like_button.configure(
            text="♥" if liked else "♡",
            text_color=GREEN if liked else MUTED,
            state="normal" if path else "disabled",
        )

    def _preview_seek(self, value):
        if self.current_duration:
            position = self.current_duration * float(value) / 100
            self.current_time_label.configure(text=format_time(position))

    def _seek(self, _event=None):
        self._seek_local()

    def _schedule_volume(self, value):
        self._set_local_volume(float(value))

    def _update_modes(self):
        self.shuffle_button.configure(
            text_color=GREEN if self.local_shuffle_enabled else MUTED
        )
        self.repeat_button.configure(
            text="↻¹" if self.local_repeat_enabled else "↻",
            text_color=GREEN if self.local_repeat_enabled else MUTED,
        )

if __name__ == "__main__":
    root = ctk.CTk()
    app = MusicPlayer(root)
    root.mainloop()
