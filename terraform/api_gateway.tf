# ---------------------------------------------------------------------------
# API Gateway (REST API) - routes HTTP requests to the correct Lambda.
#
# Routes:
#   GET  /restaurants            -> restaurants-api Lambda
#   GET  /restaurants/{id}       -> restaurants-api Lambda
#   POST /auth/login             -> auth-login Lambda
#   POST /auth/signup            -> auth-login Lambda
#   POST /orders                 -> orders-api Lambda
#   GET  /orders/user/{user_id}  -> orders-api Lambda
#   POST /webhooks/stripe        -> payments-webhook Lambda
#
# CORS: every browser-facing resource has an OPTIONS method backed by a MOCK
# integration that returns the required preflight headers. The Lambdas also
# set CORS headers on their own responses for non-preflight requests.
# /webhooks/stripe is the one exception - it's called server-to-server by
# Stripe, never by a browser, so CORS doesn't apply to it at all.
# ---------------------------------------------------------------------------

resource "aws_api_gateway_rest_api" "foodie" {
  name = "${var.app_name}-api"
  tags = { App = var.app_name }
}

# ---------------------------------------------------------------------------
# /restaurants
# ---------------------------------------------------------------------------

resource "aws_api_gateway_resource" "restaurants" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  parent_id   = aws_api_gateway_rest_api.foodie.root_resource_id
  path_part   = "restaurants"
}

# GET /restaurants
resource "aws_api_gateway_method" "get_restaurants" {
  rest_api_id   = aws_api_gateway_rest_api.foodie.id
  resource_id   = aws_api_gateway_resource.restaurants.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "get_restaurants" {
  rest_api_id             = aws_api_gateway_rest_api.foodie.id
  resource_id             = aws_api_gateway_resource.restaurants.id
  http_method             = aws_api_gateway_method.get_restaurants.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.restaurants_api.invoke_arn
}

# OPTIONS /restaurants (CORS preflight)
resource "aws_api_gateway_method" "options_restaurants" {
  rest_api_id   = aws_api_gateway_rest_api.foodie.id
  resource_id   = aws_api_gateway_resource.restaurants.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_restaurants" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  resource_id = aws_api_gateway_resource.restaurants.id
  http_method = aws_api_gateway_method.options_restaurants.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_restaurants" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  resource_id = aws_api_gateway_resource.restaurants.id
  http_method = aws_api_gateway_method.options_restaurants.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = true
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
  }
}

resource "aws_api_gateway_integration_response" "options_restaurants" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  resource_id = aws_api_gateway_resource.restaurants.id
  http_method = aws_api_gateway_method.options_restaurants.http_method
  status_code = aws_api_gateway_method_response.options_restaurants.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
  }
}

# ---------------------------------------------------------------------------
# /restaurants/{id}
# ---------------------------------------------------------------------------

resource "aws_api_gateway_resource" "restaurant_id" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  parent_id   = aws_api_gateway_resource.restaurants.id
  path_part   = "{id}"
}

resource "aws_api_gateway_method" "get_restaurant_id" {
  rest_api_id   = aws_api_gateway_rest_api.foodie.id
  resource_id   = aws_api_gateway_resource.restaurant_id.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "get_restaurant_id" {
  rest_api_id             = aws_api_gateway_rest_api.foodie.id
  resource_id             = aws_api_gateway_resource.restaurant_id.id
  http_method             = aws_api_gateway_method.get_restaurant_id.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.restaurants_api.invoke_arn
}

resource "aws_api_gateway_method" "options_restaurant_id" {
  rest_api_id   = aws_api_gateway_rest_api.foodie.id
  resource_id   = aws_api_gateway_resource.restaurant_id.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_restaurant_id" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  resource_id = aws_api_gateway_resource.restaurant_id.id
  http_method = aws_api_gateway_method.options_restaurant_id.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_restaurant_id" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  resource_id = aws_api_gateway_resource.restaurant_id.id
  http_method = aws_api_gateway_method.options_restaurant_id.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = true
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
  }
}

