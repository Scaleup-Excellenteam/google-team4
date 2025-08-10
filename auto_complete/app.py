# app.py
# CustomTkinter (dark theme) GUI for the Autocomplete project.
# Now supports: Folder / ZIP / .txt files (multi-select)
# - Uses your Engine + build_index_fast
# - Debounced search, background indexing, clean dark UI

import threading
import tkinter as tk
import zipfile
import tempfile
import shutil
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

# --- Project imports (unchanged API) ---
from src.autocomplete.engine import Engine, build_index_fast
from src.autocomplete.models import AutoCompleteData
from src.autocomplete.config import TOP_K
from src.autocomplete import config as CFG  # we mutate DATA_ROOT, READ_MODE, WORKERS


class AutocompleteApp(ctk.CTk):
    """
    Dark-themed CustomTkinter GUI that wraps the Engine-based Autocomplete project.

    Supports three input modes:
      1) Choose Corpus Folder
      2) Choose ZIP Corpus  (extracted to a temp dir)
      3) Choose .txt Files  (staged into a temp dir)

    All modes set CFG.DATA_ROOT to a directory before calling build_index_fast(self.engine).
    """

    def __init__(self) -> None:
        super().__init__()

        # ---- Global theme ----
        ctk.set_appearance_mode("Dark")          # "Light" | "Dark" | "System"
        ctk.set_default_color_theme("blue")      # "blue" | "green" | "dark-blue"

        self.title("Autocomplete Engine – Dark UI")
        self.geometry("900x640")
        self.minsize(820, 560)

        # ---- App state ----
        self.engine = Engine()
        self._corpus_loaded = False
        self._loading_thread: threading.Thread | None = None
        self._search_after_id: str | None = None
        self._temp_dirs: list[Path] = []  # track all temp dirs to clean up
        self._k_var = tk.IntVar(value=TOP_K)

        # ---- Build UI ----
        self._build_widgets()

        # Quick shortcuts
        self.bind("<Control-f>", lambda e: self.entry_query.focus_set())
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ========================= UI =========================
    def _build_widgets(self) -> None:
        # Top bar: actions + status
        top = ctk.CTkFrame(self, corner_radius=12, fg_color="transparent")
        top.pack(side="top", fill="x", padx=12, pady=(12, 6))

        self.btn_pick_folder = ctk.CTkButton(
            top, text="Choose Corpus Folder", command=self.on_pick_folder
        )
        self.btn_pick_folder.pack(side="left", padx=(0, 8))

        self.btn_pick_zip = ctk.CTkButton(
            top, text="Choose ZIP Corpus", command=self.on_pick_zip
        )
        self.btn_pick_zip.pack(side="left", padx=(0, 8))

        self.btn_pick_txts = ctk.CTkButton(
            top, text="Choose .txt Files", command=self.on_pick_txts
        )
        self.btn_pick_txts.pack(side="left", padx=(0, 8))

        self.btn_clear_log = ctk.CTkButton(
            top, text="Clear Log", command=self._clear_log
        )
        self.btn_clear_log.pack(side="left", padx=(0, 8))

        self.lbl_folder = ctk.CTkLabel(
            top, text="No source selected", anchor="w"
        )
        self.lbl_folder.pack(side="left", padx=8)

        # Status line
        self.lbl_status = ctk.CTkLabel(self, text="Status: Ready", anchor="w")
        self.lbl_status.pack(side="top", fill="x", padx=14)

        # Search area
        search = ctk.CTkFrame(self, corner_radius=12)
        search.pack(side="top", fill="x", padx=12, pady=8)

        ctk.CTkLabel(search, text="Type to search:").pack(
            side="top", anchor="w", padx=8, pady=(8, 0)
        )
        self.entry_query = ctk.CTkEntry(search, placeholder_text="Enter query…")
        self.entry_query.pack(side="top", fill="x", padx=8, pady=(4, 10))
        self.entry_query.bind("<KeyRelease>", self.on_query_changed)

        # K (top-k) control
        k_row = ctk.CTkFrame(search, fg_color="transparent")
        k_row.pack(side="top", fill="x", padx=8, pady=(0, 10))
        ctk.CTkLabel(k_row, text="Results (k):").pack(side="left")
        self.k_slider = ctk.CTkSlider(
            k_row, from_=1, to=50, number_of_steps=49,
            command=lambda v: self._k_var.set(int(float(v)))
        )
        self.k_slider.set(TOP_K)
        self.k_slider.pack(side="left", fill="x", expand=True, padx=10)
        self.k_value = ctk.CTkLabel(k_row, text=str(TOP_K))
        self.k_value.pack(side="left")
        self._k_var.trace_add("write", lambda *_: self.k_value.configure(text=str(self._k_var.get())))

        # Main split: results (top) + log (bottom)
        main = ctk.CTkFrame(self, corner_radius=12)
        main.pack(side="top", fill="both", expand=True, padx=12, pady=(0, 12))

        # Results panel
        results_frame = ctk.CTkFrame(main, corner_radius=12)
        results_frame.pack(side="top", fill="both", expand=True, padx=8, pady=8)

        ctk.CTkLabel(results_frame, text="Results").pack(
            side="top", anchor="w", padx=10, pady=(8, 4)
        )
        self.txt_results = ctk.CTkTextbox(results_frame, height=250)
        self.txt_results.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(0, 10))

        res_scroll = ctk.CTkScrollbar(results_frame, command=self.txt_results.yview)
        res_scroll.pack(side="right", fill="y", padx=(0, 10), pady=(0, 10))
        self.txt_results.configure(yscrollcommand=res_scroll.set)

        # Log panel
        log_frame = ctk.CTkFrame(main, corner_radius=12)
        log_frame.pack(side="bottom", fill="both", expand=False, padx=8, pady=(0, 8))

        ctk.CTkLabel(log_frame, text="Log").pack(
            side="top", anchor="w", padx=10, pady=(8, 4)
        )
        self.txt_log = ctk.CTkTextbox(log_frame, height=140)
        self.txt_log.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(0, 10))

        log_scroll = ctk.CTkScrollbar(log_frame, command=self.txt_log.yview)
        log_scroll.pack(side="right", fill="y", padx=(0, 10), pady=(0, 10))
        self.txt_log.configure(yscrollcommand=log_scroll.set)

        # Initial placeholder
        self._set_results("(No results yet — load a corpus and start typing.)")

    # =================== Events / Actions ===================
    def on_pick_folder(self) -> None:
        """Open a folder picker and kick off background corpus loading."""
        path = filedialog.askdirectory(title="Choose Corpus Folder")
        if not path:
            return
        self._prepare_new_corpus(Path(path), is_temp=False)

    def on_pick_zip(self) -> None:
        """Open a ZIP picker, extract to a temp dir, and load."""
        zip_path = filedialog.askopenfilename(
            title="Choose ZIP Corpus",
            filetypes=[("ZIP archives", "*.zip")]
        )
        if not zip_path:
            return

        try:
            temp_dir = Path(tempfile.mkdtemp(prefix="autocomplete_corpus_"))
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(temp_dir)
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to extract ZIP:\n{exc}")
            return

        self._temp_dirs.append(temp_dir)
        self._prepare_new_corpus(temp_dir, is_temp=True)

    def on_pick_txts(self) -> None:
        """Select one or more .txt files; stage them into a temp dir and load."""
        files = filedialog.askopenfilenames(
            title="Choose .txt Files",
            filetypes=[("Text files", "*.txt")]
        )
        if not files:
            return

        try:
            staged_dir = self._stage_txt_files_to_temp(files)
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to stage .txt files:\n{exc}")
            return

        self._temp_dirs.append(staged_dir)
        self._prepare_new_corpus(staged_dir, is_temp=True)

    def _stage_txt_files_to_temp(self, file_paths: tuple[str] | list[str]) -> Path:
        """
        Copy selected .txt files into a new temp directory so that build_index_fast,
        which expects a directory root, can index them uniformly.
        """
        temp_dir = Path(tempfile.mkdtemp(prefix="autocomplete_txts_"))
        used_names: set[str] = set()

        for raw in file_paths:
            src = Path(raw)
            if src.suffix.lower() != ".txt":
                # Skip non-txt (shouldn't happen due to filter, but be safe)
                continue

            name = src.name
            stem, suffix = src.stem, src.suffix
            # Ensure unique names to avoid collisions
            i = 1
            while name in used_names or (temp_dir / name).exists():
                name = f"{stem}_{i}{suffix}"
                i += 1
            used_names.add(name)

            shutil.copy2(src, temp_dir / name)

        if not any(temp_dir.iterdir()):
            # Nothing copied -> user picked invalid files or cancellation
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise ValueError("No .txt files were staged.")

        return temp_dir

    def _prepare_new_corpus(self, root: Path, is_temp: bool) -> None:
        """Reset engine state and start a background indexing run."""
        self.lbl_folder.configure(
            text=f"{'Temp ' if is_temp else ''}Source: {root}"
        )
        self.engine = Engine()  # reset engine
        if self._loading_thread and self._loading_thread.is_alive():
            messagebox.showinfo("Loading", "A load is already in progress. Please wait.")
            return

        self._log(f"Starting corpus load from: {root}")
        self._set_status(f"Loading corpus from: {root}")
        self._corpus_loaded = False
        self._set_inputs_enabled(False)

        self._loading_thread = threading.Thread(
            target=self._load_corpus_worker,
            args=(str(root),),
            daemon=True,
        )
        self._loading_thread.start()

    def _load_corpus_worker(self, path_str: str) -> None:
        """Background thread: set config + build the index into self.engine."""
        try:
            CFG.DATA_ROOT = Path(path_str)
            CFG.READ_MODE = "threads"
            CFG.WORKERS = 16

            build_index_fast(self.engine)
            n = len(self.engine.corpus.sentences)
        except Exception as exc:
            self._log(f"ERROR loading corpus: {exc!r}")
            self.after(0, lambda: self._set_status("Error: failed to load corpus."))
            self.after(0, lambda: messagebox.showerror("Error", f"Failed to load corpus:\n{exc}"))
            self.after(0, lambda: self._set_inputs_enabled(True))
            return

        self.after(0, lambda: self._on_corpus_loaded(n))

    def _on_corpus_loaded(self, n_sentences: int) -> None:
        self._corpus_loaded = True
        self._set_status(f"Loaded {n_sentences:,} sentences.")
        self._log(f"Corpus loaded: {n_sentences} sentences.")
        self._set_inputs_enabled(True)
        self.entry_query.focus_set()

    def on_query_changed(self, event=None) -> None:
        """Debounce key events and trigger search."""
        if self._search_after_id is not None:
            self.after_cancel(self._search_after_id)
        self._search_after_id = self.after(150, self._do_search)

    def _do_search(self) -> None:
        q = self.entry_query.get()
        if not q.strip():
            self._set_results("")
            return

        if not self._corpus_loaded:
            self._set_results("Error: please load a corpus before searching.")
            self._log("Search attempted before corpus load.")
            return

        k = int(self._k_var.get())
        self._log(f"engine.query('{q}', k={k})...")
        try:
            results = self.engine.query(q, k=k)
        except Exception as exc:
            self._set_results(f"Search error: {exc}")
            self._log(f"ERROR in search: {exc!r}")
            return

        if not results:
            self._set_results("No matches found.")
            return

        lines = [self._format_result(r) for r in results]
        self._set_results("\n".join(lines))

    # =================== Utilities ===================
    @staticmethod
    def _format_result(r: AutoCompleteData) -> str:
        source_display = str(r.source_text)
        return f"score={r.score} | {source_display}:{r.offset} | {r.completed_sentence}"

    def _set_status(self, text: str) -> None:
        self.lbl_status.configure(text=f"Status: {text}")

    def _set_results(self, text: str) -> None:
        self.txt_results.configure(state="normal")
        self.txt_results.delete("1.0", "end")
        if text:
            self.txt_results.insert("1.0", text)
        self.txt_results.configure(state="disabled")

    def _log(self, msg: str) -> None:
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", f"{msg}\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _clear_log(self) -> None:
        self.txt_log.configure(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.configure(state="disabled")

    def _set_inputs_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.btn_pick_folder.configure(state=state)
        self.btn_pick_zip.configure(state=state)
        self.btn_pick_txts.configure(state=state)
        self.btn_clear_log.configure(state=state)
        self.entry_query.configure(state=state)
        self.k_slider.configure(state=state)

    def _on_close(self) -> None:
        # Best-effort cleanup of all temp directories
        for d in self._temp_dirs:
            try:
                shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass
        self.destroy()


if __name__ == "__main__":
    app = AutocompleteApp()
    app.mainloop()
