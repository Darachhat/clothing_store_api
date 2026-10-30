import asyncio
from typing import Callable, Any, Dict, Optional

from app.core.enum.common_enum import EXECUTION_STRATEGY_ENUM
from app.core.logger import logger


class TASK_DISPATCHER:

    @staticmethod
    def dispatch(
        task_func   : Callable
        , strategy  : EXECUTION_STRATEGY_ENUM = EXECUTION_STRATEGY_ENUM.ASYNCIO
        , args      : Optional[tuple] = None
        , kwargs    : Optional[Dict[str, Any]] = None
    ) -> Any:
        args   = args or ()
        kwargs = kwargs or {}

        if strategy == EXECUTION_STRATEGY_ENUM.CELERY:
            if hasattr(task_func, "delay"):
                logger.info(f"Dispatching Celery task: {task_func.__name__}")
                return task_func.delay(*args, **kwargs)
            else:
                logger.warning(f"Task {task_func.__name__} does not have Celery delay method. Falling back to asyncio.")
                return asyncio.create_task(task_func(*args, **kwargs))

        elif strategy == EXECUTION_STRATEGY_ENUM.ASYNCIO:
            logger.info(f"Dispatching in-memory asyncio task: {task_func.__name__}")
            if asyncio.iscoroutinefunction(task_func):
                return asyncio.create_task(task_func(*args, **kwargs))
            else:
                return asyncio.to_thread(task_func, *args, **kwargs)

        else:
            raise ValueError(f"Unsupported execution strategy: {strategy}")

