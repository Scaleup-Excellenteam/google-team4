# app.py
# CustomTkinter GUI for the Autocomplete project (dark theme, ZIP-aware).
# - Load from a folder OR a ZIP archive (ZIP extracted safely to a temp dir).
# - Background loading thread (keeps UI responsive).
# - Live search with debounce; results & event log panes.

from __future__ import annotations
import os
import shutil
import threading
import zipfile
import tempfile
from pathlib import Path
from typing import List, Optional

import tkinter.filedialog as fd
import tkinter.messagebox as mb
import customtkinter as ctk

# Project imports (ensure PYTHONPATH=src)
from src.autocomplete.engine import load_corpus, get_best_k_completions
from src.autocomplete.models import AutoCompleteData


# -------------------- small helpers --------------------

def shorten_path(p: str, max_chars: int = 60) -> str:
    """Shorten long paths neatly for labels."""
    if len(p) <= max_chars:
        return p
    keep = max_chars // 2 - 3
    return p[:keep] + "..." + p[-keep:]


def safe_extract_zip(zip_path: str, dest_dir: str) -> None:
    """
    Extract zip contents to dest_dir with basic zip-slip protection.
    Only ensures members stay within dest_dir (no absolute paths / .. traversal).
    """
    dest_abs = os.path.abspath(dest_dir)
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            # Normalize final target path
            target = os.path.abspath(os.path.join(dest_abs, info.filename))
            # Allow the dest root itself (for top-level dirs), otherwise require prefix
            if target != dest_abs and not target.startswith(dest_abs + os.sep):
                raise RuntimeError(f"Unsafe zip entry: {info.filename!r}")
        # If all entries are safe, extract
        zf.extractall(dest_abs)


# -------------------- main app --------------------

