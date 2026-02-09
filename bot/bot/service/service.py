import random
import string


async def generate_random_string(length: int = 15) -> str:
    """
    Генерирует строку указанной длины, содержащую случайные буквы и цифры.

    :param length: Длина строки (по умолчанию 15).
    :return: Случайная строка из букв и цифр.
    """
    return ''.join(random.choices(
        string.ascii_letters + string.digits, k=length)
    )