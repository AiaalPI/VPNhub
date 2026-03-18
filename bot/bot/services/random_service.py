import random
import string


async def generate_random_string(length: int = 15) -> str:
    """Return a random ASCII alphanumeric string of the requested length."""
    return ''.join(
        random.choices(string.ascii_letters + string.digits, k=length)
    )
