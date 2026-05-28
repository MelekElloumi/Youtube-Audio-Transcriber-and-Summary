import os
import tkinter as tk

from config import TRANSCRIPTIONS_DIR, ICON_PATH, setup_logging
from theme import COLORS, FONTS, apply_theme, make_label
from wizard import TranscribeWizard


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        setup_logging()
        apply_theme(self)
        self.title("YT Transcriber")
        if os.path.exists(ICON_PATH):
            self.iconbitmap(ICON_PATH)
        self.minsize(400, 300)
        self._center(450, 340)
        self._wizard_open = False
        self._build_ui()

    def _center(self, w, h):
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        # ── Title ──
        make_label(self, "YT Transcriber", font_key='title').pack(pady=(50, 6))
        make_label(self, "Transcribe, summarize, and save to Notion",
                   font_key='body', color_key='text_secondary').pack(pady=(0, 36))

        # ── Buttons ──
        btn_frame = tk.Frame(self, bg=COLORS['bg_dark'])
        btn_frame.pack()

        self.transcribe_btn = tk.Button(
            btn_frame, text="Transcribe a new video",
            font=FONTS['body_bold'],
            fg=COLORS['text'], bg=COLORS['accent'],
            activeforeground=COLORS['text'], activebackground=COLORS['accent_hover'],
            relief="flat", cursor="hand2", padx=20, pady=10,
            command=self._open_wizard)
        self.transcribe_btn.pack(pady=(0, 12))

        view_btn = tk.Button(
            btn_frame, text="View transcriptions",
            font=FONTS['body'],
            fg=COLORS['text_secondary'], bg=COLORS['bg_light'],
            activeforeground=COLORS['text'], activebackground=COLORS['bg_light'],
            relief="flat", cursor="hand2", padx=16, pady=8,
            command=self._open_folder)
        view_btn.pack(pady=(0, 12))

        quit_btn = tk.Button(
            btn_frame, text="Quit",
            font=FONTS['body'],
            fg=COLORS['text_dim'], bg=COLORS['bg_dark'],
            activeforeground=COLORS['text_secondary'], activebackground=COLORS['bg_dark'],
            relief="flat", cursor="hand2", padx=16, pady=6,
            command=self.destroy)
        quit_btn.pack()

    def _open_wizard(self):
        if self._wizard_open:
            return
        self._wizard_open = True
        self.transcribe_btn.configure(state="disabled")
        TranscribeWizard(self, on_close=self._on_wizard_close)

    def _on_wizard_close(self):
        self._wizard_open = False
        self.transcribe_btn.configure(state="normal")

    def _open_folder(self):
        os.makedirs(TRANSCRIPTIONS_DIR, exist_ok=True)
        os.startfile(TRANSCRIPTIONS_DIR)


if __name__ == "__main__":
    app = App()
    app.mainloop()
