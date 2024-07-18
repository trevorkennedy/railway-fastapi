from http import HTTPStatus
from typing import Annotated
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
import uuid
import pathlib
import platform
import boto3
from botocore.exceptions import ClientError
from os import getenv, path, makedirs
from dotenv import load_dotenv
from psycopg2 import connect, Error
from psycopg2.sql import Identifier, SQL
from mailersend import emails

dir_name = "uploads" # store uploaded image in this folder
table_name = "uploads" # Postgres table name

load_dotenv()

# Makre sure uploads dir exists
if not path.exists(dir_name):
     makedirs(dir_name)

app = FastAPI()


def send_email(subject, message):
    mail_body = {}

    mail_from = {
        "name": getenv('MAILER_FROM_NAME'),
        "email": getenv('MAILER_FROM'),
    }

    recipients = [
        {
            "email": getenv('MAILER_TO'),
        }
    ]

    mailer = emails.NewEmail(getenv("MAILER_KEY"))
    mailer.set_mail_from(mail_from, mail_body)
    mailer.set_reply_to(mail_from, mail_body)
    mailer.set_mail_to(recipients, mail_body)
    mailer.set_subject(subject, mail_body)
    mailer.set_html_content(message, mail_body)
    return mailer.send(mail_body)


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


def s3_client():
    return boto3.client(
        service_name="s3",
        endpoint_url=getenv('S3ENDPOINT'),
        aws_access_key_id=getenv('S3ACCESSKEY'),
        aws_secret_access_key=getenv('S3SECRETKEY'),
        region_name=getenv('S3REGION'),
    )

def get_metadata(key):
    res = s3_client().list_objects_v2(Bucket=getenv('S3BUCKET'), Prefix=key, MaxKeys=1)
    size = res['Contents'][0]['Size'] if 'Contents' in res else -1
    content_type = ''

    if size >= 0:
        object_information = s3_client().head_object(Bucket=getenv('S3BUCKET'), Key=key)
        if 'content-type' in object_information['ResponseMetadata']['HTTPHeaders']:
            content_type = object_information['ResponseMetadata']['HTTPHeaders']['content-type']

    return size, content_type


@app.get("/")
async def root():
    response = {"count": -1}

    try:
        with pg_connection().cursor() as cur:
            cur.execute("SELECT now()")
            response['time'] = cur.fetchone()[0].isoformat()
            cur.execute(SQL("SELECT count(*) FROM {}").format(Identifier(table_name)))
            response['count'] = cur.fetchone()[0]
    except Error as err:
        print ("An exception has occured:", err)
        response['message'] = str(type(err))
        print ("Exception TYPE:", type(err))

    return JSONResponse(status_code=HTTPStatus.OK, content=response)


@app.get("/file/{name}")
async def say_hello(name: str):
    try:
        local_name = path.join(dir_name, 'temp')
        size, content_type = get_metadata(name)

        if size > 0:
            s3_client().download_file(getenv('S3BUCKET'), name, local_name)        
            return FileResponse(path=local_name, 
                                    status_code=HTTPStatus.OK, 
                                    headers={'Content-Type': content_type},
                                    content_disposition_type=f'attachment; filename="{name}"')
    except ClientError as e:
        print(e)

    return Response(status_code=HTTPStatus.NOT_FOUND)


@app.post("/files/")
async def create_file(
    file: Annotated[UploadFile, File()],
    token: Annotated[str, Form()],
):
    guid = str(uuid.uuid4())
    file_extension = pathlib.Path(file.filename).suffix
    new_name = f'{guid}{file_extension}'
    new_token = guid if token == '' else token[:50]

    # persist to s3
    try:
        s3_client().upload_fileobj(file.file, getenv('S3BUCKET'), new_name, ExtraArgs={'ContentType': file.content_type})
    except ClientError as e:
        print(e)

    # create database entry
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                sql = "INSERT INTO {} (id, token, file_name, content_type, file_size) VALUES (%s, %s, %s, %s, %s)"
                vals = (guid, new_token, new_name, file.content_type, file.size)
                cur.execute(SQL(sql).format(Identifier(table_name)), vals)
            conn.commit()
    except Error as err:
        print ("An exception has occured:", err)
        response['message'] = str(type(err))
        print ("Exception TYPE:", type(err))

    # Send email
    share_url = f'https://api.galen.agency/file/{new_name}'
    html = f'<p>Contact form submission</p><p>File: {share_url}</p><p>{platform.uname().node}</p>'
    send_email('Form submission', html)
    # save_hubspot_note(contact_id, html)

    response = {
        "size": file.size,
        "name": file.filename,
        "new_name": new_name,
        "token": new_token,
        "content_type": file.content_type,
    }

    return JSONResponse(status_code=HTTPStatus.OK, content=response)