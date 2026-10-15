import mysql.connector

from database import get_db_connection


def get_books(search_text=None):
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        if search_text:
            search_pattern = f"%{search_text}%"
            cursor.execute(
                """
                SELECT id, title, author, isbn, category, quantity,
                       available_quantity
                FROM books
                WHERE title LIKE %s
                   OR author LIKE %s
                   OR category LIKE %s
                   OR isbn LIKE %s
                ORDER BY id
                """,
                (search_pattern,) * 4,
            )
        else:
            cursor.execute(
                """
                SELECT id, title, author, isbn, category, quantity,
                       available_quantity
                FROM books
                ORDER BY id
                """
            )

        return cursor.fetchall()
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def get_book_by_id(book_id):
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, title, author, isbn, category, quantity,
                   available_quantity
            FROM books
            WHERE id = %s
            """,
            (book_id,),
        )
        return cursor.fetchone()
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def create_book(book_data):
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            INSERT INTO books
                (title, author, isbn, category, quantity, available_quantity)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                book_data["title"],
                book_data["author"],
                book_data["isbn"],
                book_data["category"],
                book_data["quantity"],
                book_data["quantity"],
            ),
        )
        book_id = cursor.lastrowid
        connection.commit()
        cursor.execute(
            """
            SELECT id, title, author, isbn, category, quantity,
                   available_quantity
            FROM books
            WHERE id = %s
            """,
            (book_id,),
        )
        return cursor.fetchone()
    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def update_book(book_id, changes):
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT quantity, available_quantity
            FROM books
            WHERE id = %s
            FOR UPDATE
            """,
            (book_id,),
        )
        current_book = cursor.fetchone()
        if current_book is None:
            return None

        if "quantity" in changes:
            borrowed_quantity = (
                current_book["quantity"] - current_book["available_quantity"]
            )
            if changes["quantity"] < borrowed_quantity:
                raise ValueError(
                    "Quantity cannot be less than the number of borrowed copies."
                )

        allowed_fields = ("title", "author", "isbn", "category", "quantity")
        assignments = []
        values = []
        for field in allowed_fields:
            if field in changes:
                if field == "quantity":
                    assignments.append(
                        "available_quantity = available_quantity + (%s - quantity)"
                    )
                    values.append(changes[field])
                assignments.append(f"{field} = %s")
                values.append(changes[field])

        values.append(book_id)
        cursor.execute(
            f"UPDATE books SET {', '.join(assignments)} WHERE id = %s",
            tuple(values),
        )
        connection.commit()
        cursor.execute(
            """
            SELECT id, title, author, isbn, category, quantity,
                   available_quantity
            FROM books
            WHERE id = %s
            """,
            (book_id,),
        )
        return cursor.fetchone()
    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def delete_book(book_id):
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("DELETE FROM books WHERE id = %s", (book_id,))
        deleted = cursor.rowcount == 1
        connection.commit()
        return deleted
    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()
