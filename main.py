import ast
from http import HTTPStatus
from typing import Annotated
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
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
from hubspot_helper import save_hubspot_contact, get_contact_by_email, save_hubspot_note

lead_type_regex = r"^(candidate|employer|other)$"
email_regex = r"^[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$"
dir_name = "uploads" # store uploaded image in this folder
table_name = "uploads" # Postgres table name
file_url = "https://api.galen.agency/file/"
allowed_extensions = ['.pdf', '.doc', '.docx', 'txt']
max_file_size = 5 * 1000 * 1000

load_dotenv()

# Makre sure uploads dir exists
if not path.exists(dir_name):
     makedirs(dir_name)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

headers = {'Access-Control-Allow-Origin': '*'}

def send_email(subject: str, message: str):
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
    response = {
        "count": -1, 
        "node": platform.uname().node,
        "emails": ast.literal_eval(getenv('MAILER_ENABLED')),
        "id": get_contact_by_email('test@example.org'),
    }

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


def raise_exception(msg: str, input: str):
    error = {
            "type": "value_error",
            "loc": [
                "body",
                "file"
            ],
            "msg": msg ,
            "input": input,
            "url": "https://errors.pydantic.dev/2.8/v/value_error"
        }
    raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail=[error], headers=headers)

@app.post("/files/")
async def create_file(
    email: Annotated[str, Form(max_length=50, regex=email_regex)],
    first_name: Annotated[str, Form(max_length=50)],
    last_name: Annotated[str, Form(max_length=50)],
    lead_type: Annotated[str, Form(max_length=50, regex=lead_type_regex)],
    phone: Annotated[str, Form(max_length=50)] = None,
    file: Annotated[UploadFile, File()] = None
):
    new_name = None
    content_type = None
    guid = str(uuid.uuid4())
    file_size = -1 if file is None else file.size
    file_name = file.filename if file is None else ''

    if file_size > 0:
        content_type = file.content_type
        file_extension = pathlib.Path(file_name).suffix
        new_name = f'{guid}{file_extension}'
        if file_size > max_file_size:
            raise_exception(f"File size exceeds {max_file_size} bytes", file_name)
        # elif file_extension not in allowed_extensions:
        #     type_list = ",".join(allowed_extensions) # avoid complier crash on Railway
        #     raise_exception(f"File type must be one of: {type_list}", file_name)

    # persist to s3
    if file_size > 0:
        try:
            args = {} if content_type is None else {'ContentType': content_type}
            s3_client().upload_fileobj(file.file, getenv('S3BUCKET'), new_name, ExtraArgs=args)
        except ClientError as e:
            print(e)

    # create database entry
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                sql = "INSERT INTO {} (id, token, file_name, content_type, file_size) VALUES (%s, %s, %s, %s, %s)"
                vals = (guid, email, new_name, content_type, file_size)
                cur.execute(SQL(sql).format(Identifier(table_name)), vals)
            conn.commit()
    except Error as err:
        print ("An exception has occured:", err)

    # Save to Hubspot
    contact_data = {
        'email': email,
        'firstname': first_name,
        'lastname': last_name,
        'phone': phone,
        'about_me': lead_type,
        'lifecyclestage': 'lead'
    }
    contact_id = save_hubspot_contact(contact_data)

    html = "<p>Contact form submission</p>"
    if file_size > 0:
        html += f"<p>File: {file_url}{new_name}</p>"
    else:
        html += f"<p>File: no file attchment</p>"
    html += f"<p>Node: {platform.uname().node}</p>"
    
    # Send email 
    save_hubspot_note(contact_id, html)
    if ast.literal_eval(getenv('MAILER_ENABLED')):
        send_email('Form submission', html)

    

    return Response(status_code=HTTPStatus.OK, headers=headers)