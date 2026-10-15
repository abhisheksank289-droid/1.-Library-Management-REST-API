import csv
import json
import mysql.connector
from datetime import date
from typing import Any

from fastapi import (
    FastAPI,
    File,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

import book_queries
import borrow_queries
import csv_operations
import file_operations
import json_operations
import member_queries
import upload_operations

app = FastAPI(title="Library Management API")


class BookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    author: str = Field(min_length=1, max_length=255)
    isbn: str = Field(min_length=1, max_length=20)
    category: str = Field(min_length=1, max_length=100)
    quantity: int = Field(ge=0)

    @field_validator("title", "author", "isbn", "category")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value


class BookUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    author: str | None = Field(default=None, min_length=1, max_length=255)
    isbn: str | None = Field(default=None, min_length=1, max_length=20)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    quantity: int | None = Field(default=None, ge=0)

    @field_validator("title", "author", "isbn", "category")
    @classmethod
    def strip_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value

    @model_validator(mode="after")
    def require_valid_changes(self):
        if not self.model_fields_set:
            raise ValueError("At least one book field must be provided.")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Book fields cannot be null.")
        return self


class MemberCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: str = Field(
        min_length=3,
        max_length=255,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def strip_member_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank.")
        return value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("phone", "address")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class MemberUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = Field(
        default=None,
        min_length=3,
        max_length=255,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def strip_member_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank.")
        return value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("phone", "address")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def require_valid_changes(self):
        if not self.model_fields_set:
            raise ValueError("At least one member field must be provided.")
        if any(
            getattr(self, field) is None
            for field in self.model_fields_set
            if field in ("name", "email")
        ):
            raise ValueError("Member name and email cannot be null.")
        return self


class IssueBookRequest(BaseModel):
    book_id: int = Field(gt=0)
    member_id: int = Field(gt=0)
    due_date: date

    @model_validator(mode="after")
    def require_future_due_date(self):
        if self.due_date <= date.today():
            raise ValueError("Due date must be after today.")
        return self


class TextContent(BaseModel):
    content: str


class TextFilenameChange(BaseModel):
    new_filename: str = Field(min_length=1, max_length=255)


def handle_database_error(error: mysql.connector.Error) -> None:
    unavailable_error_codes = {1045, 1049, 2002, 2003, 2005, 2006, 2055}
    if (
        isinstance(error, mysql.connector.InterfaceError)
        or error.errno in unavailable_error_codes
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The database is unavailable. Check the database settings and try again.",
        ) from error

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected database error occurred.",
    ) from error


def handle_borrow_error(error: ValueError) -> None:
    error_responses = {
        "Book not found.": (status.HTTP_404_NOT_FOUND, "Book not found."),
        "Member not found.": (status.HTTP_404_NOT_FOUND, "Member not found."),
        "Book is not available.": (
            status.HTTP_409_CONFLICT,
            "No copies of this book are currently available.",
        ),
        "Borrowing record not found.": (
            status.HTTP_404_NOT_FOUND,
            "Borrowing record not found.",
        ),
        "Borrowing record has already been returned.": (
            status.HTTP_409_CONFLICT,
            "This borrowing record has already been returned.",
        ),
    }
    error_response = error_responses.get(
        str(error),
        (status.HTTP_400_BAD_REQUEST, "Invalid borrowing request."),
    )
    raise HTTPException(
        status_code=error_response[0],
        detail=error_response[1],
    ) from error


def handle_text_file_error(error: ValueError | OSError) -> None:
    if isinstance(error, UnicodeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The file does not contain valid UTF-8 text.",
        ) from error
    if isinstance(error, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    if isinstance(error, FileNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Text file not found.",
        ) from error
    if isinstance(error, FileExistsError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A text file with that filename already exists.",
        ) from error
    if isinstance(error, PermissionError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The server does not have permission to access this text file.",
        ) from error

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected text-file error occurred.",
    ) from error


def handle_csv_file_error(error: ValueError | OSError | csv.Error) -> None:
    if isinstance(error, UnicodeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The CSV file is not valid UTF-8 text.",
        ) from error
    if isinstance(error, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    if isinstance(error, FileNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CSV file not found.",
        ) from error
    if isinstance(error, PermissionError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The server does not have permission to access this CSV file.",
        ) from error
    if isinstance(error, csv.Error):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The CSV file is malformed or contains invalid CSV data.",
        ) from error

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected CSV file error occurred.",
    ) from error


def handle_json_file_error(error: ValueError | OSError | TypeError) -> None:
    if isinstance(error, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The JSON file contains invalid JSON.",
        ) from error
    if isinstance(error, UnicodeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The JSON file is not valid UTF-8 text.",
        ) from error
    if isinstance(error, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    if isinstance(error, FileNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="JSON file not found.",
        ) from error
    if isinstance(error, PermissionError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The server does not have permission to access this JSON file.",
        ) from error
    if isinstance(error, TypeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The request contains data that cannot be represented as JSON.",
        ) from error

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected JSON file error occurred.",
    ) from error


def handle_upload_error(error: ValueError | OSError) -> None:
    if isinstance(error, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    if isinstance(error, FileNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uploaded file not found.",
        ) from error
    if isinstance(error, PermissionError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The server does not have permission to access the uploaded file.",
        ) from error
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected upload file error occurred.",
    ) from error


def _validate_csv_rows(csv_data, model):
    valid_rows = []
    invalid_rows = []
    for row in csv_data["rows"]:
        if row["errors"]:
            invalid_rows.append(
                {"row": row["row_number"], "errors": row["errors"]}
            )
            continue
        try:
            valid_rows.append(
                {
                    "row_number": row["row_number"],
                    "data": model.model_validate(row["data"]).model_dump(),
                }
            )
        except ValidationError as error:
            invalid_rows.append(
                {
                    "row": row["row_number"],
                    "errors": [
                        f"{'.'.join(str(part) for part in detail['loc'])}: {detail['msg']}"
                        for detail in error.errors()
                    ],
                }
            )
    return valid_rows, invalid_rows


def _import_validated_rows(filename, valid_rows, invalid_rows, create_record, unique_field):
    imported = 0
    for row in valid_rows:
        try:
            create_record(row["data"])
            imported += 1
        except mysql.connector.IntegrityError as error:
            if error.errno == 1062:
                invalid_rows.append(
                    {
                        "row": row["row_number"],
                        "errors": [f"A record with this {unique_field} already exists."],
                    }
                )
            else:
                handle_database_error(error)
        except mysql.connector.Error as error:
            handle_database_error(error)

    invalid_rows.sort(key=lambda row: row["row"])
    return {
        "filename": filename,
        "imported": imported,
        "invalid": len(invalid_rows),
        "errors": invalid_rows,
    }


def _import_csv_rows(csv_data, model, create_record, unique_field):
    valid_rows, invalid_rows = _validate_csv_rows(csv_data, model)
    return _import_validated_rows(
        csv_data["filename"],
        valid_rows,
        invalid_rows,
        create_record,
        unique_field,
    )


def _validate_json_records(json_data, collection_name, model):
    if not isinstance(json_data, dict):
        raise ValueError("The JSON document must be an object.")
    if collection_name not in json_data:
        raise ValueError(
            f'The JSON document must contain a "{collection_name}" array.'
        )

    records = json_data[collection_name]
    if not isinstance(records, list):
        raise ValueError(f'The "{collection_name}" value must be an array.')

    valid_rows = []
    invalid_rows = []
    for row_number, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            invalid_rows.append(
                {
                    "row": row_number,
                    "errors": ["Each record must be a JSON object."],
                }
            )
            continue
        try:
            valid_rows.append(
                {
                    "row_number": row_number,
                    "data": model.model_validate(record).model_dump(),
                }
            )
        except ValidationError as error:
            invalid_rows.append(
                {
                    "row": row_number,
                    "errors": [
                        f"{'.'.join(str(part) for part in detail['loc'])}: {detail['msg']}"
                        for detail in error.errors()
                    ],
                }
            )
    return valid_rows, invalid_rows


def _read_json_for_api(filename):
    try:
        return json_operations.read_json_file(filename)
    except (ValueError, OSError) as error:
        handle_json_file_error(error)


def _read_csv_for_api(filename, required_columns):
    try:
        return csv_operations.read_csv_records(filename, required_columns)
    except (ValueError, OSError, csv.Error) as error:
        handle_csv_file_error(error)


@app.post("/books", status_code=status.HTTP_201_CREATED)
def add_book(book: BookCreate):
    try:
        return book_queries.create_book(book.model_dump())
    except mysql.connector.IntegrityError as error:
        if error.errno == 1062:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A book with this ISBN already exists.",
            ) from error
        handle_database_error(error)
    except mysql.connector.Error as error:
        handle_database_error(error)


