import time
import random
import logging
from functools import wraps
from typing import Callable, Any, Type, Tuple

logger = logging.getLogger("autonomous_creator.retry")


def with_retry(
    max_attempts: int = 3,
    backoff_base: float = 2.0,
    initial_delay: float = 0.5,
    max_delay: float = 10.0,
    allowed_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    fallback_factory: Callable[..., Any] | None = None
) -> Callable:
    """
    Decorator for robust retry with exponential backoff and jitter.
    
    Args:
        max_attempts: Maximum number of attempts.
        backoff_base: Exponential multiplier.
        initial_delay: Initial sleep in seconds.
        max_delay: Cap on delay in seconds.
        allowed_exceptions: Tuple of exceptions to catch and retry.
        fallback_factory: Optional callable returning a fallback result if all retries fail.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            delay = initial_delay
            last_error = None
            
            while attempt < max_attempts:
                attempt += 1
                try:
                    return func(*args, **kwargs)
                except allowed_exceptions as exc:
                    last_error = exc
                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} for {func.__name__} failed with: {exc}"
                    )
                    if attempt >= max_attempts:
                        break
                    
                    # Compute delay with jitter
                    sleep_time = min(delay * (backoff_base ** (attempt - 1)), max_delay)
                    jitter = random.uniform(0.8, 1.2) * sleep_time
                    time.sleep(jitter)
            
            if fallback_factory is not None:
                logger.info(f"Invoking fallback factory for {func.__name__} after {max_attempts} failures.")
                return fallback_factory(*args, **kwargs)
            
            raise last_error  # Re-raise final exception if no fallback provided
        return wrapper
    return decorator
