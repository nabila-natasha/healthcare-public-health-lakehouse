import json
import os
import sys
from datetime import datetime, timezone

from confluent_kafka import Consumer
from azure.storage.filedatalake import DataLakeServiceClient


# ============================================================
# CONFIGURATION
# ============================================================

EVENT_HUB_NAME = "healthcare-events"

EVENT_HUB_BOOTSTRAP_SERVER = (
    "eh-lakehouse-bello.servicebus.windows.net:9093"
)

STORAGE_ACCOUNT = "stlakehousebello"
FILESYSTEM = "healthcare"

RAW_PREFIX = "raw/cdc"
BRONZE_PREFIX = "bronze/cdc"
QUARANTINE_PREFIX = "quarantine/cdc"

REQUIRED_FIELDS = [
    "event_id",
    "event_time",
    "ingestion_time",
    "source",
    "patient_id",
    "event_type",
    "region",
    "status",
]


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_required_env(name):
    """Read a required environment variable."""

    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            f"Required environment variable is missing: {name}"
        )

    return value


def utc_now():
    """Return the current UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


def validate_event(event):
    """
    Validate that a CDC event contains all required fields.
    """

    missing_fields = [
        field
        for field in REQUIRED_FIELDS
        if field not in event
    ]

    if missing_fields:
        return False, (
            "Missing required fields: "
            + ", ".join(missing_fields)
        )

    if not event["event_id"]:
        return False, "event_id is empty"

    if not event["event_time"]:
        return False, "event_time is empty"

    return True, ""


def upload_json(file_system_client, path, payload):
    """
    Write a JSON object to ADLS Gen2.
    """

    file_client = file_system_client.get_file_client(path)

    content = json.dumps(
        payload,
        indent=2
    )

    file_client.upload_data(
        content,
        overwrite=True
    )


# ============================================================
# MAIN CONSUMER
# ============================================================

def main():

    # --------------------------------------------------------
    # 1. Read secrets from environment variables
    # --------------------------------------------------------

    event_hub_connection_string = get_required_env(
        "EVENT_HUB_CONNECTION_STRING"
    )

    storage_connection_string = get_required_env(
        "AZURE_STORAGE_CONNECTION_STRING"
    )


    # --------------------------------------------------------
    # 2. Configure Kafka-compatible Event Hubs consumer
    # --------------------------------------------------------

    consumer_config = {
        "bootstrap.servers": EVENT_HUB_BOOTSTRAP_SERVER,

        "security.protocol": "SASL_SSL",

        "sasl.mechanisms": "PLAIN",

        "sasl.username": "$ConnectionString",

        "sasl.password": event_hub_connection_string,

        "group.id": "healthcare-bronze-consumer-v1",

        "auto.offset.reset": "earliest",

        "enable.auto.commit": False,
    }


    # --------------------------------------------------------
    # 3. Create Event Hubs consumer
    # --------------------------------------------------------

    consumer = Consumer(consumer_config)


    # --------------------------------------------------------
    # 4. Connect to ADLS Gen2
    # --------------------------------------------------------

    service_client = (
        DataLakeServiceClient.from_connection_string(
            storage_connection_string
        )
    )

    file_system_client = (
        service_client.get_file_system_client(
            FILESYSTEM
        )
    )


    # --------------------------------------------------------
    # 5. Subscribe to Event Hubs
    # --------------------------------------------------------

    consumer.subscribe([EVENT_HUB_NAME])


    # --------------------------------------------------------
    # 6. Create counters and duplicate tracking
    # --------------------------------------------------------

    processed_event_ids = set()

    raw_count = 0
    accepted_count = 0
    duplicate_count = 0
    quarantine_count = 0


    print()
    print("================================================")
    print("HEALTHCARE CDC EVENT CONSUMER")
    print("================================================")
    print(
        f"Event Hub : {EVENT_HUB_NAME}"
    )
    print(
        f"Filesystem: {FILESYSTEM}"
    )
    print("Consumer group: healthcare-bronze-consumer-v1")
    print("================================================")
    print()


    try:

        # ----------------------------------------------------
        # 7. Continuously poll Event Hubs
        # ----------------------------------------------------

        while True:

            message = consumer.poll(5.0)


            # ------------------------------------------------
            # No new messages
            # ------------------------------------------------

            if message is None:

                print("No new messages. Consumer stopping.")

                break


            # ------------------------------------------------
            # Event Hubs / Kafka error
            # ------------------------------------------------

            if message.error():

                print(
                    f"Consumer error: {message.error()}"
                )

                continue


            # ------------------------------------------------
            # 8. Read the message payload
            # ------------------------------------------------

            raw_payload = message.value()


            # ------------------------------------------------
            # 9. Parse JSON
            # ------------------------------------------------

            try:

                event = json.loads(
                    raw_payload.decode("utf-8")
                )

            except json.JSONDecodeError:

                quarantine = {
                    "received_at": utc_now(),
                    "partition": message.partition(),
                    "offset": message.offset(),
                    "reason": "Invalid JSON",
                    "raw_payload": raw_payload.decode(
                        "utf-8",
                        errors="replace"
                    ),
                }

                quarantine_path = (
                    f"{QUARANTINE_PREFIX}/"
                    f"partition={message.partition()}/"
                    f"offset={message.offset()}.json"
                )

                upload_json(
                    file_system_client,
                    quarantine_path,
                    quarantine
                )

                quarantine_count += 1

                consumer.commit(
                    message=message,
                    asynchronous=False
                )

                continue


            # ------------------------------------------------
            # 10. Write the received event to RAW
            # ------------------------------------------------

            raw_count += 1

            ingestion_date = datetime.now(
                timezone.utc
            ).strftime("%Y-%m-%d")


            raw_path = (
                f"{RAW_PREFIX}/"
                f"ingestion_date={ingestion_date}/"
                f"partition={message.partition()}/"
                f"offset={message.offset()}.json"
            )


            raw_record = {
                "event": event,

                "event_hub_partition": (
                    message.partition()
                ),

                "event_hub_offset": (
                    message.offset()
                ),

                "received_at": utc_now(),
            }


            upload_json(
                file_system_client,
                raw_path,
                raw_record
            )


            print(
                f"RAW WRITTEN: {event.get('event_id')}"
            )


            # ------------------------------------------------
            # 11. Validate the event
            # ------------------------------------------------

            is_valid, reason = validate_event(event)


            if not is_valid:

                quarantine = {
                    "event": event,

                    "received_at": utc_now(),

                    "partition": message.partition(),

                    "offset": message.offset(),

                    "reason": reason,
                }


                quarantine_path = (
                    f"{QUARANTINE_PREFIX}/"
                    f"ingestion_date={ingestion_date}/"
                    f"{event.get('event_id', 'unknown')}_"
                    f"{message.partition()}_"
                    f"{message.offset()}.json"
                )


                upload_json(
                    file_system_client,
                    quarantine_path,
                    quarantine
                )


                quarantine_count += 1


                print(
                    f"QUARANTINED: "
                    f"{event.get('event_id', 'unknown')} "
                    f"| reason={reason}"
                )


                consumer.commit(
                    message=message,
                    asynchronous=False
                )

                continue


            # ------------------------------------------------
            # 12. Detect duplicate event IDs
            # ------------------------------------------------

            event_id = event["event_id"]


            if event_id in processed_event_ids:

                duplicate_count += 1

                print(
                    f"DUPLICATE SKIPPED: {event_id}"
                )


                consumer.commit(
                    message=message,
                    asynchronous=False
                )

                continue


            # ------------------------------------------------
            # 13. Remember this event ID
            # ------------------------------------------------

            processed_event_ids.add(event_id)


            # ------------------------------------------------
            # 14. Add Bronze processing timestamp
            # ------------------------------------------------

            event["processed_time"] = utc_now()


            # ------------------------------------------------
            # 15. Write valid unique event to BRONZE
            # ------------------------------------------------

            bronze_path = (
                f"{BRONZE_PREFIX}/"
                f"ingestion_date={ingestion_date}/"
                f"{event_id}.json"
            )


            upload_json(
                file_system_client,
                bronze_path,
                event
            )


            accepted_count += 1


            print(
                f"BRONZE ACCEPTED: {event_id}"
            )


            # ------------------------------------------------
            # 16. Commit the Event Hubs offset
            # ------------------------------------------------

            consumer.commit(
                message=message,
                asynchronous=False
            )


    finally:

        # ----------------------------------------------------
        # 17. Close the consumer
        # ----------------------------------------------------

        consumer.close()


        # ----------------------------------------------------
        # 18. Print final summary
        # ----------------------------------------------------

        print()
        print("================================================")
        print("CONSUMER SUMMARY")
        print("================================================")
        print(
            f"RAW messages       : {raw_count}"
        )
        print(
            f"Bronze accepted    : {accepted_count}"
        )
        print(
            f"Duplicates skipped : {duplicate_count}"
        )
        print(
            f"Quarantined        : {quarantine_count}"
        )
        print("================================================")


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except Exception as exc:

        print(f"ERROR: {exc}")

        sys.exit(1)
