import csv
from pathlib import Path


CSV_FILES_DIRECTORY = Path(__file__).resolve().parent / "reports" / "csv"
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


def _get_csv_file_path(filename):
    invalid_characters = '<>:"/\\|?*'
    if (
        not filename
        or filename in {".", ".."}
        or filename != filename.strip()
        or Path(filename).name != filename
        or any(character in invalid_characters for character in filename)
        or any(ord(character) < 32 for character in filename)
        or not filename.lower().endswith(".csv")
    ):
        raise ValueError(
            "Use a simple .csv filename without path separators or invalid characters."
        )

    file_stem = filename.split(".", maxsplit=1)[0].upper()
    if file_stem in WINDOWS_RESERVED_NAMES or filename.endswith("."):
        raise ValueError("This filename cannot be used on Windows.")

    CSV_FILES_DIRECTORY.mkdir(parents=True, exist_ok=True)
    directory = CSV_FILES_DIRECTORY.resolve()
    file_path = (directory / filename).resolve()
    try:
        file_path.relative_to(directory)
    except ValueError as error:
        raise ValueError("The requested file must stay inside the CSV folder.") from error

    return file_path


def read_csv_records(filename, required_columns):
    file_path = _get_csv_file_path(filename)
    with file_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file, strict=True)
        if reader.fieldnames is None:
            raise ValueError("The CSV file must contain a header row.")

        headers = [header.strip() if header is not None else "" for header in reader.fieldnames]
        if any(not header for header in headers):
            raise ValueError("CSV column names cannot be blank.")
        if len(headers) != len(set(headers)):
            raise ValueError("CSV column names must be unique.")

        missing_columns = [
            column for column in required_columns if column not in headers
        ]
        if missing_columns:
            missing = ", ".join(missing_columns)
            raise ValueError(f"CSV is missing required column(s): {missing}.")

        records = []
        for row in reader:
            row_number = reader.line_num
            if row is None or all(
                value is None or not value.strip()
                for key, value in row.items()
                if key is not None
            ):
                continue
            if None in row:
                records.append(
                    {
                        "row_number": row_number,
                        "data": {},
                        "errors": ["This row has more values than the header."],
                    }
                )
                continue

            normalized_row = {
                key.strip(): value.strip() if value is not None else None
                for key, value in row.items()
                if key is not None
            }
            records.append(
                {
                    "row_number": row_number,
                    "data": normalized_row,
                    "errors": [],
                }
            )

        return {"filename": file_path.name, "headers": headers, "rows": records}


def write_csv_records(filename, columns, records):
    file_path = _get_csv_file_path(filename)
    with file_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=columns,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(records)

    return {
        "filename": file_path.name,
        "rows_exported": len(records),
    }
