# state.py
from dataclasses import dataclass


@dataclass
class AgentState:
    face: str = "happy"
    energy: int = 80
    mood: int = 75
    hunger: int = 30
    last_thought: str = "..."
    commands_run: int = 0
    background_cycles: int = 0
    session_id: int = 0

    def clamp(self) -> None:
        self.energy = max(0, min(100, self.energy))
        self.mood = max(0, min(100, self.mood))
        self.hunger = max(0, min(100, self.hunger))
