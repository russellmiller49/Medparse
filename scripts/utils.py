from tenacity import retry, stop_after_attempt, wait_exponential

def robust_api_call(max_attempts: int = 3):
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True,
    )