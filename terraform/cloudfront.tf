# ---------------------------------------------------------------------------
# CloudFront - CDN + HTTPS in front of the S3 static site.
# custom_error_response on 404 -> index.html supports React Router's
# client-side navigation when users refresh or deep-link.
# ---------------------------------------------------------------------------

resource "aws_cloudfront_distribution" "frontend" {
  origin {
    # Use the S3 website endpoint (not the REST endpoint) so
    # index.html is served for directory-style paths.
    domain_name = aws_s3_bucket_website_configuration.frontend.website_endpoint
    origin_id   = "S3Website"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  enabled             = true
  default_root_object = "index.html"
  comment             = "${var.app_name} frontend"

  default_cache_behavior {
    target_origin_id       = "S3Website"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }

    min_ttl     = 0
    default_ttl = 3600
    max_ttl     = 86400
  }

  # Return index.html for any 404 so React Router handles the route
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = { App = var.app_name }
}
