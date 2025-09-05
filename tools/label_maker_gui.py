#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FPF Label Maker — графическая утилита для разметки паттернов FPF (SHORT / LONG).
Версия: 0.2

Особенности:
- Две панели со схемами паттернов (SHORT и LONG) на Canvas.
- Для каждой нумерованной точки два поля: Цена (верхняя строка) и Дата (нижняя строка).
- Дата вводится в 2025 году. Принимаются форматы: "DD,MM", "DD.MM", "DD/MM", "DD-MM", "DD MM", "DDMM".
- Кнопки "СФОРМИРОВАТЬ" под каждой панелью формируют JSONL-строку
  с типом FPF_SHORT или FPF_LONG и словарём точек. Строка копируется в буфер
  и может быть дописана в файл журнала (по умолчанию data/labeling/fpf_generic.jsonl).
- Пара общих полей сверху: SYMBOL и TF.

Запуск:  python tools/label_maker_gui.py
"""

from __future__ import annotations
import os
import re
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from dataclasses import dataclass

import sys, traceback

# --- optional Pillow for image preview ---
try:
    from PIL import Image, ImageTk  # type: ignore
    PIL_OK = True
except Exception:
    PIL_OK = False

# --- optional tkinterdnd2 for Drag&Drop ---
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD  # type: ignore
    DND_OK = True
except Exception:
    DND_OK = False

# === Ive/Apple‑like minimal palette ===
DARK_BG   = "#0f0f10"   # main window
PANEL_BG  = "#151517"   # panels
CANVAS_BG = "#0b0b0c"   # image area
ACCENT    = "#0A84FF"   # iOS blue
ACCENT_DIM = "#0969DA"
PURPLE = "#8A2BE2"  # blue-violet for FIX/PREFIX
LINE_COLOR = "#3A3A3C"  # subtle graphite lines
TEXT_LIGHT = "#F2F2F7"  # primary text
TEXT_MUTED = "#8E8E93"  # secondary text
BORDER_COL = "#2C2C2E"  # separators / strokes

SYMBOLS = [
    "BTCUSDT","ETHUSDT","BNBUSDT","BCHUSDT","DOGEUSDT","1INCHUSDT","AAVEUSDT","ADAUSDT","APEUSDT","AXSUSDT","DOTUSDT","SOLUSDT","XRPUSDT","LTCUSDT","MATICUSDT","AVAXUSDT","LINKUSDT","TRXUSDT","ATOMUSDT","UNIUSDT","XLMUSDT","ALGOUSDT","ICPUSDT","FILUSDT","ETCUSDT","APTUSDT","NEARUSDT","FTMUSDT","OPUUSDT","ARBUSDT","LDOUSDT","THETAUSDT","MANAUSDT","SANDUSDT","GRTUSDT","MKRUSDT","COMPUSDT","CRVUSDT","SNXUSDT","KSMUSDT","RUNEUSDT","FLOWUSDT","EGLDUSDT","ZECUSDT","DASHUSDT","KAVAUSDT","BATUSDT","ENAUSDT"
]

YEAR_FIXED = 2025
DEFAULT_OUT = os.path.join("data", "labeling", "fpf_generic.jsonl")

DATE_RE_SPLIT = re.compile(r"[\s\./,\\-]+")

# ---------- helpers ----------

def parse_price(s: str) -> float | None:
    s = (s or "").strip().replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None

def normalize_date(s: str) -> str | None:
    """Принимает строку вида "05,06" / "05.06" / "0506" / "5 6" и т.п.
    Возвращает ISO-дату в 2025: YYYY-MM-DD."""
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    # Если слитно без разделителей
    digits = re.sub(r"\D", "", s)
    if len(digits) == 4:
        dd, mm = digits[:2], digits[2:]
    else:
        parts = [p for p in DATE_RE_SPLIT.split(s) if p]
        if len(parts) != 2:
            return None
        dd, mm = parts[0], parts[1]
    try:
        day = int(dd)
        mon = int(mm)
        if not (1 <= day <= 31 and 1 <= mon <= 12):
            return None
        return f"{YEAR_FIXED:04d}-{mon:02d}-{day:02d}"
    except Exception:
        return None

@dataclass
class PointInputs:
    price_entry: tk.Entry
    date_entry: tk.Entry

# ---------- UI ----------

class PatternPanel(ttk.Frame):
    def __init__(self, master, title: str, points_spec: list[tuple[str, float, float]], kind: str):
        """
        points_spec: список (label, x, y) для размещения подписи и полей относительно Canvas.
        kind: "short" | "long"
        """
        super().__init__(master)
        self.kind = kind
        self.points_spec = points_spec
        self.inputs: dict[str, PointInputs] = {}

        # Каркас
        head = ttk.Label(self, text=title, font=("Helvetica Neue", 16, "bold"), foreground=TEXT_MUTED)
        head.pack(anchor="center", pady=(4, 6))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)

        # Canvas с рисунком паттерна
        self.canvas = tk.Canvas(body, width=640, height=280, bg=PANEL_BG, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        # Правый столбец с полями
        fields = ttk.Frame(body)
        fields.grid(row=0, column=1, sticky="ns")
        fields.configure(style='TFrame')

        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # Нарисуем базовую линию паттерна
        self._draw_pattern()

        # Сгенерируем поля по точкам
        # We need to get titles dictionary for the labels
        if self.kind == "short":
            titles = {
                "1.1": "старт↑",
                "1.2": "ФИКС",
                "1.3": "ЛОЙ-Ф",
                "1.4": "ХАЙ ПАТТЕРН",
                "1.5": "обн.ЛФ",
                "1.6": "ПРЕФ",
                "1.7": "БУ 25%",
                "1.8": "TP max"
            }
        else:
            titles = {
                "2.1": "старт↓",
                "2.2": "ФИКС",
                "2.3": "ХАЙ-Ф",
                "2.4": "ЛОЙ ПАТТЕРН",
                "2.5": "обн.ХФ",
                "2.6": "ПРЕФ",
                "2.7": "БУ 25%",
                "2.8": "TP max"
            }

        # Add header labels for the price and date columns
        ttk.Label(fields, text="цена").grid(row=0, column=1, sticky="s", pady=(0,4))
        ttk.Label(fields, text="дата").grid(row=0, column=2, sticky="s", pady=(0,4))

        # Validation command for price entries: allow only digits, dot, comma, empty string
        def validate_price_char(P):
            if P == "":
                return True
            return all(c in "0123456789.," for c in P)
        vcmd = (self.register(validate_price_char), '%P')

        for i, (code, x, y) in enumerate(self.points_spec, start=1):
            row = i
            lbl = ttk.Label(fields, text=titles.get(code, code))
            lbl.grid(row=row, column=0, sticky="w", padx=4, pady=2)
            pe = ttk.Entry(fields, width=12, validate='key', validatecommand=vcmd)
            de = ttk.Entry(fields, width=10)
            pe.grid(row=row, column=1, padx=2, pady=2)
            de.grid(row=row, column=2, padx=2, pady=2)
            self.inputs[code] = PointInputs(price_entry=pe, date_entry=de)
            # Bind events for auto-fill
            pe.bind('<KeyRelease>', lambda e, c=code: self._on_price_change(c, event='key'))
            pe.bind('<FocusOut>',  lambda e, c=code: self._on_price_change(c, event='focusout'))
            # Enter key moves focus to date field of the same row
            pe.bind('<Return>', lambda e, d=de: d.focus_set())

        # Кнопка сформировать
        btn = ttk.Button(self, text="СФОРМИРОВАТЬ", command=self.on_make)
        btn.pack(pady=8)

        # Колбек назначения (установит родитель)
        self.on_make_callback = None
        # Callback when a pattern point button is clicked (code string like '1.1')
        self.on_point_click = None

    def _on_price_change(self, src_code, event: str = 'key'):
        src_entry = self.inputs.get(src_code)
        if not src_entry:
            return
        raw = self._normalized_str(src_entry.price_entry.get())
        # Автозаполнение теперь срабатывает только при уходе фокуса,
        # чтобы не подставлять обрезанные значения (типа '114' вместо '114700').
        if event != 'focusout':
            return
        val = parse_price(raw)
        if val is None:
            return
        if self.kind == "short":
            if src_code == "1.2":
                for target_code in ("1.6", "1.7"):
                    tgt_entry = self.inputs.get(target_code)
                    if tgt_entry:
                        tgt_entry.price_entry.delete(0, "end")
                        tgt_entry.price_entry.insert(0, raw)
            elif src_code == "1.3":
                tgt_entry = self.inputs.get("1.5")
                if tgt_entry:
                    tgt_entry.price_entry.delete(0, "end")
                    tgt_entry.price_entry.insert(0, raw)
        elif self.kind == "long":
            if src_code == "2.2":
                for target_code in ("2.6", "2.7"):
                    tgt_entry = self.inputs.get(target_code)
                    if tgt_entry:
                        tgt_entry.price_entry.delete(0, "end")
                        tgt_entry.price_entry.insert(0, raw)
            elif src_code == "2.3":
                tgt_entry = self.inputs.get("2.5")
                if tgt_entry:
                    tgt_entry.price_entry.delete(0, "end")
                    tgt_entry.price_entry.insert(0, raw)


    def _normalized_str(self, s: str) -> str:
        s = (s or '').strip().replace(',', '.')
        return s

    # ----- отрисовка паттерна -----
    def _point_pressed(self, code: str):
        if callable(getattr(self, 'on_point_click', None)):
            try:
                self.on_point_click(code)
            except Exception:
                pass

    def _draw_pattern(self):
        c = self.canvas
        c.delete("all")
        # Линия паттерна
        if self.kind == "short":
            # final leg goes down to the right (short pattern)
            pts = [(40,240),(140,120),(200,180),(260,60),(300,200),(380,140),(430,185),(500,220)]
            titles = {
                "1.1": "старт↑",
                "1.2": "ФИКС",
                "1.3": "ЛОЙ-Ф",
                "1.4": "ХАЙ ПАТТЕРН",
                "1.5": "обн.ЛФ",
                "1.6": "ПРЕФ",
                "1.7": "БУ 25%",
                "1.8": "TP max"
            }
            spec = [("1.1",80,255),("1.2",150,130),("1.3",190,190),("1.4",260,75),("1.5",300,205),("1.6",380,150),("1.7",430,190),("1.8",520,220)]
        else:
            pts = [(40,60),(110,205),(180,115),(240,245),(305,95),(375,205),(445,135),(520,45)]
            titles = {
                "2.1": "старт↓",
                "2.2": "ФИКС",
                "2.3": "ХАЙ-Ф",
                "2.4": "ЛОЙ ПАТТЕРН",
                "2.5": "обн.ХФ",
                "2.6": "ПРЕФ",
                "2.7": "БУ 25%",
                "2.8": "TP max"
            }
            spec = [("2.1",120,85),("2.2",165,210),("2.3",225,125),("2.4",265,245),("2.5",330,105),("2.6",385,190),("2.7",470,145),("2.8",540,70)]
        for i in range(len(pts)-1):
            c.create_line(*pts[i], *pts[i+1], width=1, fill=LINE_COLOR)
        # Нарисуем точки и подписи в виде закруглённых прямоугольников с текстом
        self.points_spec = spec
        self.inputs = getattr(self, 'inputs', {})
        r_width = 64
        r_height = 36
        r_radius = 12
        for code, x, y in self.points_spec:
            # Координаты прямоугольника
            x0 = x - r_width//2
            y0 = y - r_height//2
            x1 = x + r_width//2
            y1 = y + r_height//2
            # Создание закругленного прямоугольника с помощью create_polygon с smooth=True
            points = [
                x0+r_radius, y0,
                x1-r_radius, y0,
                x1, y0,
                x1, y0+r_radius,
                x1, y1-r_radius,
                x1, y1,
                x1-r_radius, y1,
                x0+r_radius, y1,
                x0, y1,
                x0, y1-r_radius,
                x0, y0+r_radius,
                x0, y0,
            ]
            poly_id = c.create_polygon(points, fill=PANEL_BG, outline=ACCENT, width=1, smooth=True)
            title = titles.get(code, "")
            txt1_id = c.create_text(x, y - 6, text=code, font=("Helvetica Neue", 10, "bold"), fill=TEXT_LIGHT)
            txt2_id = c.create_text(x, y + 8, text=title, font=("Helvetica Neue", 8), fill=TEXT_MUTED)

            # Добавляем общий тег для полигона и текстов
            c.addtag_withtag(f"poly_{code}", poly_id)
            c.addtag_withtag(f"poly_{code}", txt1_id)
            c.addtag_withtag(f"poly_{code}", txt2_id)

            # Общий тег для всей «кнопки» и бинды на него
            btn_tag = f"poly_{code}"
            c.tag_bind(btn_tag, '<Enter>',    lambda e, pid=poly_id: (c.itemconfigure(pid, outline=ACCENT, width=2), c.config(cursor='hand2')))
            c.tag_bind(btn_tag, '<Leave>',    lambda e, pid=poly_id: (c.itemconfigure(pid, outline=ACCENT, width=1), c.config(cursor='')))
            c.tag_bind(btn_tag, '<Button-1>', lambda e, ccode=code: self._point_pressed(ccode))
            # ensure button sits on top and reacts on release too
            c.tag_raise(poly_id); c.tag_raise(txt1_id); c.tag_raise(txt2_id)
            c.tag_bind(btn_tag, '<ButtonRelease-1>', lambda e, ccode=code: self._point_pressed(ccode))
            c.tag_bind(btn_tag, '<Button-1>', lambda e: c.focus_set())

    # ----- сбор значений -----
    def collect(self) -> dict:
        out = {}
        for code, inp in self.inputs.items():
            ptxt = inp.price_entry.get().strip()
            if ptxt.lower() in ('цена',''):
                price = None
            else:
                price = parse_price(ptxt)
            dtxt = inp.date_entry.get().strip()
            if dtxt.lower() in ('дата',''):
                date_iso = None
            else:
                date_iso = normalize_date(dtxt)
            out[code] = {"price": price, "date": date_iso}
        return out

    def on_make(self):
        data = self.collect()
        if self.on_make_callback:
            self.on_make_callback(self.kind, data)

class ImageAnnotPanel(ttk.Frame):
    """Панель загрузки картинки и аннотаций: перетаскиваемые уровни (цены) и метки дат.
    Двойной клик по линии открывает окно для ввода кода точки (1.2, 1.6, 2.7) и значения.
    Кнопки применяют значения в SHORT/LONG панели (по кодам).
    """
    def __init__(self, master, on_apply_short, on_apply_long, get_short_codes, get_long_codes):
        super().__init__(master)
        self.on_apply_short = on_apply_short
        self.on_apply_long = on_apply_long
        self.get_short_codes = get_short_codes
        self.get_long_codes = get_long_codes

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=6, pady=4)
        ttk.Button(bar, text="Загрузить…", command=self._load_image).pack(side="left")
        ttk.Button(bar, text="Добавить уровень (цена)", command=self._add_hline).pack(side="left", padx=4)
        ttk.Button(bar, text="Добавить дату", command=self._add_vline).pack(side="left", padx=4)
        ttk.Button(bar, text="Применить → SHORT", command=lambda: self._apply(to="short")).pack(side="right", padx=4)
        ttk.Button(bar, text="Применить → LONG", command=lambda: self._apply(to="long")).pack(side="right")

        self.canvas = tk.Canvas(self, width=520, height=360, bg=CANVAS_BG, highlightthickness=1, highlightbackground=BORDER_COL)
        self.canvas.pack(fill="both", expand=True, padx=6, pady=6)
        # core canvas bindings (active always)
        self.canvas.bind('<Button-1>', self._on_down)
        self.canvas.bind('<B1-Motion>', self._on_move)
        self.canvas.bind('<ButtonRelease-1>', self._on_up)
        self.canvas.bind('<Double-Button-1>', self._on_edit)
        # delete active object via keyboard
        self.canvas.bind('<Delete>', self._on_delete)
        self.canvas.bind('<BackSpace>', self._on_delete)
        # zoom (wheel) and pan (middle mouse)
        self.canvas.bind('<MouseWheel>', self._on_zoom)       # Windows/macOS
        self.canvas.bind('<Button-4>', self._on_zoom)         # X11 zoom in
        self.canvas.bind('<Button-5>', self._on_zoom)         # X11 zoom out
        self.canvas.bind('<ButtonPress-2>', self._pan_start)
        self.canvas.bind('<B2-Motion>', self._on_pan)
        self.canvas.bind('<Escape>', lambda e: setattr(self, '_drag_item', None))
        # DnD file drop
        if 'DND_OK' in globals() and DND_OK:
            try:
                self.canvas.drop_target_register(DND_FILES)
                self.canvas.dnd_bind('<<Drop>>', self._on_drop)
            except Exception:
                pass
        # Hover cursor for draggable items
        self.canvas.tag_bind('draggable', '<Enter>', self._cursor_fleur)
        self.canvas.tag_bind('draggable', '<Leave>', self._cursor_arrow)

        self.overlays: dict[int, dict] = {}
        self.image_id: int | None = None
        self.tk_img = None
        self._alpha_imgs = []  # keep RGBA overlays alive

        self._drag_item: int | None = None
        self._drag_dx = 0
        self._drag_dy = 0
        self._drag_sub = None  # 'a' | 'b' | 'center' | None
    # ---------- interactive objects API ----------
    def activate_from_code(self, code: str, kind: str):
        """Create or activate object by code (e.g., '1.1', '2.1')."""
        print(f"[label_maker][dbg] activate_from_code(code={code}, kind={kind}) has _ensure_ray13? {hasattr(self, '_ensure_ray13')}")
        if code in ("1.1", "2.1"):
            self._ensure_start_line(code)
            return
        if code in ("1.2","1.6") and kind == 'short':
            self._ensure_fixprefix(left_code='1.2', right_code='1.6', activate_code=code)
            return
        if code in ("2.2","2.6") and kind == 'long':
            self._ensure_fixprefix(left_code='2.2', right_code='2.6', activate_code=code)
            return
        if code == "1.3" and kind == 'short':
            handler = getattr(self, "_ensure_ray13", None)
            if callable(handler):
                handler(code)
            else:
                # inline fallback: create horizontal ray with two handles and label
                cw = int(self.canvas.winfo_width() or 520)
                ch = int(self.canvas.winfo_height() or 360)
                cx, cy = cw // 2, ch // 2
                x1, y1 = cx - cw // 6, cy     # anchor (left)
                x2, y2 = cx + cw // 6, cy     # tail (right)
                line = self.canvas.create_line(x1, y1, x2, y2, width=1, fill=ACCENT)
                # handles
                r = 5
                h_anchor = self.canvas.create_oval(x1 - r, y1 - r, x1 + r, y1 + r, fill=ACCENT, outline='')
                s = 5
                h_tail = self.canvas.create_rectangle(x2 - s, y2 - s, x2 + s, y2 + s, fill=ACCENT, outline='')
                # label
                mx, my = (x1 + x2) / 2.0, y1 - 10
                label = self.canvas.create_text(mx, my, text='[1.3]', fill=TEXT_MUTED, font=("Helvetica Neue", 9, 'bold'))
                # tags
                for it in (line, h_anchor, h_tail, label):
                    self.canvas.addtag_withtag('overlay', it)
                    self.canvas.addtag_withtag('draggable', it)
                # meta
                self.overlays[line] = {
                    'kind': 'ray13',
                    'code': code,
                    'value': '',
                    'date': '',
                    'handle_anchor': h_anchor,
                    'handle_tail': h_tail,
                    'label_id': label,
                }
                self._bring_to_front(line)
                self._drag_item = line
            return
        if (code == "1.4" and kind == 'short') or (code == "2.4" and kind == 'long'):
                self._ensure_hmark(code)
                return
    def _create_shaded_rect(self, x0, y0, x1, y1, color=PURPLE):
        if PIL_OK:
            img_id, _ = self._create_alpha_rect(x0, y0, x1, y1, color=color, alpha=110)
            return img_id, 'image'
        rid = self.canvas.create_rectangle(x0, y0, x1, y1, outline='', fill=color, stipple='gray25')
        try:
            self.canvas.addtag_withtag('overlay', rid)
            self.canvas.addtag_withtag('draggable', rid)
        except Exception:
            pass
        return rid, 'stipple'
        # other codes will be implemented in next iterations
    def _ensure_fixprefix(self, left_code: str, right_code: str, activate_code: str):
        # look for existing
        for rid, meta in self.overlays.items():
            if meta.get('kind') == 'fixprefix':
                self._bring_to_front(rid)
                self._drag_item = rid
                return
        # create new centered rect (40% width, 25% height of canvas)
        cw = int(self.canvas.winfo_width() or 520)
        ch = int(self.canvas.winfo_height() or 360)
        w = max(80, int(cw * 0.40)); h = max(60, int(ch * 0.25))
        cx, cy = cw // 2, ch // 2
        x0, y0, x1, y1 = cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2
        # заливка stipple (масштабируется), плюс контур
        shade_id, shade_kind = self._create_shaded_rect(x0, y0, x1, y1, color=PURPLE)
        rect = self.canvas.create_rectangle(x0, y0, x1, y1, outline=PURPLE, width=1)
        # держим заливку под контуром
        self.canvas.tag_lower(shade_id, rect)
        # corner handles
        s = 4
        lt = self.canvas.create_rectangle(x0 - s, y0 - s, x0 + s, y0 + s, fill=PURPLE, outline='')
        rt = self.canvas.create_rectangle(x1 - s, y0 - s, x1 + s, y0 + s, fill=PURPLE, outline='')
        lb = self.canvas.create_rectangle(x0 - s, y1 - s, x0 + s, y1 + s, fill=PURPLE, outline='')
        rb = self.canvas.create_rectangle(x1 - s, y1 - s, x1 + s, y1 + s, fill=PURPLE, outline='')
        # label top-center
        label = self.canvas.create_text(cx, y0 - 10, text=f"[{left_code}↔{right_code}]", fill=PURPLE, font=("Helvetica Neue", 9, 'bold'))
        # tag items
        for it in (rect, lt, rt, lb, rb, label):
            if it:
                self.canvas.addtag_withtag('overlay', it)
                self.canvas.addtag_withtag('draggable', it)

        # register overlay meta ONCE
        self.overlays[rect] = {
            'kind': 'fixprefix',
            'code_left': left_code,
            'code_right': right_code,
            'value_left': '',
            'value_right': '',
            'handle_lt': lt,
            'handle_rt': rt,
            'handle_lb': lb,
            'handle_rb': rb,
            'label_id': label,
            'shade_id': shade_id,
            'shade_kind': shade_kind,
        }
        # ensure z-order (image bottom, shade under outline, handles/label on top)
        if getattr(self, 'image_id', None):
            try:
                self.canvas.tag_lower(self.image_id)
            except Exception:
                pass
        # Keep shaded fill **under** outline, but make sure outline is above the image
        if isinstance(shade_id, int):
            try:
                # already lowered under the outline, ensure order just in case
                self.canvas.tag_lower(shade_id, rect)
            except Exception:
                pass
        # raise outline itself; handles/label will be raised below
        self.canvas.tag_raise(rect)
        # then handles and label above everything for easy grabbing
        for it in (lt, rt, lb, rb, label):
            self.canvas.tag_raise(it)
        self._drag_item = rect

    # ---------- helpers for semi-transparent rectangles over image ----------
    def _hex_to_rgb(self, hex_color: str):
        hc = hex_color.lstrip('#')
        return tuple(int(hc[i:i+2], 16) for i in (0, 2, 4))

    def _create_alpha_rect(self, x0: float, y0: float, x1: float, y1: float, color: str = PURPLE, alpha: int = 96):
        """Create a semi-transparent rectangle as an image on the canvas (over the chart image).
        Returns (img_id, tk_image). Requires Pillow.
        """
        if not PIL_OK:
            return None, None
        # normalize coords
        x0, y0, x1, y1 = float(x0), float(y0), float(x1), float(y1)
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0
        w = max(1, int(x1 - x0))
        h = max(1, int(y1 - y0))
        rgba = (*self._hex_to_rgb(color), max(0, min(255, alpha)))
        img = Image.new('RGBA', (w, h), rgba)
        tkimg = ImageTk.PhotoImage(img)
        img_id = self.canvas.create_image(x0, y0, anchor='nw', image=tkimg)
        # keep a reference so it is not garbage-collected
        self._alpha_imgs.append(tkimg)
        try:
            self.canvas.addtag_withtag('overlay', img_id)
            self.canvas.addtag_withtag('draggable', img_id)
        except Exception:
            pass
        return img_id, tkimg

    def _ensure_start_line(self, code: str):
        # reuse if exists: store by a fixed key 'start'
        # find existing
        for main_id, meta in self.overlays.items():
            if meta.get('kind') == 'start':
                # make it active (bring to front visually)
                self._bring_to_front(main_id)
                self._drag_item = main_id
                return
        # create new in center with default size
        cw = int(self.canvas.winfo_width() or 520)
        ch = int(self.canvas.winfo_height() or 360)
        cx, cy = cw//2, ch//2
        dx = cw/3.0/2.0
        dy = ch/5.0/2.0
        x1, y1 = cx - dx, cy + dy  # left-down
        x2, y2 = cx + dx, cy - dy  # right-up
        # width=2 вместо 3
        line = self.canvas.create_line(x1, y1, x2, y2, width=2, fill=ACCENT)
        # end handles (a = left/down, b = right/up)
        r = 6
        ha = self.canvas.create_oval(x1-r, y1-r, x1+r, y1+r, fill=ACCENT, outline='')
        hb = self.canvas.create_oval(x2-r, y2-r, x2+r, y2+r, fill=ACCENT, outline='')
        # center handle (small square at midpoint)
        mx, my = (x1+x2)/2.0, (y1+y2)/2.0
        s = 6
        hc = self.canvas.create_rectangle(mx-s, my-s, mx+s, my+s, outline='', fill=ACCENT)
        # tags for scaling and drag cursor
        for it in (line, ha, hb, hc):
            self.canvas.addtag_withtag('overlay', it)
            self.canvas.addtag_withtag('draggable', it)
        self.overlays[line] = {
            'kind': 'start',
            'code': code,
            'handle_a': ha,
            'handle_b': hb,
            'center_id': hc,
        }
        self._bring_to_front(line)
        self._drag_item = line

    def _ensure_ray13(self, code: str):
        """Horizontal ray (LOY‑FIX) from left to right with two handles."""
        # Reuse existing if present
        for main_id, meta in self.overlays.items():
            if meta.get('kind') == 'ray13':
                self._bring_to_front(main_id)
                self._drag_item = main_id
                return
        cw = int(self.canvas.winfo_width() or 520)
        ch = int(self.canvas.winfo_height() or 360)
        cx, cy = cw // 2, ch // 2
        x1, y1 = cx - cw // 6, cy     # anchor (left)
        x2, y2 = cx + cw // 6, cy     # tail (right)
        line = self.canvas.create_line(x1, y1, x2, y2, width=1, fill=ACCENT)
        # handles
        r = 5
        h_anchor = self.canvas.create_oval(x1 - r, y1 - r, x1 + r, y1 + r, fill=ACCENT, outline='')
        s = 5
        h_tail = self.canvas.create_rectangle(x2 - s, y2 - s, x2 + s, y2 + s, fill=ACCENT, outline='')
        # label
        mx, my = (x1 + x2) / 2.0, y1 - 10
        label = self.canvas.create_text(mx, my, text='[1.3]', fill=TEXT_MUTED, font=("Helvetica Neue", 9, 'bold'))
        # tags
        for it in (line, h_anchor, h_tail, label):
            self.canvas.addtag_withtag('overlay', it)
            self.canvas.addtag_withtag('draggable', it)
        # meta
        self.overlays[line] = {
            'kind': 'ray13',
            'code': code,
            'value': '',
            'date': '',
            'handle_anchor': h_anchor,
            'handle_tail': h_tail,
            'label_id': label,
        }
        self._bring_to_front(line)
        self._drag_item = line

    def ensure_ray13(self, code: str):
        """Alias for compatibility."""
        return self._ensure_ray13(code)

    def _ensure_hmark(self, code: str):
        """Short independent horizontal marker (1.4 HIGHPATTERN / 2.4 LOWPATTERN)."""
        # Reuse existing by code
        for main_id, meta in self.overlays.items():
            if meta.get('kind') == 'hmark' and (meta.get('code') == code):
                self._bring_to_front(main_id)
                self._drag_item = main_id
                return
        cw = int(self.canvas.winfo_width() or 520)
        ch = int(self.canvas.winfo_height() or 360)
        cx, cy = cw // 2, ch // 2
        length = max(60, cw // 8)
        x1, y1 = cx - length//2, cy
        x2, y2 = cx + length//2, cy
        line = self.canvas.create_line(x1, y1, x2, y2, width=1, fill=LINE_COLOR)
        # two square handles
        s = 4
        ha = self.canvas.create_rectangle(x1 - s, y1 - s, x1 + s, y1 + s, fill=ACCENT, outline='')
        hb = self.canvas.create_rectangle(x2 - s, y2 - s, x2 + s, y2 + s, fill=ACCENT, outline='')
        # label above center
        mx, my = (x1 + x2) / 2.0, y1 - 12
        label = self.canvas.create_text(mx, my, text=f"[{code}]", fill=TEXT_MUTED, font=("Helvetica Neue", 9, 'bold'))
        for it in (line, ha, hb, label):
            self.canvas.addtag_withtag('overlay', it)
            self.canvas.addtag_withtag('draggable', it)
        self.overlays[line] = {
            'kind': 'hmark',
            'code': code,
            'value': '',
            'handle_a': ha,
            'handle_b': hb,
            'label_id': label,
        }
        self._bring_to_front(line)
        self._drag_item = line

    def _bring_to_front(self, main_id: int):
        meta = self.overlays.get(main_id)
        if not meta:
            return
        # raise main item
        self.canvas.tag_raise(main_id)
        # keep shade (if any) just below the main outline
        sid = meta.get('shade_id')
        if sid:
            try:
                self.canvas.tag_lower(sid, main_id)
            except Exception:
                pass
        # raise handles/labels above
        for k in ('center_id','handle_a','handle_b','label_id',
                  'handle_lt','handle_rt','handle_lb','handle_rb',
                  'handle_anchor','handle_tail'):
            if meta.get(k):
                try:
                    self.canvas.tag_raise(meta[k])
                except Exception:
                    pass
        # Always ensure image stays below overlays for interactivity
        if getattr(self, 'image_id', None):
            try:
                self.canvas.tag_lower(self.image_id)
            except Exception:
                pass

    # ---------- image loader / zoom & pan ----------
    def _set_image_from_path(self, path: str):
        """Load image via Pillow (preferred) and reset canvas with current scale/position preserved.
        If Pillow not available, try tk.PhotoImage for PNG; otherwise show a messagebox error.
        """
        from tkinter import messagebox
        # Normalize path (support file:// URL, ~ expansion) and verify existence
        try:
            p_in = (path or '').strip()
            # handle file:// URL
            if p_in.startswith('file://'):
                try:
                    from urllib.parse import urlparse, unquote
                    p_in = unquote(urlparse(p_in).path)
                except Exception:
                    pass
            p_in = os.path.expanduser(p_in)
            if not os.path.isfile(p_in):
                messagebox.showerror("Загрузка изображения", f"Файл не найден:\n{path}")
                return
            path = p_in
        except Exception:
            pass
        self.canvas.delete('all')
        self.overlays.clear()
        self._scale = 1.0
        self._min_scale = 0.2
        self._max_scale = 5.0
        self._pan_last = None  # (x,y) during pan
        self._img_w = None
        self._img_h = None

        self._pil_img = None
        self.tk_img = None
        try:
            if PIL_OK:
                img = Image.open(path)
                self._pil_img = img.convert('RGBA') if img.mode in ('P','LA') else img
                self._img_w, self._img_h = self._pil_img.size
                # initial fit into canvas
                cw = max(1, int(self.canvas.winfo_width() or 520))
                ch = max(1, int(self.canvas.winfo_height() or 360))
                k = min(cw / self._img_w, ch / self._img_h, 1.0)
                self._scale = max(k, 0.2)
                disp = self._pil_img.resize((int(self._img_w*self._scale), int(self._img_h*self._scale)), Image.LANCZOS)
                self.tk_img = ImageTk.PhotoImage(disp)
                self.image_id = self.canvas.create_image(0, 0, anchor='nw', image=self.tk_img)
                self.canvas.tag_lower(self.image_id)
            else:
                # Fallback: try tk.PhotoImage (best for PNG)
                try:
                    self.tk_img = tk.PhotoImage(file=path)
                    self._img_w = self.tk_img.width(); self._img_h = self.tk_img.height()
                    self._scale = 1.0
                    self.image_id = self.canvas.create_image(0, 0, anchor='nw', image=self.tk_img)
                    self.canvas.tag_lower(self.image_id)
                except Exception as e:
                    messagebox.showerror("Загрузка изображения", f"Не удалось открыть файл:\n{path}\n\n{e}")
                    self.image_id = None
                    return
        except Exception as e:
            messagebox.showerror("Загрузка изображения", f"Ошибка чтения изображения:\n{path}\n\n{e}")
            self.image_id = None
            return
        # Ensure image is behind overlays (safe no-op if already lowest)
        if getattr(self, 'image_id', None):
            try:
                self.canvas.tag_lower(self.image_id)
            except Exception:
                pass
        # update scrollregion
        bbox = self.canvas.bbox('all')
        if bbox:
            self.canvas.configure(scrollregion=bbox)

    def _update_image_zoom(self, factor: float, pivot_x: int, pivot_y: int):
        """Zoom around (pivot_x, pivot_y). Scales overlays via canvas.scale and resizes the raster image via Pillow."""
        # clamp
        new_scale = max(self._min_scale, min(self._max_scale, self._scale * factor))
        if abs(new_scale - self._scale) < 1e-6 or self._pil_img is None:
            return
        # resize raster
        self._scale = new_scale
        nw = max(1, int(self._img_w * self._scale))
        nh = max(1, int(self._img_h * self._scale))
        disp = self._pil_img.resize((nw, nh), Image.LANCZOS)
        self.tk_img = ImageTk.PhotoImage(disp)
        self.canvas.itemconfigure(self.image_id, image=self.tk_img)
        # move image top-left to keep pivot stable
        ix, iy = self.canvas.coords(self.image_id)
        # previous factor already applied to overlays below; for image, recompute position
        # After zoom, desired top-left so that vector (pivot - top-left) scales by 'factor'
        # We approximate using factor passed in
        dx = pivot_x - (pivot_x - ix) * factor - ix
        dy = pivot_y - (pivot_y - iy) * factor - iy
        self.canvas.move(self.image_id, dx, dy)
        # scale overlays (all except image)
        self.canvas.scale('overlay', pivot_x, pivot_y, factor, factor)
        # Recreate RGBA shades (if any) so their raster matches the new scale
        try:
            for main_id, meta in list(self.overlays.items()):
                if meta.get('kind') == 'fixprefix' and meta.get('shade_kind') == 'image' and PIL_OK:
                    # get current geometry of the outline rect after scaling
                    coords = self.canvas.coords(main_id)
                    if not coords or len(coords) < 4:
                        continue
                    x0, y0, x1, y1 = coords[:4]
                    old_sid = meta.get('shade_id')
                    if old_sid:
                        try:
                            self.canvas.delete(old_sid)
                        except Exception:
                            pass
                    new_sid, _ = self._create_alpha_rect(x0, y0, x1, y1, color=PURPLE, alpha=110)
                    meta['shade_id'] = new_sid
                    # keep shade just below the outline
                    try:
                        self.canvas.tag_lower(new_sid, main_id)
                    except Exception:
                        pass
        except Exception:
            pass
        # also move any text/lines not tagged yet by ensuring we tag overlays when creating
        # update scrollregion
        bbox = self.canvas.bbox('all')
        if bbox:
            self.canvas.configure(scrollregion=bbox)

    def _pan_start(self, e):
        self._pan_last = (e.x, e.y)

    def _on_pan(self, e):
        if not self._pan_last:
            return
        dx = e.x - self._pan_last[0]
        dy = e.y - self._pan_last[1]
        self._pan_last = (e.x, e.y)
        self.canvas.move('all', dx, dy)

    def _on_zoom(self, e):
        # Mouse wheel: positive up (zoom in) on Windows/macOS, on X11 use Button-4/5
        if hasattr(e, 'delta') and e.delta != 0:
            factor = 1.1 if e.delta > 0 else 0.9
        else:
            # Button-4/5 case
            factor = 1.1 if getattr(e, 'num', 0) == 4 else 0.9
        self._update_image_zoom(factor, e.x, e.y)

    def _load_image(self):
        patterns = ("*.png", "*.PNG", "*.jpg", "*.JPG", "*.jpeg", "*.JPEG", "*.webp", "*.WEBP", "*.bmp", "*.BMP")
        p = filedialog.askopenfilename(
            title="Выберите картинку",
            filetypes=[("Images", patterns), ("All", ("*",))],
            defaultextension=".png"
        )
        if not p:
            return
        self._set_image_from_path(p)

    def _on_drop(self, event):
        raw = (getattr(event, 'data', '') or '').strip()
        if not raw:
            return
        # tkinterdnd2 may pass: "{path with spaces} {second}" or plain path or file:// URL
        # Take the first item only.
        p = None
        try:
            if raw.startswith('file://'):
                p = raw.splitlines()[0]
            elif raw.startswith('{'):
                # extract first braced token
                # e.g. { /path with spaces } { /second }
                # find the first closing brace
                end = raw.find('}')
                if end != -1:
                    p = raw[1:end].strip()
            else:
                # plain string; may contain spaces but there is only one path in most cases
                p = raw.splitlines()[0]
        except Exception:
            p = raw
        if not p:
            return
        self._set_image_from_path(p)

    # ---------- overlays ----------
    def _cursor_fleur(self, _e=None):
        try:
            self.canvas.configure(cursor='fleur')
        except Exception:
            pass

    def _cursor_arrow(self, _e=None):
        try:
            self.canvas.configure(cursor='')
        except Exception:
            pass

    def _add_hline(self):
        y = 120
        w = int(self.canvas.winfo_width() or 520)
        line = self.canvas.create_line(20, y, w-20, y, width=1, fill=LINE_COLOR)
        label = self.canvas.create_text(30, y-12, anchor='w', text="[цена] code: —", fill=TEXT_MUTED, font=("Helvetica", 9, "bold"))
        # handle (small circle) at the left edge
        hx, hy, r = 20, y, 2
        handle = self.canvas.create_oval(hx-r, hy-r, hx+r, hy+r, fill=ACCENT, outline='')
        # tags for scaling and drag cursor
        for it in (line, label, handle):
            self.canvas.addtag_withtag('overlay', it)
            self.canvas.addtag_withtag('draggable', it)
        self.overlays[line] = {"kind":"hline", "code":"", "value":"", "label_id": label, "handle_id": handle}
        # Ensure overlays are above image
        self._bring_to_front(line)

    def _add_vline(self):
        x = 200
        h = int(self.canvas.winfo_height() or 360)
        line = self.canvas.create_line(x, 20, x, h-20, width=1, fill=LINE_COLOR)
        label = self.canvas.create_text(x+8, 28, anchor='nw', text="[дата] code: —", fill=TEXT_MUTED, font=("Helvetica", 9, "bold"))
        hx, hy, r = x, 20, 2
        handle = self.canvas.create_oval(hx-r, hy-r, hx+r, hy+r, fill=ACCENT, outline='')
        for it in (line, label, handle):
            self.canvas.addtag_withtag('overlay', it)
            self.canvas.addtag_withtag('draggable', it)
        self.overlays[line] = {"kind":"vline", "code":"", "value":"", "label_id": label, "handle_id": handle}
        # Ensure overlays are above image
        self._bring_to_front(line)

    def _hit_test(self, x, y):
        """Robust hit-test: prefer handles, then main rect interior, then shade/labels/other lines."""
        # enlarge probe box to make handles easier to grab
        items = self.canvas.find_overlapping(x-10, y-10, x+10, y+10)

        # 0) fixprefix: proximity to corners (robust even if handle items are hard to hit)
        for main_id, meta in self.overlays.items():
            if meta.get('kind') != 'fixprefix':
                continue
            try:
                cx0, cy0, cx1, cy1 = self.canvas.coords(main_id)
                if cx0 > cx1:
                    cx0, cx1 = cx1, cx0
                if cy0 > cy1:
                    cy0, cy1 = cy1, cy0
                TH = 10  # px proximity threshold
                if abs(x - cx0) <= TH and abs(y - cy0) <= TH:
                    self._drag_sub = 'lt'
                    return main_id
                if abs(x - cx1) <= TH and abs(y - cy0) <= TH:
                    self._drag_sub = 'rt'
                    return main_id
                if abs(x - cx0) <= TH and abs(y - cy1) <= TH:
                    self._drag_sub = 'lb'
                    return main_id
                if abs(x - cx1) <= TH and abs(y - cy1) <= TH:
                    self._drag_sub = 'rb'
                    return main_id
            except Exception:
                pass

        # 1) start-line handles first
        for main_id, meta in self.overlays.items():
            ha = meta.get('handle_a'); hb = meta.get('handle_b'); hc = meta.get('center_id')
            if ha in items:
                self._drag_sub = 'a';  return main_id
            if hb in items:
                self._drag_sub = 'b';  return main_id
            if hc in items:
                self._drag_sub = 'center';  return main_id
        
        # 1b) ray13 handles then line
        for main_id, meta in self.overlays.items():
            if meta.get('kind') != 'ray13':
                continue
            ha = meta.get('handle_anchor'); ht = meta.get('handle_tail')
            if ha in items:
                self._drag_sub = 'anchor'; return main_id
            if ht in items:
                self._drag_sub = 'tail'; return main_id
            if main_id in items:
                self._drag_sub = 'line'; return main_id

        # 2) fixprefix: corner handles take priority
        for main_id, meta in self.overlays.items():
            if meta.get('kind') != 'fixprefix':
                continue
            for tag, sub in ((meta.get('handle_lt'),'lt'), (meta.get('handle_rt'),'rt'), (meta.get('handle_lb'),'lb'), (meta.get('handle_rb'),'rb')):
                if tag in items:
                    self._drag_sub = sub
                    return main_id

        # 3) fixprefix: click inside main rectangle interior (independent of Canvas returns)
        for main_id, meta in self.overlays.items():
            if meta.get('kind') != 'fixprefix':
                continue
            try:
                x0, y0, x1, y1 = self.canvas.coords(main_id)
                if x0 > x1: x0, x1 = x1, x0
                if y0 > y1: y0, y1 = y1, y0
                if (x0 <= x <= x1) and (y0 <= y <= y1):
                    self._drag_sub = 'line'
                    return main_id
            except Exception:
                pass

        # 4) fallback: shade area selects the rect as well
        for main_id, meta in self.overlays.items():
            if meta.get('kind') == 'fixprefix':
                sid = meta.get('shade_id')
                if sid in items:
                    self._drag_sub = 'line'
                    return main_id

        # 5) direct line ids next
        for it in items:
            if it in self.overlays:
                self._drag_sub = 'line'
                return it

        # 6) labels can also select their owners
        for main_id, meta in self.overlays.items():
            if meta.get('label_id') in items:
                self._drag_sub = 'line'
                return main_id

        self._drag_sub = None
        return None

    def _on_down(self, e):
        self._drag_sub = None
        it = self._hit_test(e.x, e.y)
        if it:
            self._drag_item = it
            self._drag_dx = e.x
            self._drag_dy = e.y
            self.canvas.focus_set()
        else:
            self._drag_item = None
    def _on_delete(self, _e=None):
        """Удаляет активный объект (если выбран) вместе с его ручками/лейблами/заливкой."""
        it = self._drag_item
        if not it:
            return
        meta = self.overlays.pop(it, None)
        if not meta:
            self._drag_item = None
            return

        def _safe_del(item_id):
            if item_id:
                try:
                    self.canvas.delete(item_id)
                except Exception:
                    pass

        kind = meta.get('kind')
        if kind in ('hline', 'vline'):
            _safe_del(it)
            _safe_del(meta.get('label_id'))
            _safe_del(meta.get('handle_id'))
        elif kind == 'start':
            _safe_del(it)
            _safe_del(meta.get('handle_a'))
            _safe_del(meta.get('handle_b'))
            _safe_del(meta.get('center_id'))
        elif kind == 'fixprefix':
            _safe_del(it)
            _safe_del(meta.get('handle_lt'))
            _safe_del(meta.get('handle_rt'))
            _safe_del(meta.get('handle_lb'))
            _safe_del(meta.get('handle_rb'))
            _safe_del(meta.get('label_id'))
            _safe_del(meta.get('shade_id'))
        else:
            _safe_del(it)
            _safe_del(meta.get('label_id'))
            _safe_del(meta.get('handle_id'))

        self._drag_item = None

    def _on_move(self, e):
        if not self._drag_item:
            return
        it = self._drag_item
        meta = self.overlays.get(it)
        if not meta:
            return
        dx = e.x - self._drag_dx
        dy = e.y - self._drag_dy
        self._drag_dx = e.x
        self._drag_dy = e.y
        if meta["kind"] == 'hline':
            self.canvas.move(it, 0, dy)
            self.canvas.move(meta["label_id"], 0, dy)
            self.canvas.move(meta["handle_id"], 0, dy)
        elif meta["kind"] == 'start':
            # move/resize depending on grabbed sub-part
            x1, y1, x2, y2 = self.canvas.coords(it)
            if self._drag_sub == 'a':
                # Move only endpoint A (x1, y1)
                x1 += dx
                y1 += dy
            elif self._drag_sub == 'b':
                # Move only endpoint B (x2, y2)
                x2 += dx
                y2 += dy
            else:  # center or line -> move whole
                x1 += dx; y1 += dy; x2 += dx; y2 += dy
            self.canvas.coords(it, x1, y1, x2, y2)
            # move handles to endpoints / midpoint
            ha = meta.get('handle_a'); hb = meta.get('handle_b'); hc = meta.get('center_id')
            r = 6; s = 6
            if ha:
                self.canvas.coords(ha, x1-r, y1-r, x1+r, y1+r)
            if hb:
                self.canvas.coords(hb, x2-r, y2-r, x2+r, y2+r)
            if hc:
                mx, my = (x1+x2)/2.0, (y1+y2)/2.0
                self.canvas.coords(hc, mx-s, my-s, mx+s, my+s)
        elif meta["kind"] == 'fixprefix':
            x0, y0, x1, y1 = self.canvas.coords(it)
            if self._drag_sub == 'lt':
                x0, y0 = e.x, e.y
            elif self._drag_sub == 'rt':
                x1, y0 = e.x, e.y
            elif self._drag_sub == 'lb':
                x0, y1 = e.x, e.y
            elif self._drag_sub == 'rb':
                x1, y1 = e.x, e.y
            else:  # drag whole rect
                x0 += dx; y0 += dy; x1 += dx; y1 += dy
            # normalize to keep x0<x1,y0<y1
            if x0 > x1: x0, x1 = x1, x0
            if y0 > y1: y0, y1 = y1, y0
            self.canvas.coords(it, x0, y0, x1, y1)
            s = 4
            self.canvas.coords(meta['handle_lt'], x0-s, y0-s, x0+s, y0+s)
            self.canvas.coords(meta['handle_rt'], x1-s, y0-s, x1+s, y0+s)
            self.canvas.coords(meta['handle_lb'], x0-s, y1-s, x0+s, y1+s)
            self.canvas.coords(meta['handle_rb'], x1-s, y1-s, x1+s, y1+s)
            # move label to top-center
            self.canvas.coords(meta['label_id'], (x0+x1)/2.0, y0-10)
            # move/resize shaded rect (stipple) or recreate RGBA image
            shade_id = meta.get('shade_id')
            if shade_id:
                if meta.get('shade_kind') == 'image':
                    # Pillow image cannot be resized via coords — recreate with new size
                    try:
                        self.canvas.delete(shade_id)
                    except Exception:
                        pass
                    new_id, _ = self._create_alpha_rect(x0, y0, x1, y1, color=PURPLE, alpha=110)
                    meta['shade_id'] = new_id
                    # keep shade below the outline rectangle
                    try:
                        self.canvas.tag_lower(new_id, it)
                    except Exception:
                        pass
                else:
                    # stipple rectangle can be resized with coords
                    self.canvas.coords(shade_id, x0, y0, x1, y1)
            # keep z-order
            if getattr(self, 'image_id', None):
                try:
                    self.canvas.tag_lower(self.image_id)
                except Exception:
                    pass
            self.canvas.tag_raise(it)
            self.canvas.tag_raise(meta['handle_lt']); self.canvas.tag_raise(meta['handle_rt'])
            self.canvas.tag_raise(meta['handle_lb']); self.canvas.tag_raise(meta['handle_rb'])
            self.canvas.tag_raise(meta['label_id'])
        elif meta["kind"] == 'ray13':
            x1, y1, x2, y2 = self.canvas.coords(it)
            if self._drag_sub == 'anchor':
                x1 += dx; y1 += dy
            elif self._drag_sub == 'tail':
                x2 += dx; y2 = y2 + dy
            else:
                x1 += dx; y1 += dy; x2 += dx; y2 += dy
            y2 = y1  # keep horizontal
            self.canvas.coords(it, x1, y1, x2, y2)
            r = 5; s = 5
            self.canvas.coords(meta['handle_anchor'], x1 - r, y1 - r, x1 + r, y1 + r)
            self.canvas.coords(meta['handle_tail'],   x2 - s, y2 - s, x2 + s, y2 + s)
            self.canvas.coords(meta['label_id'], (x1 + x2) / 2.0, y1 - 10)
            self._bring_to_front(it)
        elif meta["kind"] == 'hmark':
            x1, y1, x2, y2 = self.canvas.coords(it)
            if self._drag_sub == 'a':
                x1 += dx; y1 += dy
            elif self._drag_sub == 'b':
                x2 += dx; y2 += dy
            else:
                x1 += dx; y1 += dy; x2 += dx; y2 += dy
            # keep horizontal
            y2 = y1
            self.canvas.coords(it, x1, y1, x2, y2)
            s = 4
            self.canvas.coords(meta['handle_a'], x1 - s, y1 - s, x1 + s, y1 + s)
            self.canvas.coords(meta['handle_b'], x2 - s, y2 - s, x2 + s, y2 + s)
            self.canvas.coords(meta['label_id'], (x1 + x2) / 2.0, y1 - 12)
            self._bring_to_front(it)
        else:
            self.canvas.move(it, dx, 0)
            self.canvas.move(meta["label_id"], dx, 0)
            self.canvas.move(meta["handle_id"], dx, 0)

    def _on_up(self, e):
        self._drag_item = None

    def _on_edit(self, e):
        it = self._hit_test(e.x, e.y)
        if not it:
            return
        meta = self.overlays.get(it)
        if not meta:
            return
        if meta['kind'] == 'fixprefix':
            popup = tk.Toplevel(self)
            popup.title("ФИКС–ПРЕФИКС")
            ttk.Label(popup, text="Код слева (ФИКС)").grid(row=0, column=0, sticky='w', padx=6, pady=4)
            v_lc = tk.StringVar(value=meta.get('code_left',''))
            e_lc = ttk.Entry(popup, textvariable=v_lc, width=10)
            e_lc.grid(row=0, column=1, padx=6, pady=4)
            ttk.Label(popup, text="Цена слева").grid(row=0, column=2, sticky='w', padx=6, pady=4)
            v_lv = tk.StringVar(value=meta.get('value_left',''))
            e_lv = ttk.Entry(popup, textvariable=v_lv, width=12)
            e_lv.grid(row=0, column=3, padx=6, pady=4)

            ttk.Label(popup, text="Код справа (ПРЕФИКС)").grid(row=1, column=0, sticky='w', padx=6, pady=4)
            v_rc = tk.StringVar(value=meta.get('code_right',''))
            e_rc = ttk.Entry(popup, textvariable=v_rc, width=10)
            e_rc.grid(row=1, column=1, padx=6, pady=4)
            ttk.Label(popup, text="Цена справа").grid(row=1, column=2, sticky='w', padx=6, pady=4)
            v_rv = tk.StringVar(value=meta.get('value_right',''))
            e_rv = ttk.Entry(popup, textvariable=v_rv, width=12)
            e_rv.grid(row=1, column=3, padx=6, pady=4)

            def ok_fp():
                meta['code_left'] = v_lc.get().strip()
                meta['code_right'] = v_rc.get().strip()
                meta['value_left'] = v_lv.get().strip()
                meta['value_right'] = v_rv.get().strip()
                self.canvas.itemconfigure(meta['label_id'], text=f"[{meta['code_left']}↔{meta['code_right']}]")
                popup.destroy()
            ttk.Button(popup, text="Ок", command=ok_fp).grid(row=2, column=0, columnspan=4, pady=6)
            popup.transient(self); popup.grab_set(); e_lc.focus_set()
            return
        if meta['kind'] == 'ray13':
            popup = tk.Toplevel(self)
            popup.title("ЛОЙ‑ФИКС [1.3]")
            ttk.Label(popup, text="Код (по умолч. 1.3)").grid(row=0, column=0, sticky='w', padx=6, pady=4)
            v_code = tk.StringVar(value=meta.get('code','1.3'))
            e_code = ttk.Entry(popup, textvariable=v_code, width=10)
            e_code.grid(row=0, column=1, padx=6, pady=4)

            ttk.Label(popup, text="Цена").grid(row=1, column=0, sticky='w', padx=6, pady=4)
            v_val = tk.StringVar(value=meta.get('value',''))
            e_val = ttk.Entry(popup, textvariable=v_val, width=14)
            e_val.grid(row=1, column=1, padx=6, pady=4)

            ttk.Label(popup, text="Дата (DD.MM)").grid(row=2, column=0, sticky='w', padx=6, pady=4)
            v_dt = tk.StringVar(value=meta.get('date',''))
            e_dt = ttk.Entry(popup, textvariable=v_dt, width=14)
            e_dt.grid(row=2, column=1, padx=6, pady=4)

            def ok_ray():
                meta['code'] = v_code.get().strip() or '1.3'
                meta['value'] = v_val.get().strip()
                meta['date'] = v_dt.get().strip()
                self.canvas.itemconfigure(meta['label_id'], text=f"[{meta['code']}] {meta['value']} {meta['date']}")
                popup.destroy()

            ttk.Button(popup, text="Ок", command=ok_ray).grid(row=3, column=0, columnspan=2, pady=6)
            popup.transient(self); popup.grab_set(); e_code.focus_set()
            return
        if meta['kind'] == 'hmark':
            popup = tk.Toplevel(self)
            popup.title("ГОРИЗОНТАЛЬ (1.4/2.4)")
            ttk.Label(popup, text="Код (1.4 или 2.4)").grid(row=0, column=0, sticky='w', padx=6, pady=4)
            v_code = tk.StringVar(value=meta.get('code',''))
            e_code = ttk.Entry(popup, textvariable=v_code, width=10)
            e_code.grid(row=0, column=1, padx=6, pady=4)
            ttk.Label(popup, text="Цена").grid(row=1, column=0, sticky='w', padx=6, pady=4)
            v_val = tk.StringVar(value=meta.get('value',''))
            e_val = ttk.Entry(popup, textvariable=v_val, width=14)
            e_val.grid(row=1, column=1, padx=6, pady=4)
            def ok_hm():
                meta['code'] = v_code.get().strip() or meta.get('code','')
                meta['value'] = v_val.get().strip()
                self.canvas.itemconfigure(meta['label_id'], text=f"[{meta['code']}] {meta['value']}")
                popup.destroy()
            ttk.Button(popup, text="Ок", command=ok_hm).grid(row=2, column=0, columnspan=2, pady=6)
            popup.transient(self); popup.grab_set(); e_code.focus_set()
            return
        popup = tk.Toplevel(self)
        popup.title("Правка")
        ttk.Label(popup, text=("Код точки (напр.: 1.2, 1.6, 2.7)" if meta['kind']=='hline' else "Код точки для даты")).grid(row=0,column=0,sticky='w', padx=6, pady=4)
        var_code = tk.StringVar(value=meta.get('code',''))
        ent_code = ttk.Entry(popup, textvariable=var_code, width=12)
        ent_code.grid(row=0, column=1, padx=6, pady=4)
        if meta['kind']=='hline':
            ttk.Label(popup, text="Цена").grid(row=1,column=0,sticky='w', padx=6, pady=4)
        else:
            ttk.Label(popup, text="Дата (DD.MM)").grid(row=1,column=0,sticky='w', padx=6, pady=4)
        var_val = tk.StringVar(value=meta.get('value',''))
        ent_val = ttk.Entry(popup, textvariable=var_val, width=14)
        ent_val.grid(row=1, column=1, padx=6, pady=4)
        def ok():
            meta['code'] = var_code.get().strip()
            meta['value'] = var_val.get().strip()
            self.canvas.itemconfigure(meta['label_id'], text=(f"[цена] {meta['value']} code:{meta['code']}" if meta['kind']=='hline' else f"[дата] {meta['value']} code:{meta['code']}"))
            popup.destroy()
        ttk.Button(popup, text="Ок", command=ok).grid(row=2, column=0, columnspan=2, pady=6)
        popup.transient(self)
        popup.grab_set()
        ent_code.focus_set()

    def _apply(self, to: str):
        prices: dict[str, str] = {}
        dates: dict[str, str] = {}
        for it, meta in self.overlays.items():
            kind = meta.get('kind')
            if kind == 'hline':
                code = (meta.get('code') or '').strip()
                val = (meta.get('value') or '').strip()
                if code and val:
                    prices[code] = val
            elif kind == 'vline':
                code = (meta.get('code') or '').strip()
                val = (meta.get('value') or '').strip()
                if code and val:
                    dates[code] = val
            elif kind == 'ray13':
                code = (meta.get('code') or '').strip()
                val = (meta.get('value') or '').strip()
                dts = (meta.get('date') or '').strip()
                if code and val:
                    prices[code] = val
                if code and dts:
                    dates[code] = dts
            elif kind == 'hmark':
                code = (meta.get('code') or '').strip()
                val = (meta.get('value') or '').strip()
                if code and val:
                    prices[code] = val
            elif kind == 'fixprefix':
                lc = (meta.get('code_left') or '').strip()
                rc = (meta.get('code_right') or '').strip()
                lv = (meta.get('value_left') or '').strip()
                rv = (meta.get('value_right') or '').strip()
                if lc and lv:
                    prices[lc] = lv
                if rc and rv:
                    prices[rc] = rv
        if to == 'short':
            self.on_apply_short(prices, dates)
        else:
            self.on_apply_long(prices, dates)

class App(TkinterDnD.Tk if 'DND_OK' in globals() and DND_OK else tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FPF Label Maker — схемы")
        print("[label_maker] init App...")
        self.geometry("1360x760")
        self.configure(bg=DARK_BG)
        try:
            self.call('tk', 'scaling', 1.2)
        except Exception:
            pass
        style = ttk.Style(self)
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure('.', background=DARK_BG, foreground=TEXT_LIGHT)
        # -- Ive‑style ttk tweaks --
        def _apply_ive_style(st: ttk.Style):
            base_font = ("Helvetica Neue", 11)
            st.configure('.', background=DARK_BG, foreground=TEXT_LIGHT, font=base_font)
            st.configure('TFrame', background=DARK_BG)
            st.configure('TLabelframe', background=DARK_BG, foreground=TEXT_LIGHT)
            st.configure('TLabelframe.Label', background=DARK_BG, foreground=TEXT_MUTED, font=("Helvetica Neue", 12, "bold"))
            st.configure('TLabel', background=DARK_BG, foreground=TEXT_LIGHT)
            st.configure('TEntry', fieldbackground=PANEL_BG, foreground=TEXT_LIGHT, insertcolor=TEXT_LIGHT)
            st.configure('TCombobox', fieldbackground=PANEL_BG, foreground=TEXT_LIGHT)
            st.configure('TButton', background=PANEL_BG, foreground=TEXT_LIGHT, padding=(10,6))
            st.map('TButton', background=[('active', '#1c1c1e')])
            st.configure('TPanedwindow', background=DARK_BG)
        _apply_ive_style(style)

        # Верхняя панель общих полей
        top = ttk.Frame(self)
        top.pack(fill="x", padx=12, pady=8)

        self.var_symbol = tk.StringVar(value=SYMBOLS[0])
        self.var_tf = tk.StringVar(value="1h")
        self.var_outfile = tk.StringVar(value=DEFAULT_OUT)

        ttk.Label(top, text="SYMBOL").pack(side="left")
        cb_sym = ttk.Combobox(top, textvariable=self.var_symbol, values=SYMBOLS, width=12)
        cb_sym.pack(side="left", padx=6)
        cb_sym.configure(state='normal')  # оставить редактируемым

        ttk.Label(top, text="TF").pack(side="left")
        ttk.Combobox(top, textvariable=self.var_tf, values=["5m","15m","30m","1h","4h","1d"], width=6, state="readonly").pack(side="left", padx=6)
        ttk.Label(top, text="Журнал").pack(side="left", padx=(14,2))
        ttk.Entry(top, textvariable=self.var_outfile, width=48).pack(side="left", padx=6)
        ttk.Button(top, text="Обзор…", command=self._browse).pack(side="left", padx=6)

        # Главный вертикальный ресайзабельный контейнер
        pan = ttk.Panedwindow(self, orient='vertical')
        pan.pack(fill="both", expand=True, padx=10, pady=(0,8))

        # Верхняя панель: Картинка / Аннотации (эластичная)
        frmAnnot = ttk.Labelframe(pan, text="Картинка / Аннотации")
        pan.add(frmAnnot, weight=3)

        # Нижняя часть (ещё одна рамка внутри PanedWindow)
        center = ttk.Frame(pan)
        pan.add(center, weight=2)

        # Внутри center — две панели со схемами
        mid = ttk.Frame(center)
        mid.pack(fill="both", expand=True, padx=0, pady=(6,6))
        mid.grid_columnconfigure(0, weight=1)
        mid.grid_columnconfigure(1, weight=1)
        mid.grid_rowconfigure(0, weight=1)

        def apply_short(prices: dict[str,str], dates: dict[str,str]):
            for code, val in prices.items():
                inp = self.panel_short.inputs.get(code)
                if inp:
                    inp.price_entry.delete(0,'end'); inp.price_entry.insert(0, val)
            for code, val in dates.items():
                inp = self.panel_short.inputs.get(code)
                if inp:
                    inp.date_entry.delete(0,'end'); inp.date_entry.insert(0, val)

        def apply_long(prices: dict[str,str], dates: dict[str,str]):
            for code, val in prices.items():
                inp = self.panel_long.inputs.get(code)
                if inp:
                    inp.price_entry.delete(0,'end'); inp.price_entry.insert(0, val)
            for code, val in dates.items():
                inp = self.panel_long.inputs.get(code)
                if inp:
                    inp.date_entry.delete(0,'end'); inp.date_entry.insert(0, val)

        def get_short_codes():
            return list(self.panel_short.inputs.keys())
        def get_long_codes():
            return list(self.panel_long.inputs.keys())

        self.annot = ImageAnnotPanel(frmAnnot, apply_short, apply_long, get_short_codes, get_long_codes)
        self.annot.pack(fill="both", expand=True, padx=6, pady=6)

        # Спеки расположения точек (примерные координаты на Canvas)
        short_spec = [("1.1",80,255),("1.2",150,130),("1.3",190,190),("1.4",260,75),("1.5",300,205),("1.6",370,150),("1.7",420,190),("1.8",500,85)]
        long_spec  = [("2.1",120,85),("2.2",160,210),("2.3",220,125),("2.4",260,245),("2.5",320,105),("2.6",360,190),("2.7",460,140),("2.8",520,70)]

        self.panel_short = PatternPanel(mid, "FPF SHORT", short_spec, kind="short")
        self.panel_short.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self.panel_short.on_make_callback = self._made
        self.panel_short.on_point_click = lambda code: self._on_point_click_from_panel(code, 'short')

        self.panel_long = PatternPanel(mid, "FPF LONG", long_spec, kind="long")
        self.panel_long.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        self.panel_long.on_make_callback = self._made
        self.panel_long.on_point_click  = lambda code: self._on_point_click_from_panel(code, 'long')

        self.panel_short._draw_pattern()
        self.panel_long._draw_pattern()

        self.update_idletasks()
        print("[label_maker] UI widgets created")

        if not ("DND_OK" in globals() and DND_OK):
            print("[label_maker] Drag&Drop недоступен (не установлен tkinterdnd2). Используйте кнопку ‘Загрузить…’ или установите пакет: pip install tkinterdnd2")

        # Низ — вывод
        bot = ttk.LabelFrame(center, text="Вывод (JSONL)")
        bot.pack(fill="both", expand=False, padx=0, pady=(0,10))
        self.txt = tk.Text(bot, height=6, wrap="word",
                           bg=PANEL_BG, fg=TEXT_LIGHT,
                           insertbackground=TEXT_LIGHT,
                           highlightthickness=1, highlightbackground=BORDER_COL)
        self.txt.pack(fill="both", expand=True, padx=6, pady=6)

        act = ttk.Frame(center)
        act.pack(fill="x", padx=0, pady=(0,12))
        ttk.Button(act, text="Копировать", command=self._copy).pack(side="left", padx=4)
        ttk.Button(act, text="Дописать в файл", command=self._append).pack(side="left", padx=4)
        ttk.Button(act, text="Очистить", command=lambda: self.txt.delete("1.0","end")).pack(side="left", padx=4)

        hint = ttk.Label(center, text="• Вводите цену и дату (2025) для каждой точки. Допустимые форматы даты: DD,MM | DD.MM | DDMM | DD/MM | DD-MM | '5 6'.", foreground=TEXT_MUTED)
        hint.pack(anchor="w", padx=0, pady=(0,8))

    # ----- callbacks -----
    def _browse(self):
        p = filedialog.asksaveasfilename(title="Выберите файл JSONL", initialfile=os.path.basename(self.var_outfile.get()), initialdir=os.path.dirname(self.var_outfile.get()) or ".", defaultextension=".jsonl", filetypes=[("JSON Lines","*.jsonl"),("All Files","*.*")])
        if p:
            self.var_outfile.set(p)

    def _made(self, kind: str, data: dict):
        symbol = (self.var_symbol.get() or "").upper()
        tf = self.var_tf.get()
        patt_type = "FPF_SHORT" if kind=="short" else "FPF_LONG"
        payload = {
            "symbol": symbol,
            "tf": tf,
            "type": patt_type,
            "year": YEAR_FIXED,
            "points": data
        }
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        self.txt.insert("end", line + "\n")
        self.txt.see("end")
        self.clipboard_clear(); self.clipboard_append(line); self.update()
        messagebox.showinfo("FPF Label Maker", "Строка сформирована и скопирована в буфер.")

    def _copy(self):
        data = self.txt.get("1.0","end").strip()
        if not data:
            return
        self.clipboard_clear(); self.clipboard_append(data); self.update()
        messagebox.showinfo("FPF Label Maker", "Содержимое вывода скопировано.")

    def _append(self):
        data = self.txt.get("1.0","end").strip()
        if not data:
            messagebox.showwarning("FPF Label Maker", "Нет данных для записи.")
            return
        out = self.var_outfile.get() or DEFAULT_OUT
        os.makedirs(os.path.dirname(out), exist_ok=True)
        if not data.endswith("\n"):
            data += "\n"
        with open(out, "a", encoding="utf-8") as f:
            f.write(data)
        messagebox.showinfo("FPF Label Maker", f"Дописано в файл:\n{out}")

    def _on_point_click_from_panel(self, code: str, kind: str):
        try:
            self.annot.activate_from_code(code, kind)
        except Exception as e:
            print('[label_maker] point->annot error:', e)
            import traceback; traceback.print_exc()

if __name__ == "__main__":
    try:
        print("[label_maker] starting UI...")
        print("[label_maker] module file:", __file__)
        app = App()
        app.after(100, lambda: print("[label_maker] mainloop running"))
        app.mainloop()
    except Exception as e:
        print("[label_maker] ERROR:", e)
        traceback.print_exc()