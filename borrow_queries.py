from datetime import date

import mysql.connector

from database import get_db_connection


def issue_book(book_id, member_id, due_date):
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT id FROM members WHERE id = %s FOR UPDATE",
            (member_id,),
        )
        if cursor.fetchone() is None:
            connection.rollback()
            raise ValueError("Member not found.")

        cursor.execute(
            """
            SELECT id, available_quantity
            FROM books
            WHERE id = %s
            FOR UPDATE
            """,
            (book_id,),
        )
        book = cursor.fetchone()
        if book is None:
            connection.rollback()
            raise ValueError("Book not found.")
        if book["available_quantity"] < 1:
            connection.rollback()
            raise ValueError("Book is not available.")

        cursor.execute(
            """
            UPDATE books
            SET available_quantity = available_quantity - 1
            WHERE id = %s AND available_quantity > 0
            """,
            (book_id,),
        )
        if cursor.rowcount != 1:
            connection.rollback()
            raise ValueError("Book is not available.")

        cursor.execute(
            """
            INSERT INTO borrow_records
                (book_id, member_id, issue_date, due_date, status)
            VALUES (%s, %s, %s, %s, 'issued')
            """,
            (book_id, member_id, date.today(), due_date),
        )
        record_id = cursor.lastrowid
        connection.commit()

        cursor.execute(
            """
            SELECT id, book_id, member_id, issue_date, due_date,
                   return_date, status
            FROM borrow_records
            WHERE id = %s
            """,
            (record_id,),
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


def get_borrow_records(issued_only=False):
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        if issued_only:
            cursor.execute(
                """
                SELECT id, book_id, member_id, issue_date, due_date,
                       return_date, status
                FROM borrow_records
                WHERE status = 'issued'
                ORDER BY id
                """
            )
        else:
            cursor.execute(
                """
                SELECT id, book_id, member_id, issue_date, due_date,
                       return_date, status
                FROM borrow_records
                ORDER BY id
                """
            )
        return cursor.fetchall()
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def get_member_borrow_records(member_id):
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT id FROM members WHERE id = %s",
            (member_id,),
        )
        if cursor.fetchone() is None:
            return None

        cursor.execute(
            """
            SELECT id, book_id, member_id, issue_date, due_date,
                   return_date, status
            FROM borrow_records
            WHERE member_id = %s
            ORDER BY id
            """,
            (member_id,),
        )
        return cursor.fetchall()
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def return_book(record_id):
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, book_id, status
            FROM borrow_records
            WHERE id = %s
            FOR UPDATE
            """,
            (record_id,),
        )
        record = cursor.fetchone()
        if record is None:
            connection.rollback()
            raise ValueError("Borrowing record not found.")
        if record["status"] != "issued":
            connection.rollback()
            raise ValueError("Borrowing record has already been returned.")

        cursor.execute(
            "SELECT id FROM books WHERE id = %s FOR UPDATE",
            (record["book_id"],),
        )
        if cursor.fetchone() is None:
            connection.rollback()
            raise ValueError("Book not found.")

        cursor.execute(
            """
            UPDATE books
            SET available_quantity = available_quantity + 1
            WHERE id = %s
            """,
            (record["book_id"],),
        )
        cursor.execute(
            """
            UPDATE borrow_records
            SET return_date = %s, status = 'returned'
            WHERE id = %s
            """,
            (date.today(), record_id),
        )
        connection.commit()

        cursor.execute(
            """
            SELECT id, book_id, member_id, issue_date, due_date,
                   return_date, status
            FROM borrow_records
            WHERE id = %s
            """,
            (record_id,),
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
