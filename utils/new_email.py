"""
All the handlers for New Email ID type
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


from .libraries import psycopg2
from .constants import POSTGRES_DB_URI, logging
from .database import (
    get_server_load_stats_from_q_db,
    set_email_server_and_activate,
    check_email_domain_locked,
    get_required_email_quota,
    get_all_active_servers,
    calculate_health_stats,
    update_server_quota
)


def _get_possible_servers(cursor, email: str) -> dict:
    """
    Get the possible servers based on locked servers and total active servers
    If there are any locked servers then use only that servers
    Else use all the active servers
    :param cursor: Database cursor
    :return: Dictionary of possible servers with their quota information
    """
    # Check if the email domain is locked
    locked_servers = check_email_domain_locked(cursor, email)

    # Total servers to be used for the email
    total_active_servers = get_all_active_servers(cursor)
    if not total_active_servers:
        logging.error("No active servers found in the database.")
        return {}

    if locked_servers:
        return {server: total_active_servers[server] for server in locked_servers if server in total_active_servers}

    return total_active_servers


def _possible_servers_by_quota(available_servers: dict, required_quota: float) -> dict:
    """
    Filter the available servers based on the required quota
    :param available_servers: Dictionary of available servers with their quota information
    :param required_quota: Required quota for the email
    :return: Dictionary of servers that can accommodate the required quota
    """
    final_possible_servers = {}
    for server_id, server_info in available_servers.items():
        available_server_space = server_info['quota_allocated'] - server_info['quota_utilized']
        if available_server_space >= required_quota:
            final_possible_servers[server_id] = server_info

    # If there are servers that can accommodate the required quota, return them
    if final_possible_servers:
        return final_possible_servers

    # If there are no servers that can accommodate the required quota
    # Calculate the server with largest available space and return that server
    max_server = max(available_servers.items(), key=lambda x: x[1]['quota_allocated'] - x[1]['quota_utilized'])
    return {max_server[0]: max_server[1]}


def handle_new_email(email: str) -> None:
    """
    Handle the new email ID by checking if it exists in the QuestDB.
    If it does not exist, insert it into the database.
    """
    try:
        with psycopg2.connect(POSTGRES_DB_URI, connect_timeout=120) as conn:
            with conn.cursor() as cursor:
                # Get the possible servers based on locked servers and total active servers
                available_servers: dict = _get_possible_servers(cursor=cursor, email=email)
                logging.info(f"Available servers for email {email}: {available_servers}")
                if not available_servers:
                    logging.error(f"No possible servers found for email: {email}")
                    return

                # Get required email quota
                required_email_quota: float = get_required_email_quota(email_id=email, cursor=cursor)
                logging.info(f"Required quota for email {email} is {required_email_quota} GB")

                # Based on the servers and required quota, figure out the possible servers
                final_possible_servers = _possible_servers_by_quota(
                    available_servers=available_servers,
                    required_quota=required_email_quota
                )
                logging.info(f"Possible servers for email {email} after quota check: {final_possible_servers}")
                if not final_possible_servers:
                    logging.error(f"No servers found that can accommodate the required quota for email: {email}")
                    return

                # If there is only one server, use that server directly
                if len(final_possible_servers) == 1:
                    server_id = list(final_possible_servers.keys())[0]  # Since its only one server set that server
                    set_email_server_and_activate(cursor=cursor, email=email, server_id=server_id)
                    update_server_quota(cursor=cursor, server_id=server_id, add_utilized_quota=required_email_quota)

                    logging.info(f"Email {email} assigned to server {server_id} as it was the only available server.")

                # If there are multiple servers, Get the best server based on health metrics
                else:
                    server_stats_df = get_server_load_stats_from_q_db(server_ids=list(final_possible_servers.keys()))
                    health_scores: dict = calculate_health_stats(email_id=email, df=server_stats_df)

                    # Sort servers by health score in descending order
                    sorted_servers = sorted(health_scores.items(), key=lambda x: x[1], reverse=True)
                    best_server_id = sorted_servers[0][0]  # Get the server with the highest health score

                    # Set the best server for the email
                    set_email_server_and_activate(cursor=cursor, email=email, server_id=best_server_id)
                    update_server_quota(cursor=cursor, server_id=best_server_id, add_utilized_quota=required_email_quota)

                    logging.info(f"Email {email} assigned to server {best_server_id} based on health metrics.")

                logging.info(f"New email {email} handled successfully, assigned to server")
                # TODO: Spawn a background task to handle the new email creation process

    except Exception as e:
        logging.error(f"Error handling new email {email}: {e}")
