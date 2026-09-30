# Cloud Deployment

## Approach A - Student-friendly / Free-tier

1. **Database**: create a free PostgreSQL instance on Supabase or Neon. Copy its connection string.
2. **Backend**: push this repo to GitHub, connect it to Render (or Railway/Fly.io) as a Web Service.
   - Build command: `pip install -r requirements.txt -r requirements-cloud.txt`
   - Start command: `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`
   - Environment variables: set `DATABASE_URL` (from Supabase/Neon), `JWT_SECRET` (a long random
     value), `CORS_ORIGINS` (your frontend's URL).
3. **Frontend**: the bundled `frontend/public` demo is served by the same FastAPI process, so no
   separate hosting is required for Option A. For Option B/C (React), deploy `frontend/` to Vercel/
   Netlify and point `CORS_ORIGINS`/the API base URL at each other.
4. **Real-time**: WebSockets work on Render's free tier as long as the client sends periodic pings
   (this project's frontend does) so the connection is treated as active and the service is not spun
   down mid-session; a cold start after 15 minutes of full inactivity is expected on the free tier.
5. **Notifications**: stay in-app (no paid email/SMS provider needed) unless you wire up a free-tier
   email provider (e.g. Resend, Brevo) in `cloud/notification_service.py::_external_channels`.

## Approach B - Enterprise Cloud (AWS example)

```
Users -> CloudFront (CDN, static frontend) -> API Gateway (REST + WebSocket API)
       -> AWS Lambda (this FastAPI app via Mangum, or containers on ECS Fargate)
       -> RDS PostgreSQL (managed database) / DynamoDB for high-throughput tables
Authentication: Amazon Cognito (replaces cloud/auth_service.py)
Notifications:  Amazon SNS (push/SMS) + SES (email)
Monitoring:     CloudWatch Logs + Alarms
```

**Azure equivalent**: Front Door (CDN) -> API Management -> Azure Functions/App Service -> Azure
Database for PostgreSQL; Azure AD B2C for auth; Azure Notification Hubs; Azure Monitor.

**GCP equivalent**: Cloud CDN -> API Gateway -> Cloud Run/Cloud Functions -> Cloud SQL for PostgreSQL;
Firebase Auth; Firebase Cloud Messaging; Cloud Logging/Monitoring.
