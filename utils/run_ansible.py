"""
Run Ansible playbooks
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


from .libraries import subprocess, shlex
from .constants import ANSIBLE_PLAYBOOKS_PATH, logging


def run_ansible_playbook(playbook: str, params: dict[str, str]) -> dict:
    """
    Run the Ansible playbook and capture the full output as a string.
    Returns a dictionary with the following keys:
    stdout: The standard output of the playbook execution.
    stderr: The standard error output of the playbook execution.
    returncode: The return code of the playbook execution.
    """
    extra_vars = ' '.join([f'{k}={v}' for k, v in params.items()])
    command = f'ansible-playbook {playbook}'

    if extra_vars:
        command += f' -e "{extra_vars}"'

    logging.info(f"Running Ansible playbook: {command}")

    result = subprocess.run(
        shlex.split(command),
        cwd=ANSIBLE_PLAYBOOKS_PATH,
        capture_output=True,
        text=True
    )

    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode
    }
