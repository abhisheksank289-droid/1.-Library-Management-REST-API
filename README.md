# Library Management REST API

A beginner-friendly REST API for managing books, library members, and book
borrowing. It is built with Python, FastAPI, MySQL/MariaDB, and Uvicorn. It also
demonstrates safe text, CSV, and JSON file operations and file uploads.

## Features

- Create, list, retrieve, update, search, and safely delete books.
- Register, list, retrieve, search, update, and safely delete members.
- Issue and return books with transactional stock updates and borrowing records.
- Create, write, append, read, copy, rename, inspect, and delete text files.
- Preview, validate, import, and export book and member CSV files.
- Read and write JSON documents and validate, import, and export book/member
  collections.
- Upload and download validated `.txt`, `.csv`, and `.json` files.
- Keep local database settings in an ignored `.env` file.

## Technologies

- Python 3.10 or later
- FastAPI for the API and automatic OpenAPI documentation
- Uvicorn as the local development server
- MySQL or MariaDB with InnoDB tables
- `mysql-connector-python` for Python/database connections
- `python-dotenv` for local environment settings
- `python-multipart` for multipart file uploads

## Project structure

```text
.
├── main.py                 # Request models, validation, HTTP routes, errors
├── database.py             # Loads local settings and opens MySQL connections
├── book_queries.py         # SQL operations for books
├── member_queries.py       # SQL operations for members
├── borrow_queries.py       # Transactional book issue/return operations
├── file_operations.py      # Safe text-file operations
├── csv_operations.py       # Safe CSV reading and writing
├── json_operations.py      # Safe JSON reading and writing
├── upload_operations.py    # Validates, stores, and locates uploaded files
├── requirements.txt        # Python package dependencies
├── .env.example            # Shareable local-settings template
├── .env                    # Local secrets; ignored by Git
├── uploads/                # Generated upload files; ignored by Git
└── reports/
    ├── text/               # Text files managed by the API; ignored by Git
    ├── csv/                # CSV imports and exports; ignored by Git
    └── json/               # JSON imports and exports; ignored by Git
```

The `uploads/` and `reports/` directories are created when first used.

## Requirements

- Windows, macOS, or Linux
- Python 3.10 or later and pip
- MySQL or MariaDB; XAMPP is a convenient option for local Windows development
- Git is recommended for version control

The commands below use Windows PowerShell from the project folder.

## Set up the Python environment

Open the project folder in VS Code, then open **Terminal → New Terminal**.
Create a virtual environment and activate it:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

A virtual environment keeps this project's installed packages separate from
other Python projects. If PowerShell blocks activation, use the environment's
interpreter directly instead of changing the computer's execution policy:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Install the project dependencies:

```powershell
python -m pip install -r requirements.txt
python -m pip check
```

`requirements.txt` lists the direct dependencies:

- `fastapi` defines and validates the API endpoints.
- `uvicorn` runs the API server.
- `mysql-connector-python` connects Python to MySQL/MariaDB.
- `python-dotenv` loads local settings from `.env`.
- `python-multipart` enables FastAPI form-based file uploads.

For Git Bash, activate the environment with:

```bash
source .venv/Scripts/activate
```

## Configure the database

