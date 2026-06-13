"""部署状态机。"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class Status(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Deployment:
    """一次部署操作的状态跟踪。"""
    components: List[str] = field(default_factory=list)
    status: Status = Status.PENDING
    results: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def start(self):
        self.status = Status.RUNNING

    def component_done(self, comp_key: str):
        self.results[comp_key] = {"status": "done"}

    def component_failed(self, comp_key: str, rc: int = -1):
        self.results[comp_key] = {"status": "failed", "rc": rc}

    def finish(self):
        all_ok = all(r["status"] == "done" for r in self.results.values())
        self.status = Status.DONE if all_ok else Status.FAILED
