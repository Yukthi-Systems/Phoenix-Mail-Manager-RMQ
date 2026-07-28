"""
IMAP Sync Utility Functions
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


from .libraries import psycopg2, shlex, Thread, base64
from .constants import POSTGRES_DB_URI, logging
from .run_ansible import run_ansible_playbook


def _build_imapsync_command(
    host1: str,
    user1: str,
    password1: str,
    host2: str,
    user2: str,
    password2: str,
    port1: int = None,
    port2: int = None,
    folder: str = None,
    from_date: str = None,
    to_date: str = None
):
    """
    Build an imapsync command with the given parameters.
    :param host1: Source IMAP server host
    :param user1: Source IMAP username
    :param password1: Source IMAP password
    :param host2: Destination IMAP server host
    :param user2: Destination IMAP username
    :param password2: Destination IMAP password
    :param port1: Source IMAP server port (optional)
    :param port2: Destination IMAP server port (optional)
    :param folder: Specific folder to sync (optional)
    :param from_date: Start date for email sync in format 'DD-MMM-YYYY' (optional)
    :param to_date: End date for email sync in format 'DD-MMM-YYYY' (optional)
    :return: Constructed imapsync command as a string
    """
    cmd = ["imapsync"]

    # Host 1 details
    cmd.extend(["--host1", host1])
    cmd.extend(["--user1", user1])
    cmd.extend(["--password1", password1])

    if port1:
        cmd.extend(["--port1", str(port1)])

    if folder:
        cmd.extend(["--folder", folder])

    # Host 2 details
    cmd.extend(["--host2", host2])
    cmd.extend(["--user2", user2])
    cmd.extend(["--password2", password2])

    if port2:
        cmd.extend(["--port2", str(port2)])

    if folder:
        cmd.extend(["--folder", folder])

    # Additional Global Options
    if from_date and to_date:
        search = f"SENTSINCE {from_date} SENTBEFORE {to_date}"
        cmd.extend(["--search", search])

    cmd.extend(["--syncinternaldates"])
    cmd.extend(["--useheader", "Message-Id"])
    cmd.extend(["--delete2duplicates"])
    cmd.extend(["--automap"])

    return " ".join(shlex.quote(part) for part in cmd)


def set_imap_sync_job_status(imap_sync_job_id: str, job_status: str) -> None:
    """
    Set the IMAP sync job status in the database
    """
    query = """
    UPDATE imap_sync_jobs
    SET sync_status = %s, updated_at = CURRENT_TIMESTAMP
    WHERE job_id = %s
    """
    try:
        with psycopg2.connect(POSTGRES_DB_URI, connect_timeout=30) as conn:
            with conn.cursor() as cursor:        
                cursor.execute(query, (job_status, imap_sync_job_id))
                if cursor.rowcount == 0:
                    logging.warning(f"No IMAP sync job found with ID {imap_sync_job_id} to update status.")
                    return
                
                # Commit the transaction
                conn.commit()

        logging.info(f"IMAP sync job {imap_sync_job_id} status updated to {job_status}.")

    except Exception as e:
        logging.error(f"Error updating IMAP sync job status for {imap_sync_job_id}: {e}", exc_info=True)


def background_process_imap_sync(imap_sync_job_id: str, command_str: str) -> None:
    """
    Background process to handle IMAP sync.
    :param imap_sync_job_id: The IMAP sync job identifier
    :param imap_sync_params: Dictionary of parameters for IMAP sync
    :return: None
    """
    try:
        # Run the Ansible playbook and wait for it to complete
        response = run_ansible_playbook(
            playbook="books/imap_sync.yaml",
            params={
                "run_imap_sync_cmd": base64.b64encode(command_str.encode("utf-8")).decode("ascii"),
                "job_id": imap_sync_job_id
            }
        )
        logging.debug(f"Ansible playbook response for IMAP sync job {imap_sync_job_id}: {response}")

        if response["returncode"] == 0:
            logging.info(f"IMAP sync job {imap_sync_job_id} completed successfully.")
            set_imap_sync_job_status(imap_sync_job_id, "COMPLETED")
        else:
            logging.error(f"IMAP sync job {imap_sync_job_id} failed with return code {response['returncode']}.")
            set_imap_sync_job_status(imap_sync_job_id, "FAILED")

    except Exception as e:
        logging.error(f"Error in background IMAP sync for job {imap_sync_job_id}: {e}", exc_info=True)
        set_imap_sync_job_status(imap_sync_job_id, "FAILED")


def handle_imap_sync(imap_sync_job_id: str, imap_sync_params: dict) -> None:
    """
    Handle IMAP sync for the given job ID.
    :param imap_sync_job_id: The IMAP sync job identifier
    :return: None
    """
    logging.info(f"Start IMAP sync handler called for job ID: {imap_sync_job_id}")
    try:
        command_str = _build_imapsync_command(**imap_sync_params)
        logging.info(f"For IMAP sync job {imap_sync_job_id}, constructed command: {command_str}")

        # Mark the IMAP sync job as started in the database
        set_imap_sync_job_status(imap_sync_job_id, "IN_PROGRESS")
        logging.info(f"IMAP sync job {imap_sync_job_id} marked as IN_PROGRESS in database.")

        # Start the background thread to process IMAP sync
        Thread(
            target=background_process_imap_sync,
            args=(
                imap_sync_job_id,
                command_str
            ),
            daemon=True
        ).start()
        logging.info(f"Background thread started for IMAP sync job {imap_sync_job_id}.")

    except Exception as e:
        logging.error(f"Error handling IMAP sync for job {imap_sync_job_id}: {e}", exc_info=True)
