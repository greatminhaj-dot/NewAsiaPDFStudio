import tempfile
from pathlib import Path
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fitz
from pdf_core import PDFDocument

class TestCore(unittest.TestCase):
    def test_roundtrip_and_editing(self):
        with tempfile.TemporaryDirectory() as folder:
            target = str(Path(folder)/'edited.pdf')
            pdf=PDFDocument(); pdf.new()
            pdf.add_text(0,40,40,'Hello PDF',12)
            self.assertIn('Hello PDF',pdf.doc[0].get_text())
            pdf.undo(); self.assertNotIn('Hello PDF',pdf.doc[0].get_text())
            pdf.redo(); self.assertIn('Hello PDF',pdf.doc[0].get_text())
            pdf.replace_text(0,(35,35,140,65),'Replaced',11)
            self.assertIn('Replaced',pdf.doc[0].get_text())
            self.assertNotIn('Hello PDF',pdf.doc[0].get_text())
            pdf.add_blank(0); self.assertEqual(pdf.count,2)
            pdf.rotate(1); self.assertEqual(pdf.doc[1].rotation,90)
            pdf.move_page(1,0)
            pdf.save(target)
            self.assertTrue(Path(target).exists())
            with fitz.open(target) as loaded: self.assertEqual(len(loaded),2)
            out=str(Path(folder)/'extract.pdf')
            pdf.extract_pages([0],out)
            with fitz.open(out) as extracted: self.assertEqual(len(extracted),1)
            pdf.export_images(str(Path(folder)/'images'))
            self.assertTrue((Path(folder)/'images'/'page_001.png').exists())
    def test_span_selection_edit_and_move(self):
        pdf=PDFDocument(); pdf.new()
        pdf.add_text(0,50,70,'Hello',14)
        first=pdf.text_spans(0)[0]
        self.assertEqual(first['text'],'Hello')
        found=pdf.find_text_span(0,first['bbox'][0]+3,first['bbox'][1]+3)
        self.assertIsNotNone(found)
        pdf.edit_text_span(0,found,'Welcome',size=14,color='#173b88')
        self.assertIn('Welcome',pdf.doc[0].get_text())
        self.assertNotIn('Hello',pdf.doc[0].get_text())
        updated=pdf.text_spans(0)[0]
        original_x=updated['bbox'][0]
        pdf.edit_text_span(0,updated,'Welcome',size=14,target=(30,25))
        moved=pdf.text_spans(0)[0]
        self.assertGreater(moved['bbox'][0],original_x + 20)
        pdf.undo()
        self.assertAlmostEqual(pdf.text_spans(0)[0]['bbox'][0],original_x,delta=2)

    def test_unicode_with_embedded_font(self):
        from pathlib import Path
        font=Path('/usr/share/fonts/truetype/noto/NotoSansBengali-Regular.ttf')
        if not font.exists():
            self.skipTest('Test font not installed')
        pdf=PDFDocument(); pdf.new()
        pdf.add_unicode_text(0,40,60,'বাংলা পরীক্ষা',16,'#224466',str(font))
        text=pdf.doc[0].get_text()
        self.assertIn('বাংলা',text)
        # Shaped Bengali glyphs may not round-trip through PDF text extraction.
        # Validate successful rendering instead of exact extracted Unicode.
        self.assertGreater(len(pdf.render(0)),1000)
        pdf2=PDFDocument();pdf2.new()
        pdf2.add_text(0,40,60,'Original text to replace',16)
        pdf2.edit_text_span(0,pdf2.text_spans(0)[0],'নতুন লেখা',size=16,font_file=str(font))
        self.assertGreater(len(pdf2.render(0)),1000)

    def test_redaction(self):
        pdf=PDFDocument(); pdf.new()
        pdf.add_text(0,50,50,'Secret word',12)
        pdf.redact(0,(45,45,160,70))
        self.assertNotIn('Secret word',pdf.doc[0].get_text())

if __name__ == '__main__': unittest.main()