@app.get("/books")
def get_all_books():
    try:
        return book_queries.get_books()
    except mysql.connector.Error as error:
        handle_database_error(error)


@app.get("/books/search")
def search_books(q: str = Query(min_length=1, max_length=100)):
    search_text = q.strip()
    if not search_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Search text cannot be blank.",
        )

    try:
        return book_queries.get_books(search_text)
    except mysql.connector.Error as error:
        handle_database_error(error)


@app.get("/books/{book_id}")
def get_book(book_id: int = Path(gt=0)):
    try:
        book = book_queries.get_book_by_id(book_id)
    except mysql.connector.Error as error:
        handle_database_error(error)

    if book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found.",
        )
    return book


@app.patch("/books/{book_id}")
def update_book(book_id: int, changes: BookUpdate):
    try:
        book = book_queries.update_book(
            book_id,
            changes.model_dump(exclude_unset=True),
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except mysql.connector.IntegrityError as error:
        if error.errno == 1062:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A book with this ISBN already exists.",
            ) from error
        handle_database_error(error)
    except mysql.connector.Error as error:
        handle_database_error(error)

    if book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found.",
        )
    return book


@app.delete("/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(book_id: int) -> Response:
    try:
        deleted = book_queries.delete_book(book_id)
    except mysql.connector.IntegrityError as error:
        if error.errno == 1451:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This book cannot be deleted because borrowing records refer to it.",
            ) from error
        handle_database_error(error)
    except mysql.connector.Error as error:
        handle_database_error(error)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/members", status_code=status.HTTP_201_CREATED)
