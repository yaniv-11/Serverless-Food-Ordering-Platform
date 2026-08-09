variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "ap-southeast-2"
}

variable "app_name" {
  description = "Prefix applied to every resource name"
  type        = string
  default     = "foodie"
}

variable "upstash_redis_rest_url" {
  description = "Upstash Redis REST URL (from the Upstash dashboard)"
  type        = string
  sensitive   = true
}

variable "upstash_redis_rest_token" {
  description = "Upstash Redis REST token (from the Upstash dashboard)"
  type        = string
  sensitive   = true
}

variable "jwt_secret" {
  description = "HMAC signing secret for JWTs issued by the auth Lambda - generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
  type        = string
  sensitive   = true
}

variable "stripe_secret_key" {
  description = "Stripe secret API key (test mode: sk_test_...) - from the Stripe dashboard"
  type        = string
  sensitive   = true
}

variable "stripe_webhook_secret" {
  description = "Stripe webhook signing secret (whsec_...) - from the Stripe dashboard, after registering the webhook endpoint"
  type        = string
  sensitive   = true
}
