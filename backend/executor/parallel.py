import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from models.schemas import SQLTask
from db.clickhouse import execute_query, SQLSecurityError
from config import settings

logger = logging.getLogger(__name__)


class ParallelExecutor:
    def __init__(self, max_workers: Optional[int] = None):
        self.max_workers = max_workers or settings["executor"]["max_workers"]
        self.retry_shrink = settings["executor"]["retry_time_shrink"]

    def _run_one(self, task: SQLTask, progress_cb: Optional[Callable] = None) -> dict:
        start = time.perf_counter()
        try:
            df = execute_query(task.sql)
            elapsed = time.perf_counter() - start
            logger.debug("Task %s succeeded: %.2fs, %d rows", task.task_id, elapsed, len(df))
            if progress_cb:
                progress_cb(task.task_id, "success")
            return {
                "task_id": task.task_id,
                "status": "success",
                "df": df,
                "description": task.description,
            }
        except SQLSecurityError as e:
            elapsed = time.perf_counter() - start
            logger.error("Task %s blocked (%.2fs): %s", task.task_id, elapsed, e)
            if progress_cb:
                progress_cb(task.task_id, "error")
            return {
                "task_id": task.task_id,
                "status": "error",
                "error": str(e),
                "description": task.description,
            }
        except Exception as e:
            elapsed = time.perf_counter() - start
            logger.error("Task %s failed (%.2fs): %s", task.task_id, elapsed, e, exc_info=True)
            if progress_cb:
                progress_cb(task.task_id, "error")
            return {
                "task_id": task.task_id,
                "status": "error",
                "error": str(e),
                "description": task.description,
            }

    def run(self, tasks: list, progress_cb: Optional[Callable] = None) -> dict:
        logger.info("Starting parallel execution: %d tasks, max_workers=%d", len(tasks), self.max_workers)
        start = time.perf_counter()
        results = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self._run_one, t, progress_cb): t for t in tasks}
            for future in as_completed(futures):
                result = future.result()
                results[result["task_id"]] = result
        elapsed = time.perf_counter() - start
        logger.info("All tasks complete: %.2fs", elapsed)
        return results
