# patch_manager.py
import ast
import difflib
import importlib.util
import py_compile
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class PatchError(Exception):
    pass


class PatchManager:
    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir).resolve()
        self.patches_dir = self.project_dir / "patches"
        self.backups_dir = self.project_dir / "backups"
        self.tests_dir = self.project_dir / "tests"

        self.patches_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self.tests_dir.mkdir(parents=True, exist_ok=True)

        self.allowed_files = {
            "agent.py",
            "parser.py",
            "tools.py",
            "background.py",
        }

        self.protected_files = {
            "main.py",
            "config.py",
            "db.py",
            "safety.py",
            "llm.py",
            "state.py",
            "utils.py",
        }

    def is_allowed_target(self, file_name: str) -> bool:
        return file_name in self.allowed_files

    def is_protected_target(self, file_name: str) -> bool:
        return file_name in self.protected_files

    def get_target_path(self, file_name: str) -> Path:
        target = (self.project_dir / file_name).resolve()
        try:
            target.relative_to(self.project_dir)
        except Exception as e:
            raise PatchError(f"path_outside_project:{file_name}") from e
        return target

    def read_file(self, file_name: str) -> str:
        path = self.get_target_path(file_name)
        if not path.exists():
            raise PatchError(f"file_not_found:{file_name}")
        return path.read_text(encoding="utf-8")

    def write_patch_candidate(
        self,
        file_name: str,
        new_code: str,
        reason: str = "",
        author: str = "aria",
    ) -> Path:
        if not self.is_allowed_target(file_name):
            raise PatchError(f"target_not_allowed:{file_name}")

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        patch_path = self.patches_dir / f"patch_{file_name.replace('.py', '')}_{ts}.py"
        meta_path = self.patches_dir / f"patch_{file_name.replace('.py', '')}_{ts}.meta.txt"

        patch_path.write_text(new_code, encoding="utf-8")

        meta = [
            f"created_at={datetime.now().isoformat()}",
            f"target={file_name}",
            f"author={author}",
            f"reason={reason.strip()}",
            f"patch_file={patch_path.name}",
        ]
        meta_path.write_text("\n".join(meta), encoding="utf-8")
        return patch_path

    def create_backup(self, file_name: str) -> Path:
        target = self.get_target_path(file_name)
        if not target.exists():
            raise PatchError(f"file_not_found:{file_name}")

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backups_dir / f"{file_name}.{ts}.bak"
        shutil.copy2(target, backup_path)
        return backup_path

    def restore_backup(self, backup_path: Path, file_name: str) -> None:
        target = self.get_target_path(file_name)
        shutil.copy2(backup_path, target)

    def validate_python_syntax(self, code: str) -> Tuple[bool, str]:
        try:
            ast.parse(code)
            return True, "ok"
        except SyntaxError as e:
            return False, f"syntax_error:{e}"

    def validate_importable_file(self, path: Path) -> Tuple[bool, str]:
        try:
            py_compile.compile(str(path), doraise=True)
            return True, "ok"
        except py_compile.PyCompileError as e:
            return False, f"compile_error:{e}"

    def basic_safety_scan(self, code: str) -> Tuple[bool, List[str]]:
        bad_patterns = [
            "os.system(",
            "subprocess.run(",
            "subprocess.Popen(",
            "shell=True",
            "eval(",
            "exec(",
            "__import__(",
            "shutil.rmtree(",
            "unlink(",
            "rm -rf",
            "requests.get(",
            "requests.post(",
        ]

        hits = [p for p in bad_patterns if p in code]
        return len(hits) == 0, hits

    def diff(self, old_code: str, new_code: str, file_name: str = "file.py") -> str:
        old_lines = old_code.splitlines(keepends=True)
        new_lines = new_code.splitlines(keepends=True)
        return "".join(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=f"a/{file_name}",
                tofile=f"b/{file_name}",
            )
        )

    def validate_patch(self, file_name: str, new_code: str) -> Dict[str, object]:
        syntax_ok, syntax_msg = self.validate_python_syntax(new_code)
        compile_ok = False
        compile_msg = "skipped"

        safe_ok, safe_hits = self.basic_safety_scan(new_code)

        temp_path = self.patches_dir / f".tmp_validate_{file_name}"
        try:
            temp_path.write_text(new_code, encoding="utf-8")
            compile_ok, compile_msg = self.validate_importable_file(temp_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

        return {
            "target": file_name,
            "allowed": self.is_allowed_target(file_name),
            "protected": self.is_protected_target(file_name),
            "syntax_ok": syntax_ok,
            "syntax_msg": syntax_msg,
            "compile_ok": compile_ok,
            "compile_msg": compile_msg,
            "safety_ok": safe_ok,
            "safety_hits": safe_hits,
            "valid": self.is_allowed_target(file_name) and syntax_ok and compile_ok and safe_ok,
        }

    def apply_patch(self, file_name: str, new_code: str) -> Dict[str, object]:
        report = self.validate_patch(file_name, new_code)
        if not report["valid"]:
            raise PatchError(f"patch_invalid:{report}")

        old_code = self.read_file(file_name)
        backup_path = self.create_backup(file_name)
        target_path = self.get_target_path(file_name)

        try:
            target_path.write_text(new_code, encoding="utf-8")
            compiled_ok, compiled_msg = self.validate_importable_file(target_path)
            if not compiled_ok:
                raise PatchError(f"post_apply_compile_failed:{compiled_msg}")

            patch_diff = self.diff(old_code, new_code, file_name=file_name)
            diff_path = self.patches_dir / f"applied_{file_name.replace('.py', '')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.diff"
            diff_path.write_text(patch_diff, encoding="utf-8")

            return {
                "status": "applied",
                "target": file_name,
                "backup": str(backup_path),
                "diff": str(diff_path),
            }

        except Exception as e:
            self.restore_backup(backup_path, file_name)
            raise PatchError(f"patch_reverted:{e}") from e

    def apply_patch_file(self, file_name: str, patch_path: Path) -> Dict[str, object]:
        patch_path = Path(patch_path).resolve()
        if not patch_path.exists():
            raise PatchError(f"patch_file_not_found:{patch_path}")
        new_code = patch_path.read_text(encoding="utf-8")
        return self.apply_patch(file_name, new_code)

    def list_patch_candidates(self) -> List[Path]:
        return sorted(self.patches_dir.glob("patch_*.py"))

    def list_backups(self, file_name: Optional[str] = None) -> List[Path]:
        if file_name:
            return sorted(self.backups_dir.glob(f"{file_name}.*.bak"))
        return sorted(self.backups_dir.glob("*.bak"))

    def latest_backup(self, file_name: str) -> Optional[Path]:
        backups = self.list_backups(file_name)
        return backups[-1] if backups else None

    def rollback_latest(self, file_name: str) -> Dict[str, str]:
        backup = self.latest_backup(file_name)
        if not backup:
            raise PatchError(f"no_backup_for:{file_name}")

        target = self.get_target_path(file_name)
        shutil.copy2(backup, target)
        return {
            "status": "rolled_back",
            "target": file_name,
            "backup": str(backup),
        }
