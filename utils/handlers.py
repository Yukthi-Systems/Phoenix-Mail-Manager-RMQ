"""
All base handlers are defined here
"""

"""
Copyright (C) 2026 Yukthi Systems Private Limited

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 3
as published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
version 3 along with this program. If not, see
<https://www.gnu.org/licenses/>.
"""


from .libraries import json
from .constants import logging


def _process_json_body(body: bytes) -> dict:
    """
    Process the JSON body of the message.
    """
    try:
        return json.loads(body.decode('utf-8'))
    except json.JSONDecodeError as e:
        logging.error(f"Failed to decode JSON body: {e}")
        return {}


def validate_keys(required_keys: list[str], message_data: dict) -> bool:
    """
    Validate that all required keys are present in the message data.
    """
    if not all(key in message_data for key in required_keys):
        logging.error(f"Message body is missing required keys: {message_data}")
        return False
    return True


def differentiate_message(message: dict) -> tuple[str, dict]:
    """
    Differentiate the message based on the type
    """
    message_headers: dict = message["headers"]
    message_type: str = message_headers.get("type", "unknown").lower()
    message_data = _process_json_body(body=message["body"])

    if not message_data:
        logging.error(f"Message body is not valid JSON: {message['body']}")
        return message_type, {}

    match message_type:
        case "new_email":
            # If its a new email id then make sure the body is valid and has required fields
            required_email_id_keys = ["email"]
            if not validate_keys(required_email_id_keys, message_data):
                return message_type, {}

            # If all checks pass, return the message type and formatted data
            return message_type, {
                "email": message_data["email"]
            }

        case "start_migration":
            # If its a start migration message then make sure the body is valid and has required fields
            required_migration_keys = ["migration_id", "email", "source_server_id", "target_server_id"]
            if not validate_keys(required_migration_keys, message_data):
                return message_type, {}
            
            # If all checks pass, return the message type and formatted data
            return message_type, {
                "migration_id": message_data["migration_id"],
                "email": message_data["email"],
                "source_server_id": message_data["source_server_id"],
                "target_server_id": message_data["target_server_id"]
            }

        case "relay_unblock_email":
            # If its a relay unblock email message then make sure the body is valid and has required
            required_fields = ["email"]
            if not validate_keys(required_fields, message_data):
                return message_type, {}
            
            # If all checks pass, return the message type and formatted data
            return message_type, {
                "email": message_data["email"]
            }

        case "delete_email":
            # If its a delete email message then make sure the body is valid and has required fields
            required_delete_email_keys = ["email_prefix", "domain_name", "server_id"]
            if not validate_keys(required_delete_email_keys, message_data):
                return message_type, {}

            # If all checks pass, return the message type and formatted data
            return message_type, {
                "email_prefix": message_data["email_prefix"],
                "domain_name": message_data["domain_name"],
                "server_id": message_data["server_id"]
            }

        case "new_domain":
            # If its a new domain message then make sure the body is valid and has required fields
            required_domain_keys = ["domain_name"]
            if not validate_keys(required_domain_keys, message_data):
                return message_type, {}

            # If all checks pass, return the message type and formatted data
            return message_type, {
                "domain": message_data["domain_name"]
            }

        case "delete_domain":
            # If its a delete domain message then make sure the body is valid and has required fields
            required_domain_keys = ["domain_name"]
            if not validate_keys(required_domain_keys, message_data):
                return message_type, {}

            # If all checks pass, return the message type and formatted data
            return message_type, {
                "domain": message_data["domain_name"]
            }
        
        case "imap_sync":
            # If its an IMAP sync message then make sure the body is valid and has required
            required_imap_sync_keys = ["job_id", "params"]
            if not validate_keys(required_imap_sync_keys, message_data):
                return message_type, {}
            
            # If all checks pass, return the message type and formatted data
            return message_type, {
                "job_id": message_data["job_id"],
                "params": message_data["params"]
            }

        case _:
            # If its a unknown message then log the error
            logging.error(f"Unknown message type: {message_type}. Message headers: {message_headers}, body: {message['body']}")
            return "unknown", {}
