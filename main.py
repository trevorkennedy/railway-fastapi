import ast
from http import HTTPStatus
from typing import Annotated
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, JSONResponse, Response, PlainTextResponse
import platform
from os import getenv, path
from dotenv import load_dotenv
from contact_form import ContactForm, dir_name, email_regex, lead_type_regex, max_field_len
from hubspot_helper import get_contact_by_email
from pg import get_row_count
from s3 import download_file, get_metadata

load_dotenv()
app = FastAPI()
headers = {'Access-Control-Allow-Origin': '*'}


@app.get("/")
async def root():
    return JSONResponse(status_code=HTTPStatus.OK, content={
        "node": platform.uname().node,
        "emails": ast.literal_eval(getenv('MAILER_ENABLED')),
        "id": get_contact_by_email('test@example.org'),
        "count": get_row_count()
    })


@app.get("/file/{name}")
async def say_hello(name: str):
    size, content_type = get_metadata(name)
    if size > 0:
        local_name = path.join(dir_name, 'temp')
        download_file(name, local_name)
        return FileResponse(path=local_name,
                            status_code=HTTPStatus.OK,
                            headers={'Content-Type': content_type},
                            content_disposition_type=f'attachment; filename="{name}"')
    else:
        return Response(status_code=HTTPStatus.NOT_FOUND)


def raise_exception(msg: str, value: str):
    error = {
        "type": "value_error",
        "loc": ["body", "file"],
        "msg": msg,
        "input": value,
        "url": "https://errors.pydantic.dev/2.8/v/value_error"
    }
    raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail=[error], headers=headers)


@app.post("/files/")
async def create_file(
        email: Annotated[str, Form(max_length=max_field_len, regex=email_regex)],
        first_name: Annotated[str, Form(max_length=max_field_len)],
        last_name: Annotated[str, Form(max_length=max_field_len)],
        lead_type: Annotated[str, Form(max_length=max_field_len, regex=lead_type_regex)],
        phone: Annotated[str, Form(max_length=max_field_len)] = None,
        file: Annotated[UploadFile, File()] = None
):
    data = ContactForm()
    data.file_content_type = file.content_type
    data.file_name = file.filename
    data.file_size = file.size
    data.file_content = file.file.read()
    data.lead_type = lead_type
    data.first_name = first_name
    data.last_name = last_name
    data.phone = phone
    data.email = email
    return PlainTextResponse(
        headers=headers,
        status_code=HTTPStatus.OK,
        content=data.process())


@app.post("/submit/")
async def submit_form(request: Request):
    async with request.form() as form:
        file_attachment = form.get('file')
        data = ContactForm()
        data.file_content_type = file_attachment.content_type
        data.file_name = file_attachment.filename
        data.file_size = file_attachment.size
        data.file_content = await file_attachment.read()
        data.lead_type = form.get('lead_type')
        data.first_name = form.get('first_name')
        data.last_name = form.get('last_name')
        data.phone = form.get('phone')
        data.email = form.get('email')
        return PlainTextResponse(
            headers=headers,
            status_code=HTTPStatus.OK,
            content=data.process())
