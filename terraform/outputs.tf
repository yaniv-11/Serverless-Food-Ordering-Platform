# ---------------------------------------------------------------------------
# Outputs printed after `terraform apply` completes.
# Use these values to finish the deployment.
# ---------------------------------------------------------------------------

output "api_gateway_url" {
  description = "Paste this into frontend/.env as VITE_API_URL, then rebuild"
  value       = aws_api_gateway_stage.prod.invoke_url
}

output "cloudfront_url" {
  description = "Your live app URL (HTTPS via CloudFront)"
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "s3_bucket_name" {
  description = "Upload the contents of frontend/dist/ here after building"
  value       = aws_s3_bucket.frontend.id
}

output "seed_lambda_name" {
  description = "Invoke this Lambda once to populate DynamoDB with sample data"
  value       = aws_lambda_function.seed_restaurants.function_name
}
