import queue
import threading
import time
from typing import Optional

from config import CONFIG
from agent import Agent
from db import MemoryDB
from state import AgentState
from utils import append_log


class BackgroundWorker:
    def __init__(self, agent: Agent, state: AgentState, db: MemoryDB):
        self.agent = agent
        self.state = state
        self.db = db
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.pending_messages: "queue.Queue[str]" = queue.Queue()

    def start(self) -> None:
        if not CONFIG["background_enabled"]:
            return
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.running = False

    def _loop(self) -> None:
        time.sleep(30)
        while self.running:
            try:
                self._tick()
            except Exception as e:
                append_log(f"BG ERROR: {e}")

            sleep_left = int(CONFIG["background_interval_sec"])
            while self.running and sleep_left > 0:
                time.sleep(1)
                sleep_left -= 1

    def _tick(self) -> None:
        self.state.background_cycles += 1
        cycle = self.state.background_cycles

        tasks = [
            "Тихо проверь батарею. Если заряд ниже 20, коротко предупреди хозяина.",
            "Коротко придумай одну полезную заметку для Андрея. Если действительно полезно, сохрани через append_note.",
            "Если есть смысл, проверь погоду в Hamar и дай короткую сводку без лишнего мусора.",
            "Посмотри последние заметки и предложи краткое полезное продолжение, только если оно реально нужно.",
        ]
        prompt = f"[ФОН #{cycle}] {tasks[cycle % len(tasks)]}"

        reply = self.agent.respond(prompt)
        text = reply.strip()

        if text and not text.startswith("Ошибка"):
            self.pending_messages.put(text[:300])

    def pop_pending(self) -> Optional[str]:
        try:
            return self.pending_messages.get_nowait()
        except queue.Empty:
            return None
