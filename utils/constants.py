"""
All constants and configurations are defined here.
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


import os
import logging
from datetime import datetime


# RabbitMQ connection details
RABBIT_SERVER_IP = os.getenv("RABBIT_SERVER_IP", "0.0.0.0")
RABBIT_SERVER_PORT = int(os.getenv("RABBIT_SERVER_PORT", 1234))
RABBIT_USER = os.getenv("RABBIT_USER", "user")
RABBIT_PASSWORD = os.getenv("RABBIT_PASSWORD", "password")
RABBIT_QUEUE_NAME = os.getenv("RABBIT_QUEUE_NAME", "archive")
RABBIT_VHOST = os.getenv("RABBIT_VHOST", "yukthi")

# PostgreSQL connection details
POSTGRES_DB_USERNAME = os.environ.get("POSTGRES_DB_USERNAME", "user")
POSTGRES_DB_PASSWORD = os.environ.get("POSTGRES_DB_PASSWORD", "password")
POSTGRES_DB_HOST = os.environ.get("POSTGRES_DB_HOST", "0.0.0.0")
POSTGRES_DB_PORT = int(os.environ.get("POSTGRES_DB_PORT", "5432"))
POSTGRES_DB_DATABASE = os.environ.get("POSTGRES_DB_DATABASE", "yukthi")
POSTGRES_POOL_SIZE = int(os.environ.get("POSTGRES_POOL_SIZE", 10))
POSTGRES_DB_URI = os.environ.get("POSTGRES_DB_URI", f"postgresql://{POSTGRES_DB_USERNAME}:{POSTGRES_DB_PASSWORD}@{POSTGRES_DB_HOST}:{POSTGRES_DB_PORT}/{POSTGRES_DB_DATABASE}")

# QuestDB Constants
QUEST_DB_HOST = os.environ.get("QUEST_DB_HOST", "0.0.0.0")
QUEST_DB_PORT = int(os.environ.get("QUEST_DB_PORT", "1234"))
QUEST_DB_USER = os.environ.get("QUEST_DB_USER", "user")
QUEST_DB_PASSWORD = os.environ.get("QUEST_DB_PASSWORD", "password")

# DKIM API Configuration
DKIM_API_URL = os.getenv("DKIM_API_URL", "http://0.0.0.0:1234")
DKIM_API_KEY = os.getenv("DKIM_API_AUTH_TOKEN", "Put-Token-Here")

# Health score weights
HEALTH_SCORE_WEIGHTS = {
    "cpu": 0.06,
    "load_1": 0.08,
    "load_5": 0.11,
    "load_15": 0.12,
    "mem": 0.11,
    "disk": 0.11,
    "io": 0.24,
    "net": 0.17
}

# Ansible playbooks path
ANSIBLE_PLAYBOOKS_PATH = '/ansible'

# Logging configuration
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(module)s - %(message)s", datefmt="%d-%b-%y %H:%M:%S", level=logging.DEBUG, filename=f"/var/log/rmq_worker/{datetime.now().strftime("%d-%m-%Y")}.log")
# logging.basicConfig(format="%(asctime)s - %(levelname)s - %(module)s - %(message)s", datefmt="%d-%b-%y %H:%M:%S", level=logging.DEBUG, filename=f"logs/{datetime.now().strftime("%d-%m-%Y")}.log")
logging.getLogger("pika.adapters.base_connection").setLevel(logging.CRITICAL)
logging.getLogger("json").setLevel(logging.CRITICAL)
logging.getLogger("requests").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)
logging.getLogger("urllib3.connection").setLevel(logging.ERROR)
logging.getLogger("pyamqp").setLevel(logging.ERROR)
logging.getLogger("pika").setLevel(logging.ERROR)
logging.getLogger().addHandler(logging.StreamHandler())
logging = logging.getLogger(__name__)
