# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 SoftRyva Development contributors
# This file is provided without warranty. See LICENSE.

"""SoftRyva ImageFlow v0.3.1 — offline image optimizer with Image Resizer.

UI: Tkinter + Pillow. The engine performs real JPEG/PNG/WebP conversions,
batch processing, safe output naming, preview comparison, local preferences
and local history. No advertisements, login, analytics or network requests.
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
from dataclasses import replace
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageOps, ImageTk
from core import ACCEPTED_EXTENSIONS, PRESETS, Options, Result, optimize_image, readable_bytes, resize_dimensions

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    RootClass = TkinterDnD.Tk
    DND_AVAILABLE = True
except ImportError:
    RootClass = tk.Tk
    DND_AVAILABLE = False

APP_NAME = 'SoftRyva ImageFlow'
APP_VERSION = '0.3.1'
ASSETS = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / 'assets'
DATA_DIR = Path(os.getenv('LOCALAPPDATA', '') or (Path.home() / '.local' / 'share')) / 'SoftRyva' / 'ImageFlow'
PREFS_PATH = DATA_DIR / 'settings.json'
HISTORY_PATH = DATA_DIR / 'history.json'
DEFAULT_FOLDER = Path.home() / 'Pictures' / 'ImageFlow' / 'Output'

C = {
    'bg': '#03101f', 'side': '#06192c', 'panel': '#071e34',
    'panel2': '#0b2741', 'raised': '#102c47', 'line': '#19405e',
    'muted': '#9fb2c8', 'text': '#f4f8fe', 'blue': '#098dff',
    'cyan': '#21caff', 'orange': '#ff9d29', 'green': '#11d89b',
    'red': '#ff6c86'
}
FONT = ('Segoe UI' if sys.platform == 'win32' else 'DejaVu Sans')


def round_rect(canvas, x1, y1, x2, y2, r, **opts):
    """Draw a smooth rounded rectangle as one polygon."""
    r = max(0, min(r, (x2-x1)/2, (y2-y1)/2))
    return canvas.create_polygon(
        [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r,
         x2, y2-r, x2, y2, x2-r, y2, x1+r, y2,
         x1, y2, x1, y2-r, x1, y1+r, x1, y1],
        smooth=True, splinesteps=12, **opts)


def safe_read_json(path, fallback):
    try:
        with path.open('r', encoding='utf-8') as handle:
            return json.load(handle)
    except (FileNotFoundError, OSError, ValueError, TypeError):
        return fallback


def safe_save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    with temp.open('w', encoding='utf-8') as handle:
        json.dump(obj, handle, indent=2, ensure_ascii=False)
    os.replace(temp, path)


class GradientButton(tk.Canvas):
    def __init__(self, parent, text, command=None, height=50, start='#0a8bff', end='#05bce8',
                 fg='white', width=180, font_size=12, outline=False):
        super().__init__(parent, height=height, width=width, bd=0, highlightthickness=0,
                         bg=parent.cget('bg'), cursor='hand2')
        self.label = text
        self.command = command
        self.start = start
        self.end = end
        self.fg = fg
        self.outline = outline
        self.font_size = font_size
        self.active = True
        self._cached_image = None
        self.bind('<Configure>', self._draw)
        self.bind('<Button-1>', self._click)
        self.bind('<Enter>', lambda _: self._draw())

    def _draw(self, _=None):
        w, h = max(3, self.winfo_width()), max(3, self.winfo_height())
        self.delete('all')
        if self.outline:
            round_rect(self, 2, 2, w-2, h-2, 13, fill=C['side'], outline=C['line'], width=1)
        else:
            # Use a clipping mask, so the blue→orange gradient has rounded corners.
            img = Image.new('RGB', (w, h))
            draw = ImageDraw.Draw(img)
            def rgb(s):
                s=s.lstrip('#'); return tuple(int(s[j:j+2],16) for j in (0,2,4))
            a, b = rgb(self.start), rgb(self.end)
            for x in range(w):
                t = x / max(w-1,1)
                draw.line((x,0,x,h), fill=tuple(int(a[i]*(1-t)+b[i]*t) for i in range(3)))
            mask = Image.new('L',(w,h),0)
            ImageDraw.Draw(mask).rounded_rectangle((0,0,w-1,h-1),radius=13,fill=255)
            bg = Image.new('RGB',(w,h),self.cget('bg'))
            bg.paste(img,mask=mask)
            self._cached_image = ImageTk.PhotoImage(bg)
            self.create_image(0,0,anchor='nw',image=self._cached_image)
        self.create_text(w/2, h/2, text=self.label, fill=self.fg if self.active else C['muted'],
                         font=(FONT,self.font_size,'bold'))

    def _click(self, _event):
        if self.command is not None and self.active:
            self.command()

    def set_enabled(self, enabled):
        self.active = enabled
        self.config(cursor='hand2' if enabled else 'arrow')
        self._draw()


def label(parent, text, size=11, color='text', bold=False, **kwargs):
    return tk.Label(parent, text=text, font=(FONT, size, 'bold' if bold else 'normal'),
                    fg=C.get(color,color), bg=parent.cget('bg'), **kwargs)


def frame(parent, bg='panel', border=False, **kwargs):
    return tk.Frame(parent, bg=C.get(bg,bg), bd=0,
                    highlightbackground=C['line'] if border else C.get(bg,bg),
                    highlightthickness=1 if border else 0, **kwargs)


class QualitySlider(tk.Canvas):
    """Cross-platform custom slider (avoids OS-dependent native scale colors)."""
    def __init__(self, parent, variable, width=265, height=35, on_change=None):
        super().__init__(parent, width=width, height=height,
                         bg=parent.cget('bg'), bd=0, highlightthickness=0,
                         cursor='hand2')
        self.value = variable
        self.on_change = on_change
        self.bind('<Configure>', lambda _: self.paint())
        self.bind('<Button-1>', self._set_from_event)
        self.bind('<B1-Motion>', self._set_from_event)
        self.value.trace_add('write',lambda *_: self.paint() if self.winfo_exists() else None)

    def paint(self):
        w,h=self.winfo_width(),self.winfo_height()
        if w<35:return
        a,b=12,w-12
        level=min(100,max(1,int(self.value.get())))
        knob=a+(b-a)*(level-1)/99
        self.delete('all')
        self.create_line(a,h/2,b,h/2,fill='#52647d',width=7,capstyle='round')
        self.create_line(a,h/2,knob,h/2,fill=C['blue'],width=7,capstyle='round')
        self.create_oval(knob-9,h/2-9,knob+9,h/2+9,fill=C['blue'],outline=C['cyan'],width=2)

    def _set_from_event(self,event):
        w=max(35,self.winfo_width());a,b=12,w-12
        level=int(round(1+99*max(0,min(1,(event.x-a)/max(1,b-a)))))
        self.value.set(level)
        if self.on_change:self.on_change()


def select_menu(parent, variable, options, width=15):
    menu=tk.OptionMenu(parent,variable,*options)
    menu.configure(bg=C['panel2'],fg=C['text'],activebackground=C['blue'],
                   activeforeground='white',highlightthickness=1,
                   highlightbackground=C['line'],bd=0,relief='flat',
                   indicatoron=1,font=(FONT,10),width=width)
    menu['menu'].configure(bg=C['panel2'],fg=C['text'],
                           activebackground=C['blue'],activeforeground='white',font=(FONT,10))
    return menu


def comfortable_scrollbar_width(widget):
    """24px minimum at 100% scale; grow proportionally on HiDPI displays."""
    try:
        return min(44, max(24, round(18 * float(widget.tk.call('tk', 'scaling')))))
    except (tk.TclError, TypeError, ValueError):
        return 24


class ScrollablePanel(tk.Frame):
    """Frame that never hides lower controls on small/high-DPI displays."""
    def __init__(self, parent, bg='panel'):
        background = C.get(bg, bg)
        super().__init__(parent, bg=background, bd=0, highlightthickness=0)
        self.canvas = tk.Canvas(self, bg=background, bd=0, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(
            self, command=self.canvas.yview, width=comfortable_scrollbar_width(self),
            bg=C['blue'], troughcolor=C['side'], activebackground=C['cyan'],
            bd=0, relief='flat', highlightthickness=0, elementborderwidth=2,
            cursor='hand2')
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.inner = tk.Frame(self.canvas, bg=background)
        self.handle = self.canvas.create_window(0, 0, window=self.inner, anchor='nw')
        self.inner.bind('<Configure>', self._update_region)
        self.canvas.bind('<Configure>', self._resize_inner)
        self.canvas.bind('<Enter>', self._enable_wheel)
        self.inner.bind('<Enter>', self._enable_wheel)
        self.canvas.bind('<Leave>', self._disable_wheel)
        self.inner.bind('<Leave>', lambda e: None)

    def _update_region(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def _resize_inner(self, event):
        self.canvas.itemconfigure(self.handle, width=event.width)
        self._update_region()

    def _enable_wheel(self, _event=None):
        self.canvas.bind_all('<MouseWheel>', self._wheel)
        self.canvas.bind_all('<Button-4>', self._wheel)
        self.canvas.bind_all('<Button-5>', self._wheel)

    def _disable_wheel(self, _event=None):
        self.canvas.unbind_all('<MouseWheel>')
        self.canvas.unbind_all('<Button-4>')
        self.canvas.unbind_all('<Button-5>')

    def _wheel(self, event):
        if not self.winfo_exists():
            return
        if event.num == 4:
            steps = -1
        elif event.num == 5:
            steps = 1
        else:
            steps = -int(event.delta / 120) if abs(event.delta) >= 120 else (-1 if event.delta > 0 else 1)
        self.canvas.yview_scroll(steps, 'units')


class ImageFlowApp(RootClass):
    def __init__(self):
        super().__init__()
        self.title(f'{APP_NAME}  |  v{APP_VERSION}')
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        # Fit smaller Windows laptop screens; avoid hiding controls below taskbar.
        self.geometry(f'{min(1470,max(940,sw-36))}x{min(875,max(560,sh-94))}')
        self.minsize(910, 560)
        self.configure(bg=C['bg'])
        try:
            self.iconphoto(True, ImageTk.PhotoImage(Image.open(ASSETS / 'icon.png').resize((64,64))))
        except Exception:
            pass
        self.protocol('WM_DELETE_WINDOW', self._exit)

        prefs = safe_read_json(PREFS_PATH, {})
        if not isinstance(prefs, dict):
            prefs = {}
        self.folder_var = tk.StringVar(value=str(prefs.get('output_dir',DEFAULT_FOLDER)))
        self.format_var = tk.StringVar(value=prefs.get('format','Original') if prefs.get('format') in ('Original','Auto','JPEG','PNG','WEBP') else 'Original')
        self.smart_var = tk.BooleanVar(value=bool(prefs.get('smart', True)))
        self.smart_preset_var = tk.StringVar(value=prefs.get('smart_preset','Balanced') if prefs.get('smart_preset') in PRESETS else 'Balanced')
        self.quality_var = tk.IntVar(value=int(prefs.get('quality',75)) if str(prefs.get('quality',75)).isdigit() else 75)
        self.quality_var.set(min(100,max(1,self.quality_var.get())))
        self.metadata_var = tk.BooleanVar(value=bool(prefs.get('keep_metadata',False)))
        self.suffix_var = tk.StringVar(value=prefs.get('suffix','_optimized'))
        # Existing V0.2 settings and history are retained in the same local folder.
        self.resize_enabled_var = tk.BooleanVar(value=bool(prefs.get('resize_enabled', False)))
        self.resize_mode_var = tk.StringVar(value=prefs.get('resize_mode', 'Pixels'))
        if self.resize_mode_var.get() not in ('Pixels', 'Percent'):
            self.resize_mode_var.set('Pixels')
        self.resize_width_var = tk.StringVar(value=str(prefs.get('resize_width') or ''))
        self.resize_height_var = tk.StringVar(value=str(prefs.get('resize_height') or ''))
        self.resize_percent_var = tk.StringVar(value=str(prefs.get('resize_percent', 50)))
        self.resize_lock_var = tk.BooleanVar(value=bool(prefs.get('resize_lock_aspect', True)))
        self.resize_upscale_var = tk.BooleanVar(value=bool(prefs.get('resize_allow_upscale', False)))
        self.history = safe_read_json(HISTORY_PATH, [])
        if not isinstance(self.history, list):
            self.history=[]
        self.history=self.history[:100]

        self.selected: list[Path] = []
        self.results: list[Result] = []
        self.last_run_results: list[Result] = []
        self.last_output_dir = None
        self.preview_index = 0
        self.preview_split = 0.5
        self._preview_source = None
        self._preview_result = None
        self._preview_tk = []
        self._preview_render_size = (0,0)
        self._queue = queue.Queue()
        self.processing = False
        self.nav_name = 'Optimize'
        self.nav_buttons = {}
        self.quality_value_label = None
        self.progress_status = None
        self._make_shell()
        self._go('Optimize')
        self.after(100,self._process_events)

    def _make_shell(self):
        shell = frame(self,'bg')
        shell.pack(fill='both',expand=True)
        self.sidebar = frame(shell,'side',border=True, width=204 if self.winfo_screenwidth()<=1200 else (230 if self.winfo_screenwidth()<=1450 else 270))
        self.sidebar.pack(side='left', fill='y')
        self.sidebar.pack_propagate(False)
        self.app_area = frame(shell,'bg')
        self.app_area.pack(side='left',fill='both',expand=True)

        branding = frame(self.sidebar,'side', height=110 if self.winfo_screenheight()<=900 else 122)
        branding.pack(fill='x',padx=12,pady=(9,5))
        branding.pack_propagate(False)
        try:
            logo = Image.open(ASSETS/'icon.png').convert('RGBA')
            self._sidebar_icon = ImageTk.PhotoImage(logo.resize((59,59), Image.Resampling.LANCZOS))
            tk.Label(branding,image=self._sidebar_icon,bg=C['side']).place(x=0,y=0)
        except OSError:
            pass
        label(branding,'SoftRyva',size=16,bold=True).place(x=65,y=6)
        label(branding,'ImageFlow',size=16,bold=True,color='cyan').place(x=65,y=35)
        label(branding,'Smart Image Optimizer',size=9,color='muted').place(x=2,y=77)
        label(branding,'& Converter  •  Offline',size=9,color='muted').place(x=2,y=94)

        navbox = frame(self.sidebar,'side')
        navbox.pack(fill='x',padx=10)
        for icon_text, name in [('⚡','Optimize'),('▦','Dashboard'),('◷','History'),
                                ('⚙','Settings'),('▧','My Images'),('☷','Batch Convert'),('ⓘ','Support')]:
            row = frame(navbox,'side',height=42 if self.winfo_screenheight()<=900 else 51)
            row.pack(fill='x',pady=2)
            row.pack_propagate(False)
            canvas=tk.Canvas(row,bg=C['side'],height=40 if self.winfo_screenheight()<=900 else 48,highlightthickness=0,cursor='hand2')
            canvas.pack(fill='both',expand=True)
            canvas.bind('<Configure>', lambda e,n=name,ico=icon_text,cnv=canvas: self._render_nav(cnv,ico,n))
            canvas.bind('<Button-1>', lambda e,n=name:self._go(n))
            self.nav_buttons[name]=(canvas,icon_text)

        promo = frame(self.sidebar,'panel',border=True)
        promo.pack(side='bottom',fill='x',padx=10,pady=8) if self.winfo_screenheight()>900 else None
        label(promo,'⚡  FAST LOCAL',size=13,bold=True,color='cyan').pack(anchor='w',padx=15,pady=(16,2))
        label(promo,'PROCESSING',size=13,bold=True,color='orange').pack(anchor='w',padx=15)
        for sentence in ('✓  Works without internet', '✓  Files stay on your PC',
                         '✓  Original files are safe','✓  Convert entire batches'):
            label(promo,sentence,size=9).pack(anchor='w',padx=15,pady=6)
        label(promo,'FREE  •  NO ACCOUNT NEEDED',size=9,color='muted').pack(padx=10,pady=(14,17))

        top = frame(self.app_area,'bg',height=47 if self.winfo_screenheight()<=900 else 62)
        top.pack(fill='x',padx=15,pady=(2,2))
        top.pack_propagate(False)
        label(top,'IMAGEFLOW  /  WORKSPACE',size=10,bold=True,color='muted').pack(side='left',padx=(8,0))
        badge = frame(top,'panel',border=True)
        badge.pack(side='right',padx=(0,3),pady=10)
        label(badge,'●  100% LOCAL  •  PRIVATE',size=9,color='green',bold=True).pack(padx=13,pady=7)
        self.saved_banner=label(top,'',size=9,color='green',bold=True)
        self.saved_banner.pack(side='right',padx=8)
        self.page_container = frame(self.app_area,'bg')
        self.page_container.pack(fill='both',expand=True,padx=(13,15),pady=(0,4))
        footer = frame(self.app_area,'panel',border=True,height=48 if self.winfo_screenheight()<=900 else 58)
        footer.pack(fill='x',side='bottom',padx=(13,15),pady=(0,6))
        footer.pack_propagate(False)
        for j,(tag,caption) in enumerate([('⚡ SUPER FAST','Local processing'),('◇ PRIVATE','No cloud uploads'),
                                            ('▤ BATCH READY','Multiple files'),('✦ HIGH QUALITY','Choose your level')]):
            item = frame(footer,'panel')
            item.pack(side='left',fill='both',expand=True,padx=10)
            label(item,tag,size=9,bold=True,color='cyan' if j%2==0 else 'orange').pack(anchor='center',pady=(4,0))
            label(item,caption,size=8,color='muted').pack(anchor='center')

    def _render_nav(self,canvas,ico,name):
        w,h=max(canvas.winfo_width(),1),max(canvas.winfo_height(),1)
        canvas.delete('all')
        active = name == self.nav_name
        if active:
            round_rect(canvas,2,2,w-3,h-3,13,fill=C['blue'],outline='')
        canvas.create_text(25,h/2,text=ico,fill='white' if active else C['cyan'],font=(FONT,19,'bold'))
        canvas.create_text(55,h/2,text=name,anchor='w',fill='white' if active else C['text'],font=(FONT,12,'bold' if active else 'normal'))

    def _go(self,name):
        self.nav_name=name
        for canvas,ico in self.nav_buttons.values():
            for navname,(c,icon) in self.nav_buttons.items():
                if c is canvas:
                    self._render_nav(c,icon,navname)
                    break
        for widget in self.page_container.winfo_children():
            widget.destroy()
        self.quality_value_label=None
        self.progress_status=None
        if name in ('Optimize','Batch Convert'):
            self._page_optimize(batch=(name=='Batch Convert'))
        elif name=='Settings':
            self._page_settings()
        elif name=='Dashboard':
            self._page_dashboard()
        elif name=='History':
            self._page_history()
        elif name=='My Images':
            self._page_images()
        else:
            self._page_support()

    def _heading(self,parent,title,subtitle):
        header=frame(parent,'panel',border=True,height=73)
        header.pack(fill='x',pady=(0,12))
        header.pack_propagate(False)
        label(header,title,size=20,bold=True).pack(anchor='w',padx=20,pady=(8,1))
        label(header,subtitle,size=9,color='muted').pack(anchor='w',padx=20)
        return header

    def _page_optimize(self,batch=False):
        area=self.page_container
        columns=frame(area,'bg')
        columns.pack(fill='both',expand=True)
        center=frame(columns,'bg')
        center.pack(side='left',fill='both',expand=True,padx=(0,13))
        compact=self.winfo_screenheight() <= 900
        right=frame(columns,'panel',border=True,width=272 if self.winfo_screenwidth()<=1200 else (292 if self.winfo_screenwidth()<=1450 else 332))
        right.pack(side='right',fill='y')
        right.pack_propagate(False)

        upload=frame(center,'panel',border=True,height=135 if compact else 173)
        upload.pack(fill='x',pady=(0,12))
        upload.pack_propagate(False)
        upload_canvas=tk.Canvas(upload,bg=C['panel'],highlightthickness=0,cursor='hand2')
        upload_canvas.pack(fill='both',expand=True,padx=8,pady=7)
        upload_canvas.bind('<Configure>',lambda e:self._draw_drop(upload_canvas,batch))
        upload_canvas.bind('<Button-1>',lambda _:self._choose_files())
        if DND_AVAILABLE:
            try:
                upload_canvas.drop_target_register(DND_FILES)
                upload_canvas.dnd_bind('<<Drop>>',self._on_drop)
            except Exception:
                pass

        preview_box=frame(center,'panel',border=True)
        preview_box.pack(fill='both',expand=True,pady=(0,10))
        self.preview_canvas=tk.Canvas(preview_box,bg='#0b2b42',height=190 if compact else 280,highlightthickness=0)
        self.preview_canvas.pack(fill='both',expand=True,padx=9,pady=9)
        self.preview_canvas.bind('<Configure>',lambda _:self._draw_preview())
        self.preview_canvas.bind('<Button-1>',self._move_compare)
        self.preview_canvas.bind('<B1-Motion>',self._move_compare)
        self.preview_canvas.bind('<Double-Button-1>',lambda _:self._choose_files())
        self.stats_holder = frame(preview_box,'panel',height=67 if compact else 81)
        self.stats_holder.pack(fill='x',padx=8,pady=(0,8))
        self.stats_holder.pack_propagate(False)
        self.stats_widgets=[]
        for headline,value,colors in [('Original Size','—','text'),('Optimized Size','—','cyan'),('Reduction','—','green')]:
            stat=frame(self.stats_holder,'panel2')
            stat.pack(side='left',fill='both',expand=True,padx=3)
            label(stat,headline,size=9,color='muted').pack(pady=(7 if compact else 13,2))
            metric=label(stat,value,size=14 if compact else 17,bold=True,color=colors)
            metric.pack()
            self.stats_widgets.append(metric)
        info=frame(center,'bg',height=29)
        info.pack(fill='x')
        info.pack_propagate(False)
        self.file_status=label(info,self._selected_caption(),size=9,color='muted',anchor='w')
        self.file_status.pack(side='left',fill='x',expand=True)
        btn=GradientButton(info,'ADD IMAGES +',self._choose_files,height=28,width=122, font_size=9,
                           outline=True)
        btn.pack(side='right',padx=(5,0))
        if batch:
            GradientButton(info,'ADD FOLDER',self._choose_image_folder,height=28,width=112, font_size=9,
                           outline=True).pack(side='right')
        else:
            GradientButton(info,'NEXT  ▶',self._next_preview,height=28,width=88,font_size=9,
                           outline=True).pack(side='right')

        right_scroll=ScrollablePanel(right,'panel')
        right_scroll.pack(fill='both',expand=True)
        right_pad=frame(right_scroll.inner,'panel')
        right_pad.pack(fill='both',expand=True,padx=9 if compact else 13,pady=9 if compact else 15)
        label(right_pad,'Optimization Level',size=14,bold=True).pack(anchor='w')
        self.quality_value_label=label(right_pad,f'{self.quality_var.get()}%',size=17,bold=True,color='cyan')
        self.quality_value_label.pack(anchor='e',pady=(0,0))
        quality = QualitySlider(right_pad,self.quality_var,width=270,height=36,
                                on_change=self._refresh_quality)
        quality.pack(fill='x',pady=(0,7))
        frow=frame(right_pad,'panel')
        frow.pack(fill='x',pady=(2,13))
        label(frow,'Output format',size=10,color='muted').pack(side='left')
        select_menu(frow,self.format_var,('Original','Auto','JPEG','PNG','WEBP'),width=9).pack(side='right')
        self.resize_quick_btn=GradientButton(right_pad,self._resize_summary(),self._show_resize_dialog,
                         outline=True,height=39,font_size=10)
        self.resize_quick_btn.pack(fill='x',pady=(0,8))
        self.optimize_btn=GradientButton(right_pad,'⚡   OPTIMIZE IMAGES',self._start_optimization,
                                          start='#087dff',end='#ff9b27',height=57,font_size=12)
        self.optimize_btn.pack(fill='x',pady=(0,7))
        # The two most important actions must ALWAYS remain visible on laptop screens.
        action=frame(right_pad,'panel')
        action.pack(fill='x',pady=(0,7))
        GradientButton(action,'OPEN RESULTS',self._open_latest_folder,outline=True,
                       height=37,font_size=9,width=120).pack(side='left',fill='x',expand=True,padx=(0,3))
        GradientButton(action,'SAVE AS…',self._save_as_last_result,
                       start='#078edb',end='#12bd92',height=37,font_size=9,width=110).pack(side='right',fill='x',expand=True,padx=(3,0))
        self.destination_hint=label(right_pad,'Results saved to: '+str(self.folder_var.get()),
                                    size=8,color='muted',wraplength=267,justify='left')
        self.destination_hint.pack(anchor='w',pady=(0,5))
        label(right_pad,'FEATURES   •   CLICK TO CONFIGURE',size=9,bold=True,color='cyan').pack(anchor='w',pady=(10,3))
        cards=[('↔','Image Resizer','Pixels • Percent • Keep proportions','cyan',self._show_resize_dialog),
            ('◈','Smart Compression','Try encodings; compare fidelity','green',self._show_smart_dialog),
            ('▧','Multiple Formats','JPG  •  PNG  •  WEBP  •  AUTO','blue',self._show_format_dialog),
            ('♢','Secure & Private','Local files • EXIF controls','cyan',self._show_privacy_dialog),
            ('⚡','Fast & Efficient','Batch processing and folders','orange',lambda:self._go('Batch Convert')),
            ('✓','High Quality','Fine-tune quality and preset','green',self._show_smart_dialog)]
        for icon_tag,title,sub,accent,action in cards:
            self._feature_card(right_pad,icon_tag,title,sub,accent,action)
        self.progress_status=label(right_pad,'Ready to optimize images',size=9,color='muted',wraplength=280)
        self.progress_status.pack(anchor='w',pady=(4,3))
        self.progress=ttk.Progressbar(right_pad,orient='horizontal',mode='determinate',maximum=100)
        self.progress.pack(fill='x',pady=(0,4))
        GradientButton(right_pad,'CHANGE OUTPUT FOLDER',self._choose_output,outline=True,
                       height=30,font_size=9).pack(fill='x',pady=(4,0))
        if self.selected:
            self.preview_index=min(self.preview_index,len(self.selected)-1)
            self._load_preview()
        else:
            self._draw_preview()

    def _draw_drop(self,canvas,batch):
        w,h=canvas.winfo_width(),canvas.winfo_height()
        if w<10 or h<10:return
        canvas.delete('all')
        canvas.create_rectangle(13,13,w-13,h-13,outline=C['cyan'],width=2,dash=(7,7))
        canvas.create_text(w/2,h*.30,text='☁  ↑',fill=C['cyan'],font=(FONT,30,'bold'))
        title=('Drop images here or click to browse' if w<560 and DND_AVAILABLE else
               'Click to choose images' if w<560 else
               'Drag & drop images or click to upload' if DND_AVAILABLE
               else 'Click to choose images from your computer')
        canvas.create_text(w/2,h*.60,text=title,fill=C['text'],font=(FONT,12 if w<560 else 14,'bold'),width=max(60,w-40))
        canvas.create_text(w/2,h*.81,text=('JPG  •  PNG  •  WEBP' if w<560 else 'JPG  •  PNG  •  WEBP  •  MULTIPLE FILES SUPPORTED'),
                           fill=C['muted'],font=(FONT,9))

    def _move_compare(self,event):
        if self._preview_source:
            self.preview_split = min(.95,max(.05,event.x / max(1,self.preview_canvas.winfo_width())))
            self._draw_preview()

    def _draw_preview(self):
        canvas=getattr(self,'preview_canvas',None)
        if canvas is None or not canvas.winfo_exists():return
        w,h=canvas.winfo_width(),canvas.winfo_height()
        if w<20 or h<20:return
        canvas.delete('all')
        if self._preview_source is None:
            canvas.create_rectangle(0,0,w,h,fill='#0b2a42',outline='')
            for i in range(4):
                canvas.create_oval(w*.1+i*60,h*.2,w*.8+i*18,h*1.5,
                                   outline=('#0d354f' if i%2 else '#0d304b'),width=2)
            canvas.create_text(w/2,h*.42,text='▧',fill=C['cyan'],font=(FONT,49))
            canvas.create_text(w/2,h*.60,text='BEFORE  /  AFTER  PREVIEW',
                               fill=C['text'],font=(FONT,16,'bold'))
            canvas.create_text(w/2,h*.72,text='Choose a photo to see the real comparison here',
                               fill=C['muted'],font=(FONT,10))
            return
        # Only read images on selection, not on every slider movement.
        target=self._preview_result or self._preview_source
        try:
            original=ImageOps.pad(self._preview_source,(w,h),method=Image.Resampling.LANCZOS,color='#082339')
            optimized=ImageOps.pad(target,(w,h),method=Image.Resampling.LANCZOS,color='#082339')
        except ValueError:
            return
        x=int(w*self.preview_split)
        composed=original.copy()
        composed.paste(optimized.crop((x,0,w,h)),(x,0))
        self._preview_tk=[ImageTk.PhotoImage(composed)]
        canvas.create_image(0,0,image=self._preview_tk[0],anchor='nw')
        canvas.create_line(x,0,x,h,fill='white',width=3)
        canvas.create_oval(x-18,h/2-18,x+18,h/2+18,fill='white',outline=C['cyan'],width=2)
        canvas.create_text(x,h/2,text='‹ ›',fill=C['bg'],font=(FONT,15,'bold'))
        round_rect(canvas,12,12,94,41,9,fill='#041321',outline='')
        canvas.create_text(53,27,text='Original',fill='white',font=(FONT,10,'bold'))
        round_rect(canvas,w-108,12,w-12,41,9,fill=('#036b54' if self._preview_result else '#1d4663'),outline='')
        canvas.create_text(w-60,27,text=('Optimized' if self._preview_result else 'Preview'),
                           fill='white',font=(FONT,10,'bold'))

    def _selected_caption(self):
        if not self.selected:return 'No images selected yet'
        suffix='s' if len(self.selected)!=1 else ''
        text = f'{len(self.selected)} image{suffix} selected  •  ' + self.selected[self.preview_index].name[:38]
        current = self.selected[self.preview_index]
        match = next((r for r in reversed(self.results) if Path(r.source)==current),None)
        if match and match.source_width:
            text += f'  •  {match.source_width}×{match.source_height} → {match.target_width}×{match.target_height}'
        return text

    def _next_preview(self):
        if not self.selected:
            messagebox.showinfo('ImageFlow','Add images first.',parent=self)
            return
        self.preview_index=(self.preview_index+1)%len(self.selected)
        self._load_preview()

    def _choose_image_folder(self):
        directory=filedialog.askdirectory(parent=self,title='Select folder containing images')
        if directory:self._add_files([directory])

    def _choose_files(self):
        files=filedialog.askopenfilenames(parent=self,title='Choose images',
                                         filetypes=[('Supported images','*.jpg *.jpeg *.png *.webp'),('All files','*.*')])
        if files:self._add_files(files)

    def _on_drop(self,event):
        try:
            paths=self.tk.splitlist(event.data)
        except Exception:
            paths=[event.data]
        self._add_files(paths)

    def _add_files(self,files):
        existing={str(p).lower() for p in self.selected}
        added=0
        for p in files:
            path=Path(p).expanduser()
            if path.is_dir():
                candidates=sorted(q for q in path.iterdir() if q.is_file() and q.suffix.lower() in ACCEPTED_EXTENSIONS)
            else:
                candidates=[path]
            for candidate in candidates:
                if candidate.is_file() and candidate.suffix.lower() in ACCEPTED_EXTENSIONS and str(candidate).lower() not in existing:
                    self.selected.append(candidate)
                    existing.add(str(candidate).lower())
                    added+=1
        if not added:
            messagebox.showinfo('SoftRyva ImageFlow','No new JPG, PNG or WebP images were found.',parent=self)
            return
        self.preview_index=max(0,len(self.selected)-added)
        self._load_preview()
        if self.nav_name not in ('Optimize','Batch Convert'):
            self._go('Optimize')
        else:
            self.file_status.config(text=self._selected_caption())

    def _load_preview(self):
        self._preview_source=None
        self._preview_result=None
        if not self.selected:return
        path=self.selected[self.preview_index]
        try:
            with Image.open(path) as img:
                self._preview_source=ImageOps.exif_transpose(img).convert('RGBA')
        except Exception as err:
            messagebox.showerror('Preview error',f'Could not open image:\n{err}',parent=self)
            return
        matching=next((r for r in reversed(self.results) if Path(r.source)==path),None)
        if matching and Path(matching.target).exists():
            try:
                with Image.open(matching.target) as img:
                    self._preview_result=ImageOps.exif_transpose(img).convert('RGBA')
            except OSError:
                self._preview_result=None
        self._update_stats(matching)
        self._draw_preview()
        if self.nav_name in ('Optimize','Batch Convert') and hasattr(self,'file_status') and self.file_status.winfo_exists():
            self.file_status.config(text=self._selected_caption())

    def _update_stats(self,result):
        if not hasattr(self,'stats_widgets') or any(not w.winfo_exists() for w in self.stats_widgets):
            return
        if not self.selected:return
        size=self.selected[self.preview_index].stat().st_size
        self.stats_widgets[0].config(text=readable_bytes(size))
        self.stats_widgets[1].config(text=readable_bytes(result.target_size) if result else 'Not processed')
        self.stats_widgets[2].config(text=f'{result.reduction_percent:+.1f}%' if result else '—')
        self.stats_widgets[2].config(fg=C['green'] if result and result.reduction_percent>=0 else (C['red'] if result else C['muted']))

    def _refresh_quality(self):
        if self.quality_value_label is not None and self.quality_value_label.winfo_exists():
            self.quality_value_label.config(text=f'{self.quality_var.get()}%')

    def _choose_output(self):
        start=self.folder_var.get()
        if not Path(start).is_dir():start=str(Path.home())
        path=filedialog.askdirectory(parent=self,title='Select output folder',initialdir=start)
        if path:
            self.folder_var.set(path)
            if hasattr(self,'destination_hint') and self.destination_hint.winfo_exists():
                self.destination_hint.configure(text='Results saved to: '+path)
            # Persist the chosen folder, even when changed outside Settings.
            self._persist_settings(notify=False)

    def _open_path(self, path):
        target=Path(path).expanduser()
        if not target.exists():
            messagebox.showerror('File not found',f'The following path does not exist:\n{target}',parent=self)
            return False
        try:
            if sys.platform=='win32':os.startfile(str(target))
            elif sys.platform=='darwin':subprocess.Popen(['open',str(target)])
            else:subprocess.Popen(['xdg-open',str(target)])
            return True
        except (OSError,ValueError) as err:
            messagebox.showerror('Cannot open path',str(err),parent=self)
            return False

    def _open_output(self):
        return self._open_path(self.folder_var.get())

    def _last_saved_result(self):
        if self.last_run_results:return self.last_run_results[-1]
        if self.results:return self.results[-1]
        for entry in self.history:
            if isinstance(entry,dict) and Path(str(entry.get('target',''))).is_file():
                return Result(str(entry.get('source','')),str(entry['target']),
                              int(entry.get('source_size',0)),int(entry.get('target_size',0)),
                              float(entry.get('elapsed_seconds',0)),str(entry.get('format','')))
        return None

    def _open_latest_folder(self):
        result=self._last_saved_result()
        directory=Path(result.target).parent if result else Path(self.folder_var.get())
        if not directory.is_dir():
            messagebox.showinfo('Where are my images?',
                'The output folder does not exist yet.\n\nClick Optimize Images to save images first.\n\n'
                +str(directory),parent=self)
            return
        self._open_path(directory)

    def _save_as_last_result(self):
        result=self._last_saved_result()
        if result is None or not Path(result.target).is_file():
            messagebox.showinfo('Save As','Optimize an image first to enable Save As.',parent=self)
            return
        self._save_result_as(result)

    def _save_result_as(self,result,parent=None):
        src=Path(result.target)
        if not src.is_file():
            messagebox.showerror('File not found','The optimized file is missing:\n'+str(src),parent=parent or self)
            return
        dest=filedialog.asksaveasfilename(parent=parent or self,title='Save optimized image as…',
                    initialdir=str(Path.home() / 'Pictures'),initialfile=src.name,
                    defaultextension=src.suffix,
                    filetypes=[(src.suffix.upper().lstrip('.')+' image','*'+src.suffix),('All files','*.*')])
        if not dest:return
        dst=Path(dest)
        if dst.suffix.lower()!=src.suffix.lower():
            messagebox.showerror('Format mismatch','For this image, use the extension '+src.suffix+'.\nUse Output Format to convert it.',parent=parent or self)
            return
        if src.resolve()==dst.resolve():
            messagebox.showinfo('Already saved','This is the original saved result:\n'+str(src),parent=parent or self)
            return
        try:
            shutil.copy2(src,dst)
        except OSError as err:
            messagebox.showerror('Save failed',str(err),parent=parent or self)
            return
        messagebox.showinfo('Copy saved','Image saved successfully to:\n'+str(dst),parent=parent or self)


    def _feature_card(self, parent, icon_text, title, description, accent, action):
        card=frame(parent,'panel2',border=True,height=57)
        card.pack(fill='x',pady=3)
        card.pack_propagate(False)
        left=label(card,icon_text,size=21,bold=True,color=accent,cursor='hand2')
        left.pack(side='left',padx=(10,7))
        text_wrap=frame(card,'panel2',cursor='hand2')
        text_wrap.pack(side='left',fill='both',expand=True,pady=5)
        heading=label(text_wrap,title,size=10,bold=True,cursor='hand2')
        heading.pack(anchor='w')
        subtitle=label(text_wrap,description,size=8,color='muted',cursor='hand2',anchor='w')
        subtitle.pack(anchor='w')
        caret=label(card,'›',size=20,color='cyan',cursor='hand2')
        caret.pack(side='right',padx=6)
        for widget in (card,left,text_wrap,heading,subtitle,caret):
            widget.bind('<Button-1>',lambda _event,fn=action:fn())

    def _feature_dialog(self,title,subtitle):
        dialog=tk.Toplevel(self)
        dialog.title('SoftRyva ImageFlow — '+title)
        dialog.configure(bg=C['bg'])
        dialog.resizable(False,False)
        dialog.transient(self)
        w,h=510,375
        x=self.winfo_rootx()+max(0,(self.winfo_width()-w)//2)
        y=self.winfo_rooty()+max(0,(self.winfo_height()-h)//2)
        dialog.geometry(f'{w}x{h}+{x}+{y}')
        panel=frame(dialog,'panel',border=True)
        panel.pack(fill='both',expand=True,padx=10,pady=10)
        label(panel,title,size=19,bold=True,color='cyan').pack(anchor='w',padx=17,pady=(16,5))
        label(panel,subtitle,size=10,color='muted',wraplength=450,justify='left').pack(anchor='w',padx=17,pady=(0,13))
        dialog.grab_set()
        dialog.focus_force()
        return dialog,panel

    def _show_smart_dialog(self):
        dialog,panel=self._feature_dialog('Smart Compression',
            'Real local encoding comparison: tests file size and approximate visual fidelity. No cloud or AI model.')
        body=frame(panel,'panel')
        body.pack(fill='both',expand=True,padx=18)
        tk.Checkbutton(body,text='Enable Smart Compression',variable=self.smart_var,
           font=(FONT,12,'bold'),bg=C['panel'],fg=C['text'],activeforeground=C['text'],
           activebackground=C['panel'],selectcolor=C['raised']).pack(anchor='w',pady=5)
        label(body,'Smart preset',size=11,bold=True).pack(anchor='w',pady=(11,4))
        select_menu(body,self.smart_preset_var,PRESETS,width=22).pack(anchor='w')
        label(body,'Optimization level: adjust on the Optimize screen.\n'
             'Balanced checks candidate sizes while preserving a minimum approximate fidelity.\n'
             'PNG remains lossless; JPEG/WebP are usually lossy.',size=9,color='muted',
             wraplength=450,justify='left').pack(anchor='w',pady=(13,0))
        GradientButton(panel,'SAVE & CLOSE',lambda:(self._persist_settings(notify=False),dialog.destroy()),
                 height=40,font_size=10).pack(side='bottom',pady=12)

    def _show_format_dialog(self):
        dialog,panel=self._feature_dialog('Multiple Formats',
            'Select the actual output encoder. Auto tests eligible formats and chooses the smallest acceptable output.')
        body=frame(panel,'panel')
        body.pack(fill='both',expand=True,padx=22)
        descriptions={'Original':'Preserve input format (JPG / PNG / WebP)',
           'Auto':'Smart format selection; alpha transparency remains supported',
           'JPEG':'Smaller photos; transparent areas become white',
           'PNG':'Lossless pixels; suitable for graphics and screenshots',
           'WEBP':'Modern format, usually excellent for web images'}
        for fmt,caption in descriptions.items():
            row=frame(body,'panel')
            row.pack(fill='x',pady=3)
            rb=tk.Radiobutton(row,text=fmt,variable=self.format_var,value=fmt,
                bg=C['panel'],fg=C['text'],activeforeground=C['cyan'],activebackground=C['panel'],
                selectcolor=C['raised'],font=(FONT,10,'bold'))
            rb.pack(side='left')
            label(row,caption,size=8,color='muted').pack(side='left',padx=8)
        GradientButton(panel,'APPLY FORMAT',lambda:(self._persist_settings(notify=False),dialog.destroy(),
             self._go(self.nav_name) if self.nav_name in ('Optimize','Batch Convert') else None),
             height=39,font_size=10).pack(side='bottom',pady=12)

    def _show_privacy_dialog(self):
        dialog,panel=self._feature_dialog('Secure & Private',
            'Everything is processed on your PC. There are no image uploads, accounts, or trackers.')
        body=frame(panel,'panel')
        body.pack(fill='both',expand=True,padx=20)
        label(body,'✓   Photos never leave your computer',size=11,color='green').pack(anchor='w',pady=5)
        label(body,'✓   Source images are never overwritten',size=11,color='green').pack(anchor='w',pady=5)
        label(body,'✓   Local history can be cleared in History',size=11,color='green').pack(anchor='w',pady=5)
        tk.Checkbutton(body,text='Preserve EXIF and ICC metadata when supported',
            variable=self.metadata_var,bg=C['panel'],fg=C['text'],activeforeground=C['text'],
            activebackground=C['panel'],selectcolor=C['raised'],font=(FONT,10)).pack(anchor='w',pady=(22,8))
        label(body,'For privacy, this is OFF by default. Embedded metadata may contain camera\n'
            'information or location data.',size=9,color='muted',justify='left').pack(anchor='w')
        GradientButton(panel,'SAVE & CLOSE',lambda:(self._persist_settings(notify=False),dialog.destroy()),
            height=40,font_size=10).pack(side='bottom',pady=12)

    @staticmethod
    def _optional_pixel(value):
        text = str(value).strip()
        if not text:
            return None
        if not text.isdecimal():
            raise ValueError('Pixel dimensions must be positive whole numbers.')
        return int(text)

    def _resize_summary(self):
        if not self.resize_enabled_var.get():
            return '↔   IMAGE RESIZER  •  OFF'
        if self.resize_mode_var.get() == 'Percent':
            return f'↔   IMAGE RESIZER  •  {self.resize_percent_var.get()}%'
        width = self.resize_width_var.get().strip() or 'Auto'
        height = self.resize_height_var.get().strip() or 'Auto'
        return f'↔   IMAGE RESIZER  •  {width} × {height}'

    def _current_options(self):
        percentage = self.resize_percent_var.get().strip()
        if not percentage.isdecimal():
            # A disabled resizer should never block regular image optimization.
            if self.resize_enabled_var.get() and self.resize_mode_var.get() == 'Percent':
                raise ValueError('Resize percentage must be a whole number.')
            percentage = '50'
        return Options(output_dir=self.folder_var.get(),output_format=self.format_var.get(),
                       quality=int(self.quality_var.get()),keep_metadata=self.metadata_var.get(),
                       filename_suffix=self.suffix_var.get(),smart=self.smart_var.get(),
                       smart_preset=self.smart_preset_var.get(),
                       resize_enabled=self.resize_enabled_var.get(),
                       resize_mode=self.resize_mode_var.get(),
                       resize_width=self._optional_pixel(self.resize_width_var.get()) if self.resize_enabled_var.get() and self.resize_mode_var.get() == 'Pixels' else None,
                       resize_height=self._optional_pixel(self.resize_height_var.get()) if self.resize_enabled_var.get() and self.resize_mode_var.get() == 'Pixels' else None,
                       resize_percent=int(percentage),
                       resize_lock_aspect=self.resize_lock_var.get(),
                       resize_allow_upscale=self.resize_upscale_var.get())

    def _show_resize_dialog(self):
        """Configure real resizing; settings are committed only on Apply."""
        dialog=tk.Toplevel(self)
        dialog.title('SoftRyva ImageFlow — Image Resizer')
        dialog.configure(bg=C['bg'])
        dialog.transient(self)
        dialog.minsize(455, 430)
        sw, sh=self.winfo_screenwidth(), self.winfo_screenheight()
        width=min(605,sw-45)
        height=min(610,sh-100)
        x=max(0,self.winfo_rootx()+(self.winfo_width()-width)//2)
        y=max(0,self.winfo_rooty()+(self.winfo_height()-height)//2)
        dialog.geometry(f'{width}x{height}+{x}+{y}')

        enabled=tk.BooleanVar(value=self.resize_enabled_var.get())
        mode=tk.StringVar(value=self.resize_mode_var.get())
        width_var=tk.StringVar(value=self.resize_width_var.get())
        height_var=tk.StringVar(value=self.resize_height_var.get())
        percent=tk.StringVar(value=self.resize_percent_var.get())
        locked=tk.BooleanVar(value=self.resize_lock_var.get())
        upscale=tk.BooleanVar(value=self.resize_upscale_var.get())
        panel=frame(dialog,'panel',border=True)
        panel.pack(fill='both',expand=True,padx=9,pady=9)
        label(panel,'↔   Image Resizer',size=19,bold=True,color='cyan').pack(anchor='w',padx=16,pady=(11,3))
        label(panel,'Resize photos by exact pixels or a percentage. Works with Batch Convert.',
              size=9,color='muted',wraplength=520,justify='left').pack(anchor='w',padx=16,pady=(0,9))

        buttons=frame(panel,'panel')
        buttons.pack(side='bottom',fill='x',padx=12,pady=(9,11))
        scroll=ScrollablePanel(panel,'panel')
        scroll.pack(fill='both',expand=True,padx=(10,8))
        body=frame(scroll.inner,'panel')
        body.pack(fill='both',expand=True,padx=(4,8),pady=6)
        def check(parent,text,var):
            return tk.Checkbutton(parent,text=text,variable=var,bg=C['panel'],fg=C['text'],
                activeforeground=C['text'],activebackground=C['panel'],selectcolor=C['raised'],
                font=(FONT,10,'bold'),anchor='w')
        check(body,'Enable image resizing during optimization',enabled).pack(anchor='w',pady=(0,10))
        label(body,'Resize mode',size=11,bold=True).pack(anchor='w',pady=(0,6))
        modes=frame(body,'panel')
        modes.pack(fill='x',pady=(0,7))
        for option in ('Pixels','Percent'):
            tk.Radiobutton(modes,text=option,variable=mode,value=option,
                bg=C['panel'],fg=C['text'],activebackground=C['panel'],
                activeforeground=C['cyan'],selectcolor=C['raised'],font=(FONT,10,'bold')).pack(side='left',padx=(0,26))
        pixels_block=frame(body,'panel2',border=True)
        pixels_block.pack(fill='x',pady=(0,8))
        label(pixels_block,'TARGET DIMENSIONS  •  PIXELS',size=10,bold=True,color='cyan').pack(anchor='w',padx=12,pady=(11,3))
        inputs=frame(pixels_block,'panel2')
        inputs.pack(fill='x',padx=10,pady=(4,4))
        for name,var in (('Width (px)',width_var),('Height (px)',height_var)):
            section=frame(inputs,'panel2')
            section.pack(side='left',fill='x',expand=True,padx=4)
            label(section,name,size=9,color='muted').pack(anchor='w',pady=(0,4))
            entry=tk.Entry(section,textvariable=var,bg=C['raised'],fg=C['text'],
                insertbackground=C['text'],font=(FONT,12),relief='flat',width=12)
            entry.pack(fill='x',ipady=7)
        check(pixels_block,'Keep original aspect ratio (recommended)',locked).pack(anchor='w',padx=12,pady=(9,4))
        label(pixels_block,'With aspect ratio locked, width/height are maximum bounds.\nLeave one field blank to resize by just that dimension.',
             size=9,color='muted',justify='left',wraplength=505).pack(anchor='w',padx=12,pady=(2,10))
        percent_block=frame(body,'panel2',border=True)
        percent_block.pack(fill='x',pady=(0,8))
        r=frame(percent_block,'panel2')
        r.pack(fill='x',padx=12,pady=11)
        label(r,'Scale (1–400%)',size=11,bold=True).pack(side='left')
        tk.Entry(r,textvariable=percent,bg=C['raised'],fg=C['text'],
                 insertbackground=C['text'],font=(FONT,12),relief='flat',width=8,justify='center').pack(side='right',ipady=5)
        check(body,'Allow enlarging smaller images',upscale).pack(anchor='w',pady=(4,9))
        preview_box=frame(body,'panel2',border=True)
        preview_box.pack(fill='x',pady=(0,10))
        label(preview_box,'LIVE DIMENSION PREVIEW',size=10,bold=True,color='cyan').pack(anchor='w',padx=12,pady=(8,3))
        preview=label(preview_box,'',size=10,color='text',justify='left',wraplength=500)
        preview.pack(anchor='w',padx=12,pady=(0,9))
        def calculate_opts():
            pct_text=percent.get().strip()
            if mode.get() == 'Percent' and enabled.get():
                if not pct_text.isdecimal():
                    raise ValueError('Percentage must be a whole number from 1 to 400.')
            pct = int(pct_text) if pct_text.isdecimal() else 50
            return replace(self._current_options(),
                resize_enabled=enabled.get(),resize_mode=mode.get(),
                resize_width=self._optional_pixel(width_var.get()) if enabled.get() and mode.get()=='Pixels' else None,
                resize_height=self._optional_pixel(height_var.get()) if enabled.get() and mode.get()=='Pixels' else None,
                resize_percent=pct,resize_lock_aspect=locked.get(),
                resize_allow_upscale=upscale.get())
        def refresh(*_):
            for block,active in ((pixels_block,mode.get()=='Pixels'),(percent_block,mode.get()=='Percent')):
                block.configure(highlightbackground=C['blue'] if active else C['line'])
            if not self.selected:
                preview.config(text='Add an image to see its target dimensions. Each batch image uses its own size.')
                return
            try:
                source=self.selected[self.preview_index]
                with Image.open(source) as picture:
                    size=ImageOps.exif_transpose(picture).size
                opts=calculate_opts()
                target=resize_dimensions(size,opts)
                prefix='Disabled: ' if not enabled.get() else ''
                preview.config(fg=C['green'],text=f'{prefix}{size[0]:,} × {size[1]:,} px  →  {target[0]:,} × {target[1]:,} px\n'
                  f'Preview: {source.name[:48]}')
            except (ValueError,OSError) as e:
                preview.config(fg=C['red'],text=str(e))
        for var in (enabled,mode,width_var,height_var,percent,locked,upscale):
            var.trace_add('write',refresh)
        refresh()
        def apply():
            try:
                opts=calculate_opts()
                opts.validate()
                # A preview of the requested dimensions must also be feasible.
                if enabled.get() and self.selected:
                    with Image.open(self.selected[self.preview_index]) as picture:
                        resize_dimensions(ImageOps.exif_transpose(picture).size,opts)
            except (ValueError,OSError) as e:
                messagebox.showerror('Invalid resize settings',str(e),parent=dialog)
                return
            self.resize_enabled_var.set(enabled.get())
            self.resize_mode_var.set(mode.get())
            self.resize_width_var.set(width_var.get().strip())
            self.resize_height_var.set(height_var.get().strip())
            self.resize_percent_var.set(percent.get().strip() if percent.get().strip().isdecimal() else '50')
            self.resize_lock_var.set(locked.get())
            self.resize_upscale_var.set(upscale.get())
            if not self._persist_settings(notify=False):
                return
            dialog.grab_release()
            dialog.destroy()
            if self.nav_name in ('Optimize','Batch Convert','Settings'):
                self._go(self.nav_name)
        GradientButton(buttons,'CANCEL',dialog.destroy,outline=True,
                       height=41,width=125,font_size=10).pack(side='left',padx=3)
        GradientButton(buttons,'APPLY RESIZE ✓',apply,start='#078aff',end='#ff9d29',
                       height=41,width=180,font_size=10).pack(side='right',padx=3)
        dialog.grab_set()
        dialog.focus_force()
        self._resize_dialog=dialog


    def _start_optimization(self):
        if self.processing:return
        if not self.selected:
            self._choose_files()
            if not self.selected:return
        try:
            opts=self._current_options()
            opts.validate()
        except ValueError as err:
            messagebox.showerror('Check settings',str(err),parent=self)
            return
        files=list(self.selected)
        self.last_run_results=[]
        self.processing=True
        self.optimize_btn.set_enabled(False)
        if self.progress_status is not None:
            self.progress_status.config(text=f'Processing 0 / {len(files)} images…')
        if hasattr(self,'progress') and self.progress.winfo_exists():
            self.progress['value']=0
        thread=threading.Thread(target=self._work,args=(files,opts),daemon=True)
        thread.start()

    def _work(self,files,opts):
        done=[]
        failed=[]
        for i,path in enumerate(files,1):
            try:
                result=optimize_image(path,opts)
                done.append(result)
                self._queue.put(('result',result))
            except Exception as err:
                failed.append((path.name,str(err)))
            self._queue.put(('progress',i,len(files)))
        self._queue.put(('finished',len(done),failed))

    def _process_events(self):
        try:
            while True:
                entry=self._queue.get_nowait()
                kind=entry[0]
                if kind=='result':
                    result=entry[1]
                    self.results.append(result)
                    self.last_run_results.append(result)
                    self.history.insert(0,{'when':datetime.now().isoformat(timespec='seconds'),**result.as_dict()})
                    self.history=self.history[:100]
                    try:safe_save_json(HISTORY_PATH,self.history)
                    except OSError:pass
                    if self.selected and Path(result.source)==self.selected[self.preview_index]:
                        self._load_preview()
                elif kind=='progress':
                    i,total=entry[1:]
                    if hasattr(self,'progress') and self.progress.winfo_exists():
                        self.progress['value']=i*100/max(total,1)
                    if self.progress_status is not None and self.progress_status.winfo_exists():
                        self.progress_status.config(text=f'Processing {i} / {total} images…')
                elif kind=='finished':
                    count,failed=entry[1:]
                    self.processing=False
                    if hasattr(self,'optimize_btn') and self.optimize_btn.winfo_exists():
                        self.optimize_btn.set_enabled(True)
                    msg=f'Completed: {count} image(s).'
                    if failed:
                        msg+=f'  •  Failed: {len(failed)}'
                    if self.progress_status is not None and self.progress_status.winfo_exists():
                        self.progress_status.config(text=msg)
                    self._load_preview()
                    if count:
                        self.last_output_dir=str(Path(self.last_run_results[-1].target).parent)
                        self.saved_banner.config(text=f'✓  {count} FILE(S) SAVED')
                        if hasattr(self,'destination_hint') and self.destination_hint.winfo_exists():
                            self.destination_hint.config(text='Saved to: '+self.last_output_dir)
                    elif failed:
                        self.saved_banner.config(text='⚠  NOTHING SAVED')
                    self._show_completion_dialog(count,failed)
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(100,self._process_events)

    def _show_completion_dialog(self,count,failed):
        # Always give explicit feedback for successful runs AND total failures.
        dialog=tk.Toplevel(self)
        dialog.title('SoftRyva ImageFlow — Processing result')
        dialog.configure(bg=C['bg'])
        dialog.resizable(False,False)
        dialog.transient(self)
        dialog.grab_set()
        resized=bool(count and self.last_run_results and
                 (self.last_run_results[-1].source_width != self.last_run_results[-1].target_width or
                  self.last_run_results[-1].source_height != self.last_run_results[-1].target_height))
        w,h=640,392 if failed else (346 if resized else 314)
        px=self.winfo_rootx()+max(0,(self.winfo_width()-w)//2)
        py=self.winfo_rooty()+max(0,(self.winfo_height()-h)//2)
        dialog.geometry(f'{w}x{h}+{px}+{py}')
        body=frame(dialog,'panel',border=True)
        body.pack(fill='both',expand=True,padx=12,pady=12)
        label(body,'✓  Images saved successfully' if count else '⚠  Processing failed',
              size=19,color='green' if count else 'red',bold=True).pack(anchor='w',padx=21,pady=(20,12))
        label(body,f'{count} image(s) saved.'+(f'  {len(failed)} failed.' if failed else ''),
              size=13).pack(anchor='w',padx=21)
        output=Path(self.last_run_results[-1].target).parent if count else Path(self.folder_var.get())
        label(body,'Output folder:',size=10,bold=True,color='muted').pack(anchor='w',padx=21,pady=(17,3))
        path_label=label(body,str(output),size=10,color='cyan',wraplength=575,justify='left')
        path_label.pack(anchor='w',padx=21)
        if count:
            last=self.last_run_results[-1]
            label(body,'Last image:  '+Path(last.target).name+'     '+
                  f'{readable_bytes(last.source_size)} → {readable_bytes(last.target_size)}',
                  size=10,color='muted',wraplength=585).pack(anchor='w',padx=21,pady=(11,0))
            if resized:
                label(body,f'Dimensions: {last.source_width} × {last.source_height}  →  '
                      f'{last.target_width} × {last.target_height} pixels',
                      size=10,color='cyan').pack(anchor='w',padx=21,pady=(5,0))
        if failed:
            details='; '.join(f'{f}: {reason}' for f,reason in failed[:2])
            label(body,'Errors: '+details,size=9,color='red',wraplength=580,justify='left').pack(anchor='w',padx=21,pady=(9,0))
        buttons=frame(body,'panel')
        buttons.pack(side='bottom',fill='x',padx=19,pady=17)
        def close_then(action):
            dialog.grab_release()
            dialog.destroy()
            action()
        if count:
            GradientButton(buttons,'OPEN FOLDER',lambda:close_then(lambda:self._open_path(output)),
                  height=42,width=150,start='#087fff',end='#0dc4ce',font_size=10).pack(side='left',padx=3)
            GradientButton(buttons,'SAVE AS…',lambda:close_then(self._save_as_last_result),
                  height=42,width=130,outline=True,font_size=10).pack(side='left',padx=3)
        GradientButton(buttons,'CLOSE',dialog.destroy,height=42,width=115,outline=True,font_size=10).pack(side='right')
        dialog.protocol('WM_DELETE_WINDOW',dialog.destroy)
        dialog.focus_force()
        self._completion_dialog=dialog

    def _add_combo(self,parent,variable,values,width=18):
        combo=ttk.Combobox(parent,textvariable=variable,values=values,width=width,state='readonly',
                           font=(FONT,10))
        style=ttk.Style()
        style.theme_use('clam')
        style.configure('TCombobox',fieldbackground=C['panel2'],background=C['raised'],
                        foreground=C['text'],bordercolor=C['line'],lightcolor=C['line'],
                        darkcolor=C['line'],selectbackground=C['blue'],selectforeground='white')
        return combo

    def _page_settings(self):
        self._heading(self.page_container,'⚙   Settings',
                      'Customize image optimization and local output preferences')
        settings_scroll=ScrollablePanel(self.page_container,'bg')
        settings_scroll.pack(fill='both',expand=True)
        outer=frame(settings_scroll.inner,'bg')
        outer.pack(fill='both',expand=True)
        inner=frame(outer,'panel',border=True)
        inner.pack(side='left',fill='both',expand=True,padx=(0,13))
        aside=frame(outer,'panel',border=True,width=277)
        if self.winfo_screenwidth()>1450:
            aside.pack(side='right',fill='y')
            aside.pack_propagate(False)
        content=frame(inner,'panel')
        content.pack(fill='both',expand=True,padx=18,pady=10)
        label(content,'GENERAL SETTINGS',size=16,bold=True).pack(anchor='w',pady=(0,9))
        label(content,'All preferences remain on your computer.',size=10,color='muted').pack(anchor='w',pady=(0,7))
        self._setting_separator(content)
        self._setting_row(content,'Output format','Choose what type of image to create.',
                          lambda parent:select_menu(parent,self.format_var,('Original','Auto','JPEG','PNG','WEBP'),width=14))
        self._setting_separator(content)
        self._setting_row(content,'Smart Compression','Evaluate several encodings and choose smallest acceptable result.',
                          lambda parent:tk.Checkbutton(parent,text='Enabled',variable=self.smart_var,
                                bg=C['panel'],fg=C['text'],activeforeground=C['cyan'],
                                activebackground=C['panel'],selectcolor=C['raised']))
        self._setting_separator(content)
        self._setting_row(content,'Smart preset','Quality-aware selection; not an AI or GPU feature.',
                          lambda parent:select_menu(parent,self.smart_preset_var,PRESETS,width=17))
        self._setting_separator(content)
        self._setting_row(content,'Default optimization level','1 = more compression, 100 = higher visual quality for JPEG/WebP.',
                          lambda parent:QualitySlider(parent,self.quality_var,width=191,height=35))
        self._setting_separator(content)
        self._setting_row(content,'Image Resizer','Pixels or percent; lock proportions for batches.',
                          lambda parent:GradientButton(parent,'CONFIGURE RESIZER',self._show_resize_dialog,
                                           height=35,width=170,font_size=9,outline=True))
        self._setting_separator(content)
        self._setting_row(content,'Preserve EXIF / ICC metadata','Default off for privacy; when on, store supported metadata.',
                          lambda parent:tk.Checkbutton(parent,variable=self.metadata_var,bg=C['panel'],
                               activebackground=C['panel'],selectcolor=C['raised'],activeforeground=C['text']))
        self._setting_separator(content)
        self._setting_row(content,'Output directory','Optimized files will be created here. Originals are never modified.',
                          lambda parent:GradientButton(parent,'CHOOSE FOLDER',self._choose_output,
                                          height=35,width=140,font_size=9,outline=True))
        folder_box=frame(content,'panel2',border=True)
        folder_box.pack(fill='x',pady=(4,9))
        label(folder_box,self.folder_var.get(),size=9,color='muted',wraplength=540,justify='left').pack(anchor='w',padx=13,pady=11)
        self.folder_var.trace_add('write',lambda *_: self._refresh_folder_label(folder_box))
        self._setting_separator(content)
        self._setting_row(content,'Filename suffix','Added to the name; duplicates receive _2, _3, etc.',
                          lambda parent:tk.Entry(parent,textvariable=self.suffix_var,width=18,
                                                bg=C['panel2'],fg=C['text'],insertbackground='white',
                                                relief='flat',font=(FONT,11)))
        self._setting_separator(content)
        label(content,'PNG is compressed losslessly; JPEG and WebP may lose visual detail.',
              size=9,color='muted',wraplength=570,justify='left').pack(anchor='w',pady=(8,5))
        actions=frame(content,'panel')
        actions.pack(side='bottom',fill='x',pady=(4,2))
        GradientButton(actions,'RESET DEFAULTS',self._reset_settings,outline=True,
                       height=44,width=156,font_size=10).pack(side='left')
        GradientButton(actions,'SAVE CHANGES  ✓',self._save_settings,
                       start='#0e94f9',end='#ff9d25',height=44,width=190,font_size=10).pack(side='right')

        aside_content=frame(aside,'panel')
        if self.winfo_screenwidth()>1450:
            aside_content.pack(fill='both',expand=True,padx=17,pady=19)
        label(aside_content,'✓  ACTUAL FEATURES',size=12,bold=True,color='cyan').pack(anchor='w',pady=(0,13))
        for title,sub in [('Local only','No images sent online'),
                          ('JPG / PNG / WebP','Format conversion and compression'),
                          ('Batch optimization','Many files in one run'),
                          ('Image Resizer','Pixel / percentage scaling; ratio lock'),
                          ('Safe file naming','Existing outputs kept intact'),
                          ('EXIF / ICC','Preserved only when requested')]:
            block=frame(aside_content,'panel2',border=True)
            block.pack(fill='x',pady=5)
            label(block,title,size=10,bold=True).pack(anchor='w',padx=11,pady=(10,2))
            label(block,sub,size=8,color='muted',wraplength=220,justify='left').pack(anchor='w',padx=11,pady=(0,11))
        label(aside_content,'ImageFlow v0.3.1',size=10,color='orange',bold=True).pack(side='bottom',pady=14)

    def _refresh_folder_label(self,folder_box):
        if not folder_box.winfo_exists():return
        for child in folder_box.winfo_children():
            if isinstance(child,tk.Label):child.configure(text=self.folder_var.get())

    def _setting_separator(self,parent):
        tk.Frame(parent,bg=C['line'],height=1).pack(fill='x',pady=2)

    def _setting_row(self,parent,title,explanation,build_widget):
        row=frame(parent,'panel',height=61)
        row.pack(fill='x',pady=(2,2))
        row.pack_propagate(False)
        left=frame(row,'panel')
        left.pack(side='left',fill='both',expand=True)
        label(left,title,size=11,bold=True).pack(anchor='w',pady=(3,4))
        label(left,explanation,size=8,color='muted',wraplength=440,justify='left').pack(anchor='w')
        right=frame(row,'panel',width=205)
        right.pack(side='right',fill='y')
        right.pack_propagate(False)
        widget=build_widget(right)
        widget.pack(side='right',padx=6,pady=9)

    def _persist_settings(self,notify=True):
        try:
            self._current_options().validate()
            safe_save_json(PREFS_PATH,{
                'output_dir':self.folder_var.get(), 'format':self.format_var.get(),
                'quality':self.quality_var.get(),'keep_metadata':self.metadata_var.get(),
                'suffix':self.suffix_var.get(),
                'smart':self.smart_var.get(),'smart_preset':self.smart_preset_var.get(),
                'resize_enabled':self.resize_enabled_var.get(),
                'resize_mode':self.resize_mode_var.get(),
                'resize_width':self.resize_width_var.get().strip() or None,
                'resize_height':self.resize_height_var.get().strip() or None,
                'resize_percent':self.resize_percent_var.get(),
                'resize_lock_aspect':self.resize_lock_var.get(),
                'resize_allow_upscale':self.resize_upscale_var.get()})
        except (ValueError,OSError) as err:
            messagebox.showerror('Settings error',str(err),parent=self)
            return
        if notify:
            messagebox.showinfo('Settings saved','Preferences saved locally on this computer.',parent=self)
        return True

    def _save_settings(self):
        self._persist_settings(notify=True)

    def _reset_settings(self):
        self.folder_var.set(str(DEFAULT_FOLDER))
        self.format_var.set('Original')
        self.quality_var.set(75)
        self.metadata_var.set(False)
        self.suffix_var.set('_optimized')
        self.smart_var.set(True)
        self.smart_preset_var.set('Balanced')
        self.resize_enabled_var.set(False)
        self.resize_mode_var.set('Pixels')
        self.resize_width_var.set('')
        self.resize_height_var.set('')
        self.resize_percent_var.set('50')
        self.resize_lock_var.set(True)
        self.resize_upscale_var.set(False)
        self._go('Settings')

    def _page_dashboard(self):
        self._heading(self.page_container,'Dashboard', 'Local image processing overview')
        totals=frame(self.page_container,'bg')
        totals.pack(fill='x',pady=(0,14))
        total_before=sum(int(h.get('source_size',0)) for h in self.history if isinstance(h,dict))
        total_after=sum(int(h.get('target_size',0)) for h in self.history if isinstance(h,dict))
        for title,value in [('Total Images',str(len(self.history))),('Original Data',readable_bytes(total_before)),
                            ('Output Data',readable_bytes(total_after)),('Net Savings',readable_bytes(total_before-total_after))]:
            stat=frame(totals,'panel',border=True)
            stat.pack(side='left',fill='both',expand=True,padx=5)
            label(stat,title,size=10,color='muted').pack(pady=(20,9))
            label(stat,value,size=20,bold=True,color='cyan').pack(pady=(0,22))
        actions=frame(self.page_container,'bg')
        actions.pack(fill='x',pady=(0,11))
        GradientButton(actions,'OPEN LATEST RESULT',self._open_latest_file,
             height=36,width=180,outline=True,font_size=9).pack(side='left',padx=(0,8))
        GradientButton(actions,'VIEW HISTORY',lambda:self._go('History'),
             height=36,width=140,font_size=9).pack(side='left')
        self._simple_panel('Recent activity',self._history_lines()[:15],fill=True)

    def _history_lines(self):
        entries=[]
        for item in self.history:
            if not isinstance(item,dict):continue
            timestamp=str(item.get('when',''))[:16].replace('T','  ')
            filename=Path(str(item.get('source','Image'))).name
            before=readable_bytes(int(item.get('source_size',0)))
            after=readable_bytes(int(item.get('target_size',0)))
            pct=float(item.get('reduction_percent',0))
            entries.append(f'{timestamp}     {filename}\n   {before}  →  {after}     ({pct:+.1f}%)')
        return entries or ['No processing history yet. Choose images in Optimize to begin.']

    def _page_history(self):
        self._heading(self.page_container,'History','Double-click a saved result to open it')
        card=frame(self.page_container,'panel',border=True)
        card.pack(fill='both',expand=True)
        top=frame(card,'panel')
        top.pack(fill='x',padx=18,pady=(14,9))
        GradientButton(top,'OPEN SELECTED IMAGE',lambda:self._history_action('file'),
                 height=38,width=193,font_size=9).pack(side='left',padx=(0,8))
        GradientButton(top,'OPEN FOLDER',lambda:self._history_action('folder'),
                 height=38,width=145,font_size=9,outline=True).pack(side='left')
        GradientButton(top,'CLEAR HISTORY',self._clear_history,
                 height=38,width=150,font_size=9,outline=True).pack(side='right')
        listframe=frame(card,'panel')
        listframe.pack(fill='both',expand=True,padx=20,pady=(0,18))
        scrollbar=tk.Scrollbar(
            listframe, width=comfortable_scrollbar_width(listframe),
            bg=C['blue'], troughcolor=C['side'], activebackground=C['cyan'],
            bd=0, relief='flat', highlightthickness=0, elementborderwidth=2,
            cursor='hand2')
        scrollbar.pack(side='right',fill='y')
        self.history_list=tk.Listbox(listframe,bg=C['side'],fg=C['text'],
                 selectbackground=C['blue'],yscrollcommand=scrollbar.set,
                 font=(FONT,11),bd=0,highlightthickness=1,highlightcolor=C['cyan'],
                 activestyle='none')
        self.history_list.pack(fill='both',expand=True)
        scrollbar.config(command=self.history_list.yview)
        self._history_view_items=[h for h in self.history if isinstance(h,dict)]
        for entry in self._history_view_items:
            path=Path(str(entry.get('target','missing'))).name
            pct=float(entry.get('reduction_percent',0))
            when=str(entry.get('when',''))[:16].replace('T',' ')
            suffix='' if Path(str(entry.get('target',''))).is_file() else '  [not found]'
            self.history_list.insert('end',f'{when}   {path}    ({pct:+.1f}%){suffix}')
        if self._history_view_items:self.history_list.selection_set(0)
        else:self.history_list.insert('end','No saved results yet.')
        self.history_list.bind('<Double-Button-1>',lambda _e:self._history_action('file'))

    def _history_action(self,action):
        if not hasattr(self,'history_list') or not self.history_list.winfo_exists():return
        indices=self.history_list.curselection()
        if not indices or indices[0]>=len(self._history_view_items):
            messagebox.showinfo('History','Select a saved image first.',parent=self)
            return
        item=self._history_view_items[indices[0]]
        path=Path(str(item.get('target','')))
        self._open_path(path if action=='file' else path.parent)

    def _open_latest_file(self):
        result=self._last_saved_result()
        if result:self._open_path(result.target)
        else:messagebox.showinfo('ImageFlow','No optimized image has been saved yet.',parent=self)

    def _clear_history(self):
        if not self.history:return
        if not messagebox.askyesno('Clear history',
                'Remove processing history entries?\nThe actual optimized images will NOT be deleted.',parent=self):return
        self.history=[]
        try:safe_save_json(HISTORY_PATH,self.history)
        except OSError as err:
            messagebox.showerror('History error',str(err),parent=self)
            return
        self._go('History')

    def _page_images(self):
        self._heading(self.page_container,'My Images',f'{len(self.selected)} image(s) in your current selection')
        panel=frame(self.page_container,'panel',border=True)
        panel.pack(fill='both',expand=True)
        inner=frame(panel,'panel')
        inner.pack(fill='both',expand=True,padx=24,pady=20)
        actions=frame(inner,'panel')
        actions.pack(fill='x',pady=(0,14))
        GradientButton(actions,'ADD IMAGES +',self._choose_files,width=145,height=39,font_size=9).pack(side='left',padx=(0,8))
        GradientButton(actions,'PREVIEW SELECTED',lambda:open_selected(None),
            width=180,height=39,font_size=9,outline=True).pack(side='left',padx=(0,8))
        GradientButton(actions,'REMOVE SELECTED',lambda:remove_selected(),
            width=180,height=39,font_size=9,outline=True).pack(side='left',padx=(0,8))
        GradientButton(actions,'CLEAR LIST',lambda:clear_list(),
            width=120,height=39,font_size=9,outline=True).pack(side='right')
        lst=tk.Listbox(inner,bg=C['side'],fg=C['text'],selectbackground=C['blue'],
                       font=(FONT,11),bd=0,highlightthickness=1,highlightcolor=C['cyan'])
        lst.pack(fill='both',expand=True)
        for file in self.selected:lst.insert('end',str(file))
        def open_selected(_):
            selection=lst.curselection()
            if selection:
                self.preview_index=selection[0]
                self._load_preview()
                self._go('Optimize')
        def remove_selected():
            selected=lst.curselection()
            if not selected:return
            for i in reversed(selected):
                self.selected.pop(i)
                lst.delete(i)
            self.preview_index=min(self.preview_index,max(0,len(self.selected)-1))
            if self.selected:self._load_preview()
            else:
                self._preview_source=None
                self._preview_result=None
        def clear_list():
            if not self.selected:return
            self.selected.clear()
            lst.delete(0,'end')
            self.preview_index=0
            self._preview_source=None
            self._preview_result=None
        lst.bind('<Double-Button-1>',open_selected)
        label(inner,'Double-click an image to view it in Optimize.',size=9,color='muted').pack(anchor='w',pady=(9,0))

    def _page_support(self):
        self._heading(self.page_container,'About & Support','SoftRyva ImageFlow  •  desktop image optimization')
        self._simple_panel('About ImageFlow',[
            'Version 0.3.1 — setup-ready candidate',
            'Processes JPEG, PNG and WebP files locally on your device.',
            'Image Resizer: pixel or percentage scaling, optional aspect ratio lock and upscaling.',
            'Batch operations, real before/after comparison, and local history are available.',
            'No login, no internet requests, no uploads; Smart Compression is encoder selection, not AI.',
            'To report a bug, note the filename, input format and error message.',
            'SoftRyva Development contributors — Copyright (C) 2026 (attribution to be verified before public release).',
            'Source code: GNU GPL v3 only (GPL-3.0-only). You may share or modify it under LICENSE.',
            'NO WARRANTY: This software is provided without any warranty, to the extent permitted by law.',
            'The complete license text is supplied as LICENSE with the source code and installer.',
            'SoftRyva is a project/brand name; trademark rights are separate from GPL licensing.'
        ],fill=True)

    def _simple_panel(self,title,lines,fill=False):
        panel=frame(self.page_container,'panel',border=True)
        panel.pack(fill='both' if fill else 'x',expand=fill)
        content=frame(panel,'panel')
        content.pack(fill='both',expand=True,padx=25,pady=22)
        label(content,title,size=16,bold=True).pack(anchor='w',pady=(0,14))
        textw=tk.Text(content,wrap='word',bg=C['side'],fg=C['text'],selectbackground=C['blue'],
                      relief='flat',bd=0,padx=20,pady=13,font=(FONT,11),spacing3=13)
        textw.pack(fill='both',expand=True)
        textw.insert('end','\n\n'.join(lines))
        textw.config(state='disabled')

    def _exit(self):
        if self.processing:
            if not messagebox.askyesno('Processing images','Images are still processing. Close the app?',parent=self):
                return
        self.destroy()


def main():
    ImageFlowApp().mainloop()


if __name__ == '__main__':
    main()
