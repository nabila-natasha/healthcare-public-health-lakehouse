import csv
import json
import os
import sys
import time
from datetime import datetime, timezone

from confluent_kafka import Producer


FIXTURE_PATH = "data/fixtures/healthcare_cdc.csv"


def get_required_env(name: str) -> str:
    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            f"Required environment variable is missing: {name}"
        )

    return value


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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

    sent_count = 0

    with open(
        FIXTURE_PATH,
        newline="",
        encoding="utf-8",
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            event = {
                "event_id": row["event_id"],
                "event_time": row["event_time"],
                "ingestion_time": utc_now(),
                "source": "cdc_replay",
                "patient_id": row["patient_id"],
                "event_type": row["event_type"],
                "region": row["region"],
                "status": row["status"],
            }

            payload = json.dumps(event).encode("utf-8")

            producer.produce(
                topic=event_hub_name,
                key=event["event_id"].encode("utf-8"),
                value=payload,
                callback=delivery_report,
            )

            producer.poll(0)

            sent_count += 1

            print(f"SENT {event['event_id']}")

            time.sleep(0.5)

            # Intentionally replay one event to test
            # duplicate detection in the downstream consumer.
            if event["event_id"] == "cdc-0005":

                producer.produce(
                    topic=event_hub_name,
                    key=event["event_id"].encode("utf-8"),
                    value=payload,
                    callback=delivery_report,
                )

                producer.poll(0)

                sent_count += 1

                print("SENT DUPLICATE cdc-0005")

                time.sleep(0.5)

    producer.flush()

    print()
    print(f"Producer complete. Events sent: {sent_count}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
