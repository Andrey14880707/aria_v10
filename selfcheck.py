# selfcheck.py
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


class SelfCheck:
    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir).resolve()
        self.log_dir = self.project_dir / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.error_log = self.log_dir / "errors.log"
        self.health_log = self.log_dir / "health.log"

    def log_error(self, error: Exception, context: str = "") -> None:
        entry = [
            f"time={datetime.now().isoformat()}",
            f"context={context}",
            f"error={repr(error)}",
            "traceback=",
            traceback.format_exc(),
            "-" * 60,
        ]
        with open(self.error_log, "a", encoding="utf-8") as f:
            f.write("\n".join(entry) + "\n")

    def log_health(self, message: str) -> None:
        entry = f"{datetime.now().isoformat()} | {message}"
        with open(self.health_log, "a", encoding="utf-8") as f:
            f.write(entry + "\n")

    def read_recent_errors(self, max_chars: int = 5000) -> str:
        if not self.error_log.exists():
            return ""
        text = self.error_log.read_text(encoding="utf-8", errors="ignore")
        return text[-max_chars:]

    def system_health(self) -> Dict[str, bool]:
        checks = {
            "config": (self.project_dir / "config.py").exists(),
            "agent": (self.project_dir / "agent.py").exists(),
            "tools": (self.project_dir / "tools.py").exists(),
            "db": (self.project_dir / "db.py").exists(),
            "logs": self.log_dir.exists(),
        }
        return checks

    def run_basic_tests(self) -> List[Tuple[str, bool]]:
        results = []

        try:
            import importlib
            modules = [
                "config",
                "utils",
                "db",
                "state",
                "parser",
                "tools",
                "agent",
            ]

            for m in modules:
                try:
                    importlib.import_module(m)
                    results.append((m, True))
                except Exception:
                    results.append((m, False))

        except Exception:
            results.append(("import_system", False))

        return results

    def health_report(self) -> Dict[str, object]:
        checks = self.system_health()
        tests = self.run_basic_tests()

        ok = all(checks.values()) and all(t[1] for t in tests)

        report = {
            "ok": ok,
            "files": checks,
            "imports": {name: status for name, status in tests},
            "timestamp": datetime.now().isoformat(),
        }

        self.log_health(f"health_check ok={ok}")
        return report
