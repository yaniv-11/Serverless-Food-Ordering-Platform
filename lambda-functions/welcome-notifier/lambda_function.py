import json


def lambda_handler(event, context):
    """Triggered by SQS whenever the login Lambda queues a new-user event.
    Simulates sending a welcome email/notification - a stand-in for whatever
    slower side-effect you don't want blocking the login response itself."""
    for record in event["Records"]:
        user = json.loads(record["body"])
        print(f"Welcome email queued for {user['name']} <{user['email']}> (user id: {user['id']})")
