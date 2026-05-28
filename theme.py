import tkinter as tk
from tkinter import ttk

# ── Colors (Tailwind-inspired dark palette) ─────────────────────
COLORS = {
    'bg_dark':        '#0f172a',
    'bg':             '#1e293b',
    'bg_light':       '#334155',
    'accent':         '#3b82f6',
    'accent_hover':   '#60a5fa',
    'text':           '#f1f5f9',
    'text_secondary': '#94a3b8',
    'text_dim':       '#64748b',
    'success':        '#22c55e',
    'error':          '#ef4444',
    'warning':        '#f59e0b',
}

# ── Fonts ────────────────────────────────────────────────────────
FONTS = {
    'title':     ('Segoe UI', 22, 'bold'),
    'heading':   ('Segoe UI', 15, 'bold'),
    'body':      ('Segoe UI', 11),
    'body_bold': ('Segoe UI', 11, 'bold'),
    'small':     ('Segoe UI', 9),
    'mono':      ('Consolas', 10),
}


def apply_theme(root):
    """Configure ttk styles and root window for the dark theme."""
    root.configure(bg=COLORS['bg_dark'])
    root.option_add('*TkFDialog*foreground', 'black')

    style = ttk.Style(root)
    style.theme_use('clam')

    # ── Frame ──
    style.configure('TFrame', background=COLORS['bg_dark'])

    # ── Label ──
    style.configure('TLabel', background=COLORS['bg_dark'],
                     foreground=COLORS['text'], font=FONTS['body'])

    # ── Button ──
    style.configure('TButton', background=COLORS['accent'],
                     foreground=COLORS['text'], font=FONTS['body'],
                     padding=(16, 8), borderwidth=0)
    style.map('TButton',
              background=[('active', COLORS['accent_hover']),
                          ('disabled', COLORS['bg_light'])],
              foreground=[('disabled', COLORS['text_dim'])])

    # ── Radiobutton ──
    style.configure('TRadiobutton', background=COLORS['bg_dark'],
                     foreground=COLORS['text'], font=FONTS['body'],
                     indicatorcolor=COLORS['bg_light'])
    style.map('TRadiobutton',
              background=[('active', COLORS['bg_dark'])],
              indicatorcolor=[('selected', COLORS['accent'])])

    # ── Checkbutton ──
    style.configure('TCheckbutton', background=COLORS['bg_dark'],
                     foreground=COLORS['text'], font=FONTS['body'],
                     indicatorcolor=COLORS['bg_light'])
    style.map('TCheckbutton',
              background=[('active', COLORS['bg_dark'])],
              indicatorcolor=[('selected', COLORS['accent'])])

    # ── Progressbar ──
    style.configure('Horizontal.TProgressbar',
                     troughcolor=COLORS['bg_light'],
                     background=COLORS['accent'],
                     thickness=18, borderwidth=0)

    # ── Separator ──
    style.configure('TSeparator', background=COLORS['bg_light'])


# ── Widget helpers (plain tk for per-instance styling) ───────────

def make_label(parent, text="", font_key='body', color_key='text', **kw):
    """Return a pre-styled tk.Label."""
    return tk.Label(parent, text=text,
                    font=FONTS.get(font_key, FONTS['body']),
                    fg=COLORS.get(color_key, COLORS['text']),
                    bg=COLORS['bg_dark'], **kw)


def make_entry(parent, **kw):
    """Return a pre-styled tk.Entry with dark background."""
    return tk.Entry(parent,
                    bg=COLORS['bg'], fg=COLORS['text'],
                    insertbackground=COLORS['text'],
                    selectbackground=COLORS['accent'],
                    selectforeground=COLORS['text'],
                    font=FONTS['body'], relief='flat',
                    highlightthickness=1,
                    highlightcolor=COLORS['accent'],
                    highlightbackground=COLORS['bg_light'], **kw)


def make_listbox(parent, **kw):
    """Return a pre-styled tk.Listbox with dark background."""
    return tk.Listbox(parent,
                      bg=COLORS['bg'], fg=COLORS['text'],
                      selectbackground=COLORS['accent'],
                      selectforeground=COLORS['text'],
                      font=FONTS['body'], relief='flat',
                      highlightthickness=1,
                      highlightcolor=COLORS['accent'],
                      highlightbackground=COLORS['bg_light'],
                      activestyle='none', exportselection=False, **kw)