resource "aws_api_gateway_integration_response" "options_restaurant_id" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  resource_id = aws_api_gateway_resource.restaurant_id.id
  http_method = aws_api_gateway_method.options_restaurant_id.http_method
  status_code = aws_api_gateway_method_response.options_restaurant_id.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
  }
}

# ---------------------------------------------------------------------------
# /auth/login
# ---------------------------------------------------------------------------

resource "aws_api_gateway_resource" "auth" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  parent_id   = aws_api_gateway_rest_api.foodie.root_resource_id
  path_part   = "auth"
}

resource "aws_api_gateway_resource" "auth_login" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  parent_id   = aws_api_gateway_resource.auth.id
  path_part   = "login"
}

resource "aws_api_gateway_method" "post_auth_login" {
  rest_api_id   = aws_api_gateway_rest_api.foodie.id
  resource_id   = aws_api_gateway_resource.auth_login.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "post_auth_login" {
  rest_api_id             = aws_api_gateway_rest_api.foodie.id
  resource_id             = aws_api_gateway_resource.auth_login.id
  http_method             = aws_api_gateway_method.post_auth_login.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.auth_login.invoke_arn
}

resource "aws_api_gateway_method" "options_auth_login" {
  rest_api_id   = aws_api_gateway_rest_api.foodie.id
  resource_id   = aws_api_gateway_resource.auth_login.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_auth_login" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  resource_id = aws_api_gateway_resource.auth_login.id
  http_method = aws_api_gateway_method.options_auth_login.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_auth_login" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  resource_id = aws_api_gateway_resource.auth_login.id
  http_method = aws_api_gateway_method.options_auth_login.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = true
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
  }
}

resource "aws_api_gateway_integration_response" "options_auth_login" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  resource_id = aws_api_gateway_resource.auth_login.id
  http_method = aws_api_gateway_method.options_auth_login.http_method
  status_code = aws_api_gateway_method_response.options_auth_login.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
  }
}

# ---------------------------------------------------------------------------
# /auth/signup - same Lambda as /auth/login, different resource/route
# ---------------------------------------------------------------------------

resource "aws_api_gateway_resource" "auth_signup" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  parent_id   = aws_api_gateway_resource.auth.id
  path_part   = "signup"
}

resource "aws_api_gateway_method" "post_auth_signup" {
  rest_api_id   = aws_api_gateway_rest_api.foodie.id
  resource_id   = aws_api_gateway_resource.auth_signup.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "post_auth_signup" {
  rest_api_id             = aws_api_gateway_rest_api.foodie.id
  resource_id             = aws_api_gateway_resource.auth_signup.id
  http_method             = aws_api_gateway_method.post_auth_signup.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.auth_login.invoke_arn
}

resource "aws_api_gateway_method" "options_auth_signup" {
  rest_api_id   = aws_api_gateway_rest_api.foodie.id
  resource_id   = aws_api_gateway_resource.auth_signup.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_auth_signup" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  resource_id = aws_api_gateway_resource.auth_signup.id
  http_method = aws_api_gateway_method.options_auth_signup.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_auth_signup" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  resource_id = aws_api_gateway_resource.auth_signup.id
  http_method = aws_api_gateway_method.options_auth_signup.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = true
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
  }
}

resource "aws_api_gateway_integration_response" "options_auth_signup" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  resource_id = aws_api_gateway_resource.auth_signup.id
  http_method = aws_api_gateway_method.options_auth_signup.http_method
  status_code = aws_api_gateway_method_response.options_auth_signup.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
  }
}

# ---------------------------------------------------------------------------
# /orders
# ---------------------------------------------------------------------------

resource "aws_api_gateway_resource" "orders" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  parent_id   = aws_api_gateway_rest_api.foodie.root_resource_id
  path_part   = "orders"
}

resource "aws_api_gateway_method" "post_orders" {
  rest_api_id   = aws_api_gateway_rest_api.foodie.id
  resource_id   = aws_api_gateway_resource.orders.id
  http_method   = "POST"
  authorization = "CUSTOM"
  authorizer_id = aws_api_gateway_authorizer.jwt.id
}

