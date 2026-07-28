"""
This module handles the deletion of email messages from cloud servers.
It connects to a PostgreSQL database to retrieve server details associated with the email,
runs an Ansible playbook to delete the email, and manages background migration flows.
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


from .libraries import psycopg2, Thread
from .run_ansible import run_ansible_playbook
from .constants import logging, POSTGRES_DB_URI
from .database import get_server_details_by_id


def handle_delete_email(email_prefix: str, domain_name: str, server_id: str) -> None:
    """
    Handle the delete email message from cloud servers
    """
    logging.info(f"Start delete email handler called for email: {email_prefix}@{domain_name}")
    try:
        with psycopg2.connect(POSTGRES_DB_URI, connect_timeout=120) as conn:
            with conn.cursor() as cursor:
                # Get the server details for the email
                server_details: dict = get_server_details_by_id(cursor=cursor, server_id=server_id)
                if not server_details:
                    logging.error(f"Server details not found for email {email_prefix}@{domain_name} with server_id {server_id}. Cannot proceed with deletion.")
                    return

                # Run the Ansible playbook in background to delete the email on the server (spawn a new thread)
                Thread(
                    target=run_ansible_playbook,
                    args=(
                        "books/delete_email.yaml",
                        {
                            "target_host": server_id,
                            "email_path": f"{server_details['storage_path']}/{domain_name}/{email_prefix}".lower()
                        }
                    ),
                    daemon=True
                ).start()

    except Exception as e:
        logging.error(f"Error handling delete email for {email_prefix}@{domain_name} with server_id {server_id}: {e}", exc_info=True)
