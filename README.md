# Foodie - Serverless Food Ordering Platform

A full-stack food ordering application built on AWS serverless primitives. Users browse restaurants, manage a cart, authenticate with JWT, pay via Stripe, and track orders - all backed by Lambda, DynamoDB, and event-driven workflows. An MCP-based AI assistant, exposed as a draggable chat widget on the frontend, answers order/spending/restaurant questions through a Langflow-orchestrated agent.

---

## Architecture Overview

```
+---------------------------------------------------------------------------+
|                              Client Layer                                 |
|  React 19 + Vite SPA --> CloudFront (HTTPS/CDN) --> S3 Static Hosting     |
|  includes a draggable ChatWidget (floating assistant button)              |
+------------------------------+------------------------+-------------------+
                                | REST (JSON)            | Webhook (chat message)
                                v                         v
+----------------------------------------------+   +----------------------------------------+
|              API Gateway (REST)               |   |   AI Central / Langflow flow           |
|  Public:   /restaurants, /auth/*, /webhooks   |   |   Webhook -> Parser (stringify) ->      |
|  JWT auth: /orders, /orders/user/{user_id}    |   |   Digital Coworker agent -> Chat Output |
|  Open*:    /mcp                                |   +--------------------+---------------------+
+---------------------+--------------------------+                        |
                       |                                                  | Streamable HTTP (MCP)
                       v                                                  v
        +-----------------------------+                    +----------------------------------+
        |      Lambda Functions       |                    |         MCP Server(s)             |
        |      (Python 3.12)          |                    |  read-only order/restaurant tools |
        +---------------+-------------+                    |  - foodie-mcp-server (Lambda)     |
                        |                                   |  - mcp-render-server (Render)     |
       +-----------+----+----+-----------+                  +-----------------+------------------+
       v           v         v           v                                    |
   DynamoDB    Upstash    Stripe API    SQS                                    v
   (4 tables)   Redis     (payments)  (new-users)              DynamoDB (orders, restaurants,
       ^         (cache)       |                                   menu_items - read-only)
       |                       | webhook
       |                       v
       |              payments-webhook
       |
       +-- EventBridge (daily) --> signup-digest
       +-- SQS --> welcome-notifier

* /mcp and the Render MCP endpoint currently accept unauthenticated requests - see
  "Current Limitations & Follow-ups".
```

**Request flow (order placement):**

1. Frontend sends `POST /orders` with a JWT in the `Authorization` header.
2. API Gateway invokes the **JWT authorizer** - verifies the token and attaches `user_id` to the request context.
3. **orders-api** reads the verified identity (never trusts the client body), validates menu items against DynamoDB, creates a Stripe PaymentIntent, and stores the order as `pending_payment`.
4. Frontend confirms payment with Stripe.js using the returned `client_secret`.
5. Stripe calls `POST /webhooks/stripe`; **payments-webhook** verifies the signature and updates the order to `paid` or `payment_failed`.

**Request flow (AI assistant query):**

1. User clicks the **ChatWidget** floating button (draggable, position persisted in `localStorage`) and sends a message.
2. The frontend POSTs the message to the AI Central webhook (`VITE_CHAT_WEBHOOK_URL`), which triggers a Langflow flow: `Webhook -> Parser (stringify) -> Digital Coworker agent -> Chat Output`.
3. The **Digital Coworker** agent calls the connected **MCP toolset** (`get_recent_orders`, `get_spending_summary`, `get_order_status`, `get_top_rated_restaurants`, `get_restaurant_menu`) over Streamable HTTP as needed to answer the question.
4. The MCP server queries DynamoDB directly via `boto3` (bypassing the REST API layer entirely) and returns structured results to the agent.
5. The agent's response flows back through the webhook response to the ChatWidget.

---

## Services

### Frontend (`frontend/`)

| Component | Technology | Role |
|-----------|------------|------|
| SPA | React 19, Vite, React Router | Browse restaurants, cart, checkout, order history |
| State | React Context (`UserContext`, `CartContext`) | Auth session and cart persistence (cart is guest-accessible, keyed to the browser via `localStorage`, independent of login) |
| Payments | Stripe.js + `@stripe/react-stripe-js` | Client-side card confirmation |
| AI Assistant | `ChatWidget` component | Draggable floating chat button + panel; posts messages to the Langflow/AI Central webhook and renders the agent's replies |
| HTTP | Axios | API calls with JWT injected per request via a request interceptor |

Hosted on **S3** (static website) behind **CloudFront** for HTTPS and CDN caching. React Router deep links are handled via CloudFront/S3 404 -> `index.html` fallback. CloudFront caches responses for up to 1 hour (`default_ttl`), so deploys should invalidate the `/*` path to go live immediately (see Quick Start).

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
| `POST` | `/mcp` | mcp-server | None (open - see limitations) |