resource "aws_api_gateway_integration" "post_orders" {
  rest_api_id             = aws_api_gateway_rest_api.foodie.id
  resource_id             = aws_api_gateway_resource.orders.id
  http_method             = aws_api_gateway_method.post_orders.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.orders_api.invoke_arn
}

resource "aws_api_gateway_method" "options_orders" {
  rest_api_id   = aws_api_gateway_rest_api.foodie.id
  resource_id   = aws_api_gateway_resource.orders.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_orders" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  resource_id = aws_api_gateway_resource.orders.id
  http_method = aws_api_gateway_method.options_orders.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_orders" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  resource_id = aws_api_gateway_resource.orders.id
  http_method = aws_api_gateway_method.options_orders.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = true
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
  }
}

resource "aws_api_gateway_integration_response" "options_orders" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  resource_id = aws_api_gateway_resource.orders.id
  http_method = aws_api_gateway_method.options_orders.http_method
  status_code = aws_api_gateway_method_response.options_orders.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
  }
}

# ---------------------------------------------------------------------------
# /orders/user/{user_id}
# ---------------------------------------------------------------------------

resource "aws_api_gateway_resource" "orders_user" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  parent_id   = aws_api_gateway_resource.orders.id
  path_part   = "user"
}

resource "aws_api_gateway_resource" "orders_user_id" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  parent_id   = aws_api_gateway_resource.orders_user.id
  path_part   = "{user_id}"
}

resource "aws_api_gateway_method" "get_orders_user" {
  rest_api_id   = aws_api_gateway_rest_api.foodie.id
  resource_id   = aws_api_gateway_resource.orders_user_id.id
  http_method   = "GET"
  authorization = "CUSTOM"
  authorizer_id = aws_api_gateway_authorizer.jwt.id
}

resource "aws_api_gateway_integration" "get_orders_user" {
  rest_api_id             = aws_api_gateway_rest_api.foodie.id
  resource_id             = aws_api_gateway_resource.orders_user_id.id
  http_method             = aws_api_gateway_method.get_orders_user.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.orders_api.invoke_arn
}

resource "aws_api_gateway_method" "options_orders_user_id" {
  rest_api_id   = aws_api_gateway_rest_api.foodie.id
  resource_id   = aws_api_gateway_resource.orders_user_id.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_orders_user_id" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  resource_id = aws_api_gateway_resource.orders_user_id.id
  http_method = aws_api_gateway_method.options_orders_user_id.http_method
  type        = "MOCK"
  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_orders_user_id" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  resource_id = aws_api_gateway_resource.orders_user_id.id
  http_method = aws_api_gateway_method.options_orders_user_id.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = true
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
  }
}

resource "aws_api_gateway_integration_response" "options_orders_user_id" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  resource_id = aws_api_gateway_resource.orders_user_id.id
  http_method = aws_api_gateway_method.options_orders_user_id.http_method
  status_code = aws_api_gateway_method_response.options_orders_user_id.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,OPTIONS'"
  }
}

# ---------------------------------------------------------------------------
# /webhooks/stripe - no OPTIONS/CORS (server-to-server, not browser-facing),
# no authorizer (Stripe authenticates via its own request signature, verified
# inside the Lambda itself, not via our JWT scheme).
# ---------------------------------------------------------------------------

resource "aws_api_gateway_resource" "webhooks" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  parent_id   = aws_api_gateway_rest_api.foodie.root_resource_id
  path_part   = "webhooks"
}

resource "aws_api_gateway_resource" "webhooks_stripe" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id
  parent_id   = aws_api_gateway_resource.webhooks.id
  path_part   = "stripe"
}

resource "aws_api_gateway_method" "post_webhooks_stripe" {
  rest_api_id   = aws_api_gateway_rest_api.foodie.id
  resource_id   = aws_api_gateway_resource.webhooks_stripe.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "post_webhooks_stripe" {
  rest_api_id             = aws_api_gateway_rest_api.foodie.id
  resource_id             = aws_api_gateway_resource.webhooks_stripe.id
  http_method             = aws_api_gateway_method.post_webhooks_stripe.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.payments_webhook.invoke_arn
}

# ---------------------------------------------------------------------------
# Lambda invoke permissions - API Gateway needs explicit permission to call
# each Lambda function.
# ---------------------------------------------------------------------------

resource "aws_lambda_permission" "restaurants_api_agw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.restaurants_api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.foodie.execution_arn}/*/*"
}

