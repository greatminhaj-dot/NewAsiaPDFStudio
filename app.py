"""NewAsiaPDFStudio - local-first Windows desktop PDF editor."""
from __future__ import annotations
import io
import os
import sys
import subprocess
import tempfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, colorchooser
from PIL import Image, ImageTk
from pdf_core import PDFDocument

BG = '#f3f5f8'
NAVY = '#20252c'
BLUE = '#3a983a'
ORANGE = '#e77522'
WHITE = '#ffffff'
APP_NAME = 'NewAsiaPDFStudio'
RESOURCE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
LOGO_PATH = RESOURCE_DIR / 'assets' / 'newasia_logo.png'

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('NewAsiaPDFStudio — PDF Editor')
        # Windows taskbar groups the bundled application under its own product identity.
        if sys.platform == 'win32':
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('NewAsiaGroup.NewAsiaPDFStudio.3')
            except Exception:
                pass
        self.geometry('1440x860')
        self.minsize(850, 550)
        self.configure(bg=BG)
        self.pdf = PDFDocument()
        self.current = 0
        self.zoom = 1.25
        self.mode = 'select'
        self.image = None
        self.drag = None
        self.selection_id = None
        self.selected_span = None
        self.preferred_font = ''
        self._thumb_refs = []
        self._thumb_signature = None
        self._thumb_wheel_accum = 0.0
        self._file_arg = next((arg for arg in sys.argv[1:] if arg.lower().endswith('.pdf') and os.path.isfile(arg)), None)
        self._build()
        self.pdf.new()
        if self._file_arg:
            try: self.pdf.open(self._file_arg)
            except Exception as exc: messagebox.showerror('Open failed', str(exc))
        self.refresh()
        self.protocol('WM_DELETE_WINDOW', self.close_app)
        # Finder 'Open With' / opening a PDF from the Dock in a packaged macOS app.
        # The first command-line document is already handled above; this handles
        # additional native Apple OpenDocument events delivered to Tk after launch.
        if sys.platform == 'darwin':
            try:
                self.createcommand('::tk::mac::OpenDocument', self._mac_open_document)
            except tk.TclError:
                pass

        self.bind_all('<Control-o>', lambda e: self.open_pdf())
        self.bind_all('<Control-s>', lambda e: self.save_pdf())
        self.bind_all('<Control-z>', lambda e: self.action(self.pdf.undo))
        self.bind_all('<Control-y>', lambda e: self.action(self.pdf.redo))
        self.bind_all('<Command-o>', lambda e: self.open_pdf())
        self.bind_all('<Command-s>', lambda e: self.save_pdf())
        self.bind_all('<Command-z>', lambda e: self.action(self.pdf.undo))
        self.bind_all('<Command-Shift-Z>', lambda e: self.action(self.pdf.redo))

    def _build(self):
        style = ttk.Style(self)
        if 'clam' in style.theme_names(): style.theme_use('clam')
        style.configure('App.TFrame', background=BG)
        style.configure('Tool.TButton', font=('Arial', 10), padding=(8, 5))
        style.configure('Accent.TButton', background=BLUE, foreground='white', padding=(12, 7))
        style.map('Accent.TButton', background=[('active', '#26782c')])
        self.logo = None
        if LOGO_PATH.exists():
            try:
                logo_img = Image.open(LOGO_PATH).convert('RGBA')
                logo_img.thumbnail((42, 36), Image.Resampling.LANCZOS)
                self.logo = ImageTk.PhotoImage(logo_img)
                self.iconphoto(True, self.logo)
            except Exception: pass

        # Desktop document tabs and app branding.
        titlebar = tk.Frame(self, bg=NAVY, height=53)
        titlebar.pack(fill='x')
        titlebar.pack_propagate(False)
        brand = tk.Frame(titlebar, bg=NAVY)
        brand.pack(side='left', padx=(17, 18))
        if self.logo:
            tk.Label(brand, image=self.logo, bg=NAVY).pack(side='left', padx=(0, 7))
        tk.Label(brand, text=APP_NAME, font=('Segoe UI', 16, 'bold'), bg=NAVY,
                 fg=WHITE).pack(side='left')
        self.doc_tab = tk.Label(titlebar, text='Untitled.pdf  ×', font=('Segoe UI', 10),
                                fg='#f5f7fa', bg='#353c45', padx=17, pady=13)
        self.doc_tab.pack(side='left', padx=5)
        tk.Button(titlebar, text='+', command=self.open_pdf, bg=NAVY, fg=WHITE,
                  relief='flat', bd=0, font=('Segoe UI', 17), cursor='hand2').pack(side='left', padx=5)
        tk.Label(titlebar, text='PRIVATE · LOCAL FILES', bg=NAVY, fg='#bdc7cc',
                 font=('Segoe UI', 9)).pack(side='right', padx=23)

        # Category ribbon similar in organization to established editors.
        tabs = tk.Frame(self, bg=WHITE, height=39)
        tabs.pack(fill='x')
        tabs.pack_propagate(False)
        self.ribbon_tabs = {}
        for tab in ['Home', 'Annotate', 'Edit', 'Pages', 'Form', 'Tools', 'Protect']:
            btn = tk.Button(tabs, text=tab, bg=WHITE, fg='#202329', bd=0,
                            activebackground='#f8faf8', font=('Arial', 10),
                            padx=16, pady=7, cursor='hand2',
                            command=lambda t=tab: self.show_ribbon(t))
            btn.pack(side='left', padx=(10 if tab == 'Home' else 1, 0))
            self.ribbon_tabs[tab] = btn
        for text, fn in [('Save', self.save_pdf), ('Open', self.open_pdf)]:
            tk.Button(tabs, text=text, command=fn, bg=WHITE, bd=0,
                      font=('Segoe UI', 10), fg='#4a515b', padx=13).pack(side='right')
        self.ribbon = tk.Frame(self, bg='#fafbfc', height=65, highlightthickness=1,
                               highlightbackground='#e1e5e9')
        self.ribbon.pack(fill='x')
        self.ribbon.pack_propagate(False)
        self.show_ribbon('Home')

        center = tk.Frame(self, bg=BG)
        center.pack(fill='both', expand=True)
        self.toolrail = tk.Frame(center, bg='#fefefe', width=51,
                                 highlightbackground='#e0e4e8', highlightthickness=1)
        self.toolrail.pack(side='left', fill='y')
        self.toolrail.pack_propagate(False)
        for symbol, label, cmd in [('▤','Thumbnails',lambda: self.toggle_sidebar()),
                                   ('⌕','Find',self.find_text),
                                   ('✎','Edit',lambda: self.set_mode('edit')),
                                   ('▧','Pages',lambda: self.show_ribbon('Pages'))]:
            tk.Button(self.toolrail, text=symbol, command=cmd, bg=WHITE,
                      fg='#273139', font=('Segoe UI Symbol', 17), relief='flat', bd=0,
                      cursor='hand2').pack(fill='x', pady=7, ipady=3)
        self.sidebar = tk.Frame(center, bg=WHITE, width=222,
                                highlightbackground='#dce1e6', highlightthickness=1)
        self.sidebar.pack(side='left', fill='y')
        self.sidebar.pack_propagate(False)
        sidetop = tk.Frame(self.sidebar, bg=WHITE)
        sidetop.pack(fill='x', pady=(12, 8))
        tk.Label(sidetop, text='Thumbnails', font=('Segoe UI', 11, 'bold'),
                 bg=WHITE, fg='#273139').pack(side='left', padx=12)
        tk.Button(sidetop, text='×', command=self.toggle_sidebar, relief='flat', bd=0,
                  bg=WHITE, font=('Segoe UI', 15)).pack(side='right', padx=12)
        self.thumb_canvas = tk.Canvas(self.sidebar, bg=WHITE, borderwidth=0,
                                      highlightthickness=0)
        self.thumb_canvas.pack(side='left', fill='both', expand=True)
        thumb_scroll = ttk.Scrollbar(self.sidebar, command=self.thumb_canvas.yview)
        thumb_scroll.pack(side='right', fill='y')
        self.thumb_canvas.configure(yscrollcommand=thumb_scroll.set)
        self.thumb_content = tk.Frame(self.thumb_canvas, bg=WHITE)
        self.thumb_window = self.thumb_canvas.create_window((0, 0), window=self.thumb_content, anchor='nw', tags='body')
        self.thumb_content.bind('<Configure>', self._update_thumbnail_scrollregion)
        self.thumb_canvas.bind('<Configure>', self._resize_thumbnail_content)
        # A dedicated bindtag allows scrolling when the pointer is over a thumbnail,
        # its frame or page number, not just the narrow scrollbar.
        self.bind_class('NewAsiaThumbnailWheel', '<MouseWheel>', self._scroll_thumbnails)
        self.bind_class('NewAsiaThumbnailWheel', '<Button-4>', lambda e: self._scroll_thumbnails_linux(-1))
        self.bind_class('NewAsiaThumbnailWheel', '<Button-5>', lambda e: self._scroll_thumbnails_linux(1))
        self._enable_thumbnail_wheel(self.thumb_canvas)
        self._enable_thumbnail_wheel(self.thumb_content)

        viewer = tk.Frame(center, bg=BG)
        self.viewer = viewer
        viewer.pack(side='left', fill='both', expand=True)
        wrapper = tk.Frame(viewer, bg=BG)
        wrapper.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(wrapper, bg='#e9edf2', highlightthickness=0, cursor='arrow')
        vs = ttk.Scrollbar(wrapper, orient='vertical', command=self.canvas.yview)
        hs = ttk.Scrollbar(wrapper, orient='horizontal', command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.canvas.grid(row=0, column=0, sticky='nsew', padx=(8, 0), pady=(7, 0))
        vs.grid(row=0, column=1, sticky='ns', pady=(7, 0))
        hs.grid(row=1, column=0, sticky='ew')
        wrapper.columnconfigure(0, weight=1)
        wrapper.rowconfigure(0, weight=1)
        self.canvas.bind('<ButtonPress-1>', self.mouse_down)
        self.canvas.bind('<Double-Button-1>', self.double_click)
        self.canvas.bind('<B1-Motion>', self.mouse_move)
        self.canvas.bind('<ButtonRelease-1>', self.mouse_up)
        self.canvas.bind('<MouseWheel>', self.mouse_wheel)
        self.canvas.bind('<Button-4>', lambda e: self.canvas.yview_scroll(-3, 'units'))
        self.canvas.bind('<Button-5>', lambda e: self.canvas.yview_scroll(3, 'units'))

        self.utilityrail = tk.Frame(center, width=48, bg='#fdfdfd',
                                    highlightthickness=1, highlightbackground='#e1e5e9')
        self.utilityrail.pack(side='right', fill='y')
        self.utilityrail.pack_propagate(False)
        for sym, cmd in [('⚙', lambda: self.show_ribbon('Tools')),
                         ('⊞', lambda: self.show_ribbon('Pages')),
                         ('✎', lambda: self.set_mode('note'))]:
            tk.Button(self.utilityrail, text=sym, bg=WHITE, bd=0, relief='flat',
                      font=('Segoe UI Symbol', 16), command=cmd).pack(fill='x', pady=11)

        bottom = tk.Frame(self, bg=WHITE, height=44,
                          highlightthickness=1, highlightbackground='#e1e5e9')
        bottom.pack(fill='x')
        bottom.pack_propagate(False)
        self.status = tk.StringVar(value='Ready')
        tk.Label(bottom, textvariable=self.status, bg=WHITE, fg='#64707c',
                 font=('Segoe UI', 9), anchor='w').pack(side='left', padx=15)
        tk.Button(bottom, text='−', command=lambda: self.change_zoom(-.15),
                  bg=WHITE, relief='flat', font=('Segoe UI', 15)).pack(side='right', padx=(2,8))
        self.zoom_label = tk.Label(bottom, bg='#f5f7f9', text='125%',
                                   font=('Segoe UI', 10), padx=7)
        self.zoom_label.pack(side='right')
        tk.Button(bottom, text='+', command=lambda: self.change_zoom(.15),
                  bg=WHITE, relief='flat', font=('Segoe UI', 15)).pack(side='right', padx=6)
        tk.Button(bottom, text='▶', command=lambda: self.goto_page(1),
                  bg=WHITE, relief='flat').pack(side='right', padx=2)
        self.page_indicator = tk.Label(bottom, text='1 / 1', bg=WHITE,
                                       font=('Segoe UI', 10), padx=12)
        self.page_indicator.pack(side='right')
        tk.Button(bottom, text='◀', command=lambda: self.goto_page(-1),
                  bg=WHITE, relief='flat').pack(side='right', padx=2)

    def show_ribbon(self, name):
        self.active_ribbon = name
        for key, tab in self.ribbon_tabs.items():
            tab.config(fg=ORANGE if key == name else '#242930',
                       font=('Arial', 10, 'bold' if key == name else 'normal'))
        for child in self.ribbon.winfo_children(): child.destroy()
        sections = {
            'Home': [('Select','select'), ('Hand','hand'), ('Highlight','highlight'),
                     ('Shapes','rectangle'), ('Text','text'), ('Edit Text','edit'),
                     ('Signature','signature'), ('Stamp','stamp'), ('OCR',self.ocr),
                     ('Redact','redact'), ('Print',self.print_pdf)],
            'Annotate': [('Highlight','highlight'), ('Rectangle','rectangle'),
                         ('Comment','note'), ('Signature','signature'), ('Stamp','stamp')],
            'Edit': [('Edit Text','edit'), ('Move Text','move'), ('Add Text','text'),
                     ('Replace Text','replace'), ('Insert Image','image'),
                     ('Undo',lambda: self.action(self.pdf.undo)),
                     ('Redo',lambda: self.action(self.pdf.redo))],
            'Pages': [('Add Page',self.add_page), ('Delete Page',self.delete_page),
                      ('Rotate',self.rotate_page), ('Move Up',lambda:self.move_page(-1)),
                      ('Move Down',lambda:self.move_page(1)), ('Merge PDFs',self.merge),
                      ('Extract',self.extract)],
            'Form': [('Add Text','text'), ('Signature','signature'), ('Comment','note')],
            'Tools': [('Find',self.find_text), ('Watermark',self.watermark),
                      ('OCR',self.ocr), ('Export',self.export), ('Save As',lambda:self.save_pdf(True))],
            'Protect': [('Redact','redact'), ('Save As',lambda:self.save_pdf(True))],
        }
        icons = {'Select':'↖','Hand':'☞','Highlight':'▰','Shapes':'▢','Text':'T',
                 'Edit Text':'✎','Signature':'✒','Stamp':'▣','OCR':'▧',
                 'Redact':'▥','Print':'▤','Rectangle':'▢','Comment':'▤',
                 'Move Text':'↔','Add Text':'T','Replace Text':'✎','Insert Image':'▧',
                 'Undo':'↶','Redo':'↷','Add Page':'+','Delete Page':'×','Rotate':'↻',
                 'Move Up':'↑','Move Down':'↓','Merge PDFs':'▦','Extract':'⇥',
                 'Find':'⌕','Watermark':'W','Export':'⇩','Save As':'▣'}
        for label, target in sections[name]:
            command = (lambda m=target: self.set_mode(m)) if isinstance(target, str) else target
            cell = tk.Frame(self.ribbon, bg='#fafbfc', width=75)
            cell.pack(side='left', fill='y', padx=1, pady=3)
            cell.pack_propagate(False)
            tk.Button(cell, text=icons.get(label, '•') + '\n' + label,
                      command=command, relief='flat', bd=0, bg='#fafbfc',
                      fg='#262b2f', activebackground='#eaf3e9',
                      font=('Arial', 9), cursor='hand2', justify='center',
                      pady=2).pack(fill='both', expand=True)

    def toggle_sidebar(self):
        if self.sidebar.winfo_manager(): self.sidebar.pack_forget()
        else: self.sidebar.pack(side='left', before=self.viewer, fill='y')

    def goto_page(self, offset):
        target = self.current + offset
        if 0 <= target < self.pdf.count:
            self.current = target
            self.refresh()

    def find_text(self):
        phrase = simpledialog.askstring('Find text', 'Find in PDF:', parent=self)
        if not phrase: return
        for page_index in list(range(self.current, self.pdf.count)) + list(range(0,self.current)):
            matches = self.pdf.doc[page_index].search_for(phrase)
            if matches:
                self.current = page_index
                self.selected_span = None
                self.refresh()
                box = matches[0]
                self.canvas.create_rectangle(self.margin+box.x0*self.zoom,
                    self.margin+box.y0*self.zoom, self.margin+box.x1*self.zoom,
                    self.margin+box.y1*self.zoom, outline=ORANGE, width=3,
                    tags='find-match')
                self.status.set(f'Found on page {page_index+1}: {phrase}')
                return
        messagebox.showinfo('Find', 'Text not found. Scanned PDFs may need OCR.', parent=self)

    def print_pdf(self):
        """Print the current (including unsaved) PDF via the OS spooler.

        On macOS `lp` sends a job to the selected/default printer; provide
        Preview as an explicit fallback for choosing page ranges and settings.
        """
        if not self.pdf.doc or self.pdf.count == 0:
            messagebox.showwarning('Print', 'Open a PDF first.', parent=self)
            return
        if sys.platform == 'darwin':
            response = messagebox.askyesnocancel(
                'Print PDF',
                'Yes: print all pages to the default printer.\n'
                'No: open in Preview to choose printer, page range and settings.\n'
                'Cancel: do nothing.', parent=self)
        else:
            response = messagebox.askyesnocancel(
                'Print PDF',
                'Yes: send all pages to the default printer.\n'
                'No: open in the default PDF viewer for printing.\n'
                'Cancel: do nothing.', parent=self)
        if response is None:
            return
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.pdf', prefix='NewAsiaPDFStudio_print_',
                                             delete=False) as temporary:
                temp_path = temporary.name
                temporary.write(self.pdf.doc.tobytes(garbage=3, deflate=True))
            if response is False:
                if sys.platform == 'darwin':
                    subprocess.Popen(['open', '-a', 'Preview', temp_path])
                elif sys.platform == 'win32':
                    os.startfile(temp_path)
                else:
                    subprocess.Popen(['xdg-open', temp_path])
                # Keep temporary file so the viewer can read it after launch.
                temp_path = None
            elif sys.platform == 'win32':
                # Windows delegates printing to the registered PDF application's print verb.
                # Some viewers do not register this verb; offer opening the file instead.
                try:
                    os.startfile(temp_path, 'print')
                    temp_path = None  # The PDF handler might read asynchronously.
                    messagebox.showinfo('Print', 'Print command sent to your default PDF application.', parent=self)
                except OSError as print_error:
                    if messagebox.askyesno('Print unavailable',
                                          'Your default PDF viewer does not support direct printing.\n'
                                          'Open this PDF in your viewer to print with Ctrl+P?\n\n'
                                          f'Details: {print_error}', parent=self):
                        os.startfile(temp_path)
                        temp_path = None
            else:
                result = subprocess.run(['lp', temp_path], capture_output=True, text=True)
                if result.returncode:
                    raise RuntimeError(result.stderr.strip() or 'No printer is configured.')
                messagebox.showinfo('Print', result.stdout.strip() or 'Print job submitted.', parent=self)
        except Exception as exc:
            messagebox.showerror('Print failed', str(exc), parent=self)
        finally:
            if temp_path and os.path.isfile(temp_path):
                try: os.unlink(temp_path)
                except OSError: pass

    def _enable_thumbnail_wheel(self, widget):
        tags = widget.bindtags()
        if 'NewAsiaThumbnailWheel' not in tags:
            widget.bindtags(('NewAsiaThumbnailWheel',) + tags)

    def _update_thumbnail_scrollregion(self, _event=None):
        self.thumb_canvas.configure(scrollregion=self.thumb_canvas.bbox('all'))

    def _resize_thumbnail_content(self, event):
        self.thumb_canvas.itemconfigure(self.thumb_window, width=event.width)
        self._update_thumbnail_scrollregion()

    def _scroll_thumbnails_linux(self, direction):
        self.thumb_canvas.yview_scroll(direction * 3, 'units')
        return 'break'

    def _scroll_thumbnails(self, event):
        # macOS trackpads commonly deliver small deltas (1-10), not ±120.
        delta = event.delta
        if sys.platform == 'darwin':
            units = -round(delta * 2)
        else:
            units = -round(delta / 120 * 3)
        if not units and delta:
            units = -1 if delta > 0 else 1
        self.thumb_canvas.yview_scroll(units, 'units')
        return 'break'

    def stamp(self, *args):
        content = simpledialog.askstring('Stamp', 'Stamp text:', parent=self)
        if content:
            self.action(self.pdf.add_text, self.current, 50, 50, content, 22, (.2, .6, .2))

    def set_mode(self, mode):
        self.mode = mode
        self.selected_span = None
        self.status.set('Tool: ' + mode + ' | Click on the document' + (' and drag to select a rectangle' if mode in ('replace','highlight','redact','rectangle','image','signature') else ''))

    def refresh(self):
        if self.pdf.count == 0: return
        self.current = max(0, min(self.current, self.pdf.count - 1))
        self.zoom_label.configure(text=f'{round(self.zoom*100)}%')
        self.page_indicator.configure(text=f'{self.current+1} / {self.pdf.count}')
        self._refresh_thumbnails()
        png = self.pdf.render(self.current, self.zoom)
        img = Image.open(io.BytesIO(png))
        self.image = ImageTk.PhotoImage(img)
        self.canvas.delete('all')
        self.margin = 30
        self.canvas.create_rectangle(self.margin+4, self.margin+4,
                                     self.margin+img.width+4, self.margin+img.height+4,
                                     fill='#b9c2cb', outline='')
        self.canvas.create_image(self.margin, self.margin, image=self.image, anchor='nw')
        self.canvas.configure(scrollregion=(0,0,img.width+70,img.height+70))
        if self.selected_span: self.draw_text_selection()
        self.status.set(f'Page {self.current+1} / {self.pdf.count}  ·  {self.mode.title()}  ·  '
                        + ('Unsaved changes' if self.pdf.dirty else 'Saved'))
        filename = os.path.basename(self.pdf.path) if self.pdf.path else 'Untitled.pdf'
        self.title(APP_NAME + ' — ' + filename + (' *' if self.pdf.dirty else ''))
        self.doc_tab.configure(text=filename[:32] + ('…' if len(filename)>32 else '') +
                               (' *' if self.pdf.dirty else '') + '  ×')

    def _refresh_thumbnails(self):
        signature = (self.pdf.count, self.current, id(self.pdf.doc), self.pdf.dirty)
        if signature == self._thumb_signature: return
        self._thumb_signature = signature
        for child in self.thumb_content.winfo_children(): child.destroy()
        self._thumb_refs = []
        for i in range(self.pdf.count):
            outer = tk.Frame(self.thumb_content, bg='#e6f3e5' if i==self.current else WHITE,
                             highlightthickness=2 if i==self.current else 1,
                             highlightbackground=BLUE if i==self.current else '#e2e5e9')
            outer.pack(padx=13, pady=10)
            self._enable_thumbnail_wheel(outer)
            try:
                page_rect = self.pdf.page_size(i)
                scale = min(142/page_rect.width, 177/page_rect.height)
                img = Image.open(io.BytesIO(self.pdf.render(i, scale)))
                preview = ImageTk.PhotoImage(img)
                self._thumb_refs.append(preview)
                button = tk.Button(outer, image=preview, command=lambda n=i:self.choose_page(n),
                                   bg=WHITE, relief='flat', bd=0, cursor='hand2')
                button.pack(padx=4,pady=4)
                self._enable_thumbnail_wheel(button)
            except Exception:
                tk.Button(outer,text=f'Page {i+1}', command=lambda n=i:self.choose_page(n)).pack()
            page_label = tk.Label(self.thumb_content, text=str(i+1), font=('Arial', 10, 'bold' if i==self.current else 'normal'),
                     bg=WHITE, fg=BLUE if i==self.current else '#222')
            page_label.pack(pady=(0,3))
            self._enable_thumbnail_wheel(page_label)

    def choose_page(self, index):
        self.current = index
        self.selected_span = None
        self.refresh()

    def action(self, fn, *args):
        try:
            fn(*args)
            self._thumb_signature = None
            self.refresh()
        except Exception as exc:
            messagebox.showerror('Operation failed', str(exc), parent=self)

    def check_unsaved(self):
        if not self.pdf.dirty: return True
        decision = messagebox.askyesnocancel('Unsaved edits', 'Save changes before continuing?')
        if decision is None: return False
        if decision: return self.save_pdf()
        return True

    def close_app(self):
        if self.check_unsaved(): self.destroy()

    def new_pdf(self):
        if self.check_unsaved():
            self.pdf.new(); self.current=0; self._thumb_signature=None; self.refresh()

    def _mac_open_document(self, *paths):
        for path in paths:
            if path and str(path).lower().endswith('.pdf') and os.path.isfile(path):
                if not self.check_unsaved():
                    return
                try:
                    self.pdf.open(path)
                    self.current = 0
                    self.selected_span = None
                    self._thumb_signature = None
                    self.refresh()
                except Exception as exc:
                    messagebox.showerror('Open failed', str(exc), parent=self)
                return

    def open_pdf(self):
        if not self.check_unsaved(): return
        path = filedialog.askopenfilename(filetypes=[('PDF files','*.pdf')]);
        if not path: return
        try:
            try: self.pdf.open(path)
            except ValueError:
                password = simpledialog.askstring('Protected PDF', 'Enter PDF password:', show='*', parent=self)
                if password is None: return
                self.pdf.open(path, password)
            self.current=0; self._thumb_signature=None; self.refresh()
        except Exception as exc: messagebox.showerror('Open failed', str(exc))

    def save_pdf(self, save_as=False):
        path = None if save_as else self.pdf.path
        if not path: path = filedialog.asksaveasfilename(defaultextension='.pdf', filetypes=[('PDF','*.pdf')])
        if not path: return False
        try:
            self.pdf.save(path); self._thumb_signature=None; self.refresh(); return True
        except Exception as exc:
            messagebox.showerror('Save failed', str(exc)); return False

    def page_selected(self, _event=None):
        sel = self.pages.curselection()
        if sel and sel[0] != self.current:
            self.current = sel[0]; self.refresh()

    def change_zoom(self, delta):
        self.zoom = max(.4, min(3.0, self.zoom+delta)); self.refresh()

    def mouse_wheel(self, event):
        units = -round(event.delta * 2) if sys.platform == 'darwin' else -round(event.delta / 120 * 3)
        if not units and event.delta:
            units = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(units, 'units')

    def coords(self, event):
        x = (self.canvas.canvasx(event.x)-self.margin)/self.zoom
        y = (self.canvas.canvasy(event.y)-self.margin)/self.zoom
        rect = self.pdf.page_size(self.current)
        return max(0, min(rect.width, x)), max(0, min(rect.height, y))

    def mouse_down(self, event):
        if self.mode in ('edit', 'move', 'select'):
            x, y = self.coords(event)
            self.selected_span = self.pdf.find_text_span(self.current, x, y)
            if self.selected_span:
                self.status.set('Selected: ' + self.selected_span['text'][:100] + ' | Double click to edit; Move Text: drag selection')
                self.draw_text_selection()
            elif self.mode in ('edit','move'):
                self.status.set('No editable text found at this point (possibly scanned image)')
        if self.mode == 'hand':
            self.canvas.scan_mark(event.x, event.y)
            self.drag = None
            return
        self.drag = self.coords(event)
        if self.selection_id: self.canvas.delete(self.selection_id); self.selection_id = None

    def mouse_move(self, event):
        if self.mode == 'hand':
            self.canvas.scan_dragto(event.x, event.y, gain=1)
            return
        if self.drag is None: return
        if self.mode in ('select','edit','hand'): return
        if self.selection_id: self.canvas.delete(self.selection_id)
        x, y = self.coords(event)
        x0,y0 = self.drag
        self.selection_id = self.canvas.create_rectangle(self.margin+x0*self.zoom, self.margin+y0*self.zoom,
                  self.margin+x*self.zoom, self.margin+y*self.zoom, outline=BLUE, dash=(5,3), width=2)

    def mouse_up(self, event):
        if self.drag is None: return
        x0,y0=self.drag; x1,y1=self.coords(event)
        self.drag=None
        area=(min(x0,x1),min(y0,y1),max(x0,x1),max(y0,y1))
        wide=(area[2]-area[0]>4 and area[3]-area[1]>4)
        mode=self.mode
        if mode in ('select','edit','hand'): return
        if mode=='move':
            if self.selected_span and (abs(x1-x0)>2 or abs(y1-y0)>2):
                dx,dy=x1-x0,y1-y0
                if messagebox.askyesno('Move selected text', 'Move the selected text here?\nThe original text will be removed and redrawn.',parent=self):
                    self.edit_selected_text(move=(dx,dy))
            return
        if mode in ('replace','highlight','redact','rectangle','image','signature') and not wide:
            self.status.set('Drag a rectangle over the PDF to use this tool'); return
        if mode=='text':
            text=simpledialog.askstring('Add text','Enter text:',parent=self)
            if text:
                size=simpledialog.askfloat('Text size','Font size (pt):',initialvalue=12,minvalue=4,maxvalue=100,parent=self)
                if size:
                    if any(ord(ch)>255 for ch in text):
                        font = self.preferred_font or filedialog.askopenfilename(title='Choose a Bengali/Unicode TTF font',filetypes=[('Font files','*.ttf *.otf')])
                        if font: self.preferred_font=font; self.action(self.pdf.add_unicode_text,self.current,x1,y1,text,size,'#000000',font)
                    else: self.action(self.pdf.add_text,self.current,x1,y1,text,size)
        elif mode=='replace':
            text=simpledialog.askstring('Replace original text','New text (selected original text will be removed):',parent=self)
            if text is not None:
                size=simpledialog.askfloat('Font size','Replacement size:',initialvalue=11,minvalue=4,maxvalue=72,parent=self)
                if size: self.action(self.pdf.replace_text,self.current,area,text,size)
        elif mode=='highlight': self.action(self.pdf.highlight,self.current,area)
        elif mode=='redact':
            if messagebox.askyesno('Permanently redact','Remove all content in the selected area? This cannot be recovered after saving.'):
                self.action(self.pdf.redact,self.current,area)
        elif mode=='rectangle': self.action(self.pdf.draw_rect,self.current,area)
        elif mode=='stamp':
            content=simpledialog.askstring('Stamp','Stamp text:',parent=self)
            if content:self.action(self.pdf.add_text,self.current,x1,y1,content,20,(.2,.55,.2))
        elif mode=='note':
            content=simpledialog.askstring('Comment','Comment:',parent=self)
            if content: self.action(self.pdf.add_note,self.current,x1,y1,content)
        elif mode in ('image','signature'):
            path=filedialog.askopenfilename(title='Choose image or scanned signature',filetypes=[('Images','*.png *.jpg *.jpeg *.webp')])
            if path: self.action(self.pdf.insert_image,self.current,area,path)

    def draw_text_selection(self):
        if not self.selected_span: return
        r = self.selected_span['bbox']
        self.canvas.delete('text-selection')
        self.canvas.create_rectangle(self.margin+r[0]*self.zoom, self.margin+r[1]*self.zoom,
            self.margin+r[2]*self.zoom, self.margin+r[3]*self.zoom,
            outline='#ef7d18', width=2, dash=(3, 2), tags='text-selection')

    def double_click(self, event):
        if self.mode not in ('edit','select','move'): return
        x,y=self.coords(event)
        self.selected_span=self.pdf.find_text_span(self.current,x,y)
        if self.selected_span:
            self.draw_text_selection()
            self.edit_selected_text()
        else:
            self.status.set('This region has no selectable PDF text; scanned PDFs need OCR first')

    def edit_selected_text(self, move=None):
        span=self.selected_span
        if not span: return
        if move is not None:
            self.action(self.pdf.edit_text_span,self.current,span,span['text'],span['size'],span['color'],self.preferred_font or None,move)
            self.selected_span=None
            return
        dlg=tk.Toplevel(self)
        dlg.title('Edit existing PDF text')
        dlg.geometry('570x450')
        dlg.transient(self); dlg.grab_set()
        frm=ttk.Frame(dlg,padding=17); frm.pack(fill='both',expand=True)
        ttk.Label(frm,text='Selected original text',font=('Arial',13,'bold')).pack(anchor='w')
        editor=tk.Text(frm,height=5,wrap='word',font=('Arial',12))
        editor.pack(fill='x',pady=(6,12))
        editor.insert('1.0',span['text'])
        row=ttk.Frame(frm);row.pack(fill='x',pady=6)
        ttk.Label(row,text='Size (pt):').pack(side='left')
        sizevar=tk.StringVar(value=str(span['size']))
        ttk.Entry(row,textvariable=sizevar,width=8).pack(side='left',padx=7)
        ttk.Label(row,text='Text color:').pack(side='left',padx=(12,0))
        colorvar=tk.StringVar(value=span['color'])
        ttk.Entry(row,textvariable=colorvar,width=10).pack(side='left',padx=7)
        def pick_color():
            chosen=colorchooser.askcolor(color=colorvar.get(),parent=dlg)[1]
            if chosen:colorvar.set(chosen)
        ttk.Button(row,text='Choose',command=pick_color).pack(side='left')
        fontvar=tk.StringVar(value=self.preferred_font)
        fontrow=ttk.Frame(frm);fontrow.pack(fill='x',pady=9)
        ttk.Label(fontrow,text='Unicode font (optional):').pack(anchor='w')
        ttk.Entry(fontrow,textvariable=fontvar).pack(side='left',fill='x',expand=True)
        def browse_font():
            file=filedialog.askopenfilename(parent=dlg,title='Choose a TTF or OTF font',filetypes=[('Fonts','*.ttf *.otf')])
            if file:fontvar.set(file)
        ttk.Button(fontrow,text='Browse',command=browse_font).pack(side='left',padx=4)
        ttk.Label(frm,text='Original PDF font: '+span['font']+'  |  Text is replaced in place, not reflowed.',
                  foreground='#586678',wraplength=510).pack(anchor='w',pady=8)
        ttk.Label(frm,text='For Bangla, select a Bengali Unicode TTF font. Check visual accuracy after saving.',
                  foreground='#586678',wraplength=510).pack(anchor='w')
        buttons=ttk.Frame(frm);buttons.pack(side='bottom',fill='x',pady=12)
        def apply():
            try:
                size=float(sizevar.get())
                font=fontvar.get().strip() or None
                text=editor.get('1.0','end-1c')
                self.pdf.edit_text_span(self.current,span,text,size,colorvar.get(),font)
                self.preferred_font=font or ''
                self.selected_span=None
                dlg.destroy();self._thumb_signature=None;self.refresh()
            except Exception as exc:
                messagebox.showerror('Edit failed',str(exc),parent=dlg)
        ttk.Button(buttons,text='Cancel',command=dlg.destroy).pack(side='right',padx=4)
        ttk.Button(buttons,text='Apply text edit',command=apply,style='Accent.TButton').pack(side='right')
        dlg.bind('<Escape>',lambda e:dlg.destroy())
        editor.focus_set()

    def add_page(self): self.action(self.pdf.add_blank,self.current); self.current+=1; self.refresh()
    def delete_page(self): self.action(self.pdf.delete_page,self.current)
    def rotate_page(self): self.action(self.pdf.rotate,self.current)
    def move_page(self, offset):
        dest=self.current+offset
        if 0<=dest<self.pdf.count:
            self.action(self.pdf.move_page,self.current,dest); self.current=dest; self.refresh()

    def merge(self):
        paths=filedialog.askopenfilenames(title='Choose PDFs to append',filetypes=[('PDF','*.pdf')])
        if paths: self.action(self.pdf.merge,paths)

    def extract(self):
        value=simpledialog.askstring('Extract pages','Page numbers (e.g. 1,3-5):',parent=self)
        if not value: return
        try:
            indices=[]
            for part in value.replace(' ','').split(','):
                if '-' in part:
                    a,b=map(int,part.split('-',1)); indices.extend(range(a-1,b))
                else: indices.append(int(part)-1)
            path=filedialog.asksaveasfilename(defaultextension='.pdf',filetypes=[('PDF','*.pdf')])
            if path:
                self.pdf.extract_pages(indices,path); messagebox.showinfo('Extracted',f'Saved to {path}')
        except Exception as exc: messagebox.showerror('Extract failed',str(exc))

    def watermark(self):
        content=simpledialog.askstring('Watermark','Watermark text:',parent=self)
        if content: self.action(self.pdf.watermark,content)

    def ocr(self):
        opt=messagebox.askyesno('OCR','Create a searchable PDF copy of all pages?\nYes: searchable PDF copy\nNo: extract text from current page')
        lang=simpledialog.askstring('OCR language','Tesseract language code (eng / ben / eng+ben):',initialvalue='eng',parent=self)
        if not lang: return
        try:
            if opt:
                path=filedialog.asksaveasfilename(defaultextension='.pdf',filetypes=[('PDF','*.pdf')])
                if path:
                    self.pdf.ocr_searchable_copy(path,lang)
                    messagebox.showinfo('OCR complete','Searchable PDF saved. Note: pages are rasterized in this output.')
            else:
                output=self.pdf.ocr_page(self.current,lang)
                dlg=tk.Toplevel(self); dlg.title('OCR text'); dlg.geometry('700x500')
                widget=tk.Text(dlg,wrap='word'); widget.pack(fill='both',expand=True)
                widget.insert('1.0',output)
        except Exception as exc: messagebox.showerror('OCR failed',str(exc))

    def export(self):
        dialog=tk.Toplevel(self); dialog.title('Export PDF'); dialog.geometry('370x210'); dialog.transient(self)
        tk.Label(dialog,text='Choose export format',font=('Arial',14,'bold')).pack(pady=14)
        choice=tk.StringVar(value='images')
        ttk.Combobox(dialog, textvariable=choice, values=['images','text','docx'], state='readonly').pack(pady=7)
        def run():
            kind=choice.get()
            try:
                if kind=='images':
                    path=filedialog.askdirectory(title='Output image folder')
                    if path: self.pdf.export_images(path)
                else:
                    ext='.txt' if kind=='text' else '.docx'
                    path=filedialog.asksaveasfilename(defaultextension=ext,filetypes=[(kind.upper(),'*'+ext)])
                    if path:
                        if kind=='text': self.pdf.export_text(path)
                        else: self.pdf.export_docx(path)
                if path:
                    dialog.destroy(); messagebox.showinfo('Export complete',f'Exported to {path}')
            except Exception as exc: messagebox.showerror('Export failed',str(exc))
        ttk.Button(dialog,text='Export',command=run,style='Accent.TButton').pack(pady=12)

if __name__=='__main__':
    App().mainloop()
