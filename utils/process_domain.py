"""
This module contains functions to handle domain creation and deletion by interacting with an external DKIM API.
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


from .libraries import requests
from .constants import logging, DKIM_API_URL, DKIM_API_KEY


def handle_create_new_domain(domain: str) -> None:
    """
    Handle the creation of a new domain.
    """
    logging.info(f"Start create new domain handler called for domain: {domain}")

    url = f"{DKIM_API_URL}/v1/{domain}"
    headers = {
        "Accept": "application/json",
        "Auth-Token": DKIM_API_KEY
    }

    try:
        response = requests.post(url=url, headers=headers, timeout=5)
        logging.info(f"Domain {domain} created successfully. Result: {response.text}; Status Code: {response.status_code}")

    except Exception as e:
        logging.error(f"Error handling create new domain for domain {domain}: {e}", exc_info=True)


def handle_delete_domain(domain: str) -> None:
    """
    Handle the deletion of a domain.
    """
    logging.info(f"Start delete domain handler called for domain: {domain}")

    url = f"{DKIM_API_URL}/v1/{domain}"
    headers = {
        "Accept": "application/json",
        "Auth-Token": DKIM_API_KEY
    }

    try:
        response = requests.delete(url=url, headers=headers, timeout=5)
        logging.info(f"Domain {domain} deleted successfully. Result: {response.text}; Status Code: {response.status_code}")

    except Exception as e:
        logging.error(f"Error handling delete domain for domain {domain}: {e}", exc_info=True)
