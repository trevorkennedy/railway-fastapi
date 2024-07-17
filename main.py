from http import HTTPStatus
from typing import Annotated
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
import uuid
import os
import pathlib

dir_name = "uploads"  # store uploaded image in this folder

app = FastAPI()

@app.get("/")
async def root():
    return {"greeting": "Hello, World!"}


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

    if not os.path.exists(dir_name):
        os.makedirs(dir_name)

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