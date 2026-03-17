# evolution.py
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from llm import AnthropicClient
from patch_manager import PatchManager, PatchError


class EvolutionError(Exception):
    pass


class EvolutionManager:
    def __init__(self, project_dir: Path, llm: AnthropicClient):
        self.project_dir = Path(project_dir).resolve()
        self.llm = llm
        self.patch_manager = PatchManager(self.project_dir)
        self.evolution_dir = self.project_dir / "evolution"
        self.evolution_dir.mkdir(parents=True, exist_ok=True)

    def _read_tail(self, path: Path, max_chars: int = 6000) -> str:
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8", errors="ignore")
        return text[-max_chars:]

    def _build_prompt(
        self,
        file_name: str,
        current_code: str,
        error_context: str,
        reason: str,
    ) -> str:
        return (
            "Ты исправляешь Python-файл локального AI-ассистента.\n"
            "Твоя задача: вернуть ПОЛНЫЙ новый код ОДНОГО файла, без пояснений, без markdown.\n\n"

            f"Целевой файл: {file_name}\n"
            f"Причина: {reason}\n\n"

            "Правила:\n"
            "- верни только валидный Python-код\n"
            "- не меняй архитектуру радикально\n"
            "- не добавляй shell=True\n"
            "- не добавляй os.system, eval, exec\n"
            "- не добавляй requests.get/post без крайней необходимости\n"
            "- сохраняй совместимость с остальными файлами проекта\n"
            "- исправь конкретную проблему минимально и аккуратно\n\n"

            "Контекст ошибки/лога:\n"
            f"{error_context}\n\n"

            "Текущий код файла:\n"
            f"{current_code}"
        )

    def _extract_code(self, text: str) -> str:
        stripped = text.strip()

        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            return "\n".join(lines).strip()

        return stripped

    def generate_patch_candidate(
        self,
        file_name: str,
        reason: str,
        error_context: str = "",
    ) -> Dict[str, object]:
        if not self.patch_manager.is_allowed_target(file_name):
            raise EvolutionError(f"target_not_allowed:{file_name}")

        current_code = self.patch_manager.read_file(file_name)
        prompt = self._build_prompt(
            file_name=file_name,
            current_code=current_code,
            error_context=error_context,
            reason=reason,
        )

        raw = self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            system=(
                "Ты генератор безопасных Python-патчей. "
                "Возвращай только полный код файла, без комментариев вне кода."
            ),
            max_tokens=4000,
        )

        new_code = self._extract_code(raw)
        report = self.patch_manager.validate_patch(file_name, new_code)

        patch_path = self.patch_manager.write_patch_candidate(
            file_name=file_name,
            new_code=new_code,
            reason=reason,
            author="evolution_manager",
        )

        meta = {
            "created_at": datetime.now().isoformat(),
            "target": file_name,
            "reason": reason,
            "patch_path": str(patch_path),
            "validation": report,
        }

        meta_path = self.evolution_dir / f"{patch_path.stem}.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        return meta

    def apply_candidate(self, patch_path: Path, file_name: str) -> Dict[str, object]:
        return self.patch_manager.apply_patch_file(file_name, patch_path)

    def evolve_from_log(
        self,
        file_name: str,
        log_path: Path,
        reason: str,
    ) -> Dict[str, object]:
        error_context = self._read_tail(log_path)
        return self.generate_patch_candidate(
            file_name=file_name,
            reason=reason,
            error_context=error_context,
        )

    def auto_fix(
        self,
        file_name: str,
        log_path: Path,
        reason: str,
    ) -> Dict[str, object]:
        meta = self.evolve_from_log(file_name=file_name, log_path=log_path, reason=reason)
        validation = meta["validation"]

        if not validation["valid"]:
            return {
                "status": "generated_but_not_applied",
                "meta": meta,
            }

        patch_path = Path(meta["patch_path"])
        try:
            result = self.apply_candidate(patch_path, file_name)
            return {
                "status": "applied",
                "meta": meta,
                "result": result,
            }
        except PatchError as e:
            return {
                "status": "apply_failed",
                "meta": meta,
                "error": str(e),
            }

    def recent_candidates(self) -> List[Path]:
        return sorted(self.evolution_dir.glob("patch_*.json"))

    def latest_candidate(self) -> Optional[Path]:
        items = self.recent_candidates()
        return items[-1] if items else None
