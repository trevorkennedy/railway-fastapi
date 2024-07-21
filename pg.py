from os import getenv
from psycopg2 import Error, connect
from psycopg2.sql import Identifier, SQL


table_name = "uploads"  # Postgres table name


def pg_connection():
    return connect(database=getenv('PGDATABASE'),
                   host=getenv('PGHOST'),
                   user=getenv('PGUSER'),
                   password=getenv('PGPASSWORD'),
                   port=getenv('PGPORT'),
                   options=f"-c search_path={getenv('PGSCHEMA')}",
                   sslmode=getenv('PGSQLMODE'),
                   sslrootcert=getenv('PGROOTCERT'),
                   connect_timeout=3)


def get_row_count() -> int:
    try:
        with pg_connection().cursor() as cur:
            cur.execute("SELECT now()")
            cur.execute(SQL("SELECT count(*) FROM {}").format(Identifier(table_name)))
            return cur.fetchone()[0]
    except Error as err:
        print("An exception has occured:", err)
        print("Exception TYPE:", type(err))


def insert_form_data(guid, email, new_name, content_type, file_size):
    # create database entry
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                sql = "INSERT INTO {} (id, token, file_name, content_type, file_size) VALUES (%s, %s, %s, %s, %s)"
                vals = (guid, email, new_name, content_type, file_size)
                cur.execute(SQL(sql).format(Identifier(table_name)), vals)
            conn.commit()
    except Error as err:
        print("An exception has occured:", err)