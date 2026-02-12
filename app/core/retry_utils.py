"""
Retry utilities and error handling for Menu Green.
Provides decorators and helpers for robust LLM/API calls.
"""
import asyncio
import logging
from typing import TypeVar, Callable, Any, Optional, Coroutine
from functools import wraps
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable, GoogleAPIError

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    

def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retry_on: tuple = (ResourceExhausted, ServiceUnavailable, GoogleAPIError, Exception),
):
    """
    Decorator for async functions with exponential backoff retry.
    
    Args:
        max_attempts: Maximum retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap
        retry_on: Tuple of exception types to retry on
        
    Usage:
        @with_retry(max_attempts=3, base_delay=2)
        async def my_function():
            ...
    """
    def decorator(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            attempt = 0
            last_exception = None
            
            while attempt < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except retry_on as e:
                    attempt += 1
                    last_exception = e
                    
                    if attempt >= max_attempts:
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise
                    
                    # Exponential backoff
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed for {func.__name__}. "
                        f"Retrying in {delay:.1f}s... Error: {type(e).__name__}: {str(e)[:100]}"
                    )
                    await asyncio.sleep(delay)
            
            # Should never reach here, but for safety
            raise last_exception or Exception(f"Failed after {max_attempts} attempts")
        
        return wrapper
    return decorator


def with_fallback(fallback_value: Any = None):
    """
    Decorator that returns a fallback value if function fails.
    
    Args:
        fallback_value: Value to return on failure
        
    Usage:
        @with_fallback(fallback_value=[])
        async def get_recipes():
            ...
    """
    def decorator(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.warning(
                    f"Function {func.__name__} failed, returning fallback. "
                    f"Error: {type(e).__name__}: {str(e)[:100]}"
                )
                return fallback_value
        
        return wrapper
    return decorator


async def safe_llm_call(
    llm_func: Callable,
    prompt: str,
    max_attempts: int = 3,
    fallback_response: str = "Xin lỗi, tôi gặp sự cố. Vui lòng thử lại.",
) -> str:
    """
    Safe wrapper for LLM API calls with retry and fallback.
    
    Args:
        llm_func: Async LLM function to call
        prompt: Prompt string
        max_attempts: Retry attempts
        fallback_response: Fallback if all attempts fail
        
    Returns:
        LLM response or fallback
    """
    for attempt in range(1, max_attempts + 1):
        try:
            response = await llm_func(prompt)
            
            # Validate response
            if hasattr(response, 'content'):
                if isinstance(response.content, str) and response.content.strip():
                    return response.content.strip()
            
            logger.warning(f"LLM returned invalid response on attempt {attempt}")
            
        except (ResourceExhausted, ServiceUnavailable) as e:
            if attempt < max_attempts:
                delay = min(2.0 * (2 ** (attempt - 1)), 60.0)
                logger.warning(f"LLM quota/service error. Retrying in {delay}s...")
                await asyncio.sleep(delay)
            else:
                logger.error(f"LLM failed after {max_attempts} attempts: {e}")
                
        except Exception as e:
            logger.error(f"Unexpected LLM error on attempt {attempt}: {e}")
            if attempt >= max_attempts:
                break
    
    return fallback_response


def validate_llm_json(response_content: str, fallback: Optional[dict] = None) -> dict:
    """
    Parse and validate LLM JSON response with fallback.
    
    Args:
        response_content: LLM response string
        fallback: Fallback dict if parsing fails
        
    Returns:
        Parsed JSON dict or fallback
    """
    import json
    
    try:
        # Clean markdown code blocks
        content = response_content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        return json.loads(content)
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON: {e}")
        logger.debug(f"Raw content: {response_content[:200]}...")
        return fallback or {}


class CircuitBreaker:
    """
    Simple circuit breaker pattern to prevent cascading failures.
    """
    def __init__(self, failure_threshold: int = 5, timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = 0.0
        self.is_open = False
    
    def record_success(self):
        """Record successful call."""
        self.failures = 0
        self.is_open = False
    
    def record_failure(self):
        """Record failed call."""
        import time
        self.failures += 1
        self.last_failure_time = time.time()
        
        if self.failures >= self.failure_threshold:
            self.is_open = True
            logger.warning(f"Circuit breaker OPEN after {self.failures} failures")
    
    def can_execute(self) -> bool:
        """Check if circuit allows execution."""
        import time
        
        if not self.is_open:
            return True
        
        # Check if timeout expired
        if time.time() - self.last_failure_time > self.timeout:
            logger.info("Circuit breaker HALF-OPEN (timeout expired)")
            self.failures = 0
            self.is_open = False
            return True
        
        return False