class AutocompleteApp(ctk.CTk):
    """Dark-themed GUI that loads a corpus from folder or ZIP and queries the engine."""

    def __init__(self) -> None:
        super().__init__()

        # Theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Window
        self.title("Autocomplete Engine")
        self.geometry("900x650")
        self.minsize(820, 560)

        # State
        self._corpus_loaded: bool = False
        self._loading_thread: Optional[threading.Thread] = None
        self._search_after_id: Optional[str] = None
        self._current_root_label: str = "No source selected"
        self._tmpdir_path: Optional[str] = None  # holds extracted ZIP dir

        # Fonts
        self.font_title = ctk.CTkFont(size=18, weight="bold")
        self.font_label = ctk.CTkFont(size=13)
        self.font_mono = ctk.CTkFont(family="Cascadia Mono, Menlo, Consolas, Courier New", size=13)

        # Layout grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)  # results
        self.grid_rowconfigure(5, weight=1)  # log

        # Build UI
        self._build_header()
        self._build_source_bar()
        self._build_search()
        self._build_results()
        self._build_log()

        self._set_status("Ready")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # --------- UI sections ---------

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, corner_radius=10)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(header, text="Autocomplete Engine", font=self.font_title)
        title.grid(row=0, column=0, sticky="w", padx=12, pady=10)

    def _build_source_bar(self) -> None:
        bar = ctk.CTkFrame(self, corner_radius=10)
        bar.grid(row=1, column=0, sticky="ew", padx=12, pady=6)
        bar.grid_columnconfigure(1, weight=1)

        # Choose folder
        btn_folder = ctk.CTkButton(bar, text="Choose Folder", command=self._choose_folder)
        btn_folder.grid(row=0, column=0, padx=(12, 6), pady=10)

        # Choose ZIP
        btn_zip = ctk.CTkButton(bar, text="Choose ZIP", command=self._choose_zip)
        btn_zip.grid(row=0, column=1, padx=(0, 6), pady=10, sticky="w")

        # Selected label
        self.lbl_source = ctk.CTkLabel(bar, text=self._current_root_label, anchor="w", font=self.font_label)
        self.lbl_source.grid(row=0, column=2, sticky="ew", padx=(6, 6), pady=10)

        # Progress + status
        self.progress = ctk.CTkProgressBar(bar, mode="indeterminate", determinate_speed=1.2)
        self.progress.grid(row=0, column=3, sticky="e", padx=(0, 6), pady=10)

        self.lbl_status = ctk.CTkLabel(bar, text="Status: —", anchor="e")
        self.lbl_status.grid(row=0, column=4, sticky="e", padx=12, pady=10)

    def _build_search(self) -> None:
        box = ctk.CTkFrame(self, corner_radius=10)
        box.grid(row=2, column=0, sticky="ew", padx=12, pady=(6, 6))
        box.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(box, text="Enter text to search:", font=self.font_label).grid(
            row=0, column=0, sticky="w", padx=12, pady=10
        )

        self.entry_query = ctk.CTkEntry(box, placeholder_text="Start typing a prefix…")
        self.entry_query.grid(row=0, column=1, sticky="ew", padx=(6, 12), pady=10)
        self.entry_query.bind("<KeyRelease>", self._on_query_changed)

    def _build_results(self) -> None:
        frame = ctk.CTkFrame(self, corner_radius=10)
        frame.grid(row=3, column=0, sticky="nsew", padx=12, pady=(6, 6))
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Results", font=self.font_label).grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 2)
        )

        inner = ctk.CTkFrame(frame, corner_radius=8)
        inner.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        inner.grid_columnconfigure(0, weight=1)
        inner.grid_rowconfigure(0, weight=1)

        self.txt_results = ctk.CTkTextbox(inner, wrap="word", font=self.font_mono)
        self.txt_results.grid(row=0, column=0, sticky="nsew")
        self.txt_results.configure(state="disabled")
        self._set_results("(no results yet — load a corpus and start typing)")

    def _build_log(self) -> None:
        frame = ctk.CTkFrame(self, corner_radius=10)
        frame.grid(row=5, column=0, sticky="nsew", padx=12, pady=(6, 12))
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Event log", font=self.font_label).grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 2)
        )

        self.txt_log = ctk.CTkTextbox(frame, height=110, wrap="word", font=ctk.CTkFont(size=12))
        self.txt_log.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self._log("GUI ready. Choose a folder or ZIP to begin.")

    # --------- source selection ---------

    def _choose_folder(self) -> None:
        path = fd.askdirectory(title="Choose corpus folder")
        if not path:
            return
        self._start_loading(mode="folder", source=path)

    def _choose_zip(self) -> None:
        path = fd.askopenfilename(
            title="Choose corpus ZIP",
            filetypes=[("ZIP archives", "*.zip"), ("All files", "*.*")]
        )
        if not path:
            return
        self._start_loading(mode="zip", source=path)

    # --------- loading pipeline (threaded) ---------

    def _start_loading(self, mode: str, source: str) -> None:
        # prevent re-entrancy
        if self._loading_thread and self._loading_thread.is_alive():
            mb.showinfo("Loading", "A corpus is already loading. Please wait.")
            return

        # clean previous temp (if any)
        self._cleanup_tmpdir()

        # UI
        tag = "ZIP" if mode == "zip" else "Folder"
        self._current_root_label = f"{tag}: {shorten_path(source)}"
        self.lbl_source.configure(text=self._current_root_label)
        self._set_status(f"Loading from {tag.lower()}…")
        self.progress.start()
        self._corpus_loaded = False

        # Launch worker
        self._loading_thread = threading.Thread(
            target=self._load_worker, args=(mode, source), daemon=True
        )
        self._loading_thread.start()

    def _load_worker(self, mode: str, source: str) -> None:
        try:
            roots: List[str]
            if mode == "zip":
                self._log(f"Extracting ZIP: {source}")
                tmpdir = tempfile.mkdtemp(prefix="autocomplete_corpus_")
                try:
                    safe_extract_zip(source, tmpdir)
                except Exception:
                    # cleanup on extraction error
                    shutil.rmtree(tmpdir, ignore_errors=True)
                    raise
                self._tmpdir_path = tmpdir  # keep until next load/exit
                roots = [tmpdir]
            else:
                roots = [source]

            corpus = load_corpus(roots)
            n = len(corpus.sentences)
        except Exception as exc:
            self.after(0, lambda: self._on_load_error(exc))
            return

        self.after(0, lambda: self._on_load_ok(n))

    def _on_load_ok(self, n_sentences: int) -> None:
        self.progress.stop()
        self._corpus_loaded = True
        self._set_status(f"Loaded {n_sentences:,} sentences.")
        self._log(f"Corpus ready ({n_sentences} sentences).")
        self.entry_query.focus_set()

    def _on_load_error(self, exc: Exception) -> None:
        self.progress.stop()
        self._set_status("Error while loading corpus.")
        self._log(f"ERROR: {exc!r}")
        mb.showerror("Load error", "Failed to load corpus.\nSee event log for details.")

    # --------- search ---------

    def _on_query_changed(self, _ev=None) -> None:
        # debounce for smoother typing
        if self._search_after_id is not None:
            try:
                self.after_cancel(self._search_after_id)
            except Exception:
                pass
        self._search_after_id = self.after(160, self._do_search)

    def _do_search(self) -> None:
        q = self.entry_query.get()
        if not q.strip():
            self._set_results("")
            return
        if not self._corpus_loaded:
            self._set_results("error: please load a corpus before searching.")
            self._log("Search attempted before corpus load.")
            return

        self._log("Calling get_best_k_completions…")
        try:
            results = get_best_k_completions(q)
        except Exception as exc:
            self._set_results(f"error while searching: {exc}")
            self._log(f"ERROR in search: {exc!r}")
            return

        if not results:
            self._set_results("(no results yet; waiting for search implementation)")
            return

        lines = [self._fmt(r) for r in results]
        self._set_results("\n".join(lines))

    @staticmethod
    def _fmt(r: AutoCompleteData) -> str:
        return f"score: {r.score:<4} | file: {r.source_text}:{r.offset} | {r.completed_sentence}"

    # --------- misc UI helpers ---------

    def _set_status(self, text: str) -> None:
        self.lbl_status.configure(text=f"Status: {text}")

    def _set_results(self, text: str) -> None:
        self.txt_results.configure(state="normal")
        self.txt_results.delete("0.0", "end")
        if text:
            self.txt_results.insert("end", text)
        self.txt_results.configure(state="disabled")

    def _log(self, msg: str) -> None:
        self.txt_log.insert("end", msg + "\n")
        self.txt_log.see("end")

    # --------- lifecycle ---------

    def _cleanup_tmpdir(self) -> None:
        if self._tmpdir_path and os.path.isdir(self._tmpdir_path):
            try:
                shutil.rmtree(self._tmpdir_path, ignore_errors=True)
            finally:
                self._tmpdir_path = None

    def _on_close(self) -> None:
        self._cleanup_tmpdir()
        self.destroy()


if __name__ == "__main__":
    app = AutocompleteApp()
    app.mainloop()