resource "aws_lambda_permission" "orders_api_agw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.orders_api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.foodie.execution_arn}/*/*"
}

resource "aws_lambda_permission" "auth_login_agw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.auth_login.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.foodie.execution_arn}/*/*"
}

resource "aws_lambda_permission" "payments_webhook_agw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.payments_webhook.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.foodie.execution_arn}/*/*"
}

# API Gateway needs its own explicit permission to invoke the authorizer -
# separate from the permission above since this is a different invocation
# path (the authorizer check itself), not a route integration.
resource "aws_lambda_permission" "jwt_authorizer_agw" {
  statement_id  = "AllowAPIGatewayInvokeAuthorizer"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.jwt_authorizer.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.foodie.execution_arn}/authorizers/*"
}

# TOKEN authorizer - verifies the JWT from Step 1. Not yet attached to any
# method's `authorizer_id` - that cutover happens once orders-api reads
# from authorizer context instead of the request body (Step 5), and the
# frontend sends real tokens (Step 6). Caching the Allow decision for 5
# minutes per distinct token avoids re-invoking this on every single request.
resource "aws_api_gateway_authorizer" "jwt" {
  name                             = "${var.app_name}-jwt-authorizer"
  rest_api_id                      = aws_api_gateway_rest_api.foodie.id
  authorizer_uri                   = aws_lambda_function.jwt_authorizer.invoke_arn
  type                             = "TOKEN"
  identity_source                  = "method.request.header.Authorization"
  authorizer_result_ttl_in_seconds = 300
}

# ---------------------------------------------------------------------------
# Deployment and stage
#
# depends_on lists every integration so the deployment waits until all
# methods are wired up before it creates a snapshot of the API.
#
# triggers forces a NEW deployment revision whenever this file changes -
# without this, adding a route (a new resource/method/integration) creates
# the underlying API Gateway objects but does NOT automatically create a new
# deployment snapshot, so the live stage keeps serving the old snapshot and
# the new route 404s with "Missing Authentication Token" until something
# forces a redeploy. depends_on alone does not trigger recreation.
# ---------------------------------------------------------------------------

resource "aws_api_gateway_deployment" "foodie" {
  rest_api_id = aws_api_gateway_rest_api.foodie.id

  triggers = {
    redeployment = filesha1("${path.module}/api_gateway.tf")
  }

  depends_on = [
    aws_api_gateway_integration.get_restaurants,
    aws_api_gateway_integration.get_restaurant_id,
    aws_api_gateway_integration.post_auth_login,
    aws_api_gateway_integration.post_auth_signup,
    aws_api_gateway_integration.post_orders,
    aws_api_gateway_integration.get_orders_user,
    aws_api_gateway_integration.post_webhooks_stripe,
    aws_api_gateway_integration.options_restaurants,
    aws_api_gateway_integration.options_restaurant_id,
    aws_api_gateway_integration.options_auth_login,
    aws_api_gateway_integration.options_auth_signup,
    aws_api_gateway_integration.options_orders,
    aws_api_gateway_integration.options_orders_user_id,
    aws_api_gateway_integration_response.options_restaurants,
    aws_api_gateway_integration_response.options_restaurant_id,
    aws_api_gateway_integration_response.options_auth_login,
    aws_api_gateway_integration_response.options_auth_signup,
    aws_api_gateway_integration_response.options_orders,
    aws_api_gateway_integration_response.options_orders_user_id,
  ]

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "prod" {
  rest_api_id   = aws_api_gateway_rest_api.foodie.id
  deployment_id = aws_api_gateway_deployment.foodie.id
  stage_name    = "prod"
  tags          = { App = var.app_name }
}
