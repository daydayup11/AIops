from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from models.schemas import SQLTask
from db.clickhouse import execute_query, SQLSecurityError
from config import settings


class ParallelExecutor:
    def __init__(self, max_workers: Optional[int] = None):
        self.max_workers = max_workers or settings["executor"]["max_workers"]
        self.retry_shrink = settings["executor"]["retry_time_shrink"]

    def _run_one(self, task: SQLTask, progress_cb: Optional[Callable] = None) -> dict:
        try:
            df = execute_query(task.sql)
            if progress_cb:
                progress_cb(task.task_id, "success")
            return {
                "task_id": task.task_id,
                "status": "success",
                "df": df,
                "description": task.description,
            }
        except SQLSecurityError as e:
            if progress_cb:
                progress_cb(task.task_id, "error")
            return {
                "task_id": task.task_id,
                "status": "error",
                "error": str(e),
                "description": task.description,
            }
        except Exception as e:
            if progress_cb:
                progress_cb(task.task_id, "error")
            return {
                "task_id": task.task_id,
                "status": "error",
                "error": str(e),
                "description": task.description,
            }

    def run(self, tasks: list, progress_cb: Optional[Callable] = None) -> dict:
        """Execute tasks in parallel using a thread pool.

        Args:
            tasks: List of SQLTask objects to execute.
            progress_cb: Optional callback(task_id, status) called when each task completes.

        Returns:
            Dict mapping task_id -> result dict with keys: task_id, status, description,
            and either 'df' (on success) or 'error' (on failure).
        """
        results = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self._run_one, t, progress_cb): t for t in tasks}
            for future in as_completed(futures):
                result = future.result()
                results[result["task_id"]] = result
        return results
