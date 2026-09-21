import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

from confluent_kafka import Producer


FIXTURE_PATH = "data/fixtures/cdc_sample_1000.json"


def get_required_env(name: str) -> str:
    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            f"Required environment variable is missing: {name}"
        )

    return value


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_event_id(row: dict) -> str:
    """
    Create a deterministic event ID from the CDC business key.

    The same CDC record will always produce the same event_id.
    This allows downstream duplicate detection.
    """

    natural_key = "|".join(
        [
            row["state"],
            row["start_date"],
            row["end_date"],
        ]
    )

    return hashlib.sha256(
        natural_key.encode("utf-8")
    ).hexdigest()


def build_event(row: dict) -> dict:
    """
    Wrap the original CDC record in a streaming event envelope.
    """

    return {
        "event_id": create_event_id(row),
        "event_time": row["date_updated"],
        "ingestion_time": utc_now(),
        "source": "cdc_historical_replay",
        "source_dataset_id": "pwn4-m3yp",
        "payload": row,
    }


def delivery_report(err, msg):
    if err is not None:
        print(f"DELIVERY FAILED: {err}")
    else:
        print(
            f"DELIVERED "
            f"event_id={msg.key().decode('utf-8')} "
            f"partition={msg.partition()} "
            f"offset={msg.offset()}"
        )


def publish_event(producer, event_hub_name, event):
    payload = json.dumps(event).encode("utf-8")

    producer.produce(
        topic=event_hub_name,
        key=event["event_id"].encode("utf-8"),
        value=payload,
        callback=delivery_report,
    )

    producer.poll(0)

    print(
        f"SENT "
        f"{event['event_id']} "
        f"| event_time={event.get('event_time', '<missing>')}"
    )


def main():

    connection_string = get_required_env(
        "EVENT_HUB_CONNECTION_STRING"
    )

    bootstrap_server = os.getenv(
        "EVENT_HUB_BOOTSTRAP_SERVER",
        "eh-lakehouse-bello.servicebus.windows.net:9093",
    )

    event_hub_name = os.getenv(
        "EVENT_HUB_NAME",
        "healthcare-events",
    )

    config = {
        "bootstrap.servers": bootstrap_server,
        "security.protocol": "SASL_SSL",
        "sasl.mechanisms": "PLAIN",
        "sasl.username": "$ConnectionString",
        "sasl.password": connection_string,
    }

    producer = Producer(config)

    with open(
        FIXTURE_PATH,
        encoding="utf-8",
    ) as file:

        rows = json.load(file)

    print()
    print("================================================")
    print("CDC HISTORICAL REPLAY PRODUCER")
    print("================================================")
    print(f"Source records : {len(rows)}")
    print(f"Event Hub      : {event_hub_name}")
    print("================================================")
    print()

    sent_count = 0

    # --------------------------------------------------------
    # Publish records in chronological order.
    #
    # One record is intentionally held back so we can replay
    # it later as a late-arriving event.
    # --------------------------------------------------------

    late_row = rows[5]

    ordered_rows = rows[:5] + rows[6:]

    for row in ordered_rows:

        event = build_event(row)

        publish_event(
            producer,
            event_hub_name,
            event,
        )

        sent_count += 1

        time.sleep(0.05)

    # --------------------------------------------------------
    # Controlled late-arriving event
    # --------------------------------------------------------

    late_event = build_event(late_row)

    print()
    print(
        "SENDING LATE EVENT: "
        f"{late_event['event_id']} "
        f"| event_time={late_event['event_time']}"
    )

    publish_event(
        producer,
        event_hub_name,
        late_event,
    )

    sent_count += 1

    # --------------------------------------------------------
    # Controlled duplicate
    #
    # Same event_id and same payload are intentionally sent
    # twice so the consumer can demonstrate deduplication.
    # --------------------------------------------------------

    print()
    print(
        "SENDING DUPLICATE: "
        f"{late_event['event_id']}"
    )

    publish_event(
        producer,
        event_hub_name,
        late_event,
    )

    sent_count += 1

    # --------------------------------------------------------
    # Controlled malformed event
    #
    # Remove event_time so the consumer must quarantine it.
    # --------------------------------------------------------

    malformed_event = build_event(rows[10])

    # Give the fault-injected event its own ID so it is treated
    # as a distinct malformed message rather than a duplicate.
    malformed_event["event_id"] = (
        malformed_event["event_id"] + "-malformed"
    )

    del malformed_event["event_time"]

    print()
    print(
        "SENDING MALFORMED EVENT: "
        f"{malformed_event['event_id']}"
    )

    publish_event(
        producer,
        event_hub_name,
        malformed_event,
    )

    sent_count += 1

    producer.flush()

    print()
    print("================================================")
    print("PRODUCER COMPLETE")
    print("================================================")
    print(f"Events sent: {sent_count}")
    print("Includes:")
    print("  - historical CDC replay")
    print("  - late-arriving event")
    print("  - duplicate event")
    print("  - malformed event")
    print("================================================")


if __name__ == "__main__":

    try:
        main()

    except Exception as exc:

        print(f"ERROR: {exc}")

        sys.exit(1)
