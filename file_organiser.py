import json
import os
import queue
import shutil
import threading
import tkinter as tk
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable


FILE_TYPES = {
    "PDF Documents": (".pdf",),
    "Excel Spreadsheets": (".xlsx", ".xls", ".csv"),
    "Word Documents": (".docx", ".doc"),
    "PowerPoint Presentations": (".pptx", ".ppt"),
    "Images": (".jpg", ".jpeg", ".png", ".gif"),
    "Videos": (".mp4", ".mov", ".avi"),
    "Text Files": (".txt",),
}


@dataclass(frozen=True)
class PlannedMove:
    source: Path
    destination: Path
    category: str


@dataclass(frozen=True)
class FilePlan:
    moves: tuple[PlannedMove, ...]
    skipped: int
    examined: int


@dataclass(frozen=True)
class OrganiseResult:
    moved: tuple[tuple[Path, Path], ...]
    errors: tuple[tuple[Path, str], ...]
    skipped: int


def parse_file_types(text: str) -> dict[str, tuple[str, ...]]:
    """Parse category definitions in the form 'Category: .ext, .other'."""
    file_types: dict[str, tuple[str, ...]] = {}
    seen_extensions: set[str] = set()
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"Line {line_number} must contain a category and extensions.")
        category, extension_text = line.split(":", 1)
        category = category.strip()
        extensions = tuple(
            extension.strip().lower()
            for extension in extension_text.split(",")
            if extension.strip()
        )
        if not category or not extensions:
            raise ValueError(f"Line {line_number} needs a category and at least one extension.")
        if any(char in category for char in '\\/:*?"<>|') or category.endswith((" ", ".")):
            raise ValueError(f"Invalid category name on line {line_number}.")
        if category in file_types:
            raise ValueError(f"Category '{category}' is listed more than once.")
        for extension in extensions:
            if (
                not extension.startswith(".")
                or extension == "."
                or any(char in extension for char in "\\/:*?\"<>|, ")
            ):
                raise ValueError(f"Invalid extension '{extension}' on line {line_number}.")
            if extension in seen_extensions:
                raise ValueError(f"Extension '{extension}' is assigned more than once.")
            seen_extensions.add(extension)
        file_types[category] = extensions
    if not file_types:
        raise ValueError("Add at least one category with one or more extensions.")
    return file_types


def configuration_path() -> Path:
    app_data = os.environ.get("APPDATA")
    base = Path(app_data) if app_data else Path.home() / ".config"
    return base / "FileOrganiser" / "file_types.json"


def load_file_types(path: Path | None = None) -> dict[str, tuple[str, ...]]:
    config_path = path or configuration_path()
    if not config_path.exists():
        return dict(FILE_TYPES)
    with config_path.open(encoding="utf-8") as config_file:
        saved = json.load(config_file)
    if not isinstance(saved, dict) or not all(
        isinstance(category, str)
        and isinstance(extensions, list)
        and all(isinstance(extension, str) for extension in extensions)
        for category, extensions in saved.items()
    ):
        raise ValueError(f"Invalid file type configuration: {config_path}")
    return parse_file_types(
        "\n".join(f"{category}: {', '.join(extensions)}" for category, extensions in saved.items())
    )


def save_file_types(file_types: dict[str, tuple[str, ...]], path: Path | None = None) -> None:
    config_path = path or configuration_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as config_file:
        json.dump(file_types, config_file, indent=2)


def _validated_destinations(
    source_folder: Path,
    destination_folders: dict[str, Path],
    file_types: dict[str, tuple[str, ...]],
) -> dict[str, Path]:
    source_folder = Path(source_folder).expanduser()
    if not source_folder.is_dir():
        raise ValueError(f"Source folder does not exist: {source_folder}")

    source_resolved = source_folder.resolve()
    destinations: dict[str, Path] = {}
    for category in file_types:
        destination = Path(
            destination_folders.get(category) or source_folder / category
        ).expanduser()
        if destination.resolve() == source_resolved:
            raise ValueError(
                f"The destination for {category} cannot be the source folder."
            )
        if destination.exists() and not destination.is_dir():
            raise ValueError(f"The destination for {category} is not a folder: {destination}")
        destinations[category] = destination
    return destinations


