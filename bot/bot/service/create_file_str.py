import io

from aiogram.types import BufferedInputFile


async def str_to_file(file_name, text: str) -> BufferedInputFile:
    file_stream = io.BytesIO(text.encode()).getvalue()
    return BufferedInputFile(file_stream, file_name)


async def replace_spaces(text):
    truncated_text = text[:10].replace(' ', '_')
    return truncated_text