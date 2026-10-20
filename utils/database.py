"""
All Database related utilities are defined here
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


from .libraries import requests, base64, psycopg2, pd, json
from .constants import QUEST_DB_HOST, QUEST_DB_PORT, QUEST_DB_USER, QUEST_DB_PASSWORD, logging, HEALTH_SCORE_WEIGHTS


def _exec_quest_db_query(query: str, offset: int = 0, page_size: int = 10) -> list[dict]:
    """
    Execute a query against the quest database and return the response
    """
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f"Basic {base64.b64encode(f'{QUEST_DB_USER}:{QUEST_DB_PASSWORD}'.encode()).decode()}"
    }
    params = {
        'count': 'false',
        'src': 'con',
        'query': query,
        'timings': 'false',
        'version': '2',
        'limit': f'{offset},{page_size}',
        'explain': 'false'
    }

    try:
        resp = requests.get(
            f"http://{QUEST_DB_HOST}:{QUEST_DB_PORT}/exec",
            params=params,
            headers=headers
        )
        data = resp.json()
        if 'error' in data:
            logging.error(f"Error executing query: {data['error']}")
            return []

        columns = [col['name'] for col in data['columns']]
        return [dict(zip(columns, row)) for row in data['dataset']]

    except Exception as e:
        logging.error(f"Error executing query via REST: {e}")
        return []


def check_email_domain_locked(cursor: psycopg2.extensions.cursor, email: str) -> list[str]:
    """
    Check if the email domain is locked and return the list of servers if it is locked
    """
    domain = email.split('@')[-1]
    query = """
    SELECT locked_servers_group
    FROM domains
    WHERE domain_name = %s
    """
    try:
        cursor.execute(query, (domain,))
        result = cursor.fetchone()
        if not result or not result[0]:
            return []

        locked_servers_group = result[0]
        if isinstance(locked_servers_group, str):
            locked_servers_group = locked_servers_group.replace('{', '').replace('}', '').split(',')

        # Convert the locked servers group to a list of strings
        return [str(server) for server in locked_servers_group]

    except Exception as e:
        logging.error(f"Error checking locked domain: {e}")
        return []


def get_all_active_servers(cursor: psycopg2.extensions.cursor) -> dict:
    """
    Get all servers from the database
    Where:
    - is_active = TRUE
    - is_accepting_new_mailboxes = TRUE
    - is_mailbox_server = TRUE
    Returns a dictionary of server_id to their quota information
    """
    query = "SELECT server_id, quota_allocated, quota_utilized, is_on_prem FROM servers WHERE is_active = TRUE AND is_accepting_new_mailboxes = TRUE AND is_mailbox_server = TRUE"
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        return {
            str(row[0]): {
                'quota_allocated': float(row[1]),
                'quota_utilized': float(row[2]),
                'is_on_prem': bool(row[3])
            } for row in rows
        }

    except Exception as e:
        logging.error(f"Error fetching active servers: {e}", exc_info=True)
        return {}


def get_required_email_quota(cursor: psycopg2.extensions.cursor, email_id: str) -> float:
    """
    Get the required email quota based on the email ID
    """
    query = "SELECT quota_allocated FROM mailboxes WHERE email = %s"
    try:
        cursor.execute(query, (email_id,))
        result = cursor.fetchone()
        if result and result[0] is not None:
            return float(result[0])
        return 10.0 # Default quota if not found

    except Exception as e:
        logging.error(f"Error fetching required email quota for {email_id}: {e}", exc_info=True)
        return 10.0 # Default quota if error occurs


def set_email_server_and_activate(cursor: psycopg2.extensions.cursor, email: str, server_id: str) -> None:
    """
    Set the email server and activate it in the database
    """
    query = """
    UPDATE mailboxes
    SET server_id = %s, is_enabled = TRUE
    WHERE email = %s
    """
    try:
        cursor.execute(query, (server_id, email))
        logging.info(f"Email {email} assigned to server {server_id}")

    except Exception as e:
        logging.error(f"Error setting email server for {email}: {e}", exc_info=True)


def get_server_load_stats_from_q_db(server_ids: list[str]) -> pd.DataFrame:
    """
    Get server load statistics from the quest database
    """
    if not server_ids:
        return pd.DataFrame()

    query = """
    SELECT
        server_id,
        CAST(
            (CAST(timestamp AS LONG) / (5 * 60 * 1000000)) * (5 * 60 * 1000000)
            AS TIMESTAMP
        ) AS interval_start,

        AVG(cpu_percent) AS avg_cpu_percent,
        AVG(load_avg_1) AS avg_load_avg_1,
        AVG(load_avg_5) AS avg_load_avg_5,
        AVG(load_avg_15) AS avg_load_avg_15,

        AVG(mem_percent) AS avg_mem_percent,

        AVG(disk_percent) AS avg_disk_percent,
        AVG(disk_read_MBps) AS avg_disk_read_MBps,
        AVG(disk_write_MBps) AS avg_disk_write_MBps,

        AVG(net_sent_MBps) AS avg_net_sent_MBps,
        AVG(net_recv_MBps) AS avg_net_recv_MBps

    FROM server_metrics
    WHERE
        timestamp > dateadd('d', -7, systimestamp())
        AND server_id IN ({})
    GROUP BY
        server_id,
        CAST(
            (CAST(timestamp AS LONG) / (5 * 60 * 1000000)) * (5 * 60 * 1000000)
            AS TIMESTAMP
        )
    ORDER BY
        server_id,
        interval_start;
    """.format(','.join(f"'{server_id}'" for server_id in server_ids))

    try:
        # Fetch data from the quest database
        total_possible_rows_per_server_per_day = 288  # 5 minutes intervals in a day
        data = _exec_quest_db_query(
            offset=0,
            query=query,
            page_size=int(total_possible_rows_per_server_per_day * len(server_ids) * 7)  # 7 days of data
        )

        if not data:
            return pd.DataFrame()

        # Convert to DataFrame and return
        return pd.DataFrame(data)

    except Exception as e:
        logging.error(f"Error fetching server load stats: {e}", exc_info=True)
        return pd.DataFrame()


def _calculate_individual_health_score(row: pd.Series) -> float:
    """
    Calculate the health score for a server based on its metrics.
    The health score is a weighted average of various metrics, normalized to a 0-1 scale.
    The weights are defined in the HEALTH_SCORE_WEIGHTS constant.
    The score is calculated as follows:
    - CPU usage is inverted (1 - normalized value) to give higher scores for lower usage
    - Load averages are inverted similarly
    - Memory, disk, and network usage are also inverted
    - Disk I/O is calculated as the average of read and write speeds, inverted
    - The final score is a weighted sum of all these normalized values, multiplied by 100
    """
    def normalize(value, min_value, max_value):
        """Clamp and normalize to 0-1"""
        return max(0, min(1, (value - min_value) / (max_value - min_value)))

    cpu = 1 - normalize(row['avg_cpu_percent'], 0, 70)
    load_1 = 1 - normalize(row['avg_load_avg_1'], 0, 10)
    load_5 = 1 - normalize(row['avg_load_avg_5'], 0, 10)
    load_15 = 1 - normalize(row['avg_load_avg_15'], 0, 10)
    mem = 1 - normalize(row['avg_mem_percent'], 0, 100)
    disk = 1 - normalize(row['avg_disk_percent'], 0, 100)

    disk_read = 1 - normalize(row['avg_disk_read_MBps'], 0, 50)
    disk_write = 1 - normalize(row['avg_disk_write_MBps'], 0, 50)
    io = (disk_read + disk_write) / 2

    net_sent = 1 - normalize(row['avg_net_sent_MBps'], 0, 50)
    net_recv = 1 - normalize(row['avg_net_recv_MBps'], 0, 50)
    net = (net_sent + net_recv) / 2

    # Calculate the weighted health score
    return (
        HEALTH_SCORE_WEIGHTS['cpu'] * cpu +
        HEALTH_SCORE_WEIGHTS['load_1'] * load_1 +
        HEALTH_SCORE_WEIGHTS['load_5'] * load_5 +
        HEALTH_SCORE_WEIGHTS['load_15'] * load_15 +
        HEALTH_SCORE_WEIGHTS['mem'] * mem +
        HEALTH_SCORE_WEIGHTS['disk'] * disk +
        HEALTH_SCORE_WEIGHTS['io'] * io +
        HEALTH_SCORE_WEIGHTS['net'] * net
    ) * 100


def calculate_health_stats(email_id: str, df: pd.DataFrame) -> dict:
    """
    Calculate health statistics for a DataFrame of server metrics.
    Returns a dictionary with the final health score as value and the server ID as key.
    """
    df['health_score'] = df.apply(_calculate_individual_health_score, axis=1)
    if df.empty:
        return {}

    health_scores = {}
    for server_id, group in df.groupby('server_id'):
        mean_score = group['health_score'].mean()
        percentile_10 = group['health_score'].quantile(0.1)
        final_health_score = 0.7 * mean_score + 0.3 * percentile_10
        health_scores[server_id] = round(float(final_health_score), 3)

    logging.info(f"For Email: {email_id} - Calculated health scores: {health_scores}")
    return health_scores


def update_server_quota(cursor: psycopg2.extensions.cursor, server_id: str, add_utilized_quota: float) -> None:
    """
    Update the utilized quota for a server in the database.
    :param cursor: Database cursor
    :param server_id: ID of the server to update
    :param add_utilized_quota: Amount of quota to add to the utilized quota
    """
    query = """
    UPDATE servers
    SET quota_utilized = quota_utilized + %s
    WHERE server_id = %s
    """
    try:
        cursor.execute(query, (add_utilized_quota, server_id))
        logging.info(f"Updated utilized quota for server {server_id} by {add_utilized_quota}")

    except Exception as e:
        logging.error(f"Error updating server quota for {server_id}: {e}", exc_info=True)


def _check_is_email_migrating(cursor: psycopg2.extensions.cursor, email: str) -> bool:
    """
    Check if the email is currently being migrated or in the process of migration.
    Returns True if the email is migrating, False otherwise.
    """
    query = """
    SELECT COUNT(*) FROM mailbox_migrations
    WHERE email = %s AND migration_status = 'IN_PROGRESS'
    """
    try:
        cursor.execute(query, (email,))
        count = cursor.fetchone()[0]
        return count > 0

    except Exception as e:
        logging.error(f"Error checking if email {email} is migrating: {e}", exc_info=True)
        return False


def _check_if_email_exists_and_mapped_server(cursor: psycopg2.extensions.cursor, email: str, server_id: str) -> bool:
    """
    Check if the email exists in the database and is mapped to the specified server.
    Returns True if the email exists and is mapped, False otherwise.
    """
    query = """
    SELECT COUNT(*) FROM mailboxes
    WHERE email = %s AND server_id = %s AND is_enabled = TRUE AND is_locked = FALSE
    """
    try:
        cursor.execute(query, (email, server_id))
        count = cursor.fetchone()[0]
        return count > 0

    except Exception as e:
        logging.error(f"Error checking if email {email} exists on server {server_id}: {e}", exc_info=True)
        return False


def _check_target_server_quota(cursor: psycopg2.extensions.cursor, target_server_id: str, required_quota: float) -> bool:
    """
    Check if the target server has enough quota to handle the migration.
    Returns True if the target server has enough quota, False otherwise.
    """
    query = """
    SELECT quota_allocated, quota_utilized FROM servers
    WHERE server_id = %s AND is_active = TRUE
    """
    try:
        cursor.execute(query, (target_server_id,))
        result = cursor.fetchone()
        if not result:
            return False

        quota_allocated, quota_utilized = result
        return (quota_allocated - quota_utilized) > required_quota  # Only greater than (not equal to) check

    except Exception as e:
        logging.error(f"Error checking target server {target_server_id} quota: {e}", exc_info=True)
        return False


def _check_target_server_status(cursor: psycopg2.extensions.cursor, target_server_id: str) -> bool:
    """
    Check if the target server is active and accepting new mailboxes.
    Returns True if the target server is active and accepting, False otherwise.
    """
    query = """
    SELECT is_active, is_accepting_new_mailboxes, is_mailbox_server FROM servers
    WHERE server_id = %s
    """
    try:
        cursor.execute(query, (target_server_id,))
        result = cursor.fetchone()
        if not result:
            return False

        is_active, is_accepting_new_mailboxes, is_mailbox_server = result
        return is_active and is_accepting_new_mailboxes and is_mailbox_server

    except Exception as e:
        logging.error(f"Error checking target server {target_server_id} status: {e}", exc_info=True)
        return False


def handle_migration_validation(
    cursor: psycopg2.extensions.cursor,
    email: str,
    source_server_id: str,
    target_server_id: str
) -> tuple[bool, dict]:
    """
    Validate the migration parameters before proceeding
    Returns a tuple (is_valid: bool, info: dict)
    """
    # Both source and target server IDs must be provided
    if not source_server_id or not target_server_id:
        return False, {
            'message': "Source and target server IDs must be provided.",
            'possible_cause': 'Either source or target server ID is missing.'
        }

    # Check if the source and target server IDs are the same
    if source_server_id == target_server_id:
        return False, {
            'message': "Source and target server IDs cannot be the same.",
            'possible_cause': 'Source and target server IDs are the same.'
        }

    # Check if the email is already being migrated or in the process of migration ('INITIALIZING', 'IN_PROGRESS' statuses, if so fail the migration)
    if _check_is_email_migrating(cursor=cursor, email=email):
        return False, {
            'message': f"Email {email} is already in the process of migration.",
            'possible_status': ['IN_PROGRESS']
        }

    # Check if the source server exists and the email is hosted on that server
    if not _check_if_email_exists_and_mapped_server(cursor=cursor, email=email, server_id=source_server_id):
        return False, {
            'message': f"Email {email} does not exist on the source server {source_server_id}. Or the mailbox is disabled or locked.",
            'possible_cause': 'Email does not exist or is disabled/locked or not mapped to the source server.'
        }

    # Check if the target server exists and is active
    required_quota = get_required_email_quota(cursor=cursor, email_id=email)
    if not _check_target_server_quota(cursor=cursor, target_server_id=target_server_id, required_quota=required_quota):
        return False, {
            'message': f"Target server {target_server_id} does not have enough quota to handle the migration.",
            'possible_cause': 'Target server does not have enough quota.'
        }
    
    # Check if the target server is active and accepting new mailboxes
    if not _check_target_server_status(cursor=cursor, target_server_id=target_server_id):
        return False, {
            'message': f"Target server {target_server_id} is not active or not accepting new mailboxes or is not a mailbox server.",
            'possible_cause': 'Target server is either inactive or not accepting new mailboxes or is not a mailbox server.'
        }

    # Check if the email domain is locked and if so, check if the target server is in the locked servers group
    locked_servers = check_email_domain_locked(cursor=cursor, email=email)
    if locked_servers and target_server_id not in locked_servers:
        return False, {
            'message': f"Email domain is locked and target server {target_server_id} is not in the locked servers group.",
            'possible_cause': 'Email domain is locked and target server is not allowed.'
        }

    # If all checks pass, return validation success
    return True, {
        'message': "Migration parameters are valid. Now starting the migration."
    }


def set_email_migration_status(
    cursor: psycopg2.extensions.cursor,
    migration_id: str,
    status: str,
    details: dict
) -> None:
    """
    Set the migration status in the database
    Possible Statuses:
        - INITIALIZING: Migration is being prepared
        - IN_PROGRESS: Migration is currently happening
        - COMPLETED: Migration has successfully completed
        - FAILED: Migration has failed
    """
    query = """
    UPDATE mailbox_migrations
    SET migration_status = %s, migration_details = %s, end_time = CURRENT_TIMESTAMP
    WHERE migration_id = %s
    """
    try:
        cursor.execute(query, (status, json.dumps(details), migration_id))
        if cursor.rowcount == 0:
            logging.warning(f"No migration found with ID {migration_id} to update status.")
            return

        logging.info(f"Migration {migration_id} status updated to {status}")

    except Exception as e:
        logging.error(f"Error updating migration status for {migration_id}: {e}", exc_info=True)


def get_server_details(cursor: psycopg2.extensions.cursor, server_id: str) -> dict:
    """
    Get the details of a server from the database
    """
    query = "SELECT * FROM servers WHERE server_id = %s"
    try:
        cursor.execute(query, (server_id,))
        row = cursor.fetchone()
        if not row:
            return {}

        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))

    except Exception as e:
        logging.error(f"Error fetching server details for {server_id}: {e}", exc_info=True)
        return {}


def get_server_details_by_id(cursor: psycopg2.extensions.cursor, server_id: str) -> dict:
    """
    Get the server details for a given email
    """
    query = "SELECT * FROM servers WHERE server_id = %s"
    try:
        cursor.execute(query, (server_id,))
        row = cursor.fetchone()
        if not row:
            return {}

        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))
    
    except Exception as e:
        logging.error(f"Error fetching server details for server ID {server_id}: {e}", exc_info=True)
        return {}
