import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import file_organiser


class FilePlanningTests(unittest.TestCase):
    def test_preview_does_not_move_files_and_plans_collision_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            destination = root / "pdf"
            source.mkdir()
            destination.mkdir()
            (source / "report.PDF").write_text("new")
            (source / "notes.unsupported").write_text("skip")
            (source / "subfolder").mkdir()
            (destination / "report.PDF").write_text("existing")

            plan = file_organiser.plan_files(
                source, {"PDF Documents": destination}
            )

            self.assertEqual(len(plan.moves), 1)
            self.assertEqual(plan.moves[0].destination.name, "report_1.PDF")
            self.assertEqual(plan.skipped, 2)
            self.assertTrue((source / "report.PDF").exists())
            self.assertFalse((destination / "report_1.PDF").exists())

    def test_invalid_source_and_destination_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            source.mkdir()
            destination_file = root / "not-a-folder"
            destination_file.write_text("file")

            with self.assertRaisesRegex(ValueError, "Source folder"):
                file_organiser.plan_files(root / "missing", {})
            with self.assertRaisesRegex(ValueError, "cannot be the source"):
                file_organiser.plan_files(source, {"PDF Documents": source})
            with self.assertRaisesRegex(ValueError, "not a folder"):
                file_organiser.plan_files(
                    source, {"PDF Documents": destination_file}
                )

    def test_execute_moves_supported_files_and_reports_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            source.mkdir()
            (source / "good.txt").write_text("good")
            (source / "bad.txt").write_text("bad")
            plan = file_organiser.plan_files(source, {})
            real_move = file_organiser.shutil.move

            def move_with_failure(source_path: str, destination_path: str) -> str:
                if Path(source_path).name == "bad.txt":
                    raise OSError("test failure")
                return real_move(source_path, destination_path)

            with patch("file_organiser.shutil.move", side_effect=move_with_failure):
                result = file_organiser.execute_plan(plan)

            self.assertEqual({source.name for source, _ in result.moved}, {"good.txt"})
            self.assertEqual({source.name for source, _ in result.errors}, {"bad.txt"})
            self.assertTrue((source / "bad.txt").exists())

    def test_undo_never_overwrites_a_recreated_original(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            original = root / "original.txt"
            current = root / "destination" / "original.txt"
            current.parent.mkdir()
            current.write_text("moved")
            original.write_text("new content")

            restored, errors = file_organiser.undo_files([(original, current)])

            self.assertEqual(restored, [])
            self.assertEqual(len(errors), 1)
            self.assertEqual(original.read_text(), "new content")
            self.assertTrue(current.exists())

    def test_file_type_parser_rejects_duplicate_extensions(self) -> None:
        with self.assertRaisesRegex(ValueError, "assigned more than once"):
            file_organiser.parse_file_types(
                "Documents: .pdf\nOther: .PDF"
            )
        with self.assertRaisesRegex(ValueError, "Invalid category"):
            file_organiser.parse_file_types("../outside: .abc")
        self.assertEqual(
            file_organiser.parse_file_types("Custom: .abc, .def"),
            {"Custom": (".abc", ".def")},
        )

    def test_file_type_configuration_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            config = Path(temporary_directory) / "settings.json"
            custom_types = {"Custom Documents": (".abc", ".def")}

            file_organiser.save_file_types(custom_types, config)

            self.assertEqual(file_organiser.load_file_types(config), custom_types)


if __name__ == "__main__":
    unittest.main()
