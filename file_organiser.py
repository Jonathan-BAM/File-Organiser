import shutil
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


FILE_TYPES = {
    "PDF Documents": (".pdf",),
    "Excel Spreadsheets": (".xlsx", ".xls", ".csv"),
    "Word Documents": (".docx", ".doc"),
    "PowerPoint Presentations": (".pptx", ".ppt"),
    "Images": (".jpg", ".jpeg", ".png", ".gif"),
    "Videos": (".mp4", ".mov", ".avi"),
    "Text Files": (".txt",),
}


def organize_files(
    source_folder: Path,
    destination_folders: dict[str, Path],
) -> tuple[list[tuple[Path, Path]], list[tuple[Path, str]], int]:
    """Move supported files to their selected destinations or category subfolders."""
    source_folder = Path(source_folder)
    if not source_folder.is_dir():
        raise ValueError(f"Source folder does not exist: {source_folder}")

    source_resolved = source_folder.resolve()
    destinations = {
        category: Path(destination_folders.get(category) or source_folder / category)
        for category in FILE_TYPES
    }
    for category, destination in destinations.items():
        if destination.resolve() == source_resolved:
            raise ValueError(
                f"The destination for {category} cannot be the source folder."
            )

    moved = []
    errors = []
    skipped = 0

    for file_path in source_folder.iterdir():
        if not file_path.is_file():
            skipped += 1
            continue

        category = next(
            (
                name
                for name, extensions in FILE_TYPES.items()
                if file_path.suffix.lower() in extensions
            ),
            None,
        )
        if category is None:
            skipped += 1
            continue

        destination_folder = destinations[category]
        try:
            destination_folder.mkdir(parents=True, exist_ok=True)
            destination = destination_folder / file_path.name

            counter = 1
            while destination.exists():
                destination = destination_folder / (
                    f"{file_path.stem}_{counter}{file_path.suffix}"
                )
                counter += 1

            shutil.move(str(file_path), str(destination))
            moved.append((file_path, destination))
        except OSError as error:
            errors.append((file_path, str(error)))

    return moved, errors, skipped


class FileOrganiserApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("File Organiser")
        self.root.minsize(720, 560)

        container = ttk.Frame(root, padding=18)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)

        ttk.Label(
            container, text="Organise your files", font=("", 18, "bold")
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            container,
            text="Choose a source folder and, if you like, a destination for each file type.",
        ).grid(row=1, column=0, sticky="w", pady=(4, 16))

        source_frame = ttk.LabelFrame(container, text="Folder to organise", padding=10)
        source_frame.grid(row=2, column=0, sticky="ew")
        source_frame.columnconfigure(0, weight=1)

        self.source_var = tk.StringVar(value=str(Path.home() / "Downloads"))
        ttk.Entry(source_frame, textvariable=self.source_var).grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        ttk.Button(source_frame, text="Browse...", command=self.choose_source).grid(
            row=0, column=1
        )

        destinations_frame = ttk.LabelFrame(
            container,
            text="Destination folders (optional)",
            padding=10,
        )
        destinations_frame.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        destinations_frame.columnconfigure(2, weight=1)
        ttk.Label(destinations_frame, text="File type").grid(
            row=0, column=0, sticky="w", padx=(0, 12), pady=(0, 6)
        )
        ttk.Label(destinations_frame, text="Extensions").grid(
            row=0, column=1, sticky="w", padx=(0, 12), pady=(0, 6)
        )
        ttk.Label(destinations_frame, text="Destination").grid(
            row=0, column=2, sticky="w", pady=(0, 6)
        )

        self.destination_vars: dict[str, tk.StringVar] = {}
        for row, (category, extensions) in enumerate(FILE_TYPES.items(), start=1):
            ttk.Label(destinations_frame, text=category).grid(
                row=row, column=0, sticky="w", padx=(0, 12), pady=3
            )
            ttk.Label(destinations_frame, text=", ".join(extensions)).grid(
                row=row, column=1, sticky="w", padx=(0, 12), pady=3
            )

            destination_var = tk.StringVar()
            self.destination_vars[category] = destination_var
            ttk.Entry(destinations_frame, textvariable=destination_var).grid(
                row=row, column=2, sticky="ew", padx=(0, 8), pady=3
            )
            ttk.Button(
                destinations_frame,
                text="Browse...",
                command=lambda var=destination_var: self.choose_destination(var),
            ).grid(row=row, column=3, pady=3)

        ttk.Label(
            container,
            text="Leave a destination blank to create that category folder inside the source folder.",
            wraplength=680,
        ).grid(row=4, column=0, sticky="w", pady=(8, 12))

        actions = ttk.Frame(container)
        actions.grid(row=5, column=0, sticky="ew")
        ttk.Button(actions, text="Organise files", command=self.organise).pack(
            side="left"
        )
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(actions, textvariable=self.status_var).pack(
            side="left", padx=(12, 0)
        )

        log_frame = ttk.LabelFrame(container, text="Activity", padding=8)
        log_frame.grid(row=6, column=0, sticky="nsew", pady=(12, 0))
        container.rowconfigure(6, weight=1)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.log = tk.Text(log_frame, height=8, wrap="word", state="disabled")
        self.log.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scrollbar.set)

    def choose_source(self) -> None:
        selected = filedialog.askdirectory(
            title="Choose the folder to organise",
            initialdir=self.source_var.get() or str(Path.home()),
        )
        if selected:
            self.source_var.set(selected)

    def choose_destination(self, variable: tk.StringVar) -> None:
        selected = filedialog.askdirectory(
            title="Choose a destination folder",
            initialdir=self.source_var.get() or str(Path.home()),
        )
        if selected:
            variable.set(selected)

    def append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def organise(self) -> None:
        source_text = self.source_var.get().strip()
        if not source_text:
            messagebox.showerror("Choose a folder", "Select a source folder first.")
            return

        destinations = {
            category: Path(value)
            for category, variable in self.destination_vars.items()
            if (value := variable.get().strip())
        }

        try:
            moved, errors, skipped = organize_files(Path(source_text), destinations)
        except (OSError, ValueError) as error:
            messagebox.showerror("Could not organise files", str(error))
            return

        self.append_log(f"Organised: {source_text}")
        for source, destination in moved:
            self.append_log(f"Moved: {source.name} -> {destination}")
        for file_path, error in errors:
            self.append_log(f"Could not move {file_path.name}: {error}")

        summary = f"Moved {len(moved)} file(s); skipped {skipped} unsupported file(s) or folder(s)."
        if errors:
            summary += f" {len(errors)} file(s) could not be moved; see Activity for details."
            self.status_var.set(f"Finished with {len(errors)} error(s)")
            messagebox.showwarning("Organisation finished with errors", summary)
        else:
            self.status_var.set(summary)
            messagebox.showinfo("Organisation complete", summary)


def main() -> None:
    root = tk.Tk()
    FileOrganiserApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