#### CORS

Every browser-facing route has an `OPTIONS` preflight (MOCK integration) returning `Access-Control-Allow-Origin: *`. The allow-list for `Access-Control-Allow-Headers` includes `Authorization` on every route the frontend's axios instance can reach - including public ones like `/restaurants` - because the frontend's request interceptor unconditionally attaches a bearer token whenever the user is logged in, regardless of whether the target route requires it. A preflight that only allows `Content-Type` would block those requests client-side even though the Lambda itself doesn't require auth. `/orders` additionally allows `Idempotency-Key`.

---

### Lambda Functions (`lambda/`)

| Function | Trigger | Responsibility |
|----------|---------|----------------|
| **restaurants-api** | API Gateway | List restaurants and fetch restaurant + menu; **Upstash Redis** cache (60s TTL) with graceful DynamoDB fallback |
| **auth-login** | API Gateway | Signup and login; PBKDF2-HMAC-SHA256 password hashing (600k iterations); issues HS256 JWTs; publishes new-user events to SQS |
| **orders-api** | API Gateway | Create orders, compute totals from live menu prices, initiate Stripe PaymentIntents (INR), list user orders with ownership checks |
| **payments-webhook** | API Gateway | Verify Stripe webhook signatures; update order status via `payment_intent_id` GSI lookup |
| **jwt-authorizer** | API Gateway | Validate JWT signature and expiry (HMAC-SHA256); attach verified `user_id` to downstream context - never trusts a client-supplied identity |
| **mcp-server** | API Gateway (`POST /mcp`) | Read-only MCP tool server: recent orders, spending summary, order status, top-rated restaurants, restaurant menu. Same code path as `mcp-render-server/`, deployed separately as a Lambda |
| **welcome-notifier** | SQS | Async side-effect on signup (simulated welcome email) - decoupled from the signup response path |
| **signup-digest** | EventBridge (daily) | Scheduled job reporting total registered users |
| **seed-restaurants** | Manual invoke | One-time population of sample restaurants and menu items |

All application Lambdas run **Python 3.12** and are packaged and deployed via Terraform.

---

### MCP / AI Assistant Layer

The same MCP server implementation is deployed two ways, both exposing five read-only tools (`get_recent_orders`, `get_spending_summary`, `get_order_status`, `get_top_rated_restaurants`, `get_restaurant_menu`) backed directly by DynamoDB via `boto3`:

| Deployment | Location | Transport | Runtime |
|------------|----------|-----------|---------|
| **AWS Lambda** | `lambda/mcp-server/`, `POST /mcp` on the existing API Gateway | Lambda proxy | Python 3.12, `foodie-mcp-server-role` (least-privilege: `GetItem`/`Query`/`Scan` on orders/restaurants/menu_items only - no `users` table access, no write actions) |
| **Standalone (Render)** | `mcp-render-server/server.py` | Streamable HTTP (`mcp.server.mcpserver.MCPServer`, mounted at `/mcp`) | Python, own IAM user with the same read-only DynamoDB scope, credentials supplied via Render environment variables |

The Render deployment additionally exposes a `GET /health` route (via `custom_route`) so Render's health checks get a `200` instead of a `404` against the MCP server's only other route.

**Langflow / AI Central flow:** a flow built on Aptean's internal AI Central platform wires these tools into a conversational agent:

```
Webhook  ->  Parser (Stringify)  ->  Digital Coworker (agent + MCP Tools)  ->  Chat Output
```

The agent ("Digital Coworker") is instructed to only use a verified `user_id` from its session context for personalized tools, and to never trust a `user_id` appearing in the free-text conversation - since the flow currently has no JWT-verification step, this instruction is the only thing standing between a request and calling `get_recent_orders`/`get_spending_summary`/`get_order_status` for an arbitrary user (see limitations below).

**Frontend integration:** the `ChatWidget` component POSTs `{ message, session_id }` to the flow's webhook URL and renders whatever text field comes back in the response.

---

### Data Stores

| Store | Table / Key Design | Used By |
|-------|-------------------|---------|
| **DynamoDB - restaurants** | PK: `id` | restaurants-api, orders-api, seed-restaurants, mcp-server |
| **DynamoDB - menu_items** | PK: `restaurant_id`, SK: `menu_item_id` | restaurants-api, orders-api, mcp-server |
| **DynamoDB - orders** | PK: `user_id`, SK: `order_id`; GSI on `payment_intent_id` | orders-api, payments-webhook, mcp-server |
| **DynamoDB - users** | PK: `email` | auth-login, signup-digest |
| **Upstash Redis** | REST API; keys `restaurants:all`, `restaurant:{id}` | restaurants-api (read-through cache) |

