# tests_runner.py
import importlib
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List


class TestsRunner:
    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir).resolve()
        self.tests_dir = self.project_dir / "tests"
        self.tests_dir.mkdir(parents=True, exist_ok=True)

        self.report_file = self.project_dir / "logs" / "tests.log"
        self.report_file.parent.mkdir(exist_ok=True)

    def _log(self, text: str):
        with open(self.report_file, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} | {text}\n")

    def run_import_tests(self) -> Dict[str, bool]:
        modules = [
            "config",
            "utils",
            "db",
            "state",
            "parser",
            "tools",
            "agent",
            "background",
        ]

        results = {}

        for m in modules:
            try:
                importlib.invalidate_caches()
                importlib.import_module(m)
                results[m] = True
                self._log(f"IMPORT_OK {m}")
            except Exception:
                results[m] = False
                self._log(f"IMPORT_FAIL {m}")
                self._log(traceback.format_exc())

        return results

    def run_basic_agent_test(self) -> bool:
        try:
            from agent import Agent
            from state import AgentState

            state = AgentState()
            agent = Agent(state)

            reply = agent.handle_message("ping")

            ok = isinstance(reply, str)
            self._log(f"AGENT_TEST {'OK' if ok else 'FAIL'}")
            return ok

        except Exception:
            self._log("AGENT_TEST_FAIL")
            self._log(traceback.format_exc())
            return False

    def run_all(self) -> Dict[str, object]:
        import_results = self.run_import_tests()
        agent_ok = self.run_basic_agent_test()

        ok = all(import_results.values()) and agent_ok

        report = {
            "ok": ok,
            "imports": import_results,
            "agent": agent_ok,
            "time": datetime.now().isoformat(),
        }

        self._log(f"TEST_SUMMARY ok={ok}")
        return report
