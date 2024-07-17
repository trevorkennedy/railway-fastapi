from http import HTTPStatus
from typing import Annotated
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
import uuid
import pathlib
from os import getenv, path, makedirs
from dotenv import load_dotenv
from psycopg2 import connect, Error
from psycopg2.sql import Identifier, SQL, Composed

dir_name = "uploads" # store uploaded image in this folder
table_name = "uploads" # Postgres table name

load_dotenv()

# Makre sure uploads dir exists
if not path.exists(dir_name):
     makedirs(dir_name)

app = FastAPI()


def pg_connection():
    # Connect to your postgres DB
    return connect(database=getenv('PGDATABASE'),
        host=getenv('PGHOST'),
        user=getenv('PGUSER'),
        password=getenv('PGPASSWORD'),
        port=getenv('PGPORT'),
        options=f"-c search_path={getenv('PGSCHEMA')}",
        sslmode='require',
        connect_timeout=3)


@app.get("/")
async def root():
    response = {
        "count": -1,
        "message": ''
    }

    try:
        with pg_connection().cursor() as cur:
            cur.execute(SQL("SELECT count(*) FROM {}").format(Identifier(table_name)))
            response['count'] = cur.fetchone()[0]
    except Error as err:
        print ("An exception has occured:", err)
        response['message'] = str(type(err))
        print ("Exception TYPE:", type(err))

    return JSONResponse(status_code=HTTPStatus.OK, content=response)


@app.get("/file/{name}")
async def say_hello(name: str):
    return FileResponse(path=f"{dir_name}/{name}", status_code=HTTPStatus.OK)


@app.post("/files/")
async def create_file(
    file: Annotated[UploadFile, File()],
    token: Annotated[str, Form()],
):
    guid = uuid.uuid4()
    file_extension = pathlib.Path(file.filename).suffix
    new_name = f'{guid}{file_extension}'
    new_token = guid if token == '' else token[:50]

    # save the file
    with open(f"{dir_name}/{new_name}", "wb") as f:
        contents = await file.read()
        f.write(contents)

    # create database entry
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                sql = "INSERT INTO {} (token, file_name, content_type, file_size) VALUES (%s, %s, %s, %s)"
                vals = (new_token, new_name, file.content_type, file.size)
                cur.execute(SQL(sql).format(Identifier(table_name)), vals)
            conn.commit()
    except Error as err:
        print ("An exception has occured:", err)
        response['message'] = str(type(err))
        print ("Exception TYPE:", type(err))

    response = {
        "size": file.size,
        "name": file.filename,
        "new_name": new_name,
        "token": new_token,
        "content_type": file.content_type,
    }

    return JSONResponse(status_code=HTTPStatus.OK, content=response)