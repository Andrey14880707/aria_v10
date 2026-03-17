# mutation_engine.py
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from evolution import EvolutionManager
from selfcheck import SelfCheck
from tests_runner import TestsRunner


class MutationEngine:
    def __init__(self, project_dir: Path, llm):
        self.project_dir = Path(project_dir).resolve()
        self.llm = llm

        self.selfcheck = SelfCheck(self.project_dir)
        self.evolution = EvolutionManager(self.project_dir, llm)
        self.tests = TestsRunner(self.project_dir)

        self.engine_dir = self.project_dir / "mutation_engine"
        self.engine_dir.mkdir(parents=True, exist_ok=True)

        self.state_file = self.engine_dir / "state.json"
        self.history_file = self.engine_dir / "history.jsonl"

        self.allowed_targets = {
            "agent.py",
            "parser.py",
            "tools.py",
            "background.py",
        }

    def _load_state(self) -> Dict[str, object]:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "runs": 0,
            "last_run": None,
            "last_target": None,
            "last_status": None,
            "recent_errors_hash": None,
        }

    def _save_state(self, state: Dict[str, object]) -> None:
        self.state_file.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _append_history(self, entry: Dict[str, object]) -> None:
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _hash_text(self, text: str) -> str:
        return str(abs(hash(text)))

    def _choose_target(self, error_text: str) -> Optional[str]:
        low = error_text.lower()

        heuristics = [
            ("tool", "tools.py"),
            ("note", "tools.py"),
            ("weather", "tools.py"),
            ("camera", "tools.py"),
            ("vision", "agent.py"),
            ("json", "parser.py"),
            ("parse", "parser.py"),
            ("state", "parser.py"),
            ("background", "background.py"),
            ("thread", "background.py"),
            ("agent", "agent.py"),
        ]

        for needle, target in heuristics:
            if needle in low:
                return target

        return "agent.py"

    def _build_reason(self, error_text: str, target: str) -> str:
        preview = error_text.strip().splitlines()[-1] if error_text.strip() else "unknown_error"
        return f"Автоисправление по логам для {target}: {preview[:200]}"

    def inspect(self) -> Dict[str, object]:
        report = self.selfcheck.health_report()
        recent_errors = self.selfcheck.read_recent_errors()

        return {
            "health": report,
            "recent_errors": recent_errors,
            "has_errors": bool(recent_errors.strip()),
        }

    def generate_candidate_from_errors(self) -> Dict[str, object]:
        recent_errors = self.selfcheck.read_recent_errors()
        if not recent_errors.strip():
            return {
                "status": "no_errors",
                "message": "Нет ошибок для анализа",
            }

        target = self._choose_target(recent_errors)
        if not target or target not in self.allowed_targets:
            return {
                "status": "no_target",
                "message": "Не удалось выбрать файл для исправления",
            }

        reason = self._build_reason(recent_errors, target)
        meta = self.evolution.generate_patch_candidate(
            file_name=target,
            reason=reason,
            error_context=recent_errors,
        )

        entry = {
            "time": datetime.now().isoformat(),
            "action": "generate_candidate",
            "target": target,
            "status": "ok",
            "meta": meta,
        }
        self._append_history(entry)

        return {
            "status": "candidate_generated",
            "target": target,
            "meta": meta,
        }

    def validate_candidate(self, patch_path: Path, file_name: str) -> Dict[str, object]:
        patch_path = Path(patch_path).resolve()
        if not patch_path.exists():
            return {
                "status": "patch_not_found",
                "patch_path": str(patch_path),
            }

        code = patch_path.read_text(encoding="utf-8")
        report = self.evolution.patch_manager.validate_patch(file_name, code)

        entry = {
            "time": datetime.now().isoformat(),
            "action": "validate_candidate",
            "target": file_name,
            "patch_path": str(patch_path),
            "status": "ok",
            "report": report,
        }
        self._append_history(entry)

        return {
            "status": "validated",
            "target": file_name,
            "patch_path": str(patch_path),
            "report": report,
        }

    def apply_candidate_with_tests(self, patch_path: Path, file_name: str) -> Dict[str, object]:
        patch_path = Path(patch_path).resolve()

        validation = self.validate_candidate(patch_path, file_name)
        report = validation.get("report", {})

        if not report or not report.get("valid"):
            result = {
                "status": "candidate_invalid",
                "target": file_name,
                "patch_path": str(patch_path),
                "validation": report,
            }
            self._append_history({
                "time": datetime.now().isoformat(),
                "action": "apply_candidate_with_tests",
                "status": "blocked_invalid",
                "result": result,
            })
            return result

        apply_result = self.evolution.apply_candidate(patch_path, file_name)
        tests_report = self.tests.run_all()

        if not tests_report.get("ok"):
            rollback_result = self.evolution.patch_manager.rollback_latest(file_name)
            result = {
                "status": "rolled_back_after_failed_tests",
                "target": file_name,
                "patch_path": str(patch_path),
                "apply_result": apply_result,
                "tests_report": tests_report,
                "rollback_result": rollback_result,
            }
            self._append_history({
                "time": datetime.now().isoformat(),
                "action": "apply_candidate_with_tests",
                "status": "rolled_back",
                "result": result,
            })
            return result

        result = {
            "status": "applied_and_tests_passed",
            "target": file_name,
            "patch_path": str(patch_path),
            "apply_result": apply_result,
            "tests_report": tests_report,
        }
        self._append_history({
            "time": datetime.now().isoformat(),
            "action": "apply_candidate_with_tests",
            "status": "success",
            "result": result,
        })
        return result

    def auto_cycle(self) -> Dict[str, object]:
        state = self._load_state()
        state["runs"] = int(state.get("runs", 0)) + 1
        state["last_run"] = datetime.now().isoformat()

        recent_errors = self.selfcheck.read_recent_errors()
        if not recent_errors.strip():
            state["last_status"] = "no_errors"
            self._save_state(state)
            result = {
                "status": "no_errors",
                "runs": state["runs"],
            }
            self._append_history({
                "time": datetime.now().isoformat(),
                "action": "auto_cycle",
                "result": result,
            })
            return result

        current_hash = self._hash_text(recent_errors)
        if state.get("recent_errors_hash") == current_hash:
            state["last_status"] = "same_errors_skipped"
            self._save_state(state)
            result = {
                "status": "same_errors_skipped",
                "runs": state["runs"],
            }
            self._append_history({
                "time": datetime.now().isoformat(),
                "action": "auto_cycle",
                "result": result,
            })
            return result

        target = self._choose_target(recent_errors)
        if not target:
            state["last_status"] = "no_target"
            self._save_state(state)
            result = {
                "status": "no_target",
                "runs": state["runs"],
            }
            self._append_history({
                "time": datetime.now().isoformat(),
                "action": "auto_cycle",
                "result": result,
            })
            return result

        reason = self._build_reason(recent_errors, target)

        try:
            meta = self.evolution.generate_patch_candidate(
                file_name=target,
                reason=reason,
                error_context=recent_errors,
            )

            validation = meta.get("validation", {})
            if not validation.get("valid"):
                state["last_target"] = target
                state["last_status"] = "generated_invalid_candidate"
                state["recent_errors_hash"] = current_hash
                self._save_state(state)

                result = {
                    "status": "generated_invalid_candidate",
                    "target": target,
                    "meta": meta,
                }
                self._append_history({
                    "time": datetime.now().isoformat(),
                    "action": "auto_cycle",
                    "result": result,
                })
                return result

            patch_path = Path(meta["patch_path"])
            result = self.apply_candidate_with_tests(patch_path, target)

            state["last_target"] = target
            state["last_status"] = result["status"]
            state["recent_errors_hash"] = current_hash
            self._save_state(state)

            self._append_history({
                "time": datetime.now().isoformat(),
                "action": "auto_cycle",
                "result": result,
            })
            return result

        except Exception as e:
            state["last_target"] = target
            state["last_status"] = f"exception:{e}"
            self._save_state(state)

            result = {
                "status": "exception",
                "target": target,
                "error": str(e),
            }
            self._append_history({
                "time": datetime.now().isoformat(),
                "action": "auto_cycle",
                "result": result,
            })
            return result

    def recent_history(self, limit: int = 20) -> List[Dict[str, object]]:
        if not self.history_file.exists():
            return []

        lines = self.history_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        items = []
        for line in lines[-limit:]:
            try:
                items.append(json.loads(line))
            except Exception:
                continue
        return items
