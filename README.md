# File Organiser

A small Windows desktop application that moves files from a source folder into folders based on file type.
An experimnent of how we can use Pyhton for automation solutions without needing agentic AI.

## Requirements

- Python 3.10 or newer
- Tkinter (included with the standard Python installation from python.org)

No third-party Python packages are required.

## Get the application from GitHub

Open the project in a browser at:

https://github.com/Jonathan-BAM/File-Organiser

To download it using Git, open Command Prompt or PowerShell and run:

```powershell
git clone https://github.com/Jonathan-BAM/File-Organiser.git
cd "File-Organiser"
```

You can also download a ZIP from the GitHub repository: click **Code**, then **Download ZIP**, extract it, and open Command Prompt or PowerShell in the extracted folder.

## Run on Windows

1. Open Command Prompt or PowerShell.
2. Change to the project folder. If you cloned the repository from this folder, it is named `File-Organiser`:

   ```powershell
   cd "C:\path\to\File Organiser"
   ```

3. Start the application:

   ```powershell
   py file_organiser.py
   ```

   If `py` is unavailable, use:

   ```powershell
   python file_organiser.py
   ```

## Using the application

1. Select the folder to organise. The **Downloads** folder is used as the default.
2. Optionally choose a destination folder for each file type.
3. Click **Organise files**.

If a destination is left blank, the application creates a category folder inside the source folder. For example, PDF files go into `PDF Documents`.

The application moves only top-level files in the source folder; it does not process subfolders. It skips unsupported files and folders. If a file name already exists at the destination, a numbered name such as `document_1.pdf` is used.

The destination folder for a category cannot be the source folder.

## Supported file types

| Category | Extensions |
|---|---|
| PDF Documents | `.pdf` |
| Excel Spreadsheets | `.xlsx`, `.xls`, `.csv` |
| Word Documents | `.docx`, `.doc` |
| PowerPoint Presentations | `.pptx`, `.ppt` |
| Images | `.jpg`, `.jpeg`, `.png`, `.gif` |
| Videos | `.mp4`, `.mov`, `.avi` |
| Text Files | `.txt` |
