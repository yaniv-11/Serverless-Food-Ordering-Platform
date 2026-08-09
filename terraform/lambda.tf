# ---------------------------------------------------------------------------
# Lambda functions
#
# The archive_file data source zips each lambda_function.py from the
# ../lambda/<name>/ directories so Terraform can upload them directly.
# source_code_hash ensures Lambda is re-deployed whenever the code changes.
# ---------------------------------------------------------------------------

locals {
  lambda_dir = "${path.module}/../lambda"
  zip_dir    = "${path.module}/zips"
}

# ---- Zip archives -----------------------------------------------------------

data "archive_file" "restaurants_api" {
  type        = "zip"
  source_file = "${local.lambda_dir}/restaurants-api/lambda_function.py"
  output_path = "${local.zip_dir}/restaurants-api.zip"
}

data "archive_file" "orders_api" {
  type        = "zip"
  source_file = "${local.lambda_dir}/orders-api/lambda_function.py"
  output_path = "${local.zip_dir}/orders-api.zip"
}

data "archive_file" "auth_login" {
  type        = "zip"
  source_file = "${local.lambda_dir}/auth-login/lambda_function.py"
  output_path = "${local.zip_dir}/auth-login.zip"
}

data "archive_file" "seed_restaurants" {
  type        = "zip"
  source_file = "${local.lambda_dir}/seed-restaurants/lambda_function.py"
  output_path = "${local.zip_dir}/seed-restaurants.zip"
}

data "archive_file" "welcome_notifier" {
  type        = "zip"
  source_file = "${local.lambda_dir}/welcome-notifier/lambda_function.py"
  output_path = "${local.zip_dir}/welcome-notifier.zip"
}

data "archive_file" "signup_digest" {
  type        = "zip"
  source_file = "${local.lambda_dir}/signup-digest/lambda_function.py"
  output_path = "${local.zip_dir}/signup-digest.zip"
}

data "archive_file" "jwt_authorizer" {
  type        = "zip"
  source_file = "${local.lambda_dir}/jwt-authorizer/lambda_function.py"
  output_path = "${local.zip_dir}/jwt-authorizer.zip"
}

data "archive_file" "payments_webhook" {
  type        = "zip"
  source_file = "${local.lambda_dir}/payments-webhook/lambda_function.py"
  output_path = "${local.zip_dir}/payments-webhook.zip"
}

# ---- Lambda functions -------------------------------------------------------

resource "aws_lambda_function" "restaurants_api" {
  function_name    = "${var.app_name}-restaurants-api"
  role             = aws_iam_role.lambda.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.restaurants_api.output_path
  source_code_hash = data.archive_file.restaurants_api.output_base64sha256

  environment {
    variables = {
      RESTAURANTS_TABLE        = aws_dynamodb_table.restaurants.name
      MENU_ITEMS_TABLE         = aws_dynamodb_table.menu_items.name
      UPSTASH_REDIS_REST_URL   = var.upstash_redis_rest_url
      UPSTASH_REDIS_REST_TOKEN = var.upstash_redis_rest_token
    }
  }

  timeout = 10

  tags = { App = var.app_name }
}

resource "aws_lambda_function" "orders_api" {
  function_name    = "${var.app_name}-orders-api"
  role             = aws_iam_role.lambda.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.orders_api.output_path
  source_code_hash = data.archive_file.orders_api.output_base64sha256

  environment {
    variables = {
      ORDERS_TABLE      = aws_dynamodb_table.orders.name
      MENU_ITEMS_TABLE  = aws_dynamodb_table.menu_items.name
      RESTAURANTS_TABLE = aws_dynamodb_table.restaurants.name
      STRIPE_SECRET_KEY = var.stripe_secret_key
    }
  }

  timeout = 10 # now makes an outbound HTTPS call to Stripe on every order

  tags = { App = var.app_name }
}

resource "aws_lambda_function" "auth_login" {
  function_name    = "${var.app_name}-auth-login"
  role             = aws_iam_role.lambda.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.auth_login.output_path
  source_code_hash = data.archive_file.auth_login.output_base64sha256

  environment {
    variables = {
      TABLE_NAME         = aws_dynamodb_table.users.name
      NEW_USER_QUEUE_URL = aws_sqs_queue.new_users.url
      JWT_SECRET         = var.jwt_secret
    }
  }

  timeout = 10 # PBKDF2 at 600k iterations takes noticeably longer than the 3s default

  tags = { App = var.app_name }
}

# Seed job - run once manually from the Lambda console after first deploy
resource "aws_lambda_function" "seed_restaurants" {
  function_name    = "${var.app_name}-seed-restaurants"
  role             = aws_iam_role.lambda.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.seed_restaurants.output_path
  source_code_hash = data.archive_file.seed_restaurants.output_base64sha256
  timeout          = 60

  environment {
    variables = {
      RESTAURANTS_TABLE = aws_dynamodb_table.restaurants.name
      MENU_ITEMS_TABLE  = aws_dynamodb_table.menu_items.name
    }
  }

  tags = { App = var.app_name }
}

# SQS-triggered: fires when auth-login queues a new-user event
resource "aws_lambda_function" "welcome_notifier" {
  function_name    = "${var.app_name}-welcome-notifier"
  role             = aws_iam_role.lambda.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.welcome_notifier.output_path
  source_code_hash = data.archive_file.welcome_notifier.output_base64sha256

  tags = { App = var.app_name }
}

# EventBridge-triggered: daily digest (defined in eventbridge.tf)
resource "aws_lambda_function" "signup_digest" {
  function_name    = "${var.app_name}-signup-digest"
  role             = aws_iam_role.lambda.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.signup_digest.output_path
  source_code_hash = data.archive_file.signup_digest.output_base64sha256

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.users.name
    }
  }

  tags = { App = var.app_name }
}

# Verifies JWTs for API Gateway before protected routes run (wired up in
# api_gateway.tf once orders-api is updated to consume its context - Step 5)
resource "aws_lambda_function" "jwt_authorizer" {
  function_name    = "${var.app_name}-jwt-authorizer"
  role             = aws_iam_role.jwt_authorizer.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.jwt_authorizer.output_path
  source_code_hash = data.archive_file.jwt_authorizer.output_base64sha256

  environment {
    variables = {
      JWT_SECRET = var.jwt_secret
    }
  }

  tags = { App = var.app_name }
}

# Receives Stripe webhooks - a public route (payments_webhook_agw) but with
# its own dedicated, tightly scoped role (jwt_authorizer's role pattern
# repeated here, not the shared app-wide one).
resource "aws_lambda_function" "payments_webhook" {
  function_name    = "${var.app_name}-payments-webhook"
  role             = aws_iam_role.payments_webhook.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.payments_webhook.output_path
  source_code_hash = data.archive_file.payments_webhook.output_base64sha256

  environment {
    variables = {
      ORDERS_TABLE          = aws_dynamodb_table.orders.name
      STRIPE_WEBHOOK_SECRET = var.stripe_webhook_secret
    }
  }

  tags = { App = var.app_name }
}

# ---- SQS event source mapping -----------------------------------------------

resource "aws_lambda_event_source_mapping" "welcome_notifier_sqs" {
  event_source_arn = aws_sqs_queue.new_users.arn
  function_name    = aws_lambda_function.welcome_notifier.arn
  batch_size       = 10
}