The examples use XAMPP's local MySQL/MariaDB server. In XAMPP Control Panel,
start **MySQL**. phpMyAdmin is available at
[http://localhost/phpmyadmin](http://localhost/phpmyadmin).

Copy `.env.example` to `.env` in the project root and set values for your local
database account. For a default local XAMPP installation with an unpassworded
`root` account, the values are:

```dotenv
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=library_db
```

If your MySQL account has a password, put it only in your local `.env`. Never
commit or share `.env`; it is ignored by Git. `.env.example` contains
placeholders and is safe to share. The API does not create the database
automatically.

Run the following SQL in phpMyAdmin's **SQL** tab to create the database and
tables:

```sql
CREATE DATABASE IF NOT EXISTS library_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE library_db;

CREATE TABLE IF NOT EXISTS books (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(255) NOT NULL,
  author VARCHAR(255) NOT NULL,
  isbn VARCHAR(20) NOT NULL UNIQUE,
  category VARCHAR(100) NOT NULL,
  quantity INT NOT NULL,
  available_quantity INT NOT NULL,
  CONSTRAINT chk_books_quantity_nonnegative CHECK (quantity >= 0),
  CONSTRAINT chk_books_available_quantity CHECK (
    available_quantity >= 0 AND available_quantity <= quantity
  )
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS members (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  email VARCHAR(255) NOT NULL UNIQUE,
  phone VARCHAR(30),
  address VARCHAR(500)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS borrow_records (
  id INT AUTO_INCREMENT PRIMARY KEY,
  book_id INT NOT NULL,
  member_id INT NOT NULL,
  issue_date DATE NOT NULL,
  due_date DATE NOT NULL,
  return_date DATE,
  status ENUM('issued', 'returned') NOT NULL DEFAULT 'issued',
  CONSTRAINT fk_borrow_records_book
    FOREIGN KEY (book_id) REFERENCES books(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_borrow_records_member
    FOREIGN KEY (member_id) REFERENCES members(id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;
```

The `id` columns are auto-incrementing primary keys. Unique constraints prevent
duplicate ISBNs and emails. The foreign keys ensure every borrowing record
refers to an existing book and member; `ON DELETE RESTRICT` protects borrowing
history. Stock checks prevent negative quantities and available stock greater
than the total quantity. InnoDB supports transactions and foreign keys.

Confirm the tables were created with:

```sql
USE library_db;
SHOW TABLES;
DESCRIBE books;
DESCRIBE members;
DESCRIBE borrow_records;
```

## Run the API

With the virtual environment active and MySQL running, launch Uvicorn:

```powershell
python -m uvicorn main:app --reload
```

The API runs at [http://127.0.0.1:8000](http://127.0.0.1:8000). Open
[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for interactive
Swagger UI. Select an endpoint, click **Try it out**, provide its path/query
values or JSON body, click **Execute**, and inspect the response and HTTP status.
Use `Ctrl+C` in the terminal to stop the server.

### Test with Postman

Send requests to `http://127.0.0.1:8000`. For JSON requests, select
**Body → raw → JSON**. For file uploads, select **Body → form-data**, add a
field named `file`, set its type to **File**, and choose a supported file.

## API endpoints

### Books

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/books` | Add a book; returns `201`. |
| `GET` | `/books` | List books. |
| `GET` | `/books/{book_id}` | Get one book. |
| `GET` | `/books/search?q=tolkien` | Search title, author, category, or ISBN. |
| `PATCH` | `/books/{book_id}` | Update supplied fields only. |
| `DELETE` | `/books/{book_id}` | Delete if no borrowing records refer to it; returns `204`. |

Example book request:

```json
{
  "title": "The Hobbit",
  "author": "J.R.R. Tolkien",
  "isbn": "9780547928227",
  "category": "Fantasy",
  "quantity": 3
}
```

`available_quantity` is initialized from `quantity`. Borrowing operations
update available stock. The API rejects a stock reduction below the number of
copies currently borrowed.

### Members

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/members` | Register a member; returns `201`. |
| `GET` | `/members` | List members. |
| `GET` | `/members/{member_id}` | Get one member. |
| `GET` | `/members/search?q=sam` | Search member name or email. |
| `PATCH` | `/members/{member_id}` | Update supplied fields only. |
| `DELETE` | `/members/{member_id}` | Delete if no borrowing records refer to them; returns `204`. |

Example member request:

```json
{
  "name": "Sam Reader",
  "email": "sam.reader@example.com",
  "phone": "555-0100",
  "address": "10 Library Lane"
}
```

Email is normalized to lowercase. Name and email are required; phone and
address can be omitted or cleared.

### Borrowing

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/borrow-records` | Issue an available book to a member. |
| `GET` | `/borrow-records` | List borrowing records. |
| `GET` | `/borrow-records/issued` | List currently issued records. |
| `GET` | `/members/{member_id}/borrow-records` | List a member's borrowing records. |
| `POST` | `/borrow-records/{record_id}/return` | Return a currently issued book. |

Issue a book with a future due date:

```json
{
  "book_id": 1,
  "member_id": 1,
  "due_date": "2026-12-01"
}
```

The API records the issue date. Issuing and returning run in MySQL transactions
so the record and available quantity are updated together. A locked book row
prevents simultaneous requests from issuing more copies than are available.
The API does not implement fines or authentication.

### Text files

Text-file operations use `reports/text` and accept simple `.txt` filenames.
They support create (`POST /files/text/{filename}`), overwrite (`PUT`), append
(`POST /files/text/{filename}/append`), read (`GET`), read lines
(`GET /files/text/{filename}/lines`), check existence
(`GET /files/text/{filename}/exists`), get size
(`GET /files/text/{filename}/size`), copy, rename, and delete (`DELETE`).
Write and append requests use `{"content":"Text to save"}`; copy and rename
requests use `{"new_filename":"notes-copy.txt"}`.

### CSV files

CSV imports and exports use `reports/csv`. Files must have simple `.csv`
filenames. Book CSV files require the headers `title,author,isbn,category,quantity`.
Member CSV files require `name,email`; `phone` and `address` are optional.
Preview and import routes report invalid rows and duplicates. Valid rows are
imported individually; a row error does not roll back other valid rows.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/files/csv/books/read?filename=books.csv` | Preview and validate books CSV rows. |
| `GET` | `/files/csv/members/read?filename=members.csv` | Preview and validate members CSV rows. |
| `POST` | `/files/csv/books/import?filename=books.csv` | Import valid book rows. |
| `POST` | `/files/csv/members/import?filename=members.csv` | Import valid member rows. |
| `GET` | `/files/csv/books/export?filename=books-export.csv` | Export database books. |
| `GET` | `/files/csv/members/export?filename=members-export.csv` | Export database members. |

### JSON files

JSON imports and exports use `reports/json`. Generic read and write operations
support JSON values. Book import files must use the shape
`{"books":[{"title":"...","author":"...","isbn":"...","category":"...","quantity":1}]}`
and member import files must use the shape
`{"members":[{"name":"...","email":"..."}]}`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/files/json/{filename}` | Read a JSON file. |
| `PUT` | `/files/json/{filename}` | Write the raw JSON request body to a file. |
| `POST` | `/files/json/books/import?filename=books.json` | Validate and import book records. |
| `POST` | `/files/json/members/import?filename=members.json` | Validate and import member records. |
| `GET` | `/files/json/books/export?filename=books-export.json` | Export books as `{"books":[...]}`. |
| `GET` | `/files/json/members/export?filename=members-export.json` | Export members as `{"members":[...]}`. |

### File uploads

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/files/upload` | Upload one `.txt`, `.csv`, or `.json` multipart form-data file. |
| `GET` | `/files/download/{filename}` | Download using the generated name returned by upload. |

Uploads are limited to 1 MiB each. The server validates UTF-8 text, parses JSON,
checks CSV headers/format, assigns a generated filename, and stores the file in
`uploads/`. Downloads are restricted to generated filenames in that folder.

## Status codes and errors

- `200 OK`: retrieval or update succeeded.
- `201 Created`: a book/member/borrowing record or upload was created.
- `204 No Content`: deletion succeeded.
- `400 Bad Request`: a requested operation is invalid.
- `404 Not Found`: a record or file does not exist.
- `409 Conflict`: a duplicate ISBN/email, unavailable stock, repeated return,
  or protected deletion conflicts with current data.
- `415 Unsupported Media Type`: a JSON write request did not use
  `application/json`.
- `422 Unprocessable Entity`: request validation, file content, or filename
  validation failed.
- `500 Internal Server Error`: an unexpected server-side error occurred.
- `503 Service Unavailable`: the database is unavailable or misconfigured.

Error responses do not include database passwords or stack traces. Keep the
local `.env` private when diagnosing configuration problems.

## Git and secret handling

The `.gitignore` excludes `.env`, `.venv/`, Python cache files, `uploads/`, and
generated `reports/` data. Before committing or pushing changes:

```powershell
git status --short
git check-ignore .env .venv uploads\sample.txt reports\csv\sample.csv
git diff --check
```

Review the exact staged files before creating a commit:

```powershell
git add README.md .gitignore .env.example requirements.txt main.py database.py book_queries.py member_queries.py borrow_queries.py file_operations.py csv_operations.py json_operations.py upload_operations.py
git diff --cached --check
git diff --cached --name-only
git diff --cached
```

Only push after confirming `.env`, `.venv/`, and generated/private data are not
staged. Do not add `.env` or real database credentials to GitHub.
