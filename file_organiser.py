
import os
import shutil
from pathlib import Path

# Choose the folder to organise
source_folder = Path.home() / "Downloads"

# File categories
file_types = {
    "PDF Documents": [".pdf"],
    "Excel Spreadsheets": [".xlsx", ".xls", ".csv"],
    "Word Documents": [".docx", ".doc"],
    "PowerPoint Presentations": [".pptx", ".ppt"],
    "Images": [".jpg", ".jpeg", ".png", ".gif"],
    "Videos": [".mp4", ".mov", ".avi"],
    "Text Files": [".txt"]
}

# Organise the files
for file in source_folder.iterdir():

    # Skip folders
    if not file.is_file():
        continue

    # Find the correct category
    category = None

    for folder, extensions in file_types.items():
        if file.suffix.lower() in extensions:
            category = folder
            break

    # Skip unsupported file types
    if category is None:
        continue

    # Create destination folder
    destination_folder = source_folder / category
    destination_folder.mkdir(exist_ok=True)

    # Prevent overwriting existing files
    destination = destination_folder / file.name

    counter = 1
    while destination.exists():
        destination = destination_folder / (
            f"{file.stem}_{counter}{file.suffix}"
        )
        counter += 1

    # Move the file
    shutil.move(str(file), str(destination))

    print(f"Moved: {file.name} -> {category}")

print("File organisation complete!")
