from os import getenv
from typing import BinaryIO

import boto3
from botocore.exceptions import ClientError


def s3_client():
    return boto3.client(
        service_name="s3",
        endpoint_url=getenv('S3ENDPOINT'),
        aws_access_key_id=getenv('S3ACCESSKEY'),
        aws_secret_access_key=getenv('S3SECRETKEY'),
        region_name=getenv('S3REGION'),
    )


def upload_file(file: BinaryIO, remote_name: str, content_type: str):
    try:
        args = {} if content_type is None else {'ContentType': content_type}
        s3_client().upload_fileobj(file, getenv('S3BUCKET'), remote_name, ExtraArgs=args)
    except ClientError as e:
        print(e)


def download_file(name, local_name):
    s3_client().download_file(getenv('S3BUCKET'), name, local_name)


def get_metadata(key):
    res = s3_client().list_objects_v2(Bucket=getenv('S3BUCKET'), Prefix=key, MaxKeys=1)
    size = res['Contents'][0]['Size'] if 'Contents' in res else -1
    content_type = ''

    if size >= 0:
        object_information = s3_client().head_object(Bucket=getenv('S3BUCKET'), Key=key)
        if 'content-type' in object_information['ResponseMetadata']['HTTPHeaders']:
            content_type = object_information['ResponseMetadata']['HTTPHeaders']['content-type']

    return size, content_type