def register_member(member: MemberCreate):
    try:
        return member_queries.create_member(member.model_dump())
    except mysql.connector.IntegrityError as error:
        if error.errno == 1062:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A member with this email already exists.",
            ) from error
        handle_database_error(error)
    except mysql.connector.Error as error:
        handle_database_error(error)


@app.get("/members")
def get_all_members():
    try:
        return member_queries.get_members()
    except mysql.connector.Error as error:
        handle_database_error(error)


@app.get("/members/search")
def search_members(q: str = Query(min_length=1, max_length=100)):
    search_text = q.strip()
    if not search_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Search text cannot be blank.",
        )

    try:
        return member_queries.get_members(search_text)
    except mysql.connector.Error as error:
        handle_database_error(error)


@app.get("/members/{member_id}")
def get_member(member_id: int = Path(gt=0)):
    try:
        member = member_queries.get_member_by_id(member_id)
    except mysql.connector.Error as error:
        handle_database_error(error)

    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found.",
        )
    return member


@app.patch("/members/{member_id}")
def update_member(member_id: int, changes: MemberUpdate):
    try:
        member = member_queries.update_member(
            member_id,
            changes.model_dump(exclude_unset=True),
        )
    except mysql.connector.IntegrityError as error:
        if error.errno == 1062:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A member with this email already exists.",
            ) from error
        handle_database_error(error)
    except mysql.connector.Error as error:
        handle_database_error(error)

    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found.",
        )
    return member


@app.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_member(member_id: int) -> Response:
    try:
        deleted = member_queries.delete_member(member_id)
    except mysql.connector.IntegrityError as error:
        if error.errno == 1451:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This member cannot be deleted because borrowing records refer to them.",
            ) from error
        handle_database_error(error)
    except mysql.connector.Error as error:
        handle_database_error(error)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/borrow-records", status_code=status.HTTP_201_CREATED)
def issue_book(request: IssueBookRequest):
    try:
        return borrow_queries.issue_book(
            request.book_id,
            request.member_id,
            request.due_date,
        )
    except ValueError as error:
        handle_borrow_error(error)
    except mysql.connector.Error as error:
        handle_database_error(error)


@app.get("/borrow-records")
def get_all_borrow_records():
    try:
        return borrow_queries.get_borrow_records()
    except mysql.connector.Error as error:
        handle_database_error(error)


