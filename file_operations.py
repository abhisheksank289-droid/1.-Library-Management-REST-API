import shutil
from pathlib import Path


TEXT_FILES_DIRECTORY = Path(__file__).resolve().parent / "reports" / "text"
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def _get_text_file_path(filename):
    invalid_characters = '<>:"/\\|?*'
    if (
        not filename
        or filename in {".", ".."}
        or filename != filename.strip()
        or Path(filename).name != filename
        or any(character in invalid_characters for character in filename)
        or any(ord(character) < 32 for character in filename)
        or not filename.lower().endswith(".txt")
    ):
        raise ValueError(
            "Use a simple .txt filename without path separators or invalid characters."
        )

    file_stem = filename.split(".", maxsplit=1)[0].upper()
    if file_stem in WINDOWS_RESERVED_NAMES or filename.endswith("."):
        raise ValueError("This filename cannot be used on Windows.")

    TEXT_FILES_DIRECTORY.mkdir(parents=True, exist_ok=True)
    directory = TEXT_FILES_DIRECTORY.resolve()
    file_path = (directory / filename).resolve()
    try:
        file_path.relative_to(directory)
    except ValueError as error:
        raise ValueError("The requested file must stay inside the text folder.") from error

    return file_path


def _file_details(file_path):
    return {
        "filename": file_path.name,
        "size_bytes": file_path.stat().st_size,
    }


def create_text_file(filename):
    file_path = _get_text_file_path(filename)
    with file_path.open("x", encoding="utf-8"):
        pass
    return _file_details(file_path)


def write_text_file(filename, content):
    file_path = _get_text_file_path(filename)
    with file_path.open("w", encoding="utf-8", newline="") as text_file:
        characters_written = text_file.write(content)
    return {
        "filename": file_path.name,
        "characters_written": characters_written,
    }


def append_text_file(filename, content):
    file_path = _get_text_file_path(filename)
    with file_path.open("a", encoding="utf-8", newline="") as text_file:
        characters_written = text_file.write(content)
    return {
        "filename": file_path.name,
        "characters_written": characters_written,
    }


def read_text_file(filename):
    file_path = _get_text_file_path(filename)
    with file_path.open("r", encoding="utf-8", newline="") as text_file:
        content = text_file.read()
    return {"filename": file_path.name, "content": content}


def read_text_file_lines(filename):
    file_path = _get_text_file_path(filename)
    with file_path.open("r", encoding="utf-8") as text_file:
        lines = [line.rstrip("\r\n") for line in text_file]
    return {"filename": file_path.name, "lines": lines}


def text_file_exists(filename):
    file_path = _get_text_file_path(filename)
    return {"filename": filename, "exists": file_path.is_file()}


def rename_text_file(filename, new_filename):
    source_path = _get_text_file_path(filename)
    destination_path = _get_text_file_path(new_filename)
    if not source_path.is_file():
        raise FileNotFoundError("The requested text file does not exist.")
    if destination_path.exists():
        raise FileExistsError("A text file with the new filename already exists.")

    source_path.rename(destination_path)
    return {
        "old_filename": filename,
        "filename": destination_path.name,
    }


def copy_text_file(filename, new_filename):
    source_path = _get_text_file_path(filename)
    destination_path = _get_text_file_path(new_filename)
    if not source_path.is_file():
        raise FileNotFoundError("The requested text file does not exist.")

    with source_path.open("rb") as source_file:
        with destination_path.open("xb") as destination_file:
            shutil.copyfileobj(source_file, destination_file)
    return {
        "source_filename": source_path.name,
        **_file_details(destination_path),
    }


def delete_text_file(filename):
    file_path = _get_text_file_path(filename)
    if not file_path.is_file():
        raise FileNotFoundError("The requested text file does not exist.")
    file_path.unlink()


def get_text_file_size(filename):
    file_path = _get_text_file_path(filename)
    if not file_path.is_file():
        raise FileNotFoundError("The requested text file does not exist.")
    return _file_details(file_path)
