"""Document operations for LocalPDF Studio. Coordinates are PDF points (72/inch)."""
from __future__ import annotations
from pathlib import Path
import io
import fitz
import html
import re


class PDFDocument:
    def __init__(self):
        self.doc = fitz.open()
        self.path: str | None = None
        self.dirty = False
        self.undo_stack: list[bytes] = []
        self.redo_stack: list[bytes] = []

    def _snapshot(self):
        self.undo_stack.append(self.doc.tobytes(garbage=3, deflate=True))
        if len(self.undo_stack) > 15:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    @property
    def count(self):
        return len(self.doc)

    def open(self, path: str, password: str | None = None):
        doc = fitz.open(path)
        if doc.needs_pass and not doc.authenticate(password or ""):
            doc.close()
            raise ValueError("Password required or incorrect")
        self.doc.close()
        self.doc = doc
        self.path = path
        self.dirty = False
        self.undo_stack.clear()
        self.redo_stack.clear()

    def new(self):
        self.doc.close()
        self.doc = fitz.open()
        self.doc.new_page(width=595, height=842)
        self.path = None
        self.dirty = False
        self.undo_stack.clear()
        self.redo_stack.clear()

    def _change(self):
        self._snapshot()
        self.dirty = True

    def save(self, target: str):
        target = str(Path(target).resolve())
        # Writing to a fresh temp file supports Save over the input safely.
        import os, tempfile
        fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=str(Path(target).parent))
        os.close(fd)
        try:
            self.doc.save(tmp, garbage=4, deflate=True, encryption=fitz.PDF_ENCRYPT_KEEP)
            # Close the source file before replacing it (required by Windows).
            self.doc.close()
            try:
                os.replace(tmp, target)
                self.doc = fitz.open(target)
            except Exception:
                # Reopen the original if replacement failed.
                self.doc = fitz.open(self.path) if self.path and os.path.exists(self.path) else fitz.open(tmp)
                raise
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        self.path = target
        self.dirty = False

    def undo(self):
        if not self.undo_stack: return False
        self.redo_stack.append(self.doc.tobytes(garbage=3, deflate=True))
        content = self.undo_stack.pop()
        self.doc.close()
        self.doc = fitz.open(stream=content, filetype="pdf")
        self.dirty = True
        return True

    def redo(self):
        if not self.redo_stack: return False
        self.undo_stack.append(self.doc.tobytes(garbage=3, deflate=True))
        content = self.redo_stack.pop()
        self.doc.close()
        self.doc = fitz.open(stream=content, filetype="pdf")
        self.dirty = True
        return True

    def page_size(self, index):
        return self.doc[index].rect

    def render(self, index: int, zoom: float = 1.25) -> bytes:
        pix = self.doc[index].get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return pix.tobytes("png")

    def add_text(self, index, x, y, text, size=12, color=(0, 0, 0)):
        if not text.strip(): return
        self._change()
        page = self.doc[index]
        # Click is top-left of first line, while insert_text expects baseline.
        page.insert_text((x, y + size), text, fontsize=size, color=color,
                         fontname="helv", overlay=True)

    def replace_text(self, index, area, text, size=11):
        """Redact chosen region and insert replacement. Complex typography is not preserved."""
        rect = fitz.Rect(area) & self.doc[index].rect
        if rect.is_empty or rect.width < 2 or rect.height < 2:
            raise ValueError("Select a larger text region")
        self._change()
        page = self.doc[index]
        page.add_redact_annot(rect, fill=(1, 1, 1), cross_out=False)
        # Images/vector drawings outside the selected text remain untouched.
        page.apply_redactions(images=0, graphics=0, text=0)
        if text.strip():
            result = page.insert_textbox(rect, text, fontname="helv", fontsize=size,
                                         color=(0, 0, 0), align=0, overlay=True)
            if result < 0:
                # Undo automatically if the replacement cannot fit.
                self.undo()
                raise ValueError("Replacement does not fit. Use a smaller font or larger selection.")

    def redact(self, index, area):
        rect = fitz.Rect(area) & self.doc[index].rect
        if rect.is_empty: raise ValueError("Select a valid area")
        self._change()
        page = self.doc[index]
        page.add_redact_annot(rect, fill=(0, 0, 0), cross_out=False)
        page.apply_redactions(images=2, graphics=1, text=0)

    def highlight(self, index, area):
        self._change()
        page = self.doc[index]
        annot = page.add_highlight_annot(fitz.Rect(area))
        if annot: annot.update()

    def add_note(self, index, x, y, note):
        self._change()
        self.doc[index].add_text_annot((x, y), note)

    def draw_rect(self, index, area, color=(0.1, 0.4, 0.9)):
        self._change()
        self.doc[index].draw_rect(fitz.Rect(area), color=color, width=1.5, overlay=True)

    def insert_image(self, index, area, path):
        self._change()
        self.doc[index].insert_image(fitz.Rect(area), filename=path, keep_proportion=True, overlay=True)

    def insert_image_bytes(self, index, area, image_bytes):
        self._change()
        self.doc[index].insert_image(fitz.Rect(area), stream=image_bytes, keep_proportion=True, overlay=True)

    def rotate(self, index, degrees=90):
        self._change()
        page = self.doc[index]
        page.set_rotation((page.rotation + degrees) % 360)

    def delete_page(self, index):
        if self.count <= 1:
            raise ValueError("Cannot delete the last page")
        self._change()
        self.doc.delete_page(index)

    def move_page(self, index, dest):
        if index == dest: return
        if not (0 <= index < self.count and 0 <= dest < self.count): return
        self._change()
        self.doc.move_page(index, dest)

    def add_blank(self, after_index=None):
        self._change()
        if self.count:
            ref = self.doc[min(after_index if after_index is not None else self.count - 1, self.count - 1)]
            width, height = ref.rect.width, ref.rect.height
        else:
            width, height = 595, 842
        pos = self.count if after_index is None else after_index + 1
        self.doc.new_page(pno=pos, width=width, height=height)

    def merge(self, paths):
        if not paths: return
        self._change()
        for path in paths:
            with fitz.open(path) as other:
                if other.needs_pass: raise ValueError(f"Password-protected input: {path}")
                self.doc.insert_pdf(other)

    def extract_pages(self, selected_indices, target):
        indices = sorted(set(selected_indices))
        if not indices: raise ValueError("No pages selected")
        out = fitz.open()
        for i in indices:
            if i < 0 or i >= self.count: raise ValueError("Page out of range")
            out.insert_pdf(self.doc, from_page=i, to_page=i)
        out.save(target, garbage=4, deflate=True)
        out.close()

    def watermark(self, text, size=36):
        if not text.strip(): return
        self._change()
        for page in self.doc:
            rect = page.rect
            box = fitz.Rect(rect.width * .08, rect.height * .42,
                            rect.width * .92, rect.height * .62)
            page.insert_textbox(box, text, fontsize=size, fontname="helv",
                                color=(.72, .72, .72), align=1, overlay=True)

    def export_images(self, folder, dpi=180):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        for i, page in enumerate(self.doc):
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            pix.save(str(folder / f"page_{i+1:03}.png"))

    def export_text(self, target):
        Path(target).write_text("\n\n".join(p.get_text() for p in self.doc), encoding="utf-8")

    def export_docx(self, target):
        try:
            from pdf2docx import Converter
        except ImportError as exc:
            raise RuntimeError("Install optional dependency: pip install pdf2docx") from exc
        import tempfile, os
        fd, temp = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        try:
            self.doc.save(temp)
            cv = Converter(temp)
            try: cv.convert(target)
            finally: cv.close()
        finally:
            os.remove(temp)

    def ocr_page(self, index, language="eng", dpi=200):
        """Return extracted OCR text; requires Tesseract installed on the computer."""
        try:
            import pytesseract
            from PIL import Image
        except ImportError as exc:
            raise RuntimeError("Install pytesseract and Pillow") from exc
        pix = self.doc[index].get_pixmap(dpi=dpi, alpha=False)
        im = Image.open(io.BytesIO(pix.tobytes("png")))
        return pytesseract.image_to_string(im, lang=language)

    def ocr_searchable_copy(self, target, language="eng"):
        """Create a searchable copy using PyMuPDF OCR; Tesseract executable required."""
        out = fitz.open()
        for page in self.doc:
            pix = page.get_pixmap(dpi=200, alpha=False)
            pdfbytes = pix.pdfocr_tobytes(language=language)
            with fitz.open(stream=pdfbytes, filetype="pdf") as one:
                out.insert_pdf(one)
        out.save(target, garbage=4, deflate=True)
        out.close()

    # Version 2: span-aware text editing. Editing removes the selected text
    # painting operators and writes new content; it cannot reflow other objects.
    def text_spans(self, index):
        spans = []
        page = self.doc[index]
        blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block["lines"]:
                if abs(line.get("dir", (1, 0))[1]) > 0.01:
                    continue  # Rotated spans not yet editable safely.
                for span in line["spans"]:
                    if not span.get("text", "").strip():
                        continue
                    rect = fitz.Rect(span["bbox"])
                    spans.append({"text": span["text"], "bbox": tuple(rect),
                                  "size": round(span["size"], 1),
                                  "font": span["font"],
                                  "color": '#%06x' % (span["color"] & 0xffffff),
                                  "origin": tuple(span["origin"])})
        return spans

    def find_text_span(self, index, x, y, tolerance=3):
        point = fitz.Point(x, y)
        candidates = []
        for span in self.text_spans(index):
            r = fitz.Rect(span["bbox"]) + (-tolerance, -tolerance, tolerance, tolerance)
            if r.contains(point):
                candidates.append(span)
        return min(candidates, key=lambda s: fitz.Rect(s["bbox"]).get_area()) if candidates else None

    def edit_text_span(self, index, original, replacement, size=None, color=None,
                       font_file=None, target=None):
        """Replace one horizontal PDF text span, optionally moving it.

        Warning: PDF original text is not a reflowable object. Selecting one span
        can affect adjacent overlapping text. A dedicated font file is needed for
        reliable Unicode output; HTML insertion handles complex shaping.
        """
        page = self.doc[index]
        source = fitz.Rect(original["bbox"]) & page.rect
        if source.is_empty or source.width < 2:
            raise ValueError('Invalid text selection')
        fontsize = float(size if size is not None else original['size'])
        if not 4 <= fontsize <= 120:
            raise ValueError('Font size must be between 4 and 120')
        hexcolor = color or original['color']
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', hexcolor):
            raise ValueError('Color must be #RRGGBB')
        dx, dy = target if target is not None else (0, 0)
        target_rect = fitz.Rect(source.x0 + dx, source.y0 + dy,
                                source.x1 + dx, source.y1 + dy)
        # Expand destination box if replacement is longer; never shift other content.
        estimated_width = max(source.width + 6, fontsize * .65 * len(replacement) + 12)
        target_rect.x1 = min(page.rect.x1 - 2, target_rect.x0 + estimated_width)
        target_rect.y1 = max(target_rect.y1 + 4, target_rect.y0 + fontsize * 2.6)
        target_rect &= page.rect
        if target_rect.is_empty or target_rect.width < 5:
            raise ValueError('Text would be outside the page')
        if font_file is not None and not Path(font_file).is_file():
            raise ValueError('Selected font file not found')
        self._change()
        try:
            page = self.doc[index]
            # Padding is intentionally small; users should inspect edits at 100%.
            page.add_redact_annot(source, fill=False, cross_out=False)
            page.apply_redactions(images=0, graphics=0, text=0)
            if replacement:
                rgb = tuple(int(hexcolor[i:i+2], 16) / 255 for i in (1, 3, 5))
                if font_file:
                    # fitz HTML Story handles Unicode shaping / complex scripts.
                    archive = fitz.Archive(str(Path(font_file).parent))
                    css = ("@font-face {font-family: userfont; src: url('" +
                           Path(font_file).name.replace("'", "") + "');} " +
                           "* {font-family: userfont;}")
                    fragment = (f'<div style="font-family:userfont;font-size:{fontsize}pt;'
                                f'color:{hexcolor};line-height:1.2;white-space:pre-wrap">'
                                f'{html.escape(replacement)}</div>')
                    spare, scale = page.insert_htmlbox(target_rect, fragment, css=css,
                                                       archive=archive, scale_low=0.75)
                    if spare < 0:
                        raise ValueError('Text does not fit; increase area or reduce font size')
                else:
                    # Built-in Helvetica only supports limited characters.
                    if any(ord(c) > 255 for c in replacement):
                        raise ValueError('For Bangla or other Unicode text, choose a TTF/OTF font file')
                    fontname = 'helv'
                    if 'Bold' in original['font'] and 'Italic' in original['font']:
                        fontname = 'hebi'
                    elif 'Bold' in original['font']:
                        fontname = 'hebo'
                    elif 'Italic' in original['font'] or 'Oblique' in original['font']:
                        fontname = 'heit'
                    # insert_text uses baseline; original baseline offset is preserved.
                    baseline_offset = original['origin'][1] - source.y0
                    pos = fitz.Point(target_rect.x0, target_rect.y0 + baseline_offset)
                    page.insert_text(pos, replacement, fontname=fontname,
                                     fontsize=fontsize, color=rgb, overlay=True)
        except Exception:
            self.undo()
            raise

    def add_unicode_text(self, index, x, y, text, size, color, font_file):
        if not text.strip(): return
        if not Path(font_file).is_file():
            raise ValueError('Choose a valid .ttf or .otf font')
        page = self.doc[index]
        rect = fitz.Rect(x, y, min(page.rect.x1 - 2, x + max(150, size * len(text))),
                         min(page.rect.y1 - 2, y + max(40, size * 3)))
        if rect.is_empty: raise ValueError('Click inside the page')
        self._change()
        try:
            archive = fitz.Archive(str(Path(font_file).parent))
            css = "@font-face {font-family:userfont;src:url('" + Path(font_file).name + "');}"
            markup = (f'<div style="font-family:userfont;font-size:{size}pt;color:{color};'
                      f'line-height:1.2">{html.escape(text)}</div>')
            spare, _ = self.doc[index].insert_htmlbox(rect, markup, css=css, archive=archive)
            if spare < 0: raise ValueError('Text could not fit in page')
        except Exception:
            self.undo()
            raise
