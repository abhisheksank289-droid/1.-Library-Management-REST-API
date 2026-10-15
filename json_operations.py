import json
from pathlib import Path


JSON_FILES_DIRECTORY = Path(__file__).resolve().parent / "reports" / "json"
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def _get_json_file_path(filename):
    invalid_characters = '<>:"/\\|?*'
    if (
        not filename
        or filename in {".", ".."}
        or filename != filename.strip()
        or Path(filename).name != filename
        or any(character in invalid_characters for character in filename)
        or any(ord(character) < 32 for character in filename)
        or not filename.lower().endswith(".json")
    ):
        raise ValueError(
            "Use a simple .json filename without path separators or invalid characters."
        )

    file_stem = filename.split(".", maxsplit=1)[0].upper()
    if file_stem in WINDOWS_RESERVED_NAMES or filename.endswith("."):
        raise ValueError("This filename cannot be used on Windows.")

    JSON_FILES_DIRECTORY.mkdir(parents=True, exist_ok=True)
    directory = JSON_FILES_DIRECTORY.resolve()
    file_path = (directory / filename).resolve()
    try:
        file_path.relative_to(directory)
    except ValueError as error:
        raise ValueError("The requested file must stay inside the JSON folder.") from error

    return file_path


def read_json_file(filename):
    file_path = _get_json_file_path(filename)
    with file_path.open("r", encoding="utf-8") as json_file:
        content = json.load(json_file)
    return {"filename": file_path.name, "content": content}


def write_json_file(filename, content):
    file_path = _get_json_file_path(filename)
    with file_path.open("w", encoding="utf-8", newline="") as json_file:
        json.dump(content, json_file, ensure_ascii=False, indent=2)
        json_file.write("\n")
    return {"filename": file_path.name}
