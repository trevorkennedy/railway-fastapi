from os import environ
from datetime import datetime
import json
from hubspot import HubSpot
from hubspot.crm.contacts import (
    ApiException,
    SimplePublicObjectInputForCreate,
    PublicObjectSearchRequest
)


def hubspot_client():
    api_client = HubSpot()
    api_client.access_token = environ.get("HUBSPOT_KEY")
    return api_client


def get_contact(contact_id):
    properties = ["zip", "email", "firstname", "lastname", "company"]

    try:
        contact_fetched = hubspot_client().crm.contacts.basic_api.get_by_id(contact_id, properties=properties)
        print(contact_fetched.to_dict())
    except ApiException as e:
        print("Exception when requesting contact by id: %s\n" % e)


def get_contact_by_email(email):
    members = PublicObjectSearchRequest(
        properties=['email'],
        filter_groups=[
            {
                "filters": [
                    {
                        "value": email,
                        "propertyName": "email",
                        "operator": "EQ"
                    }
                ]
            }
        ],
        sorts=[{"propertyName": "created_at", "direction": "ASCENDING"}],
        limit=1
    )

    try:
        result = hubspot_client().crm.contacts.search_api.do_search(public_object_search_request=members)
        if result.results:
            return result.results[0].to_dict()['id']

    except ApiException as e:
        print("Exception when requesting contact by email: %s\n" % e)
    return None


def save_hubspot_note(contact_id, body):
    utc_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    payload = {
        "properties": {
            "hs_timestamp": utc_time,
            "hs_note_body": body,
            "hubspot_owner_id": environ.get("HUBSPOT_OWNER_ID")
        },
        "associations": [
            {
                "to": {
                    "id": contact_id
                },
                "types": [
                    {
                        "associationCategory": "HUBSPOT_DEFINED",
                        "associationTypeId": "202"
                    }
                ]
            }
        ]
    }

    hubspot_client().crm.objects.notes.basic_api.create(simple_public_object_input_for_create=payload)


def save_hubspot_contact(contact_data):
    try:
        hsp_contact_id = get_contact_by_email(contact_data['email'])
        record = SimplePublicObjectInputForCreate(properties=contact_data)

        if hsp_contact_id:
            hubspot_client().crm.contacts.basic_api.update(
                simple_public_object_input=record, contact_id=hsp_contact_id)
            return hsp_contact_id
        else:
            res = hubspot_client().crm.contacts.basic_api.create(
                simple_public_object_input_for_create=record)
            return res.id
    except ApiException as e:
        # print("Exception when creating contact: %s\n" % e)
        error_message = json.loads(e.body)
        print("Exception when creating contact: %s\n" %
              error_message['message'])
        if e.status == 409:
            return None
    return None


def save_hubspot_data(email, first_name, last_name, phone, lead_type):
    contact_data = {
        'email': email,
        'firstname': first_name,
        'lastname': last_name,
        'phone': phone,
        'about_me': lead_type,
        'lifecyclestage': 'lead'
    }
    return save_hubspot_contact(contact_data)