def plan_files(
    source_folder: Path,
    destination_folders: dict[str, Path],
    file_types: dict[str, tuple[str, ...]] = FILE_TYPES,
) -> FilePlan:
    """Build a non-mutating plan for supported top-level files."""
    source_folder = Path(source_folder).expanduser()
    destinations = _validated_destinations(source_folder, destination_folders, file_types)
    planned: list[PlannedMove] = []
    reserved: set[str] = set()
    skipped = 0
    examined = 0

    for file_path in source_folder.iterdir():
        examined += 1
        if not file_path.is_file():
            skipped += 1
            continue

        category = next(
            (
                name
                for name, extensions in file_types.items()
                if file_path.suffix.lower() in extensions
            ),
            None,
        )
        if category is None:
            skipped += 1
            continue

        destination_folder = destinations[category]
        destination = destination_folder / file_path.name
        counter = 1
        while destination.exists() or os.path.normcase(str(destination)) in reserved:
            destination = destination_folder / (
                f"{file_path.stem}_{counter}{file_path.suffix}"
            )
            counter += 1
        reserved.add(os.path.normcase(str(destination)))
        planned.append(PlannedMove(file_path, destination, category))

    return FilePlan(tuple(planned), skipped, examined)


def execute_plan(
    plan: FilePlan,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> OrganiseResult:
    moved: list[tuple[Path, Path]] = []
    errors: list[tuple[Path, str]] = []
    total = len(plan.moves)

    for completed, item in enumerate(plan.moves, start=1):
        try:
            item.destination.parent.mkdir(parents=True, exist_ok=True)
            destination = item.destination
            counter = 1
            while destination.exists():
                destination = item.destination.with_name(
                    f"{item.destination.stem}_{counter}{item.destination.suffix}"
                )
                counter += 1
            shutil.move(str(item.source), str(destination))
            moved.append((item.source, destination))
        except (OSError, shutil.Error) as error:
            errors.append((item.source, str(error)))
        if progress_callback:
            progress_callback(completed, total, item.source.name)

    return OrganiseResult(tuple(moved), tuple(errors), plan.skipped)


def organize_files(
    source_folder: Path,
    destination_folders: dict[str, Path],
) -> tuple[list[tuple[Path, Path]], list[tuple[Path, str]], int]:
    """Move supported files to their selected destinations or category subfolders."""
    result = execute_plan(plan_files(source_folder, destination_folders))
    return list(result.moved), list(result.errors), result.skipped


def undo_files(
    moved: tuple[tuple[Path, Path], ...] | list[tuple[Path, Path]],
) -> tuple[list[tuple[Path, Path]], list[tuple[Path, str]]]:
    """Restore moved files without overwriting files created since the move."""
    restored: list[tuple[Path, Path]] = []
    errors: list[tuple[Path, str]] = []
    for original, current in reversed(moved):
        try:
            if original.exists():
                raise FileExistsError(f"Cannot restore because this path now exists: {original}")
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(current), str(original))
            restored.append((current, original))
        except (OSError, shutil.Error) as error:
            errors.append((current, str(error)))
    return restored, errors


class FileOrganiserApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("File Organiser")
        self.root.minsize(780, 620)
        self.file_types = dict(FILE_TYPES)
        self.undo_history: list[tuple[Path, Path]] = []
        self.last_destination: Path | None = None
        self.worker_messages: queue.Queue[tuple[str, object]] = queue.Queue()
        self.busy = False

        try:
            self.file_types = load_file_types()
        except (OSError, ValueError, json.JSONDecodeError) as error:
            messagebox.showwarning(
                "Could not load file type settings",
                f"Using the built-in file types instead.\n\n{error}",
                parent=root,
            )

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

        self.destinations_frame = ttk.LabelFrame(
            container, text="Destination folders (optional)", padding=10
        )
        self.destinations_frame.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        self.destination_vars: dict[str, tk.StringVar] = {}
        self._build_destination_rows()

        ttk.Label(
            container,
            text="Leave a destination blank to create that category folder inside the source folder.",
            wraplength=740,
        ).grid(row=4, column=0, sticky="w", pady=(8, 12))

        actions = ttk.Frame(container)
        actions.grid(row=5, column=0, sticky="ew")
        self.organise_button = ttk.Button(
            actions, text="Preview and organise...", command=self.organise
        )
        self.organise_button.pack(side="left")
        self.undo_button = ttk.Button(
            actions, text="Undo last run", command=self.undo, state="disabled"
        )
        self.undo_button.pack(side="left", padx=(8, 0))
        self.open_button = ttk.Button(
            actions, text="Open destination", command=self.open_destination, state="disabled"
        )
        self.open_button.pack(side="left", padx=(8, 0))
        self.config_button = ttk.Button(
            actions, text="Edit file types...", command=self.edit_file_types
        )
        self.config_button.pack(side="left", padx=(8, 0))

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(container, textvariable=self.status_var).grid(
            row=6, column=0, sticky="w", pady=(8, 0)
        )
        self.progress = ttk.Progressbar(container, mode="determinate")
        self.progress.grid(row=7, column=0, sticky="ew", pady=(5, 0))

        log_frame = ttk.LabelFrame(container, text="Activity", padding=8)
        log_frame.grid(row=8, column=0, sticky="nsew", pady=(12, 0))
        container.rowconfigure(8, weight=1)
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.log = tk.Text(log_frame, height=8, wrap="word", state="disabled")
        self.log.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scrollbar.set)
        self.root.after(100, self._process_worker_messages)

    def _build_destination_rows(self) -> None:
        for child in self.destinations_frame.winfo_children():
            child.destroy()

        self.destinations_frame.columnconfigure(2, weight=1)
        for column, heading in enumerate(("File type", "Extensions", "Destination")):
            ttk.Label(self.destinations_frame, text=heading).grid(
                row=0, column=column, sticky="w", padx=(0, 12), pady=(0, 6)
            )

        old_values = {
            category: variable.get()
            for category, variable in self.destination_vars.items()
        }
        self.destination_vars = {}
        for row, (category, extensions) in enumerate(self.file_types.items(), start=1):
            ttk.Label(self.destinations_frame, text=category).grid(
                row=row, column=0, sticky="w", padx=(0, 12), pady=3
            )
            ttk.Label(self.destinations_frame, text=", ".join(extensions)).grid(
                row=row, column=1, sticky="w", padx=(0, 12), pady=3
            )
            variable = tk.StringVar(value=old_values.get(category, ""))
            self.destination_vars[category] = variable
            ttk.Entry(self.destinations_frame, textvariable=variable).grid(
                row=row, column=2, sticky="ew", padx=(0, 8), pady=3
            )
            ttk.Button(
                self.destinations_frame,
                text="Browse...",
                command=lambda var=variable: self.choose_destination(var),
            ).grid(row=row, column=3, pady=3)

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

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.organise_button.configure(state="disabled" if busy else "normal")
        self.config_button.configure(state="disabled" if busy else "normal")
        self.undo_button.configure(
            state="normal" if self.undo_history and not busy else "disabled"
        )

    def _start_worker(self, task_name: str, task: Callable[[], object]) -> None:
        self._set_busy(True)
        self.status_var.set("Working...")

        def run() -> None:
            try:
                self.worker_messages.put((task_name, task()))
            except (OSError, ValueError, shutil.Error) as error:
                self.worker_messages.put(("error", error))

        threading.Thread(target=run, daemon=True).start()

    def _process_worker_messages(self) -> None:
        while True:
            try:
                kind, payload = self.worker_messages.get_nowait()
            except queue.Empty:
                break

            if kind == "progress":
                completed, total, filename = payload  # type: ignore[misc]
                self.progress.configure(maximum=max(total, 1), value=completed)
                self.status_var.set(f"Moving {completed} of {total}: {filename}")
            elif kind == "preview" and isinstance(payload, FilePlan):
                self._set_busy(False)
                self._show_preview(payload)
            elif kind == "organised" and isinstance(payload, OrganiseResult):
                self._set_busy(False)
                self._show_organise_result(payload)
            elif kind == "undone" and isinstance(payload, tuple):
                self._set_busy(False)
                self._show_undo_result(payload)
            elif kind == "error" and isinstance(payload, Exception):
                self._set_busy(False)
                messagebox.showerror("Could not complete operation", str(payload), parent=self.root)
                self.status_var.set("Operation failed")

        self.root.after(100, self._process_worker_messages)

    def organise(self) -> None:
        source_text = self.source_var.get().strip()
        if not source_text:
            messagebox.showerror("Choose a folder", "Select a source folder first.")
            return

        destinations = {
            category: Path(variable.get().strip())
            for category, variable in self.destination_vars.items()
            if variable.get().strip()
        }
        source = Path(source_text)
        self.progress.configure(maximum=1, value=0)
        self._start_worker(
            "preview",
            lambda: plan_files(source, destinations, self.file_types),
        )

    def _show_preview(self, plan: FilePlan) -> None:
        if not plan.moves:
            self.status_var.set("No supported files to organise.")
            messagebox.showinfo(
                "Nothing to organise",
                f"No supported files found. Skipped {plan.skipped} file(s) or folder(s).",
                parent=self.root,
            )
            return

        window = tk.Toplevel(self.root)
        window.title("Review file moves")
        window.transient(self.root)
        window.geometry("760x420")
        window.columnconfigure(0, weight=1)
        window.rowconfigure(1, weight=1)
        ttk.Label(
            window,
            text=f"{len(plan.moves)} file(s) will be moved; {plan.skipped} unsupported file(s) or folder(s) will be skipped.",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=10)

        tree = ttk.Treeview(window, columns=("category", "source", "destination"), show="headings")
        tree.heading("category", text="File type")
        tree.heading("source", text="File")
        tree.heading("destination", text="Destination")
        tree.column("category", width=150, stretch=False)
        tree.column("source", width=220)
        tree.column("destination", width=350)
        tree.grid(row=1, column=0, sticky="nsew", padx=(12, 0), pady=(0, 8))
        scrollbar = ttk.Scrollbar(window, orient="vertical", command=tree.yview)
        scrollbar.grid(row=1, column=1, sticky="ns", padx=(0, 12), pady=(0, 8))
        tree.configure(yscrollcommand=scrollbar.set)

        actions = ttk.Frame(window)
        actions.grid(row=2, column=0, columnspan=2, sticky="e", padx=12, pady=(0, 12))
        confirm_button = ttk.Button(actions, text="Move files", state="disabled")
        confirm_button.pack(side="right")
        ttk.Button(actions, text="Cancel", command=window.destroy).pack(
            side="right", padx=(0, 8)
        )

        def fill_rows(start: int = 0) -> None:
            if not window.winfo_exists():
                return
            end = min(start + 200, len(plan.moves))
            for item in plan.moves[start:end]:
                tree.insert(
                    "",
                    "end",
                    values=(item.category, item.source.name, str(item.destination)),
                )
            if end < len(plan.moves):
                self.root.after(1, lambda: fill_rows(end))
            else:
                confirm_button.configure(
                    command=lambda: self._confirm_plan(window, plan),
                    state="normal",
                )

        fill_rows()
        window.grab_set()
        self.status_var.set(f"Preview ready: {len(plan.moves)} file(s).")

    def _confirm_plan(self, window: tk.Toplevel, plan: FilePlan) -> None:
        window.destroy()
        self.progress.configure(maximum=max(len(plan.moves), 1), value=0)

        def report_progress(completed: int, total: int, filename: str) -> None:
            self.worker_messages.put(("progress", (completed, total, filename)))

        self._start_worker(
            "organised",
            lambda: execute_plan(plan, report_progress),
        )

    def _show_organise_result(self, result: OrganiseResult) -> None:
        self.undo_history = list(result.moved)
        self.last_destination = result.moved[-1][1].parent if result.moved else None
        self.open_button.configure(
            state="normal" if self.last_destination is not None else "disabled"
        )
        self.undo_button.configure(state="normal" if self.undo_history else "disabled")
        for source, destination in result.moved:
            self.append_log(f"Moved: {source.name} -> {destination}")
        for file_path, error in result.errors:
            self.append_log(f"Could not move {file_path.name}: {error}")

        summary = (
            f"Moved {len(result.moved)} file(s); skipped {result.skipped} "
            "unsupported file(s) or folder(s)."
        )
        if result.errors:
            summary += f" {len(result.errors)} file(s) could not be moved; see Activity for details."
            self.status_var.set(f"Finished with {len(result.errors)} error(s)")
            messagebox.showwarning(
                "Organisation finished with errors", summary, parent=self.root
            )
        else:
            self.status_var.set(summary)
            messagebox.showinfo("Organisation complete", summary, parent=self.root)

    def undo(self) -> None:
        if not self.undo_history:
            return
        if not messagebox.askyesno(
            "Undo last run",
            f"Restore {len(self.undo_history)} file(s) to their original locations?",
            parent=self.root,
        ):
            return
        history = tuple(self.undo_history)

        def run_undo() -> tuple[list[tuple[Path, Path]], list[tuple[Path, str]]]:
            return undo_files(history)

        self._start_worker("undone", run_undo)

    def _show_undo_result(self, result: object) -> None:
        if not (
            isinstance(result, tuple)
            and len(result) == 2
            and isinstance(result[0], list)
            and isinstance(result[1], list)
        ):
            raise ValueError("The undo operation returned an invalid result.")
        restored, errors = result
        for current, original in restored:
            self.append_log(f"Restored: {current} -> {original}")
            self.undo_history.remove((original, current))
        for file_path, error in errors:
            self.append_log(f"Could not restore {file_path.name}: {error}")
        self.undo_button.configure(state="normal" if self.undo_history else "disabled")
        if errors:
            summary = f"Restored {len(restored)} file(s); {len(errors)} could not be restored. See Activity."
            self.status_var.set("Undo finished with errors")
            messagebox.showwarning("Undo finished with errors", summary, parent=self.root)
        else:
            summary = f"Restored {len(restored)} file(s) to their original locations."
            self.status_var.set(summary)
            messagebox.showinfo("Undo complete", summary, parent=self.root)

    def open_destination(self) -> None:
        if self.last_destination is None:
            return
        try:
            startfile = getattr(os, "startfile", None)
            if startfile is not None:
                startfile(str(self.last_destination))
            elif not webbrowser.open(self.last_destination.resolve().as_uri()):
                raise OSError("No application accepted the destination folder.")
        except OSError as error:
            messagebox.showerror(
                "Could not open destination", str(error), parent=self.root
            )

    def edit_file_types(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("Edit file types")
        window.transient(self.root)
        window.columnconfigure(0, weight=1)
        window.rowconfigure(1, weight=1)
        ttk.Label(
            window,
            text="Enter one category per line, followed by its comma-separated extensions.",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        editor = tk.Text(window, width=58, height=16, wrap="none")
        editor.grid(row=1, column=0, sticky="nsew", padx=12)
        editor.insert(
            "1.0",
            "\n".join(
                f"{category}: {', '.join(extensions)}"
                for category, extensions in self.file_types.items()
            ),
        )
        actions = ttk.Frame(window)
        actions.grid(row=2, column=0, sticky="e", padx=12, pady=12)

        def save() -> None:
            try:
                file_types = parse_file_types(editor.get("1.0", "end-1c"))
                save_file_types(file_types)
            except (OSError, ValueError, json.JSONDecodeError) as error:
                messagebox.showerror("Invalid file types", str(error), parent=window)
                return
            self.file_types = file_types
            self._build_destination_rows()
            window.destroy()
            self.append_log("Updated file type categories.")
            self.status_var.set("File types saved.")

        ttk.Button(actions, text="Cancel", command=window.destroy).pack(side="right")
        ttk.Button(actions, text="Save", command=save).pack(side="right", padx=(0, 8))
        window.grab_set()


def main() -> None:
    root = tk.Tk()
    FileOrganiserApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
