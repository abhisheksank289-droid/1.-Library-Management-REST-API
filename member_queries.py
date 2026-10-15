import mysql.connector

from database import get_db_connection


def get_members(search_text=None):
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        if search_text:
            search_pattern = f"%{search_text}%"
            cursor.execute(
                """
                SELECT id, name, email, phone, address
                FROM members
                WHERE name LIKE %s OR email LIKE %s
                ORDER BY id
                """,
                (search_pattern, search_pattern),
            )
        else:
            cursor.execute(
                """
                SELECT id, name, email, phone, address
                FROM members
                ORDER BY id
                """
            )

        return cursor.fetchall()
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def get_member_by_id(member_id):
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, name, email, phone, address
            FROM members
            WHERE id = %s
            """,
            (member_id,),
        )
        return cursor.fetchone()
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def create_member(member_data):
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            INSERT INTO members (name, email, phone, address)
            VALUES (%s, %s, %s, %s)
            """,
            (
                member_data["name"],
                member_data["email"],
                member_data.get("phone"),
                member_data.get("address"),
            ),
        )
        member_id = cursor.lastrowid
        connection.commit()
        cursor.execute(
            """
            SELECT id, name, email, phone, address
            FROM members
            WHERE id = %s
            """,
            (member_id,),
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


def update_member(member_id, changes):
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT id FROM members WHERE id = %s FOR UPDATE",
            (member_id,),
        )
        if cursor.fetchone() is None:
            return None

        allowed_fields = ("name", "email", "phone", "address")
        assignments = []
        values = []
        for field in allowed_fields:
            if field in changes:
                assignments.append(f"{field} = %s")
                values.append(changes[field])

        values.append(member_id)
        cursor.execute(
            f"UPDATE members SET {', '.join(assignments)} WHERE id = %s",
            tuple(values),
        )
        connection.commit()
        cursor.execute(
            """
            SELECT id, name, email, phone, address
            FROM members
            WHERE id = %s
            """,
            (member_id,),
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


def delete_member(member_id):
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("DELETE FROM members WHERE id = %s", (member_id,))
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
