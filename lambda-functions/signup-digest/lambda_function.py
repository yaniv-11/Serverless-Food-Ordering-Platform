import os

import boto3

TABLE_NAME = os.environ["TABLE_NAME"]

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)


def lambda_handler(event, context):
    """Triggered on a schedule by EventBridge - a periodic 'digest' job that
    runs regardless of any single request, standing in for whatever a real
    reporting/summary job would do."""
    response = table.scan(Select="COUNT")
    print(f"Signup digest: {response['Count']} total users registered so far.")