All DynamoDB tables use **PAY_PER_REQUEST** billing - no provisioned capacity to manage. The MCP server reads these tables directly via `boto3`, bypassing `restaurants-api`/`orders-api` and their Upstash cache layer entirely.

---

### Messaging & Scheduling

| Service | Resource | Flow |
|---------|----------|------|
| **SQS** | `foodie-new-users` | auth-login -> queue -> welcome-notifier (batch size 10) |
| **EventBridge** | `rate(1 day)` rule | signup-digest daily user count report |

---

### External Integrations

| Service | Usage |
|---------|-------|
| **Stripe** | PaymentIntent creation (orders-api); webhook-driven status updates (payments-webhook); test-mode card payments in frontend |
| **Upstash Redis** | External serverless cache for restaurant reads - reduces DynamoDB scan/query load |
| **Langflow / AI Central** | Hosts the conversational agent flow that the ChatWidget talks to; orchestrates MCP tool calls against the MCP server |

---

### Infrastructure (`terraform/`)

Infrastructure is fully defined as code with Terraform (AWS provider ~> 5.0):

- **Compute:** 9 Lambda functions (including `mcp-server`) with per-function or shared IAM roles
- **API:** API Gateway REST API with explicit deployment triggers
- **Storage:** S3 bucket, 4 DynamoDB tables, SQS queue
- **CDN:** CloudFront distribution in front of S3
- **Security:** Least-privilege IAM - dedicated roles for the JWT authorizer (logs only), payments webhook (orders `Query`/`UpdateItem` only), and the MCP server (`GetItem`/`Query`/`Scan` on three tables only)
- **Secrets:** JWT secret, Stripe keys, Upstash credentials passed as Terraform variables (never committed - `terraform.tfvars` is gitignored)

---

## Key Design Highlights

### Security-first auth and payments

- **Passwords** hashed with PBKDF2 (600,000 iterations) and per-user salt; compared with `hmac.compare_digest`.
- **JWTs** are HS256-signed, 1-hour TTL; protected routes use a dedicated authorizer Lambda with minimal IAM scope.
- **Order identity** comes from authorizer context - the API never trusts `user_id` from the request body.
- **Payment truth** comes only from Stripe webhooks with signature verification and replay protection (5-minute timestamp window). The frontend cannot mark an order as paid.

### Event-driven decoupling

Signup publishes to SQS so the HTTP response is not blocked by welcome-email logic. EventBridge runs periodic digest jobs independent of user traffic. This pattern scales side-effects without slowing the critical path.

### Cache with graceful degradation

Restaurant listings and details are cached in Upstash Redis for 60 seconds. Cache failures are logged and silently fall back to DynamoDB - a broken cache never breaks a user request.

### Least-privilege IAM

Four IAM patterns instead of one monolithic role:

1. **Shared app role** - DynamoDB + SQS for core Lambdas
2. **JWT authorizer role** - CloudWatch Logs only
3. **Payments webhook role** - Query/UpdateItem on orders table only
4. **MCP server role** - GetItem/Query/Scan on orders, restaurants, and menu_items only; deliberately excludes the `users` table and all write actions, since the assistant only ever needs to answer questions, never mutate state

### AI assistant scoped to read-only tools

The MCP server is intentionally limited to five read-only tools with no path to placing orders, changing account data, or touching the `users` table - the blast radius of a prompt-injected or misused agent call is capped at "can read order/restaurant data," never "can act on the user's behalf."

### Serverless economics

No servers, no connection pools, no always-on cost. DynamoDB on-demand, Lambda per-invocation billing, and S3/CloudFront static hosting keep the stack suitable for learning projects and low-traffic production workloads.

### Infrastructure as code

Every AWS resource - routes, CORS, Lambda permissions, deployment triggers, GSI definitions, the MCP server's IAM role - is in Terraform. Route changes trigger redeployment via `filesha1` triggers to avoid stale API Gateway snapshots.

---

## Current Limitations & Follow-ups

- **`/mcp` (Lambda) and the Render MCP endpoint are both unauthenticated.** Anyone with the URL can call any of the five tools for any `user_id`. Access control today rests entirely on an instruction in the agent's prompt ("never trust a user_id from the conversation text") rather than any enforced check - the same JWT-authorizer pattern already used for `/orders` should be extended here before this handles real user data.
- **The chat webhook's request/response schema is unconfirmed.** `ChatWidget`/`api.js` POST `{ message, session_id }` and try several likely response field names (`message`, `output`, `text`, `response`); this should be replaced with the actual AI Central webhook contract once verified.
- **Two parallel MCP deployments exist** (Lambda + Render) serving the same tools. Worth deciding whether both are needed long-term or whether one should be retired once the Langflow integration settles on a single target.
- **Cart persistence is login-agnostic.** `CartContext` stores items in `localStorage` keyed to the browser, not the account - it survives logout and is shared by any user of that browser/profile.