@app.get("/borrow-records/issued")
def get_issued_books():
    try:
        return borrow_queries.get_borrow_records(issued_only=True)
    except mysql.connector.Error as error:
        handle_database_error(error)


@app.get("/members/{member_id}/borrow-records")
def get_member_borrow_records(member_id: int = Path(gt=0)):
    try:
        records = borrow_queries.get_member_borrow_records(member_id)
    except mysql.connector.Error as error:
        handle_database_error(error)

    if records is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found.",
        )
    return records


@app.post("/borrow-records/{record_id}/return")
def return_borrowed_book(record_id: int = Path(gt=0)):
    try:
        return borrow_queries.return_book(record_id)
    except ValueError as error:
        handle_borrow_error(error)
    except mysql.connector.Error as error:
        handle_database_error(error)


@app.post("/files/text/{filename}", status_code=status.HTTP_201_CREATED)
def create_text_file(filename: str):
    try:
        return file_operations.create_text_file(filename)
    except (ValueError, OSError) as error:
        handle_text_file_error(error)


@app.put("/files/text/{filename}")
def write_text_file(filename: str, request: TextContent):
    try:
        return file_operations.write_text_file(filename, request.content)
    except (ValueError, OSError) as error:
        handle_text_file_error(error)


@app.post("/files/text/{filename}/append")
def append_text_file(filename: str, request: TextContent):
    try:
        return file_operations.append_text_file(filename, request.content)
    except (ValueError, OSError) as error:
        handle_text_file_error(error)


@app.get("/files/text/{filename}")
def read_text_file(filename: str):
    try:
        return file_operations.read_text_file(filename)
    except (ValueError, OSError) as error:
        handle_text_file_error(error)


@app.get("/files/text/{filename}/lines")
def read_text_file_lines(filename: str):
    try:
        return file_operations.read_text_file_lines(filename)
    except (ValueError, OSError) as error:
        handle_text_file_error(error)


@app.get("/files/text/{filename}/exists")
def check_text_file_exists(filename: str):
    try:
        return file_operations.text_file_exists(filename)
    except (ValueError, OSError) as error:
        handle_text_file_error(error)


@app.get("/files/text/{filename}/size")
def get_text_file_size(filename: str):
    try:
        return file_operations.get_text_file_size(filename)
    except (ValueError, OSError) as error:
        handle_text_file_error(error)


@app.post("/files/text/{filename}/rename")
def rename_text_file(filename: str, request: TextFilenameChange):
    try:
        return file_operations.rename_text_file(filename, request.new_filename)
    except (ValueError, OSError) as error:
        handle_text_file_error(error)


@app.post("/files/text/{filename}/copy")
def copy_text_file(filename: str, request: TextFilenameChange):
    try:
        return file_operations.copy_text_file(filename, request.new_filename)
    except (ValueError, OSError) as error:
        handle_text_file_error(error)


@app.delete("/files/text/{filename}", status_code=status.HTTP_204_NO_CONTENT)
def delete_text_file(filename: str) -> Response:
    try:
        file_operations.delete_text_file(filename)
    except (ValueError, OSError) as error:
        handle_text_file_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/files/csv/books/read")
def read_books_csv(filename: str = Query(min_length=5, max_length=255)):
    csv_data = _read_csv_for_api(
        filename,
        ("title", "author", "isbn", "category", "quantity"),
    )
    valid_rows, invalid_rows = _validate_csv_rows(csv_data, BookCreate)
    return {
        "filename": csv_data["filename"],
        "valid_rows": [
            {"row": row["row_number"], "data": row["data"]}
            for row in valid_rows
        ],
        "invalid_rows": invalid_rows,
    }


@app.get("/files/csv/members/read")
def read_members_csv(filename: str = Query(min_length=5, max_length=255)):
    csv_data = _read_csv_for_api(filename, ("name", "email"))
    valid_rows, invalid_rows = _validate_csv_rows(csv_data, MemberCreate)
    return {
        "filename": csv_data["filename"],
        "valid_rows": [
            {"row": row["row_number"], "data": row["data"]}
            for row in valid_rows
        ],
        "invalid_rows": invalid_rows,
    }


@app.post("/files/csv/books/import")
def import_books_csv(filename: str = Query(min_length=5, max_length=255)):
    csv_data = _read_csv_for_api(
        filename,
        ("title", "author", "isbn", "category", "quantity"),
    )
    return _import_csv_rows(csv_data, BookCreate, book_queries.create_book, "ISBN")


