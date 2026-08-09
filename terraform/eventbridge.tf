# ---------------------------------------------------------------------------
# EventBridge - fires the signup-digest Lambda once per day.
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_event_rule" "signup_digest" {
  name                = "${var.app_name}-signup-digest"
  description         = "Daily signup digest job"
  schedule_expression = "rate(1 day)"
  tags                = { App = var.app_name }
}

resource "aws_cloudwatch_event_target" "signup_digest" {
  rule      = aws_cloudwatch_event_rule.signup_digest.name
  target_id = "signup-digest-lambda"
  arn       = aws_lambda_function.signup_digest.arn
}

resource "aws_lambda_permission" "signup_digest_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.signup_digest.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.signup_digest.arn
}
