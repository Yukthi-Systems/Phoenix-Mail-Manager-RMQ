"""
Main script for consuming messages from RabbitMQ in a single message mode
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


from utils.constants import (
    RABBIT_SERVER_PORT,
    RABBIT_QUEUE_NAME,
    RABBIT_SERVER_IP,
    RABBIT_PASSWORD,
    RABBIT_VHOST,
    RABBIT_USER,
    logging
)
from utils.libraries import pika, signal
from utils.new_email import handle_new_email
from utils.imap_sync import handle_imap_sync
from utils.handlers import differentiate_message
from utils.delete_mailbox import handle_delete_email
from utils.start_migration import handle_start_migration, handle_unblock_email
from utils.process_domain import handle_create_new_domain, handle_delete_domain


def process_message(message: dict) -> None:
    """Process a single message."""
    message_type, messsage = differentiate_message(message=message)
    if not messsage:
        logging.error(f"Message processing failed for type: {message_type}. Message is: {message}")
        return

    # Check the type of message and call the appropriate function
    match message_type:
        case "new_email":
            handle_new_email(email=messsage["email"])

        case "start_migration":
            handle_start_migration(
                email=messsage["email"],
                migration_id=messsage["migration_id"],
                source_server_id=messsage["source_server_id"],
                target_server_id=messsage["target_server_id"]
            )

        case "delete_email":
            handle_delete_email(email_prefix=messsage["email_prefix"], domain_name=messsage["domain_name"], server_id=messsage["server_id"])

        case "quota_update":
            logging.warning(f"Quota update message received but not implemented: {messsage}")

        case "new_domain":
            handle_create_new_domain(domain=messsage["domain"])

        case "delete_domain":
            # TODO: Fetch all emails under the domain and delete them first
            handle_delete_domain(domain=messsage["domain"])

        case "relay_unblock_email":
            handle_unblock_email(email=messsage["email"])

        case "imap_sync":
            handle_imap_sync(imap_sync_job_id=messsage["job_id"], imap_sync_params=messsage["params"])

        case _:
            logging.error(f"Unhandled message type: {message_type}. Message: {messsage}")


def callback(ch, method, properties, body: bytes):
    """Callback function to handle incoming messages one at a time."""
    message = {"body": body, "headers": properties.headers}
    try:
        process_message(message)

    except Exception as e:
        logging.error(f"Error processing message: {e}. Message is: {message}. It will not be requeued.", exc_info=True)

    finally:
        # Acknowledge the message after processing
        ch.basic_ack(delivery_tag=method.delivery_tag)


def consume_messages():
    """Consume messages from RabbitMQ one at a time."""
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=RABBIT_SERVER_IP,
            port=RABBIT_SERVER_PORT,
            virtual_host=RABBIT_VHOST,
            credentials=pika.PlainCredentials(RABBIT_USER, RABBIT_PASSWORD)
        )
    )
    channel = connection.channel()
    channel.queue_declare(queue=RABBIT_QUEUE_NAME, durable=True, arguments={"x-queue-type": "quorum"})
    channel.basic_qos(prefetch_count=1)  # Only 1 message at a time
    channel.basic_consume(
        queue=RABBIT_QUEUE_NAME,
        on_message_callback=lambda ch, method, properties, body: callback(ch, method, properties, body),
        auto_ack=False  # Explicit ack only on success
    )

    logging.info("Starting to consume messages from the RabbitMQ server (single message mode)")
    channel.start_consuming()


def signal_handler(sig, frame):
    """Signal handler to close any pending connections gracefully."""
    logging.info("Received signal to stop the process, shutting down gracefully.")
    # No need to close the connection anywhere
    exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    consume_messages()