---

## Project Structure

```
Food-Ordering/
├── frontend/              # React SPA (Vite)
│   ├── src/
│   │   ├── pages/         # Home, RestaurantDetail, Cart, Orders, Login, Signup
│   │   ├── components/    # Navbar, RestaurantCard, MenuItemCard, ChatWidget
│   │   ├── context/       # UserContext, CartContext
│   │   └── api.js         # Axios client + JWT interceptor + chat webhook client
├── lambda/
│   ├── auth-login/
│   ├── restaurants-api/
│   ├── orders-api/
│   ├── payments-webhook/
│   ├── jwt-authorizer/
│   ├── mcp-server/
│   ├── welcome-notifier/
│   ├── signup-digest/
│   └── seed-restaurants/
├── mcp-render-server/     # Standalone MCP server (same tools as lambda/mcp-server), deployed to Render
│   ├── server.py
│   ├── requirements.txt
│   └── .env.example
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
- A Render account (for the standalone MCP server) and access to the AI Central/Langflow instance the ChatWidget talks to

### 1. Deploy infrastructure

```bash
cd terraform
# Create terraform.tfvars with the variables defined in variables.tf
terraform init
terraform apply
```

Note the outputs: `api_gateway_url`, `cloudfront_url`, `s3_bucket_name`, `seed_lambda_name`. This also provisions the `mcp-server` Lambda, its IAM role, and the `/mcp` route.

### 2. Seed sample data

Invoke the **seed-restaurants** Lambda once from the AWS Console (Test with an empty event).

### 3. Configure Stripe webhook

Register `https://<api-gateway-url>/prod/webhooks/stripe` in the Stripe dashboard for `payment_intent.succeeded` and `payment_intent.payment_failed`. Copy the signing secret into `terraform.tfvars` and re-apply if needed.

### 4. Deploy the standalone MCP server (Render)

```bash
cd mcp-render-server
cp .env.example .env   # fill in real values, then paste into Render's Environment tab
```

Set `ORDERS_TABLE`, `RESTAURANTS_TABLE`, `MENU_ITEMS_TABLE` (from the Terraform outputs / DynamoDB console), `AWS_REGION`, and `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` for a dedicated IAM user scoped to `GetItem`/`Query`/`Scan` on those three tables. Deploy from the connected GitHub repo; Render injects `PORT` automatically.

### 5. Point the Langflow/AI Central flow at the MCP server

In the flow's **MCP Tools** node, connect to the Render URL's `/mcp` endpoint using the **Streamable HTTP** transport (not SSE). Set the **Digital Coworker** agent's instructions to use the connected tools and to only trust a verified `user_id` from session context, never one typed in chat.

### 6. Build and deploy frontend

```bash
cd frontend
echo "VITE_API_URL=<api_gateway_url>" > .env
echo "VITE_STRIPE_PUBLISHABLE_KEY=pk_test_..." >> .env
echo "VITE_CHAT_WEBHOOK_URL=<ai-central-webhook-url>" >> .env
npm install
npm run build
aws s3 sync dist/ s3://<s3_bucket_name> --delete
aws cloudfront create-invalidation --distribution-id <cloudfront-distribution-id> --paths "/*"
```

The invalidation step matters: CloudFront caches responses for up to an hour by default, so without it a fresh deploy can appear not to have taken effect.

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
| `VITE_CHAT_WEBHOOK_URL` | Langflow/AI Central webhook URL that triggers the assistant flow |

### MCP Server - Render (`mcp-render-server/.env`)

| Variable | Description |
|----------|-------------|
| `ORDERS_TABLE`, `RESTAURANTS_TABLE`, `MENU_ITEMS_TABLE` | DynamoDB table names (must match exactly, case-sensitive) |
| `AWS_REGION` | Region the tables are deployed in |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Credentials for a dedicated IAM user scoped to read-only access on the three tables above (Render has no AWS IAM role integration, so explicit credentials are required) |

---

## Tech Stack Summary

| Layer | Technologies |
|-------|-------------|
| Frontend | React 19, Vite 8, React Router 7, Axios, Stripe.js |
| Backend | Python 3.12, AWS Lambda, API Gateway |
| AI / Agents | MCP (Model Context Protocol) via `mcp.server.mcpserver`, Langflow (Aptean AI Central) |
| Database | Amazon DynamoDB |
| Cache | Upstash Redis (REST) |
| Payments | Stripe PaymentIntents + Webhooks |
| Messaging | Amazon SQS, Amazon EventBridge |
| Hosting | Amazon S3, Amazon CloudFront, Render (MCP server) |
| IaC | Terraform (AWS provider ~> 5.0) |
