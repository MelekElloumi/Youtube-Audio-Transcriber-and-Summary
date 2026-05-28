import os
import re
import time
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk

from theme import COLORS, FONTS, make_label, make_entry, make_listbox
from config import (
    TRANSCRIPTIONS_DIR, PROMPTS_DIR, NOTION_PARENT_PAGE_ID,
    LANGUAGE_NAMES, ICON_PATH,
)
from transcript import check_captions_available
from notion_api import (
    validate_notion_credentials, get_notion_child_pages, create_notion_page,
)
from pipeline import run_pipeline

_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*]')

SCREEN_URL = 0
SCREEN_CAPTIONS = 1
SCREEN_CATEGORY = 2
SCREEN_NOTION = 3
SCREEN_PROMPT = 4
SCREEN_RECAP = 5
SCREEN_PROGRESS = 6
SCREEN_COMPLETE = 7
_TOTAL_SCREENS = 8

_TRANSCRIPTION_PLACEHOLDER = "[INSERT TRANSCRIPTION TEXT HERE]"
_LANGUAGE_PLACEHOLDER = "[LANGUAGE]"


class TranscribeWizard(tk.Toplevel):
    """8-screen wizard for transcribing a YouTube video."""

    def __init__(self, master, on_close):
        super().__init__(master)
        self.title("New Transcription")
        self.geometry("700x530")
        self.resizable(False, False)
        self.configure(bg=COLORS['bg_dark'])
        if os.path.exists(ICON_PATH):
            self.iconbitmap(ICON_PATH)
        self._on_close_callback = on_close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ── Wizard state ────────────────────────────────────────────
        self._current_screen = -1
        self._destroyed = False

        # Screen 0
        self._url = ""
        self._lang_var = tk.StringVar(value="")

        # Screen 1
        self._matched_lang_code = None
        self._use_whisper = False
        self._whisper_var = tk.BooleanVar(value=False)

        # Screen 2
        self._category = ""
        self._video_name = ""
        self._categories = []

        # Screen 3
        self._notion_var = tk.StringVar(value="yes")
        self._notion_validated = False
        self._notion_stack = []
        self._notion_pages = []
        self._notion_page_id = None
        self._notion_page_title = ""
        self._notion_load_gen = 0

        # Screen 4 (prompt)
        self._prompt_files = []
        self._prompt_original_text = ""
        self._prompt_text = ""

        # Screen 6 (progress)
        self._target_pct = 0
        self._display_pct = 0.0
        self._animating = False
        self._start_time = 0

        # Screen 7
        self._result = None

        # ── Layout: header / body / footer ──────────────────────────
        self._header = tk.Frame(self, bg=COLORS['bg_dark'], height=40)
        self._header.pack(side="top", fill="x", padx=20, pady=(16, 0))
        self._header.pack_propagate(False)

        self._footer = tk.Frame(self, bg=COLORS['bg_dark'], height=50)
        self._footer.pack(side="bottom", fill="x", padx=20, pady=(0, 14))
        self._footer.pack_propagate(False)

        self._body = tk.Frame(self, bg=COLORS['bg_dark'])
        self._body.pack(side="top", fill="both", expand=True, padx=30, pady=(10, 0))

        # ── Step dots ───────────────────────────────────────────────
        self._dots_frame = tk.Frame(self._header, bg=COLORS['bg_dark'])
        self._dots_frame.pack(anchor="center")
        self._dot_labels = []
        for i in range(_TOTAL_SCREENS):
            lbl = tk.Label(self._dots_frame, text="○", font=('Segoe UI', 12),
                           fg=COLORS['text_dim'], bg=COLORS['bg_dark'])
            lbl.pack(side="left", padx=4)
            self._dot_labels.append(lbl)

        # ── Nav buttons ─────────────────────────────────────────────
        self._prev_btn = ttk.Button(self._footer, text="Previous", command=self._on_prev)
        self._prev_btn.pack(side="left")
        self._next_btn = ttk.Button(self._footer, text="Next", command=self._on_next)
        self._next_btn.pack(side="right")

        # ── Build all screens ───────────────────────────────────────
        self._screens = {}
        self._build_screen_url()
        self._build_screen_captions()
        self._build_screen_category()
        self._build_screen_notion()
        self._build_screen_prompt()
        self._build_screen_recap()
        self._build_screen_progress()
        self._build_screen_complete()

        self._show_screen(SCREEN_URL)

    # ════════════════════════════════════════════════════════════════
    #  Navigation
    # ════════════════════════════════════════════════════════════════

    def _show_screen(self, index):
        if self._current_screen >= 0 and self._current_screen in self._screens:
            self._screens[self._current_screen].pack_forget()
        self._current_screen = index
        self._screens[index].pack(in_=self._body, fill="both", expand=True)
        self._update_dots()

        if index in (SCREEN_PROGRESS, SCREEN_COMPLETE):
            self._footer.pack_forget()
        elif not self._footer.winfo_ismapped():
            self._body.pack_forget()
            self._footer.pack(side="bottom", fill="x", padx=20, pady=(0, 14))
            self._body.pack(side="top", fill="both", expand=True, padx=30, pady=(10, 0))

        if index == SCREEN_URL:
            self._prev_btn.state(['disabled'])
        else:
            self._prev_btn.state(['!disabled'])

        if index == SCREEN_RECAP:
            self._next_btn.configure(text="Transcribe")
        else:
            self._next_btn.configure(text="Next")

        self._next_btn.state(['!disabled'])

        hooks = {
            SCREEN_CAPTIONS: self._on_enter_captions,
            SCREEN_CATEGORY: self._on_enter_category,
            SCREEN_NOTION: self._on_enter_notion,
            SCREEN_PROMPT: self._on_enter_prompt,
            SCREEN_RECAP: self._on_enter_recap,
            SCREEN_PROGRESS: self._on_enter_progress,
        }
        if index in hooks:
            hooks[index]()

    def _update_dots(self):
        for i, lbl in enumerate(self._dot_labels):
            if i < self._current_screen:
                lbl.configure(text="●", fg=COLORS['accent'])
            elif i == self._current_screen:
                lbl.configure(text="●", fg=COLORS['text'])
            else:
                lbl.configure(text="○", fg=COLORS['text_dim'])

    def _set_next_enabled(self, enabled):
        self._next_btn.state(['!disabled'] if enabled else ['disabled'])

    def _on_next(self):
        validators = {
            SCREEN_URL: self._validate_url,
            SCREEN_CAPTIONS: self._validate_captions,
            SCREEN_CATEGORY: self._validate_category,
            SCREEN_NOTION: self._validate_notion,
            SCREEN_PROMPT: self._validate_prompt,
            SCREEN_RECAP: lambda: True,
        }
        validator = validators.get(self._current_screen, lambda: True)
        if validator():
            self._show_screen(self._current_screen + 1)

    def _on_prev(self):
        if self._current_screen > 0:
            self._show_screen(self._current_screen - 1)

    def _on_close(self):
        self._destroyed = True
        self._on_close_callback()
        self.destroy()

    def _safe_after(self, ms, func, *args):
        if not self._destroyed:
            self.after(ms, func, *args)

    # ════════════════════════════════════════════════════════════════
    #  SCREEN 0 — URL + Language
    # ════════════════════════════════════════════════════════════════

    def _build_screen_url(self):
        f = tk.Frame(self._body, bg=COLORS['bg_dark'])
        self._screens[SCREEN_URL] = f

        make_label(f, "YouTube URL", font_key='heading').pack(anchor="w", pady=(10, 6))
        self._url_entry = make_entry(f, width=60)
        self._url_entry.pack(fill="x", pady=(0, 16))

        make_label(f, "Language", font_key='heading').pack(anchor="w", pady=(0, 6))
        for code, name in [("ar", "Arabic"), ("fr", "French"), ("en", "English")]:
            ttk.Radiobutton(f, text=name, variable=self._lang_var,
                            value=code).pack(anchor="w", padx=10, pady=2)

        self._url_err = make_label(f, "", color_key='error', font_key='small')
        self._url_err.pack(anchor="w", pady=(12, 0))

    def _validate_url(self):
        url = self._url_entry.get().strip()
        lang = self._lang_var.get()
        if not re.search(r'(youtube\.com/watch\?v=|youtu\.be/)[\w-]+', url):
            self._url_err.configure(text="Please enter a valid YouTube URL.")
            return False
        if not lang:
            self._url_err.configure(text="Please select a language.")
            return False
        self._url_err.configure(text="")
        self._url = url
        return True

    # ════════════════════════════════════════════════════════════════
    #  SCREEN 1 — Caption Check
    # ════════════════════════════════════════════════════════════════

    def _build_screen_captions(self):
        f = tk.Frame(self._body, bg=COLORS['bg_dark'])
        self._screens[SCREEN_CAPTIONS] = f

        make_label(f, "Caption Check", font_key='heading').pack(anchor="w", pady=(10, 10))

        self._cap_status = make_label(f, "", font_key='body', color_key='text_secondary')
        self._cap_status.pack(anchor="w", pady=(0, 8))

        self._cap_result_frame = tk.Frame(f, bg=COLORS['bg_dark'])
        self._cap_result_frame.pack(fill="x")

        self._cap_result_label = make_label(self._cap_result_frame, "", font_key='body')
        self._cap_result_label.pack(anchor="w", pady=(0, 8))

        self._cap_whisper_chk = ttk.Checkbutton(
            self._cap_result_frame, text="Use Whisper transcription instead",
            variable=self._whisper_var, command=self._on_whisper_toggle)

        btn_frame = tk.Frame(f, bg=COLORS['bg_dark'])
        btn_frame.pack(anchor="w", pady=(10, 0))
        self._cap_refresh_btn = ttk.Button(btn_frame, text="Refresh",
                                           command=self._on_enter_captions)

    def _on_enter_captions(self):
        self._set_next_enabled(False)
        self._cap_status.configure(text="Checking captions...", fg=COLORS['text_secondary'])
        self._cap_result_label.configure(text="")
        self._cap_whisper_chk.pack_forget()
        self._cap_refresh_btn.pack_forget()
        self._whisper_var.set(False)
        self._use_whisper = False
        self._matched_lang_code = None

        lang = self._lang_var.get()
        url = self._url

        def worker():
            found, code = check_captions_available(url, lang)
            self._safe_after(0, lambda f=found, c=code: self._on_caption_result(f, c))

        threading.Thread(target=worker, daemon=True).start()

    def _on_caption_result(self, found, code):
        lang_name = LANGUAGE_NAMES.get(self._lang_var.get(), self._lang_var.get())
        if found:
            self._matched_lang_code = code
            self._cap_status.configure(text="")
            variant_note = f" ({code})" if code != self._lang_var.get() else ""
            self._cap_result_label.configure(
                text=f"Captions available in {lang_name}{variant_note}",
                fg=COLORS['success'])
            self._set_next_enabled(True)
        else:
            self._cap_status.configure(text="")
            self._cap_result_label.configure(
                text=f"No captions found for {lang_name}.",
                fg=COLORS['warning'])
            self._cap_whisper_chk.pack(anchor="w", pady=(4, 0))
        self._cap_refresh_btn.pack(side="left", pady=(6, 0))

    def _on_whisper_toggle(self):
        self._use_whisper = self._whisper_var.get()
        self._set_next_enabled(self._use_whisper)

    def _validate_captions(self):
        if self._matched_lang_code:
            self._use_whisper = False
            return True
        if self._whisper_var.get():
            self._use_whisper = True
            return True
        return False

    # ════════════════════════════════════════════════════════════════
    #  SCREEN 2 — Category + Video Name
    # ════════════════════════════════════════════════════════════════

    def _build_screen_category(self):
        f = tk.Frame(self._body, bg=COLORS['bg_dark'])
        self._screens[SCREEN_CATEGORY] = f

        make_label(f, "Category", font_key='heading').pack(anchor="w", pady=(10, 6))
        self._cat_listbox = make_listbox(f, height=6)
        self._cat_listbox.pack(fill="x", pady=(0, 4))
        self._cat_listbox.bind("<<ListboxSelect>>", self._on_cat_select)

        self._cat_add_btn = tk.Button(
            f, text="+ Add new category", font=FONTS['small'],
            fg=COLORS['text_secondary'], bg=COLORS['bg_dark'],
            activeforeground=COLORS['text'], activebackground=COLORS['bg_dark'],
            relief="flat", cursor="hand2", command=self._add_category)
        self._cat_add_btn.pack(anchor="w", pady=(0, 14))

        make_label(f, "Video name", font_key='heading').pack(anchor="w", pady=(0, 6))
        self._vname_entry = make_entry(f, width=50)
        self._vname_entry.pack(fill="x", pady=(0, 4))

        self._cat_err = make_label(f, "", color_key='error', font_key='small')
        self._cat_err.pack(anchor="w", pady=(6, 0))

    def _on_enter_category(self):
        self._populate_categories()

    def _populate_categories(self):
        self._cat_listbox.delete(0, tk.END)
        os.makedirs(TRANSCRIPTIONS_DIR, exist_ok=True)
        folders = sorted(
            d for d in os.listdir(TRANSCRIPTIONS_DIR)
            if os.path.isdir(os.path.join(TRANSCRIPTIONS_DIR, d))
        )
        self._categories = folders
        for name in folders:
            self._cat_listbox.insert(tk.END, f"  {name}")
        self._category = ""

    def _on_cat_select(self, _event):
        sel = self._cat_listbox.curselection()
        if sel:
            self._category = self._categories[sel[0]]

    def _add_category(self):
        win = tk.Toplevel(self)
        win.title("New category")
        win.resizable(False, False)
        win.configure(padx=20, pady=16, bg=COLORS['bg_dark'])
        win.grab_set()

        make_label(win, "Category name:").grid(row=0, column=0, columnspan=2, sticky="w")
        name_entry = make_entry(win, width=30)
        name_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 12))
        name_entry.focus()
        err_label = make_label(win, "", color_key='error', font_key='small')
        err_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 8))

        def submit():
            name = name_entry.get().strip()
            if not name:
                err_label.configure(text="Name cannot be empty.")
                return
            if _UNSAFE_CHARS.search(name):
                err_label.configure(text="Name contains invalid characters.")
                return
            new_path = os.path.join(TRANSCRIPTIONS_DIR, name)
            if os.path.exists(new_path):
                err_label.configure(text="Category already exists.")
                return
            os.makedirs(new_path)
            self._populate_categories()
            win.destroy()

        btn_frame = tk.Frame(win, bg=COLORS['bg_dark'])
        btn_frame.grid(row=3, column=0, columnspan=2, sticky="ew")
        ttk.Button(btn_frame, text="Create", command=submit).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Cancel", command=win.destroy).pack(side="left")
        win.bind("<Return>", lambda e: submit())

    def _validate_category(self):
        vname = self._vname_entry.get().strip()
        if not self._category:
            self._cat_err.configure(text="Please select a category.")
            return False
        if not vname:
            self._cat_err.configure(text="Please enter a video name.")
            return False
        if _UNSAFE_CHARS.search(vname):
            self._cat_err.configure(text="Video name contains invalid characters.")
            return False
        folder_path = os.path.join(TRANSCRIPTIONS_DIR, self._category, vname)
        if os.path.exists(folder_path):
            self._cat_err.configure(text="A folder with this name already exists.")
            return False
        self._cat_err.configure(text="")
        self._video_name = vname
        return True

    # ════════════════════════════════════════════════════════════════
    #  SCREEN 3 — Notion
    # ════════════════════════════════════════════════════════════════

    def _build_screen_notion(self):
        f = tk.Frame(self._body, bg=COLORS['bg_dark'])
        self._screens[SCREEN_NOTION] = f

        make_label(f, "Notion Integration", font_key='heading').pack(anchor="w", pady=(10, 6))

        toggle_frame = tk.Frame(f, bg=COLORS['bg_dark'])
        toggle_frame.pack(anchor="w", pady=(0, 10))
        ttk.Radiobutton(toggle_frame, text="Yes", variable=self._notion_var,
                         value="yes", command=self._on_notion_toggle).pack(side="left", padx=(0, 16))
        ttk.Radiobutton(toggle_frame, text="No", variable=self._notion_var,
                         value="no", command=self._on_notion_toggle).pack(side="left")

        self._notion_frame = tk.Frame(f, bg=COLORS['bg_dark'])
        self._notion_frame.pack(fill="both", expand=True)

        self._notion_status = make_label(self._notion_frame, "", font_key='small',
                                          color_key='text_secondary')
        self._notion_status.pack(anchor="w", pady=(0, 4))

        nav_frame = tk.Frame(self._notion_frame, bg=COLORS['bg_dark'])
        nav_frame.pack(fill="x", pady=(0, 4))
        self._notion_back_btn = tk.Button(
            nav_frame, text="< Back", font=FONTS['small'],
            fg=COLORS['text_secondary'], bg=COLORS['bg_dark'],
            activeforeground=COLORS['text'], activebackground=COLORS['bg_dark'],
            relief="flat", cursor="hand2", command=self._notion_go_back)
        self._notion_back_btn.pack(side="left")
        self._notion_breadcrumb = make_label(nav_frame, "Home", font_key='small',
                                              color_key='text_dim')
        self._notion_breadcrumb.pack(side="left", padx=(8, 0))

        self._notion_listbox = make_listbox(self._notion_frame, height=7)
        self._notion_listbox.pack(fill="both", expand=True, pady=(0, 4))
        self._notion_listbox.bind("<<ListboxSelect>>", self._on_notion_select)
        self._notion_listbox.bind("<Double-Button-1>", self._on_notion_double_click)

        bottom_frame = tk.Frame(self._notion_frame, bg=COLORS['bg_dark'])
        bottom_frame.pack(fill="x", pady=(2, 0))
        self._notion_refresh_btn = tk.Button(
            bottom_frame, text="Refresh", font=FONTS['small'],
            fg=COLORS['text_secondary'], bg=COLORS['bg_dark'],
            activeforeground=COLORS['text'], activebackground=COLORS['bg_dark'],
            relief="flat", cursor="hand2", command=self._refresh_notion_pages)
        self._notion_refresh_btn.pack(side="left")
        self._notion_create_btn = tk.Button(
            bottom_frame, text="+ Create category page", font=FONTS['small'],
            fg=COLORS['text_secondary'], bg=COLORS['bg_dark'],
            activeforeground=COLORS['text'], activebackground=COLORS['bg_dark'],
            relief="flat", cursor="hand2", command=self._create_notion_category_page)
        self._notion_create_btn.pack(side="left", padx=(12, 0))

        self._notion_err = make_label(f, "", color_key='error', font_key='small')
        self._notion_err.pack(anchor="w", pady=(4, 0))

    def _on_enter_notion(self):
        self._notion_err.configure(text="")
        if self._notion_var.get() == "no":
            self._notion_frame.pack_forget()
            return
        self._notion_frame.pack(fill="both", expand=True)
        if not self._notion_validated:
            self._notion_status.configure(text="Validating credentials...",
                                           fg=COLORS['text_secondary'])
            self._notion_listbox.delete(0, tk.END)
            self._set_next_enabled(False)

            def worker():
                valid, err = validate_notion_credentials()
                self._safe_after(0, lambda v=valid, e=err: self._on_notion_validated(v, e))

            threading.Thread(target=worker, daemon=True).start()
        else:
            self._load_notion_pages()

    def _on_notion_validated(self, valid, err):
        if valid:
            self._notion_validated = True
            self._notion_stack = [(NOTION_PARENT_PAGE_ID, "Home")]
            self._notion_page_id = None
            self._notion_page_title = ""
            self._load_notion_pages()
        else:
            self._notion_status.configure(
                text=f"Notion validation failed: {err}", fg=COLORS['error'])

    def _on_notion_toggle(self):
        if self._notion_var.get() == "no":
            self._notion_frame.pack_forget()
            self._set_next_enabled(True)
        else:
            self._on_enter_notion()

    def _load_notion_pages(self):
        self._notion_listbox.delete(0, tk.END)
        self._notion_status.configure(text="Loading...", fg=COLORS['text_secondary'])
        self._notion_page_id = None
        self._update_notion_breadcrumb()
        self._update_notion_back_btn()
        self._update_notion_create_btn()
        self._set_next_enabled(False)

        current_id = self._notion_stack[-1][0]
        self._notion_load_gen += 1
        gen = self._notion_load_gen

        def worker():
            try:
                pages = get_notion_child_pages(current_id)
                self._safe_after(0, lambda p=pages, g=gen: self._populate_notion_list(p, g))
            except Exception as e:
                self._safe_after(0, lambda: self._notion_status.configure(
                    text=f"Error: {type(e).__name__}", fg=COLORS['error']))

        threading.Thread(target=worker, daemon=True).start()

    def _populate_notion_list(self, pages, gen):
        if gen != self._notion_load_gen:
            return
        self._notion_pages = pages
        self._notion_listbox.delete(0, tk.END)
        if not pages:
            self._notion_status.configure(text="No child pages found.",
                                           fg=COLORS['warning'])
            return
        for _, title in pages:
            self._notion_listbox.insert(tk.END, f"  {title}")
        self._notion_status.configure(
            text="Click to select · Double-click to navigate",
            fg=COLORS['text_dim'])

    def _on_notion_select(self, _event):
        sel = self._notion_listbox.curselection()
        if not sel:
            return
        page_id, title = self._notion_pages[sel[0]]
        self._notion_page_id = page_id
        self._notion_page_title = title
        self._notion_status.configure(text=f"Selected: {title}", fg=COLORS['success'])
        self._set_next_enabled(True)

    def _on_notion_double_click(self, _event):
        sel = self._notion_listbox.curselection()
        if not sel:
            return
        page_id, title = self._notion_pages[sel[0]]
        self._notion_stack.append((page_id, title))
        self._notion_page_id = None
        self._notion_page_title = ""
        self._load_notion_pages()

    def _notion_go_back(self):
        if len(self._notion_stack) <= 1:
            return
        self._notion_stack.pop()
        self._load_notion_pages()

    def _refresh_notion_pages(self):
        self._load_notion_pages()

    def _update_notion_breadcrumb(self):
        text = " > ".join(t for _, t in self._notion_stack)
        self._notion_breadcrumb.configure(text=text)

    def _update_notion_back_btn(self):
        at_root = len(self._notion_stack) <= 1
        self._notion_back_btn.configure(
            state="disabled" if at_root else "normal",
            fg=COLORS['text_dim'] if at_root else COLORS['text_secondary'])

    def _update_notion_create_btn(self):
        at_root = len(self._notion_stack) == 1
        self._notion_create_btn.configure(
            state="normal" if at_root else "disabled",
            fg=COLORS['text_secondary'] if at_root else COLORS['text_dim'])

    def _create_notion_category_page(self):
        win = tk.Toplevel(self)
        win.title("New category page")
        win.resizable(False, False)
        win.configure(padx=20, pady=16, bg=COLORS['bg_dark'])
        win.grab_set()

        make_label(win, "Page name:").grid(row=0, column=0, columnspan=2, sticky="w")
        name_entry = make_entry(win, width=30)
        name_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 12))
        name_entry.focus()
        err_label = make_label(win, "", color_key='error', font_key='small')
        err_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 8))

        def submit():
            name = name_entry.get().strip()
            if not name:
                err_label.configure(text="Name cannot be empty.")
                return
            err_label.configure(text="Creating...", fg=COLORS['text_secondary'])

            def worker():
                try:
                    parent_id = self._notion_stack[-1][0]
                    create_notion_page(parent_id, name, [])
                    self._safe_after(0, self._load_notion_pages)
                    self._safe_after(0, win.destroy)
                except Exception as e:
                    self._safe_after(0, lambda: err_label.configure(
                        text=f"{type(e).__name__}: {e}", fg=COLORS['error']))

            threading.Thread(target=worker, daemon=True).start()

        btn_frame = tk.Frame(win, bg=COLORS['bg_dark'])
        btn_frame.grid(row=3, column=0, columnspan=2, sticky="ew")
        ttk.Button(btn_frame, text="Create", command=submit).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Cancel", command=win.destroy).pack(side="left")
        win.bind("<Return>", lambda e: submit())

    def _validate_notion(self):
        if self._notion_var.get() == "no":
            self._notion_page_id = None
            self._notion_page_title = ""
            return True
        if not self._notion_page_id:
            self._notion_err.configure(text="Please select a Notion page.")
            return False
        self._notion_err.configure(text="")
        return True

    # ════════════════════════════════════════════════════════════════
    #  SCREEN 4 — Prompt
    # ════════════════════════════════════════════════════════════════

    def _build_screen_prompt(self):
        f = tk.Frame(self._body, bg=COLORS['bg_dark'])
        self._screens[SCREEN_PROMPT] = f

        make_label(f, "Prompt", font_key='heading').pack(anchor="w", pady=(6, 6))

        # ── Bottom bar (packed first so text editor doesn't push it off) ──
        bottom = tk.Frame(f, bg=COLORS['bg_dark'])
        bottom.pack(side="bottom", fill="x", pady=(6, 0))

        # ── Split layout: list left, editor right ───────────────────
        paned = tk.Frame(f, bg=COLORS['bg_dark'])
        paned.pack(fill="both", expand=True)
        paned.columnconfigure(1, weight=1)
        paned.rowconfigure(0, weight=1)

        # Left: prompt list
        left_frame = tk.Frame(paned, bg=COLORS['bg_dark'])
        left_frame.grid(row=0, column=0, sticky="ns", padx=(0, 8))

        make_label(left_frame, "Prompts", font_key='small',
                   color_key='text_secondary').pack(anchor="w")
        self._prompt_listbox = make_listbox(left_frame, width=20, height=14)
        self._prompt_listbox.pack(fill="y", expand=True, pady=(4, 0))
        self._prompt_listbox.bind("<<ListboxSelect>>", self._on_prompt_select)

        # Right: text editor
        right_frame = tk.Frame(paned, bg=COLORS['bg_dark'])
        right_frame.grid(row=0, column=1, sticky="nsew")

        self._prompt_editor = tk.Text(
            right_frame, wrap="word", font=FONTS['mono'],
            bg=COLORS['bg'], fg=COLORS['text'],
            insertbackground=COLORS['text'],
            selectbackground=COLORS['accent'],
            selectforeground=COLORS['text'],
            relief="flat", highlightthickness=1,
            highlightcolor=COLORS['accent'],
            highlightbackground=COLORS['bg_light'],
            undo=True)
        editor_scroll = tk.Scrollbar(right_frame, command=self._prompt_editor.yview)
        self._prompt_editor.configure(yscrollcommand=editor_scroll.set)
        self._prompt_editor.pack(side="left", fill="both", expand=True)
        editor_scroll.pack(side="right", fill="y")
        self._prompt_editor.bind("<<Modified>>", self._on_prompt_modified)

        # ── Bottom bar contents ─────────────────────────────────────
        self._prompt_info = make_label(bottom, "", font_key='small',
                                        color_key='text_dim')
        self._prompt_info.pack(anchor="w")

        self._prompt_save_btn = ttk.Button(bottom, text="Save as new prompt...",
                                            command=self._save_prompt_as)

        self._prompt_err = make_label(bottom, "", color_key='error', font_key='small')
        self._prompt_err.pack(anchor="w")

    def _scan_prompt_files(self):
        """Return sorted list of .txt filenames in prompts/ directory."""
        os.makedirs(PROMPTS_DIR, exist_ok=True)
        return sorted(
            f for f in os.listdir(PROMPTS_DIR)
            if f.endswith(".txt") and os.path.isfile(os.path.join(PROMPTS_DIR, f))
        )

    def _on_enter_prompt(self):
        self._prompt_err.configure(text="")
        self._prompt_info.configure(text="")
        self._prompt_save_btn.pack_forget()

        # Refresh file list
        self._prompt_files = self._scan_prompt_files()
        self._prompt_listbox.delete(0, tk.END)
        default_index = 0
        for i, name in enumerate(self._prompt_files):
            self._prompt_listbox.insert(tk.END, f"  {name}")
            if name == "summary_prompt.txt":
                default_index = i

        # Select default prompt
        if self._prompt_files:
            self._prompt_listbox.selection_set(default_index)
            self._prompt_listbox.see(default_index)
            self._load_prompt_file(self._prompt_files[default_index])

    def _on_prompt_select(self, _event):
        sel = self._prompt_listbox.curselection()
        if not sel:
            return
        filename = self._prompt_files[sel[0]]
        self._load_prompt_file(filename)

    def _load_prompt_file(self, filename):
        path = os.path.join(PROMPTS_DIR, filename)
        try:
            with open(path, "r", encoding="utf-8") as fp:
                content = fp.read()
        except Exception:
            content = ""
        self._prompt_original_text = content
        self._prompt_editor.delete("1.0", tk.END)
        self._prompt_editor.insert("1.0", content)
        self._prompt_editor.edit_modified(False)
        self._prompt_save_btn.pack_forget()
        self._prompt_err.configure(text="")
        self._prompt_info.configure(text="")

    def _on_prompt_modified(self, _event=None):
        if not self._prompt_editor.edit_modified():
            return
        current = self._prompt_editor.get("1.0", "end-1c")
        if current != self._prompt_original_text:
            self._prompt_save_btn.pack(anchor="w", pady=(4, 0))
        else:
            self._prompt_save_btn.pack_forget()

    def _save_prompt_as(self):
        win = tk.Toplevel(self)
        win.title("Save prompt as")
        win.resizable(False, False)
        win.configure(padx=20, pady=16, bg=COLORS['bg_dark'])
        win.grab_set()

        make_label(win, "Prompt name (without .txt):").grid(
            row=0, column=0, columnspan=2, sticky="w")
        name_entry = make_entry(win, width=30)
        name_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 12))
        name_entry.focus()
        err_label = make_label(win, "", color_key='error', font_key='small')
        err_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 8))

        def submit():
            name = name_entry.get().strip()
            if not name:
                err_label.configure(text="Name cannot be empty.")
                return
            if _UNSAFE_CHARS.search(name):
                err_label.configure(text="Name contains invalid characters.")
                return
            filename = f"{name}.txt"
            filepath = os.path.join(PROMPTS_DIR, filename)
            if os.path.exists(filepath):
                err_label.configure(text="A prompt with this name already exists.")
                return
            content = self._prompt_editor.get("1.0", "end-1c")
            with open(filepath, "w", encoding="utf-8") as fp:
                fp.write(content)
            # Refresh list and select the new prompt
            self._prompt_files = self._scan_prompt_files()
            self._prompt_listbox.delete(0, tk.END)
            new_index = 0
            for i, f in enumerate(self._prompt_files):
                self._prompt_listbox.insert(tk.END, f"  {f}")
                if f == filename:
                    new_index = i
            self._prompt_listbox.selection_set(new_index)
            self._prompt_listbox.see(new_index)
            self._prompt_original_text = content
            self._prompt_editor.edit_modified(False)
            self._prompt_save_btn.pack_forget()
            win.destroy()

        btn_frame = tk.Frame(win, bg=COLORS['bg_dark'])
        btn_frame.grid(row=3, column=0, columnspan=2, sticky="ew")
        ttk.Button(btn_frame, text="Save", command=submit).pack(side="left", padx=(0, 6))
        ttk.Button(btn_frame, text="Cancel", command=win.destroy).pack(side="left")
        win.bind("<Return>", lambda e: submit())

    def _validate_prompt(self):
        text = self._prompt_editor.get("1.0", "end-1c")
        if _TRANSCRIPTION_PLACEHOLDER not in text:
            self._prompt_err.configure(
                text=f"Prompt must contain {_TRANSCRIPTION_PLACEHOLDER}")
            return False
        self._prompt_err.configure(text="")
        if _LANGUAGE_PLACEHOLDER not in text:
            self._prompt_info.configure(
                text="Note: [LANGUAGE] placeholder not found. "
                     "The summary language won't be specified in the prompt.",
                fg=COLORS['warning'])
        else:
            self._prompt_info.configure(text="")
        self._prompt_text = text
        return True

    # ════════════════════════════════════════════════════════════════
    #  SCREEN 5 — Recap
    # ════════════════════════════════════════════════════════════════

    def _build_screen_recap(self):
        f = tk.Frame(self._body, bg=COLORS['bg_dark'])
        self._screens[SCREEN_RECAP] = f

        make_label(f, "Review", font_key='heading').pack(anchor="w", pady=(10, 14))
        self._recap_frame = tk.Frame(f, bg=COLORS['bg_dark'])
        self._recap_frame.pack(fill="x")

    def _on_enter_recap(self):
        for widget in self._recap_frame.winfo_children():
            widget.destroy()

        # Determine prompt display name
        sel = self._prompt_listbox.curselection()
        prompt_name = self._prompt_files[sel[0]] if sel else "summary_prompt.txt"
        current_text = self._prompt_editor.get("1.0", "end-1c")
        if current_text != self._prompt_original_text:
            prompt_name += " (modified)"

        rows = [
            ("URL", self._url[:55] + ("..." if len(self._url) > 55 else "")),
            ("Language", self._get_lang_display()),
            ("Mode", "Whisper" if self._use_whisper else "Subtitles"),
            ("Category", self._category),
            ("Video name", self._video_name),
            ("Notion", self._notion_page_title if self._notion_page_id else "Skipped"),
            ("Prompt", prompt_name),
        ]
        for i, (label, value) in enumerate(rows):
            make_label(self._recap_frame, label, font_key='body_bold',
                       color_key='text_secondary').grid(row=i, column=0, sticky="w",
                                                         padx=(0, 20), pady=4)
            make_label(self._recap_frame, value, font_key='body',
                       color_key='text').grid(row=i, column=1, sticky="w", pady=4)

    def _get_lang_display(self):
        lang_name = LANGUAGE_NAMES.get(self._lang_var.get(), self._lang_var.get())
        if self._use_whisper:
            return f"{lang_name} (Whisper)"
        code = self._matched_lang_code or self._lang_var.get()
        if code != self._lang_var.get():
            return f"{lang_name} ({code})"
        return lang_name

    # ════════════════════════════════════════════════════════════════
    #  SCREEN 6 — Progress
    # ════════════════════════════════════════════════════════════════

    def _build_screen_progress(self):
        f = tk.Frame(self._body, bg=COLORS['bg_dark'])
        self._screens[SCREEN_PROGRESS] = f

        self._prog_heading = make_label(f, "Transcribing...", font_key='heading')
        self._prog_heading.pack(anchor="w", pady=(30, 20))

        self._progress_bar = ttk.Progressbar(f, orient="horizontal", length=500,
                                              mode="determinate", maximum=100)
        self._progress_bar.pack(fill="x", pady=(0, 12))

        # Status + percentage + timer row
        info_row = tk.Frame(f, bg=COLORS['bg_dark'])
        info_row.pack(fill="x")

        self._prog_status = make_label(info_row, "", font_key='body',
                                        color_key='text_secondary')
        self._prog_status.pack(side="left")

        self._prog_timer_label = make_label(info_row, "00:00", font_key='small',
                                             color_key='text_dim')
        self._prog_timer_label.pack(side="right")

        self._prog_pct_label = make_label(info_row, "0%", font_key='small',
                                           color_key='text_dim')
        self._prog_pct_label.pack(side="right", padx=(0, 12))

        # Error frame (hidden by default)
        self._prog_error_frame = tk.Frame(f, bg=COLORS['bg_dark'])
        self._prog_error_label = make_label(self._prog_error_frame, "",
                                             font_key='body', color_key='error')
        self._prog_error_label.pack(anchor="w", pady=(0, 10))
        self._prog_close_btn = ttk.Button(self._prog_error_frame, text="Close",
                                           command=self._on_close)

    def _on_enter_progress(self):
        self._target_pct = 0
        self._display_pct = 0.0
        self._animating = False
        self._progress_bar['value'] = 0
        self._prog_status.configure(text="Starting...")
        self._prog_pct_label.configure(text="0%")
        self._prog_timer_label.configure(text="00:00")
        self._prog_heading.configure(text="Transcribing...", fg=COLORS['text'])
        self._prog_error_frame.pack_forget()
        self._start_time = time.time()
        self._tick_timer()
        self._start_pipeline()

    def _tick_timer(self):
        if self._destroyed or self._current_screen != SCREEN_PROGRESS:
            return
        elapsed = int(time.time() - self._start_time)
        minutes, seconds = divmod(elapsed, 60)
        self._prog_timer_label.configure(text=f"{minutes:02d}:{seconds:02d}")
        self.after(1000, self._tick_timer)

    def _start_pipeline(self):
        lang = self._matched_lang_code if not self._use_whisper else self._lang_var.get()
        video_folder = os.path.join(TRANSCRIPTIONS_DIR, self._category, self._video_name)
        run_pipeline(
            url=self._url,
            lang_code=lang,
            video_folder=video_folder,
            use_whisper=self._use_whisper,
            notion_page_id=self._notion_page_id,
            on_progress=self._on_progress,
            on_done=self._on_done,
            on_error=self._on_error,
            prompt_text=self._prompt_text,
        )

    def _on_progress(self, pct, message):
        self._safe_after(0, lambda p=pct, m=message: self._update_progress(p, m))

    def _update_progress(self, pct, message):
        self._target_pct = pct
        self._prog_status.configure(text=message)
        if not self._animating:
            self._animating = True
            self._animate_progress()

    def _animate_progress(self):
        if self._destroyed:
            return
        if self._display_pct < self._target_pct:
            diff = self._target_pct - self._display_pct
            step = max(0.5, diff * 0.1)
            self._display_pct = min(self._target_pct, self._display_pct + step)
        elif self._display_pct < 100 and self._target_pct < 100:
            cap = min(self._target_pct + 8, 99)
            if self._display_pct < cap:
                self._display_pct += 0.1

        self._progress_bar['value'] = self._display_pct
        self._prog_pct_label.configure(text=f"{int(self._display_pct)}%")

        if self._display_pct >= 100:
            self._animating = False
        else:
            self.after(50, self._animate_progress)

    def _on_done(self, result):
        self._safe_after(0, lambda r=result: self._handle_done(r))

    def _handle_done(self, result):
        self._result = result
        self._target_pct = 100
        self._prog_heading.configure(text="Complete!", fg=COLORS['success'])
        self._prog_status.configure(text="All steps finished successfully.")
        if result.get("notion_url"):
            self._complete_notion_btn.pack(side="left", padx=6)
        else:
            self._complete_notion_btn.pack_forget()
        self.after(1200, lambda: self._show_screen(SCREEN_COMPLETE))

    def _on_error(self, message):
        self._safe_after(0, lambda m=message: self._handle_error(m))

    def _handle_error(self, message):
        self._animating = False
        self._prog_heading.configure(text="Error", fg=COLORS['error'])
        self._prog_status.configure(text="")
        self._prog_error_label.configure(text=message)
        self._prog_error_frame.pack(anchor="w", pady=(10, 0))
        self._prog_close_btn.pack(anchor="w", pady=(6, 0))

    # ════════════════════════════════════════════════════════════════
    #  SCREEN 7 — Complete
    # ════════════════════════════════════════════════════════════════

    def _build_screen_complete(self):
        f = tk.Frame(self._body, bg=COLORS['bg_dark'])
        self._screens[SCREEN_COMPLETE] = f

        make_label(f, "All done!", font_key='title',
                   color_key='success').pack(anchor="center", pady=(40, 10))
        make_label(f, "Your transcription and summary are ready.",
                   font_key='body', color_key='text_secondary').pack(anchor="center", pady=(0, 24))

        btn_frame = tk.Frame(f, bg=COLORS['bg_dark'])
        btn_frame.pack(anchor="center")

        self._complete_files_btn = ttk.Button(
            btn_frame, text="View files", command=self._open_files)
        self._complete_files_btn.pack(side="left", padx=6)

        self._complete_notion_btn = ttk.Button(
            btn_frame, text="View Notion page", command=self._open_notion)
        self._complete_notion_btn.pack(side="left", padx=6)

        ttk.Button(btn_frame, text="Close", command=self._on_close).pack(side="left", padx=6)

    def _open_files(self):
        if self._result and self._result.get("folder"):
            os.startfile(self._result["folder"])

    def _open_notion(self):
        if self._result and self._result.get("notion_url"):
            webbrowser.open(self._result["notion_url"])
