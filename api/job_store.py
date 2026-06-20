"""
Thread-safe in-memory ジョブレジストリ。

各 Job はライフサイクルステートと Human-in-the-loop 用の同期プリミティブを持つ。
永続化は行わない — プロセス再起動でジョブ情報は消える。
将来的に Redis や SQLite に差し替えたい場合は JobStore クラスの実装を置き換える。
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from api.schemas import JobStatus


@dataclass
class Job:
    job_id:           str
    thread_id:        str
    status:           JobStatus           = JobStatus.pending
    interrupt_data:   dict[str, Any] | None = None
    result:           str | None          = None
    files:            dict[str, str] | None = None
    error:            str | None          = None
    estimated_cost:   float | None        = None
    estimated_profit: float | None        = None

    # HITL 用: worker スレッドが wait_for_approval() でブロックし、
    # HTTP ハンドラが submit_feedback() でアンブロックする。
    _approve_event: threading.Event = field(
        default_factory=threading.Event, init=False, repr=False
    )
    _feedback: str = field(default="", init=False, repr=False)

    def wait_for_approval(self, timeout: float = 3600.0) -> str | None:
        """
        ユーザーが /approve を叩くまでブロックする (worker スレッドから呼ぶ)。
        timeout 秒以内に承認されなければ None を返す。
        """
        fired = self._approve_event.wait(timeout=timeout)
        return self._feedback if fired else None

    def submit_feedback(self, feedback: str) -> None:
        """HTTP ハンドラから呼ぶ。worker スレッドのブロックを解除する。"""
        self._feedback = feedback
        self._approve_event.set()


class JobStore:
    """スレッドセーフなジョブレジストリ。"""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, thread_id: str | None = None) -> Job:
        job_id = str(uuid.uuid4())
        job = Job(job_id=job_id, thread_id=thread_id or job_id)
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def delete(self, job_id: str) -> bool:
        with self._lock:
            return self._jobs.pop(job_id, None) is not None

    def list_all(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())


# モジュールレベルのシングルトン
job_store = JobStore()
