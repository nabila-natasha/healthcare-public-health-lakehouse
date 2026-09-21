import json
import os
import sys
from datetime import datetime, timezone

from confluent_kafka import Consumer
from azure.storage.filedatalake import DataLakeServiceClient


EVENT_HUB_NAME = "healthcare-events"

EVENT_HUB_BOOTSTRAP_SERVER = (
    "eh-lakehouse-bello.servicebus.windows.net:9093"
)

STORAGE_ACCOUNT = "stlakehousebello"
FILESYSTEM = "healthcare"

RAW_PREFIX = os.getenv("RAW_PREFIX", "raw/cdc")
BRONZE_PREFIX = os.getenv("BRONZE_PREFIX", "bronze/cdc")
QUARANTINE_PREFIX = os.getenv("QUARANTINE_PREFIX", "quarantine/cdc")

REQUIRED_EVENT_FIELDS = [
    "event_id",
    "event_time",
    "ingestion_time",
    "source",
    "source_dataset_id",
    "payload",
]

REQUIRED_PAYLOAD_FIELDS = [
    "date_updated",
    "state",
    "start_date",
    "end_date",
    "tot_cases",
    "new_cases",
    "tot_deaths",
    "new_deaths",
    "new_historic_cases",
    "new_historic_deaths",
]


def get_required_env(name):
    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            f"Required environment variable is missing: {name}"
        )

    return value


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def validate_event(event):
    """
    Validate the event envelope and CDC payload.
    """

    missing_fields = [
        field
        for field in REQUIRED_EVENT_FIELDS
        if field not in event
    ]

    if missing_fields:
        return False, (
            "Missing event fields: "
            + ", ".join(missing_fields)
        )

    if not event["event_id"]:
        return False, "event_id is empty"

    if not event["event_time"]:
        return False, "event_time is empty"

    if not isinstance(event["payload"], dict):
        return False, "payload is not an object"

    missing_payload_fields = [
        field
        for field in REQUIRED_PAYLOAD_FIELDS
        if field not in event["payload"]
    ]

    if missing_payload_fields:
        return False, (
            "Missing payload fields: "
            + ", ".join(missing_payload_fields)
        )

    return True, ""


def upload_json(file_system_client, path, payload):

    file_client = file_system_client.get_file_client(path)

    content = json.dumps(
        payload,
        indent=2
    )

    file_client.upload_data(
        content,
        overwrite=True
    )


def main():

    event_hub_connection_string = get_required_env(
        "EVENT_HUB_CONNECTION_STRING"
    )

    storage_connection_string = get_required_env(
        "AZURE_STORAGE_CONNECTION_STRING"
    )

    consumer_config = {
        "bootstrap.servers": EVENT_HUB_BOOTSTRAP_SERVER,
        "security.protocol": "SASL_SSL",
        "sasl.mechanisms": "PLAIN",
        "sasl.username": "$ConnectionString",
        "sasl.password": event_hub_connection_string,
        "group.id": os.getenv("EVENT_HUB_CONSUMER_GROUP", "healthcare-bronze-consumer-day4-v3"),
        "auto.offset.reset": os.getenv("EVENT_HUB_AUTO_OFFSET_RESET", "earliest"),
        "enable.auto.commit": False,
    }

    consumer = Consumer(consumer_config)

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

    consumer.subscribe([EVENT_HUB_NAME])

    latest_event_time_by_partition = {}
    processed_event_ids = set()

    raw_count = 0
    accepted_count = 0
    duplicate_count = 0
    quarantine_count = 0
    late_count = 0

    print()
    print("================================================")
    print("HEALTHCARE CDC EVENT CONSUMER")
    print("================================================")
    print(f"Event Hub : {EVENT_HUB_NAME}")
    print(f"Filesystem: {FILESYSTEM}")
    print(f"Consumer group: {consumer_config['group.id']}")
    print("================================================")
    print()

    try:

        while True:

            message = consumer.poll(5.0)

            if message is None:

                print("No new messages. Waiting...")

                continue

            if message.error():

                print(
                    f"Consumer error: {message.error()}"
                )

                continue

            raw_payload = message.value()

            # ------------------------------------------------
            # Parse JSON
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
            # Write every successfully parsed message to RAW.
            #
            # RAW preserves what arrived from Event Hubs.
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
                "event_hub_partition": message.partition(),
                "event_hub_offset": message.offset(),
                "received_at": utc_now(),
            }

            upload_json(
                file_system_client,
                raw_path,
                raw_record
            )

            print(
                f"RAW WRITTEN: "
                f"{event.get('event_id', 'unknown')}"
            )

            # ------------------------------------------------
            # Validate envelope + payload
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
            # Duplicate detection
            #
            # Check duplicates before late-arrival detection so
            # a repeated event is counted as a duplicate rather
            # than being counted again as a late event.
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

            processed_event_ids.add(event_id)

            # ------------------------------------------------
            # Detect late arrival
            #
            # Event-time ordering is evaluated independently
            # for each Event Hubs partition.
            #
            # An event is considered late when its event_time
            # is earlier than the latest event_time already
            # processed on the same partition.
            # ------------------------------------------------

            event_time = event["event_time"]
            partition = message.partition()

            if partition in latest_event_time_by_partition:

                if event_time < latest_event_time_by_partition[partition]:

                    late_count += 1

                    print(
                        f"LATE EVENT: "
                        f"{event_id} "
                        f"| event_time={event_time} "
                        f"| partition={partition}"
                    )

            if (
                partition not in latest_event_time_by_partition
                or event_time > latest_event_time_by_partition[partition]
            ):

                latest_event_time_by_partition[partition] = event_time

            # ------------------------------------------------
            # Add platform processing timestamp
            # ------------------------------------------------

            event["processed_time"] = utc_now()

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

            consumer.commit(
                message=message,
                asynchronous=False
            )

    finally:

        consumer.close()

        print()
        print("================================================")
        print("CONSUMER SUMMARY")
        print("================================================")
        print(f"RAW messages       : {raw_count}")
        print(f"Bronze accepted    : {accepted_count}")
        print(f"Duplicates skipped : {duplicate_count}")
        print(f"Quarantined        : {quarantine_count}")
        print(f"Late events        : {late_count}")
        print("================================================")


if __name__ == "__main__":

    try:
        main()

    except KeyboardInterrupt:

        print()
        print("Consumer stopped by user.")

    except Exception as exc:

        print(f"ERROR: {exc}")

        sys.exit(1)
