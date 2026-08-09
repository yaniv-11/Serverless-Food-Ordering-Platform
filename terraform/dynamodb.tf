# ---------------------------------------------------------------------------
# DynamoDB tables
# PAY_PER_REQUEST = no provisioned throughput cost; fits comfortably in
# the AWS free tier for a learning project.
# ---------------------------------------------------------------------------

resource "aws_dynamodb_table" "restaurants" {
  name         = "${var.app_name}-restaurants"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }

  tags = { App = var.app_name }
}

resource "aws_dynamodb_table" "menu_items" {
  name         = "${var.app_name}-menu-items"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "restaurant_id"
  range_key    = "menu_item_id"

  attribute {
    name = "restaurant_id"
    type = "S"
  }

  attribute {
    name = "menu_item_id"
    type = "S"
  }

  tags = { App = var.app_name }
}

resource "aws_dynamodb_table" "orders" {
  name         = "${var.app_name}-orders"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "order_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "order_id"
    type = "S"
  }

  attribute {
    name = "payment_intent_id"
    type = "S"
  }

  # Lets the payment webhook look up "which order does this PaymentIntent
  # belong to" with a Query, instead of scanning the whole table on every
  # webhook delivery.
  global_secondary_index {
    name            = "payment_intent_id-index"
    hash_key        = "payment_intent_id"
    projection_type = "ALL"
  }

  tags = { App = var.app_name }
}

resource "aws_dynamodb_table" "users" {
  name         = "${var.app_name}-users"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "email"

  attribute {
    name = "email"
    type = "S"
  }

  tags = { App = var.app_name }
}
