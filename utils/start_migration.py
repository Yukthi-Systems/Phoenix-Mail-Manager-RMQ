"""
All the handlers for Migrating Email from one server to another
This module handles the start migration message type ("INITIALIZING")
Possible Statuses:
    - INITIALIZING: Migration is being prepared
    - IN_PROGRESS: Migration is currently happening
    - COMPLETED: Migration has successfully completed
    - FAILED: Migration has failed
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
from .database import handle_migration_validation, set_email_migration_status, get_server_details


def _update_migration_stages(migration_id: str, state: str, details: dict) -> None:
    """
    Update the migration stages in the database
    Used only in background flow, since there will be lots of delay between stages
    """
    try:
        logging.info(f"Updating migration stages for migration_id: {migration_id}, state: {state}, details: {details}")
        with psycopg2.connect(POSTGRES_DB_URI, connect_timeout=120) as conn:
            with conn.cursor() as cursor:
                set_email_migration_status(
                    cursor=cursor,
                    migration_id=migration_id,
                    status=state,
                    details=details
                )
                logging.info(f"Migration stages updated: {migration_id}, state: {state}")

    except Exception as e:
        logging.error(f"Error updating migration stages for migration_id {migration_id}: {e}", exc_info=True)


def validate_server_space(migration_id: str, space_required: float, target_server_details: dict, stages: list) -> bool:
    """
    Validate the server space for migration.
    This function checks if the target server has enough space for the migration.
    It is called during the background migration flow.
    """
    stages.append("Validating the source and target servers for migration, including space checks")

    _update_migration_stages(migration_id=migration_id, state="IN_PROGRESS", details={"stages": stages})

    # Check/Validate the source and target servers for migration along with space checks
    response = run_ansible_playbook(
        playbook="books/validate_server_space.yaml",
        params={
            "target_host": target_server_details['server_id'],
            "required_space_in_gb": space_required,
            "vmail_dir": target_server_details['storage_path']
        }
    )
    if response['returncode'] != 0:
        logging.error(f"Failed to validate server space for migration_id {migration_id}: {response}")
        stages.append("Failed to validate server space, check logs for details")
        _update_migration_stages(migration_id=migration_id, state="FAILED", details={"stages": stages, "validate_server_space": response})
        return False
    else:
        logging.info(f"Successfully validated server space for migration_id {migration_id}: {response}")
        stages.append("Successfully validated the server space, proceeding with migration")
        _update_migration_stages(migration_id=migration_id, state="IN_PROGRESS", details={"stages": stages, "validate_server_space": response})
        return True


def block_emails_on_relay_servers(migration_id: str, email: str, stages: list) -> bool:
    """
    Block emails on the relay servers during migration.
    This function is called to block the emails on the relay servers before starting the migration.
    """
    stages.append("Blocking the emails on the relay servers")

    # Run the Ansible playbook to block the emails on the relay servers
    response = run_ansible_playbook(
        playbook="books/block_relay_mails.yaml",
        params={
            "target_host": "relay_servers",
            "block_email": email
        }
    )

    if response['returncode'] != 0:
        logging.error(f"Failed to block emails on the relay servers for email {email}: {response}")
        stages.append("Failed to block emails on the relay servers, check logs for details")
        _update_migration_stages(migration_id=migration_id, state="FAILED", details={"stages": stages, "block_response": response})
        return False
    else:
        logging.info(f"Successfully blocked emails on the relay servers for email {email}: {response}")
        stages.append("Successfully blocked the emails on the relay servers, proceeding with migration")
        return True


def migrate_email(migration_id: str, email: str, source_server_details: dict, target_server_details: dict, stages: list) -> bool:
    """
    Migrate the email from source server to target server.
    This function is called to perform the actual migration of the email.
    """
    stages.append("Starting the actual migration process on the source cloud server")

    # Run the Ansible playbook to migrate the email
    response = run_ansible_playbook(
        playbook="books/migrate_email.yaml",
        params={
            "target_host": source_server_details['server_id'],
            "email_path": f"{source_server_details['storage_path']}/{email}",
            "target_server_ip": target_server_details['host_name'],
            "email_user": email,
            "migration_id": migration_id
        }
    )

    if response['returncode'] != 0:
        logging.error(f"Failed to migrate email {email} from {source_server_details['host_name']} to {target_server_details['host_name']}: {response}")
        stages.append("Migration failed, check logs for details")
        _update_migration_stages(migration_id=migration_id, state="FAILED", details={"stages": stages, "migration_response": response})
        return False
    else:
        logging.info(f"Successfully migrated email {email} from {source_server_details['host_name']} to {target_server_details['host_name']}: {response}")
        stages.append("Successfully migrated the email, moving to next stage")
        return True


def background_migration_flow(migration_id: str, email: str, source_server_details: dict, target_server_details: dict, stages_: list) -> None:
    """
    Background flow for handling email migration.
    This function is intended to be run in a separate thread or process.
    Args:
        migration_id (str): Unique identifier for the migration.
        email (str): Email address to be migrated.
        source_server_details (dict): Details of the source email server.
        target_server_details (dict): Details of the target email server.
    """
    logging.info(f"Background migration flow started for migration_id: {migration_id}, email: {email}")
    stages = stages_.copy()  # Copy the stages to avoid modifying the original list
    stages.append("Starting the background migration flow now")
    stages.append("Freeing up the main thread to handle other tasks while migration is in progress")
    stages.append("Starting internal DB Connection to update the migration status")
    details = {"stages": stages}
    _update_migration_stages(migration_id=migration_id, state="IN_PROGRESS", details=details)

    # Validate the server space for migration
    if not validate_server_space(migration_id=migration_id, space_required=1, target_server_details=target_server_details, stages=stages):
        return

    # Block the emails on the relay servers before starting the migration
    if not block_emails_on_relay_servers(migration_id=migration_id, email=email, stages=stages):
        return

    # Run the Migration and other tasks on the source server itself
    if not migrate_email(migration_id=migration_id, email=email, source_server_details=source_server_details, target_server_details=target_server_details, stages=stages):
        return


def handle_start_migration(migration_id: str, email: str, source_server_id: str, target_server_id: str) -> None:
    """
    Handle the start migration message for email migration.
    This function initializes the migration process by validating the source and target servers,
    and updating the migration status to "INITIALIZING".
    Args:
        migration_id (str): Unique identifier for the migration.
        email (str): Email address to be migrated.
        source_server_id (str): ID of the source email server.
        target_server_id (str): ID of the target email server.
    """
    logging.info(f"Start migration handler called with migration_id: {migration_id}, email: {email}, source_server_id: {source_server_id}, target_server_id: {target_server_id}")
    stages = ["Starting Validation of email, source server, and target server including quota checks"]
    try:
        with psycopg2.connect(POSTGRES_DB_URI, connect_timeout=120) as conn:
            with conn.cursor() as cursor:
                # Start validation of the migration
                stages.append("Connected to the database successfully, now starting validation")
                set_email_migration_status(
                    cursor=cursor,
                    migration_id=migration_id,
                    status="INITIALIZING",
                    details={
                        "stages": stages
                    }
                )

                # Validate the migration
                is_valid, validation_details = handle_migration_validation(
                    cursor=cursor,
                    email=email,
                    source_server_id=source_server_id,
                    target_server_id=target_server_id
                )
                if not is_valid:
                    logging.error(f"Migration validation failed for email {email}: {validation_details}")
                    stages.append("Validation failed, more details are listed under 'error' key in this status")
                    set_email_migration_status(
                        cursor=cursor,
                        migration_id=migration_id,
                        status="FAILED",
                        details={"error": validation_details, "stages": stages}
                    )
                    return

                logging.info(f"Migration validation successful for email {email}")
                stages.append("Validation successful, proceeding with migration")
                set_email_migration_status(
                    cursor=cursor,
                    migration_id=migration_id,
                    status="IN_PROGRESS",
                    details={"stages": stages}
                )

                # Get server details for source and target servers
                stages.append("Fetching source and target server details for migration")
                source_server_details = get_server_details(cursor=cursor, server_id=source_server_id)
                target_server_details = get_server_details(cursor=cursor, server_id=target_server_id)
                if not source_server_details or not target_server_details:
                    logging.error(f"Source or target server details not found for migration_id {migration_id}")
                    stages.append("Source or target server details not found, migration cannot proceed")
                    set_email_migration_status(
                        cursor=cursor,
                        migration_id=migration_id,
                        status="FAILED",
                        details={"error": "Source or target server details not found", "stages": stages}
                    )
                    return

                # Run the background migration flow (spawn a new thread or process)
                Thread(
                    target=background_migration_flow,
                    args=(
                        migration_id,
                        email,
                        source_server_details,
                        target_server_details,
                        stages
                    ),
                    daemon=True
                ).start()

    except Exception as e:
        logging.error(f"Error handling start migration for email {email}: {e}", exc_info=True)


def handle_unblock_email(email: str) -> None:
    """
    Handle the unblock email message for relay servers
    """
    logging.info(f"Unblock email handler called for email: {email}")
    try:
        # Run the Ansible playbook to unblock the email on the relay servers
        response = run_ansible_playbook(
            playbook="books/unblock_relay_mails.yaml",
            params={
                "target_host": "relay_servers",
                "unblock_email": email
            }
        )
        if response['returncode'] != 0:
            logging.error(f"Failed to unblock email {email} on relay servers: {response}")
        else:
            logging.info(f"Successfully unblocked email {email} on relay servers: {response}")

    except Exception as e:
        logging.error(f"Error unblocking email {email}: {e}", exc_info=True)
