# ---------------------------------------------------------------------------
# SQS queue - auth-login Lambda pushes a new-user event here;
# welcome-notifier Lambda consumes it asynchronously.
# ---------------------------------------------------------------------------

resource "aws_sqs_queue" "new_users" {
  name                      = "${var.app_name}-new-users"
  message_retention_seconds = 86400 # 1 day

  tags = { App = var.app_name }
}
