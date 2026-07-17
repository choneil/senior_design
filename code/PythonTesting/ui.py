import tkinter as tk
from tkinter import messagebox
import glob
import threading

from centroid import load_centroid_file
from gcode_generator import build_gcode
from rambo_serial import Rambo
from config import *

# --- Touch sizing for 720x1280 portrait (5" Touch Display 2) --------------
# High pixel density on a 5" panel: fonts must be LARGE in px to be readable
# and tappable. Tuned for 720px width, portrait.
FULLSCREEN = True          # kiosk: no title bar, fills the panel

BTN_FONT   = ("DejaVu Sans", 26, "bold")
LIST_FONT  = ("DejaVu Sans", 24)
STAT_FONT  = ("DejaVu Sans", 28, "bold")
STOP_FONT  = ("DejaVu Sans", 34, "bold")
BTN_PAD_Y  = 28           # internal button height padding -> big touch target
GAP        = 14
SCROLLBAR_W = 44          # finger-draggable

COL_BG     = "#1e1e1e"
COL_PANEL  = "#2b2b2b"
COL_TEXT   = "#f0f0f0"
COL_RUN    = "#2e7d32"   # green
COL_STOP   = "#c62828"   # red
COL_BTN    = "#37474f"   # neutral slate
COL_BTN_TX = "#ffffff"


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Pick and Place")
        self.root.configure(bg=COL_BG)

        if FULLSCREEN:
            self.root.attributes("-fullscreen", True)
            # Escape exits fullscreen during development; remove for deploy.
            self.root.bind("<Escape>", lambda e: self.root.attributes("-fullscreen", False))

        self.rambo = Rambo()
        self.file = None
        self.running = False
        self.worker_thread = None

        # --- File list with scrollbar (top, flexible height) ---
        list_frame = tk.Frame(root, bg=COL_BG)
        list_frame.pack(fill="both", expand=True, padx=GAP, pady=(GAP, GAP))

        scrollbar = tk.Scrollbar(list_frame, width=SCROLLBAR_W)
        scrollbar.pack(side="right", fill="y")

        self.listbox = tk.Listbox(
            list_frame, font=LIST_FONT, bg=COL_PANEL, fg=COL_TEXT,
            selectbackground=COL_RUN, selectforeground="#ffffff",
            highlightthickness=0, bd=0, activestyle="none",
            yscrollcommand=scrollbar.set,
        )
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.listbox.yview)

        # --- Status line (big, always visible) ---
        self.status = tk.Label(
            root, text="Idle", font=STAT_FONT, bg=COL_BG, fg=COL_TEXT,
            anchor="w", pady=10,
        )
        self.status.pack(fill="x", padx=GAP)

        # --- Control buttons ---
        top_row = tk.Frame(root, bg=COL_BG)
        top_row.pack(fill="x", padx=GAP, pady=(0, GAP))
        self._mk_btn(top_row, "Refresh", self.refresh, COL_BTN, COL_BTN_TX).pack(
            side="left", fill="x", expand=True, padx=(0, GAP // 2))
        self._mk_btn(top_row, "Connect", self.connect, COL_BTN, COL_BTN_TX).pack(
            side="left", fill="x", expand=True, padx=(GAP // 2, 0))

        # RUN (big, green, full width)
        self._mk_btn(root, "RUN", self.run, COL_RUN, "#ffffff").pack(
            fill="x", padx=GAP, pady=(0, GAP))

        # STOP (biggest, red, full width, visually separated)
        stop = self._mk_btn(root, "STOP", self.stop, COL_STOP, "#ffffff")
        stop.configure(font=STOP_FONT)
        stop.pack(fill="x", padx=GAP, pady=(0, GAP), ipady=BTN_PAD_Y // 2)

        self.refresh()

    def _mk_btn(self, parent, text, cmd, bg, fg):
        return tk.Button(
            parent, text=text, command=cmd, font=BTN_FONT,
            bg=bg, fg=fg, activebackground=bg, activeforeground=fg,
            relief="flat", bd=0, pady=BTN_PAD_Y, highlightthickness=0,
        )

    # --- Thread-safe UI helper -------------------------------------------
    def set_status(self, text):
        self.root.after(0, lambda: self.status.config(text=text))

    # --- File discovery ---------------------------------------------------
    def refresh(self):
        self.listbox.delete(0, tk.END)
        seen = set()
        for path in USB_SEARCH_PATHS:
            for f in glob.glob(path.rstrip("/") + "/*.csv"):
                if f not in seen:
                    seen.add(f)
                    self.listbox.insert(tk.END, f)
        if self.listbox.size() == 0:
            self.listbox.insert(tk.END, "  (no CSV files - insert USB & Refresh)")

    # --- Serial connect ---------------------------------------------------
    def connect(self):
        try:
            self.rambo.connect()
            self.set_status("Connected")
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))
            self.set_status("Connection failed")

    # --- Run --------------------------------------------------------------
    def run(self):
        if self.running:
            return
        if not self.rambo.is_connected():
            messagebox.showwarning("Not connected", "Connect to the Rambo first.")
            return
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showinfo("No file", "Select a CSV file from the list.")
            return

        self.file = self.listbox.get(sel[0])
        if self.file.strip().startswith("("):
            return

        self.running = True
        self.worker_thread = threading.Thread(target=self.worker, daemon=True)
        self.worker_thread.start()

    def worker(self):
        try:
            self.set_status("Loading CSV...")
            comps = load_centroid_file(self.file)

            self.set_status("Generating g-code...")
            gcode = build_gcode(comps)

            total = len(gcode)
            for i, line in enumerate(gcode):
                if not self.running:
                    self.set_status("Aborted")
                    break
                self.set_status(f"[{i + 1}/{total}] {line}")
                self.rambo.send(line)
            else:
                self.set_status("Done")
        except Exception as e:
            self.set_status(f"Error: {e}")
        finally:
            self.running = False

    # --- Stop -------------------------------------------------------------
    def stop(self):
        self.running = False
        try:
            self.rambo.emergency_stop()
        except Exception as e:
            self.set_status(f"Stop error: {e}")
            return
        self.set_status("Stopped")