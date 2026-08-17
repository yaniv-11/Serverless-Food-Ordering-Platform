[# Foodie — Serverless Food Ordering Platform

A full-stack food ordering application built on AWS serverless primitives. Users browse restaurants, manage a cart, authenticate with JWT, pay via Stripe, and track orders — all backed by Lambda, DynamoDB, and event-driven workflows.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Client Layer                                   │
│  React 19 + Vite SPA  ──►  CloudFront (HTTPS/CDN)  ──►  S3 Static Hosting   │
└────────────────────────────────────────┬────────────────────────────────────┘
                                         │ REST (JSON)
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           API Gateway (REST)                                │
│  Public routes          │  Protected routes (JWT Authorizer)               │
│  /restaurants           │  POST /orders                                    │
│  /auth/login|signup     │  GET  /orders/user/{user_id}                     │
│  /webhooks/stripe       │                                                  │
└──────────┬──────────────┴──────────────┬───────────────────────────────────┘
           │                             │
           ▼                             ▼
┌──────────────────────┐      ┌──────────────────────┐
│   Lambda Functions   │      │   jwt-authorizer     │
│   (Python 3.12)      │      │   (dedicated IAM)    │
└──────────┬───────────┘      └──────────────────────┘
           │
     ┌─────┴─────┬─────────────┬──────────────┐
     ▼           ▼             ▼              ▼
 DynamoDB    Upstash       Stripe API      SQS
 (4 tables)   Redis         (payments)   (new-users)
     ▲           (cache)          │
     │                            │ webhook
     │                            ▼
     │                   payments-webhook
     │
     └── EventBridge (daily) ──► signup-digest
     └── SQS ──► welcome-notifier
```

**Request flow (order placement):**

1. Frontend sends `POST /orders` with a JWT in the `Authorization` header.
2. API Gateway invokes the **JWT authorizer** — verifies the token and attaches `user_id` to the request context.
3. **orders-api** reads the verified identity (never trusts the client body), validates menu items against DynamoDB, creates a Stripe PaymentIntent, and stores the order as `pending_payment`.
4. Frontend confirms payment with Stripe.js using the returned `client_secret`.
5. Stripe calls `POST /webhooks/stripe`; **payments-webhook** verifies the signature and updates the order to `paid` or `payment_failed`.

---

## Services

### Frontend (`frontend/`)

| Component | Technology | Role |
|-----------|------------|------|
| SPA | React 19, Vite, React Router | Browse restaurants, cart, checkout, order history |
| State | React Context (`UserContext`, `CartContext`) | Auth session and cart persistence |
| Payments | Stripe.js + `@stripe/react-stripe-js` | Client-side card confirmation |
| HTTP | Axios | API calls with JWT injected per request |

Hosted on **S3** (static website) behind **CloudFront** for HTTPS and CDN caching. React Router deep links are handled via CloudFront/S3 404 → `index.html` fallback.

---

### API Layer

| Service | Purpose |
|---------|---------|
| **API Gateway (REST)** | Single entry point; routes HTTP methods to Lambdas; CORS preflight on browser-facing routes |
| **JWT Authorizer** | TOKEN authorizer on protected order routes; 5-minute result cache; returns verified `user_id` in authorizer context |

#### API Routes

| Method | Path | Lambda | Auth |
|--------|------|--------|------|
| `GET` | `/restaurants` | restaurants-api | Public |
| `GET` | `/restaurants/{id}` | restaurants-api | Public |
| `POST` | `/auth/login` | auth-login | Public |
| `POST` | `/auth/signup` | auth-login | Public |
| `POST` | `/orders` | orders-api | JWT |
| `GET` | `/orders/user/{user_id}` | orders-api | JWT |
| `POST` | `/webhooks/stripe` | payments-webhook | Stripe signature |

---

### Lambda Functions (`lambda/`)

| Function | Trigger | Responsibility |
|----------|---------|----------------|
| **restaurants-api** | API Gateway | List restaurants and fetch restaurant + menu; **Upstash Redis** cache (60s TTL) with graceful DynamoDB fallback |
| **auth-login** | API Gateway | Signup and login; PBKDF2-HMAC-SHA256 password hashing (600k iterations); issues HS256 JWTs; publishes new-user events to SQS |
| **orders-api** | API Gateway | Create orders, compute totals from live menu prices, initiate Stripe PaymentIntents (INR), list user orders with ownership checks |
| **payments-webhook** | API Gateway | Verify Stripe webhook signatures; update order status via `payment_intent_id` GSI lookup |
| **jwt-authorizer** | API Gateway | Validate JWT signature and expiry; attach `user_id` to downstream context |
| **welcome-notifier** | SQS | Async side-effect on signup (simulated welcome email) — decoupled from the signup response path |
| **signup-digest** | EventBridge (daily) | Scheduled job reporting total registered users |
| **seed-restaurants** | Manual invoke | One-time population of sample restaurants and menu items |

All application Lambdas run **Python 3.12** and are packaged and deployed via Terraform.

---

### Data Stores

| Store | Table / Key Design | Used By |
|-------|-------------------|---------|
| **DynamoDB — restaurants** | PK: `id` | restaurants-api, orders-api, seed-restaurants |
| **DynamoDB — menu_items** | PK: `restaurant_id`, SK: `menu_item_id` | restaurants-api, orders-api |
| **DynamoDB — orders** | PK: `user_id`, SK: `order_id`; GSI on `payment_intent_id` | orders-api, payments-webhook |
| **DynamoDB — users** | PK: `email` | auth-login, signup-digest |
| **Upstash Redis** | REST API; keys `restaurants:all`, `restaurant:{id}` | restaurants-api (read-through cache) |

All DynamoDB tables use **PAY_PER_REQUEST** billing — no provisioned capacity to manage.

---

### Messaging & Scheduling

| Service | Resource | Flow |
|---------|----------|------|
| **SQS** | `foodie-new-users` | auth-login → queue → welcome-notifier (batch size 10) |
| **EventBridge** | `rate(1 day)` rule | signup-digest daily user count report |

---

### External Integrations

| Service | Usage |
|---------|-------|
| **Stripe** | PaymentIntent creation (orders-api); webhook-driven status updates (payments-webhook); test-mode card payments in frontend |
| **Upstash Redis** | External serverless cache for restaurant reads — reduces DynamoDB scan/query load |

---

### Infrastructure (`terraform/`)

Infrastructure is fully defined as code with Terraform (AWS provider ~> 5.0):

- **Compute:** 8 Lambda functions with per-function or shared IAM roles
- **API:** API Gateway REST API with explicit deployment triggers
- **Storage:** S3 bucket, 4 DynamoDB tables, SQS queue
- **CDN:** CloudFront distribution in front of S3
- **Security:** Least-privilege IAM — dedicated roles for JWT authorizer (logs only) and payments webhook (orders Query + UpdateItem only)
- **Secrets:** JWT secret, Stripe keys, Upstash credentials passed as Terraform variables (never committed)

---

## Key Design Highlights

### Security-first auth and payments

- **Passwords** hashed with PBKDF2 (600,000 iterations) and per-user salt; compared with `hmac.compare_digest`.
- **JWTs** are HS256-signed, 1-hour TTL; protected routes use a dedicated authorizer Lambda with minimal IAM scope.
- **Order identity** comes from authorizer context — the API never trusts `user_id` from the request body.
- **Payment truth** comes only from Stripe webhooks with signature verification and replay protection (5-minute timestamp window). The frontend cannot mark an order as paid.

### Event-driven decoupling

Signup publishes to SQS so the HTTP response is not blocked by welcome-email logic. EventBridge runs periodic digest jobs independent of user traffic. This pattern scales side-effects without slowing the critical path.

### Cache with graceful degradation

Restaurant listings and details are cached in Upstash Redis for 60 seconds. Cache failures are logged and silently fall back to DynamoDB — a broken cache never breaks a user request.

### Least-privilege IAM

Three IAM patterns instead of one monolithic role:

1. **Shared app role** — DynamoDB + SQS for core Lambdas
2. **JWT authorizer role** — CloudWatch Logs only
3. **Payments webhook role** — Query/UpdateItem on orders table only

### Serverless economics

No servers, no connection pools, no always-on cost. DynamoDB on-demand, Lambda per-invocation billing, and S3/CloudFront static hosting keep the stack suitable for learning projects and low-traffic production workloads.

### Infrastructure as code

Every AWS resource — routes, CORS, Lambda permissions, deployment triggers, GSI definitions — is in Terraform. Route changes trigger redeployment via `filesha1` triggers to avoid stale API Gateway snapshots.

---

## Project Structure

```
Food-Ordering/
├── frontend/              # React SPA (Vite)
│   └── src/
│       ├── pages/         # Home, RestaurantDetail, Cart, Orders, Login, Signup
│       ├── components/    # Navbar, RestaurantCard, MenuItemCard
│       ├── context/       # UserContext, CartContext
│       └── api.js         # Axios client + JWT interceptor
├── lambda/
│   ├── auth-login/
│   ├── restaurants-api/
│   ├── orders-api/
│   ├── payments-webhook/
│   ├── jwt-authorizer/
│   ├── welcome-notifier/
│   ├── signup-digest/
│   └── seed-restaurants/
└── terraform/             # Full AWS stack (main.tf, *.tf)
```

---

## Quick Start

### Prerequisites

- AWS account with CLI configured
- Terraform >= 1.6
- Node.js 18+
- [Upstash Redis](https://upstash.com/) REST URL and token
- [Stripe](https://stripe.com/) test keys and webhook secret

### 1. Deploy infrastructure

```bash
cd terraform
# Create terraform.tfvars with the variables defined in variables.tf
terraform init
terraform apply
```

Note the outputs: `api_gateway_url`, `cloudfront_url`, `s3_bucket_name`, `seed_lambda_name`.

### 2. Seed sample data

Invoke the **seed-restaurants** Lambda once from the AWS Console (Test with an empty event).

### 3. Configure Stripe webhook

Register `https://<api-gateway-url>/prod/webhooks/stripe` in the Stripe dashboard for `payment_intent.succeeded` and `payment_intent.payment_failed`. Copy the signing secret into `terraform.tfvars` and re-apply if needed.

### 4. Build and deploy frontend

```bash
cd frontend
echo "VITE_API_URL=<api_gateway_url>" > .env
echo "VITE_STRIPE_PUBLISHABLE_KEY=pk_test_..." >> .env
npm install
npm run build
aws s3 sync dist/ s3://<s3_bucket_name> --delete
```

Open the **CloudFront URL** from Terraform outputs.

---

## Environment Variables

### Terraform (`terraform.tfvars`)

| Variable | Description |
|----------|-------------|
| `jwt_secret` | HMAC secret for JWT signing |
| `stripe_secret_key` | Stripe secret API key (`sk_test_...`) |
| `stripe_webhook_secret` | Stripe webhook signing secret (`whsec_...`) |
| `upstash_redis_rest_url` | Upstash REST endpoint |
| `upstash_redis_rest_token` | Upstash REST token |

### Frontend (`frontend/.env`)

| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | API Gateway invoke URL (from `terraform output`) |
| `VITE_STRIPE_PUBLISHABLE_KEY` | Stripe publishable key for Stripe.js |

---

## Tech Stack Summary

| Layer | Technologies |
|-------|-------------|
| Frontend | React 19, Vite 8, React Router 7, Axios, Stripe.js |
| Backend | Python 3.12, AWS Lambda, API Gateway |
| Database | Amazon DynamoDB |
| Cache | Upstash Redis (REST) |
| Payments | Stripe PaymentIntents + Webhooks |
| Messaging | Amazon SQS, Amazon EventBridge |
| Hosting | Amazon S3, Amazon CloudFront |
| IaC | Terraform (AWS provider ~> 5.0) |
](https://github.com/yaniv-11/Serverless-Food-Ordering-Platform/blob/main/README.md)
