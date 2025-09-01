"""
HTTP retry and backoff helpers to handle timeouts and transient failures.
"""
import time
import httpx
from typing import Any, Callable, Optional, Dict
from functools import wraps
import logging

logger = logging.getLogger(__name__)

def with_retries(max_retries: int = 3, 
                 initial_delay: float = 1.0,
                 backoff_factor: float = 2.0,
                 max_delay: float = 30.0) -> Callable:
    """
    Decorator to add retry logic with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        backoff_factor: Multiplier for delay after each retry
        max_delay: Maximum delay between retries
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}")
                        raise
                    
                    # Calculate next delay
                    delay = min(delay * backoff_factor, max_delay)
                    
                    logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. "
                                 f"Retrying in {delay:.1f} seconds...")
                    time.sleep(delay)
                except Exception as e:
                    # Don't retry on other exceptions
                    logger.error(f"Non-retryable error in {func.__name__}: {e}")
                    raise
            
            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator

def fetch_with_retry(url: str,
                    method: str = 'GET',
                    timeout: float = 10.0,
                    max_retries: int = 3,
                    initial_delay: float = 1.0,
                    backoff_factor: float = 2.0,
                    **kwargs) -> httpx.Response:
    """
    Fetch URL with automatic retry and backoff.
    
    Args:
        url: URL to fetch
        method: HTTP method
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries
        backoff_factor: Multiplier for delay after each retry
        **kwargs: Additional arguments for httpx.request
    
    Returns:
        httpx.Response object
    """
    delay = initial_delay
    last_exception = None
    
    with httpx.Client(timeout=timeout) as client:
        for attempt in range(max_retries + 1):
            try:
                response = client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
                
            except httpx.TimeoutException as e:
                last_exception = e
                if attempt == max_retries:
                    logger.error(f"Timeout after {max_retries} retries for {url}")
                    raise
                    
            except httpx.NetworkError as e:
                last_exception = e
                if attempt == max_retries:
                    logger.error(f"Network error after {max_retries} retries for {url}")
                    raise
                    
            except httpx.HTTPStatusError as e:
                # Only retry on specific status codes
                if e.response.status_code in [429, 500, 502, 503, 504]:
                    last_exception = e
                    if attempt == max_retries:
                        logger.error(f"HTTP {e.response.status_code} after {max_retries} retries for {url}")
                        raise
                else:
                    # Don't retry on client errors (4xx except 429)
                    raise
                    
            except Exception as e:
                # Don't retry on other exceptions
                logger.error(f"Non-retryable error fetching {url}: {e}")
                raise
            
            # Calculate next delay
            delay = min(delay * backoff_factor, 30.0)  # Cap at 30 seconds
            
            logger.warning(f"Attempt {attempt + 1} failed for {url}. "
                         f"Retrying in {delay:.1f} seconds...")
            time.sleep(delay)
    
    # Should not reach here
    if last_exception:
        raise last_exception

def make_resilient_request(func: Callable, 
                          timeout: float = 10.0,
                          max_retries: int = 3) -> Any:
    """
    Make a function call resilient to timeouts and network errors.
    
    Useful for wrapping existing HTTP client calls.
    """
    @with_retries(max_retries=max_retries)
    def wrapped():
        # If func uses httpx, ensure it has a timeout
        return func()
    
    return wrapped()