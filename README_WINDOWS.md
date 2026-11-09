# NewAsiaPDFStudio v3.2 — Windows desktop edition

PDFGear-inspired original ribbon design with New Asia logo. Local PDF handling; no database/cloud account. Uses Python 3.12, Tkinter, PyMuPDF, Pillow.

## Build an installable Setup.exe (Windows 10/11 64-bit)
1. Install Python 3.12 from python.org (select **Add Python to PATH**).
2. Install Inno Setup 6 from https://jrsoftware.org/isdl.php.
3. Extract this ZIP to a normal local folder (for example `C:\NewAsiaPDFStudio`).
4. Double-click `build_windows.bat` and read its results.
5. When successful, distribute `installer_output\NewAsiaPDFStudio_Setup_3.2_Windows_x64.exe`.

The setup is per-user (no administrator permission required), supports a Start Menu icon, optional Desktop shortcut, uninstall, and registers the program for PDF 'Open with' without silently changing the default PDF handler.

## Running directly (for testing)
Open CMD in this folder:
```
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```

## Build without a Windows computer
Push the whole contents of this directory to a GitHub repository. Go to **Actions** → **Build NewAsiaPDFStudio Windows Installer** → **Run workflow**. Download the `NewAsiaPDFStudio-Windows-Setup` build artifact after success. This requires a GitHub account and a repository.

## Features and limitations
- View PDFs, search, page thumbnails, save, zoom, annotate, highlight, insert text/images/signatures, edit individual selected text spans, redact, merge/split, rotate, OCR with Tesseract installed separately, export.
- Print button uses the Windows file-type PDF print handler; if that handler doesn't implement printing, it offers opening the PDF in the default viewer for Ctrl+P. Unsaved changes are included via a temporary export.
- Replacing original PDF text can change font/flow; it is not full Word-like reflow. Complex Bangla shaping may vary with fonts and PDF engine.
- Windows installer has NOT been executed/tested in this Linux build environment. PDF engine tests passed here. Unsigned executables may show SmartScreen prompts; signing with a trusted code-signing certificate is recommended before wide distribution.
- Tesseract OCR and its language data must be installed separately for OCR features.

## Run tests
```
python -m unittest discover -s tests -v
```