@app.post("/files/csv/members/import")
def import_members_csv(filename: str = Query(min_length=5, max_length=255)):
    csv_data = _read_csv_for_api(filename, ("name", "email"))
    return _import_csv_rows(
        csv_data,
        MemberCreate,
        member_queries.create_member,
        "email",
    )


@app.get("/files/csv/books/export")
def export_books_csv(filename: str = Query(min_length=5, max_length=255)):
    try:
        books = book_queries.get_books()
        return csv_operations.write_csv_records(
            filename,
            (
                "id",
                "title",
                "author",
                "isbn",
                "category",
                "quantity",
                "available_quantity",
            ),
            books,
        )
    except mysql.connector.Error as error:
        handle_database_error(error)
    except (ValueError, OSError) as error:
        handle_csv_file_error(error)


@app.get("/files/csv/members/export")
def export_members_csv(filename: str = Query(min_length=5, max_length=255)):
    try:
        members = member_queries.get_members()
        return csv_operations.write_csv_records(
            filename,
            ("id", "name", "email", "phone", "address"),
            members,
        )
    except mysql.connector.Error as error:
        handle_database_error(error)
    except (ValueError, OSError) as error:
        handle_csv_file_error(error)


@app.get("/files/json/{filename}")
def read_json_file(filename: str):
    return _read_json_for_api(filename)


@app.put(
    "/files/json/{filename}",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": {}}},
        }
    },
)
async def write_json_file(filename: str, request: Request):
    content_type = request.headers.get("content-type", "").split(";", maxsplit=1)[0]
    if content_type.strip().lower() != "application/json":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Send JSON using the application/json content type.",
        )

    body = await request.body()
    if not body:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A JSON request body is required.",
        )

    try:
        content: Any = json.loads(body.decode("utf-8"))
        return json_operations.write_json_file(filename, content)
    except (ValueError, OSError, TypeError) as error:
        handle_json_file_error(error)


@app.post("/files/json/books/import")
def import_books_json(filename: str = Query(min_length=6, max_length=255)):
    json_document = _read_json_for_api(filename)
    try:
        valid_rows, invalid_rows = _validate_json_records(
            json_document["content"],
            "books",
            BookCreate,
        )
    except ValueError as error:
        handle_json_file_error(error)
    return _import_validated_rows(
        json_document["filename"],
        valid_rows,
        invalid_rows,
        book_queries.create_book,
        "ISBN",
    )


@app.post("/files/json/members/import")
def import_members_json(filename: str = Query(min_length=6, max_length=255)):
    json_document = _read_json_for_api(filename)
    try:
        valid_rows, invalid_rows = _validate_json_records(
            json_document["content"],
            "members",
            MemberCreate,
        )
    except ValueError as error:
        handle_json_file_error(error)
    return _import_validated_rows(
        json_document["filename"],
        valid_rows,
        invalid_rows,
        member_queries.create_member,
        "email",
    )


@app.get("/files/json/books/export")
def export_books_json(filename: str = Query(min_length=6, max_length=255)):
    try:
        books = book_queries.get_books()
        return json_operations.write_json_file(filename, {"books": books})
    except mysql.connector.Error as error:
        handle_database_error(error)
    except (ValueError, OSError, TypeError) as error:
        handle_json_file_error(error)


@app.get("/files/json/members/export")
def export_members_json(filename: str = Query(min_length=6, max_length=255)):
    try:
        members = member_queries.get_members()
        return json_operations.write_json_file(filename, {"members": members})
    except mysql.connector.Error as error:
        handle_database_error(error)
    except (ValueError, OSError, TypeError) as error:
        handle_json_file_error(error)


@app.post("/files/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(file: UploadFile = File(...)):
    try:
        return await upload_operations.store_uploaded_file(file)
    except (ValueError, OSError) as error:
        handle_upload_error(error)
    finally:
        await file.close()


@app.get("/files/download/{filename}")
def download_file(filename: str):
    try:
        file_path = upload_operations.get_uploaded_file_path(filename)
    except (ValueError, OSError) as error:
        handle_upload_error(error)
    return FileResponse(path=file_path, filename=file_path.name)
