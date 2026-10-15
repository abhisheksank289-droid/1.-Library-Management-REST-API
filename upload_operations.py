import csv
import io
import json
import re
import uuid
from pathlib import Path

from fastapi import UploadFile


UPLOADS_DIRECTORY = Path(__file__).resolve().parent / "uploads"
MAX_UPLOAD_SIZE_BYTES = 1_048_576
ALLOWED_EXTENSIONS = {".txt", ".csv", ".json"}
GENERATED_FILENAME_PATTERN = re.compile(
    r"[0-9a-f]{32}\.(?:txt|csv|json)\Z"
)


def _validate_file_content(extension, content):
    try:
        text = content.decode("utf-8-sig" if extension == ".csv" else "utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("The uploaded file must contain valid UTF-8 text.") from error

    if extension == ".json":
        try:
            json.loads(text)
        except json.JSONDecodeError as error:
            raise ValueError("The uploaded file does not contain valid JSON.") from error
    elif extension == ".csv":
        try:
            rows = csv.reader(io.StringIO(text, newline=""), strict=True)
            headers = next(rows, None)
            if not headers or any(not header.strip() for header in headers):
                raise ValueError("The uploaded CSV must have a non-empty header row.")
            if len(headers) != len(set(headers)):
                raise ValueError("The uploaded CSV must have unique column names.")
            for _ in rows:
                pass
        except csv.Error as error:
            raise ValueError("The uploaded file contains malformed CSV data.") from error


async def store_uploaded_file(upload_file: UploadFile):
    original_filename = upload_file.filename or ""
    extension = Path(original_filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Only .txt, .csv, and .json files are allowed.")

    chunks = []
    size_bytes = 0
    while True:
        chunk = await upload_file.read(64 * 1024)
        if not chunk:
            break
        size_bytes += len(chunk)
        if size_bytes > MAX_UPLOAD_SIZE_BYTES:
            raise ValueError(
                f"Uploaded files must not exceed {MAX_UPLOAD_SIZE_BYTES} bytes."
            )
        chunks.append(chunk)

    content = b"".join(chunks)
    _validate_file_content(extension, content)

    UPLOADS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{extension}"
    file_path = UPLOADS_DIRECTORY / filename
    destination = file_path.open("xb")
    try:
        with destination:
            destination.write(content)
    except OSError:
        file_path.unlink(missing_ok=True)
        raise

    return {
        "filename": filename,
        "size_bytes": size_bytes,
        "max_size_bytes": MAX_UPLOAD_SIZE_BYTES,
    }


def get_uploaded_file_path(filename):
    if not GENERATED_FILENAME_PATTERN.fullmatch(filename):
        raise ValueError("Use a filename returned by the upload endpoint.")

    directory = UPLOADS_DIRECTORY.resolve()
    file_path = (directory / filename).resolve()
    try:
        file_path.relative_to(directory)
    except ValueError as error:
        raise ValueError("The requested file is outside the upload folder.") from error

    if not file_path.is_file():
        raise FileNotFoundError("The uploaded file does not exist.")
    return file_path
