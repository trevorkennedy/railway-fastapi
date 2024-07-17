from http import HTTPStatus
from typing import Annotated
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
import uuid
import pathlib
from os import getenv, path, makedirs
from dotenv import load_dotenv
from psycopg2 import connect, Error

dir_name = "uploads" # store uploaded image in this folder
table_name = "galen_agency.uploads" # Postgres table name


load_dotenv()

# Makre sure uploads dir exists
if not path.exists(dir_name):
     makedirs(dir_name)

app = FastAPI()


@app.get("/")
async def root():
    count = -1
    msg = ''

    try:
        # Connect to your postgres DB
        conn = connect(database=getenv('PGDATABASE'),
                        host=getenv('PGHOST'),
                        user=getenv('PGUSER'),
                        password=getenv('PGPASSWORD'),
                        port=getenv('PGPORT'),
                        sslmode='require',
                        connect_timeout=3)

        # Open a cursor to perform database operations
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {table_name}")
        records = cur.fetchall()
        count = len(records)
    except Error as err:
        print ("Oops! An exception has occured:", err)
        msg = type(err)
        print ("Exception TYPE:", type(err))

    return JSONResponse(status_code=HTTPStatus.OK, content={"count": count, "message": msg})


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

    

    # save the file
    with open(f"{dir_name}/{new_name}", "wb") as f:
        contents = await file.read()
        f.write(contents)

    response = {
        "size": file.size,
        "name": file.filename,
        "new_name": new_name,
        "token": token,
        "content_type": file.content_type,
    }

    return JSONResponse(status_code=HTTPStatus.OK, content=response)