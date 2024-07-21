import ast
import pathlib
import uuid
import re
import platform
from http import HTTPStatus
from io import BytesIO
from os import path, makedirs, getenv
from urllib.parse import urljoin

from emailer import send_email
from hubspot_helper import save_hubspot_note, save_hubspot_data
from pg import insert_form_data
from s3 import upload_file

max_field_len = 50
max_file_size = 1 * 1000 * 1000
dir_name = "uploads"  # store uploaded image in this folder
allowed_extensions = ['.pdf', '.doc', '.docx', 'txt']
email_regex = r"^[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$"
lead_type_regex = r"^(candidate|employer|other)$"
file_url = "https://api.galen.agency/file/"


def remote_file_url(remote_name: str) -> str:
    return urljoin(file_url, remote_name)


def remote_file_name(guid: str, file_name: str) -> str:
    return f'{guid}{file_extension(file_name)}'


def valid_extension(file_name) -> bool:
    return file_extension(file_name) in allowed_extensions


def prep_local_dir():
    # Make sure uploads dir exists
    if not path.exists(dir_name):
        makedirs(dir_name)


def file_extension(file_name):
    return pathlib.Path(file_name).suffix


def valid_file_size(size: int):
    return 0 < size < max_file_size


def valid_str_len(value: str, min_len: int):
    value = '' if value is None else value.strip()
    return min_len <= len(value) <= max_field_len


def message_html(file_size, new_name):
    html = "<p>Contact form submission</p>"
    if valid_file_size(file_size):
        html += f"<p>File: {remote_file_url(new_name)}</p>"
    else:
        html += f"<p>File: no file attachment</p>"
    html += f"<p>Node: {platform.uname().node}</p>"
    return html


class ContactForm:
    lead_type: str
    first_name: str
    last_name: str
    phone: str
    email: str
    file_name: str
    file_size: int
    file_content_type: str
    file_content: bytes
    guid: str

    def __init__(self):
        self.lead_type = ''
        self.first_name = ''
        self.last_name = ''
        self.phone = ''
        self.email = ''
        self.file_name = ''
        self.file_size = -1
        self.file_content_type = ''
        self.guid = str(uuid.uuid4())

    def __str__(self):
        string = f'{self.lead_type}, {self.first_name}, {self.last_name}, {self.phone}, {self.email},'
        return string + f'{self.file_name}, {self.file_size}, {self.file_content_type}'

    def save_locally(self):
        if valid_file_size(self.file_size):
            prep_local_dir()
            temp_path = path.join(dir_name, self.file_name)
            with open(temp_path, 'wb') as temp_file:
                temp_file.write(self.file_content)

    def file_extension(self):
        return file_extension(self.file_name)

    def remote_file_url(self) -> str:
        return remote_file_url(self.remote_file_name())

    def remote_file_name(self) -> str:
        return remote_file_name(self.guid, self.file_name)

    def file_content_bytes(self) -> BytesIO:
        return BytesIO(self.file_content)

    def message_html(self):
        html = "<p>Contact form submission</p>"
        if self.valid_file_size():
            html += f"<p>File: {self.remote_file_url()}</p>"
        else:
            html += f"<p>File: no file attachment</p>"
        html += f"<p>Node: {platform.uname().node}</p>"

    def valid_extension(self):
        return valid_extension(self.file_name)

    def valid_file_size(self):
        return valid_file_size(self.file_size)

    def valid_email(self):
        return re.match(email_regex, self.email)

    def valid_lead_type(self):
        return re.match(lead_type_regex, self.lead_type)

    def valid(self):
        return (self.valid_extension()
                and self.valid_file_size()
                and self.valid_email()
                and self.valid_lead_type()
                and valid_str_len(self.first_name, 1)
                and valid_str_len(self.last_name, 1)
                and valid_str_len(self.email, 1)
                and valid_str_len(self.phone, 0)
                )

    def process(self) -> (int, str):
        if self.valid():
            self.save_locally()
            new_name = self.remote_file_name()
            upload_file(self.file_content_bytes(), new_name, self.file_content_type)
            insert_form_data(self.guid, self.email, new_name, self.file_content_type, self.file_size)

            # Save to Hubspot
            html = message_html(self.file_size, new_name)
            contact_id = save_hubspot_data(self.email, self.first_name, self.last_name, self.phone, self.lead_type)
            save_hubspot_note(contact_id, html)

            # Send email
            if ast.literal_eval(getenv('MAILER_ENABLED')):
                send_email('Form submission', html)
            return HTTPStatus.OK, str(self) + '|valid'
        else:
            return HTTPStatus.UNPROCESSABLE_ENTITY, str(self) + '|invalid'
