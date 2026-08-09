# ---------------------------------------------------------------------------
# IAM - single execution role shared by all 6 Lambda functions.
# Permissions are scoped to only the DynamoDB tables and SQS queue this
# app owns (principle of least privilege).
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${var.app_name}-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  tags               = { App = var.app_name }
}

# CloudWatch Logs (basic execution)
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# DynamoDB + SQS inline policy
resource "aws_iam_role_policy" "lambda_app" {
  name = "${var.app_name}-lambda-app-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DynamoDB"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
        ]
        Resource = [
          aws_dynamodb_table.restaurants.arn,
          aws_dynamodb_table.menu_items.arn,
          aws_dynamodb_table.orders.arn,
          "${aws_dynamodb_table.orders.arn}/index/*",
          aws_dynamodb_table.users.arn,
        ]
      },
      {
        Sid    = "SQS"
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
        ]
        Resource = aws_sqs_queue.new_users.arn
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# Dedicated role for the JWT authorizer - deliberately separate from the
# shared role above. This function verifies a token's signature and nothing
# else; it has no business being able to touch DynamoDB or SQS, so it gets
# only CloudWatch Logs access rather than inheriting the app-wide policy.
# ---------------------------------------------------------------------------

resource "aws_iam_role" "jwt_authorizer" {
  name               = "${var.app_name}-jwt-authorizer-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  tags               = { App = var.app_name }
}

resource "aws_iam_role_policy_attachment" "jwt_authorizer_basic" {
  role       = aws_iam_role.jwt_authorizer.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# ---------------------------------------------------------------------------
# Dedicated role for the payments webhook - handles requests from an
# external, internet-facing caller (Stripe), so it gets its own tightly
# scoped role: only Query (via the GSI) + UpdateItem on Orders, nothing else.
# ---------------------------------------------------------------------------

resource "aws_iam_role" "payments_webhook" {
  name               = "${var.app_name}-payments-webhook-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  tags               = { App = var.app_name }
}

resource "aws_iam_role_policy_attachment" "payments_webhook_basic" {
  role       = aws_iam_role.payments_webhook.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "payments_webhook_orders" {
  name = "${var.app_name}-payments-webhook-orders-policy"
  role = aws_iam_role.payments_webhook.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["dynamodb:Query", "dynamodb:UpdateItem"]
      Resource = [
        aws_dynamodb_table.orders.arn,
        "${aws_dynamodb_table.orders.arn}/index/*",
      ]
    }]
  })
}
