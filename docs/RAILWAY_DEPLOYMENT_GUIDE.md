# Campus Library Management System - Railway Deployment Guide

This guide walks you through deploying the **Campus Library Management System** to [Railway](https://railway.com/) with zero hassle.

---

## Architecture Overview on Railway

The repository is pre-configured with:
- [`railway.json`](../railway.json): Railway-native config with automated build detection, `/healthz` healthchecks, and auto-restart policy.
- [`Procfile`](../Procfile): Web process declaration (`web: python scripts/auto_deploy_start.py`).
- [`Dockerfile`](../Dockerfile): Production container environment with Python 3.12, system dependencies, and non-root security.
- [`scripts/auto_deploy_start.py`](../scripts/auto_deploy_start.py): Automatic bootstrap script that:
  - Generates secure fallback tokens (`SECRET_KEY`).
  - Automatically initializes database tables (`db.create_all()`).
  - Automatically seeds the demo catalog and administrator account if the database is fresh.
  - Launches high-performance Gunicorn WSGI server bound to `$PORT`.

---

## Method 1: Deploy via Railway Web Dashboard (Recommended)

This is the fastest, cleanest method with automatic CI/CD on every `git push`.

### Step 1: Open Railway and Create New Project
1. Log into your [Railway Dashboard](https://railway.com/dashboard).
2. Click **"+ New Project"**.
3. Select **"Deploy from GitHub repo"**.
4. Choose `TECHYBOY1529/LIBRARY-MANAGEMENT-SYSTEM`.

### Step 2: (Optional but Recommended) Add PostgreSQL Database
1. In the project canvas, click **"+ New"** (top right) or press `Ctrl + K`.
2. Select **"Database"** -> **"Add PostgreSQL"**.
3. Railway will provision a Postgres instance and automatically link `DATABASE_URL` to your web service!
   *(If you skip this step, the application will automatically fall back to an internal SQLite database).*

### Step 3: (Optional) Add Redis Cache
1. Click **"+ New"** -> **"Database"** -> **"Add Redis"**.
2. Railway provides `REDIS_URL`, enabling high-performance distributed rate limiting and caching.

### Step 4: Generate Public Domain
1. Click on your **web service** card in the Railway dashboard.
2. Go to the **"Settings"** tab.
3. Scroll down to **"Public Networking"** and click **"Generate Domain"** (e.g. `library-management-system-production.up.railway.app`).
4. (Optional) Set the environment variable:
   - `PUBLIC_BASE_URL` = `https://your-generated-domain.up.railway.app`

### Step 5: Verify Deployment
1. Go to the **"Deployments"** tab to view build logs.
2. Once the status turns green (**Active**), click your public domain URL to open the live application!

---

## Method 2: Deploy via Railway CLI (From your Terminal)

The Railway CLI (`railway 5.71.0`) is already installed on your machine.

### Step 1: Login
In your terminal / PowerShell, run:
```powershell
railway login
```
*A browser window will open. Click "Approve" or "Verify" to link your Railway account.*

### Step 2: Initialize or Link Project
```powershell
railway init
```
*Follow the interactive prompt: select "Create a new project" and name it (e.g., `campus-library`).*

### Step 3: Add PostgreSQL Database Service (Optional)
```powershell
railway add -d postgres
```

### Step 4: Add Redis Service (Optional)
```powershell
railway add -d redis
```

### Step 5: Deploy Code
```powershell
railway up
```

### Step 6: Generate Public URL
```powershell
railway domain
```
*Railway will output your live URL (e.g., `https://campus-library-production.up.railway.app`).*

---

## Recommended Environment Variables

You can configure these under **Service Settings -> Variables** in the Railway Dashboard:

| Variable | Recommended Value | Description |
|---|---|---|
| `APP_ENV` | `production` | Enables strict security, HTTPS headers, and production enforcement. |
| `SECRET_KEY` | *(64-character hex string)* | Flask session signing key (auto-generated if omitted). |
| `DATABASE_URL` | *(Auto-provided by Railway Postgres)* | Database connection URI (`postgresql+psycopg://...`). |
| `REDIS_URL` | *(Auto-provided by Railway Redis)* | Redis URL for rate limiting and session storage. |
| `PUBLIC_BASE_URL` | `https://your-domain.up.railway.app` | Canonical public URL used for links and password reset emails. |
| `TRUST_PROXY` | `true` | Allows Gunicorn to trust Railway's reverse proxy headers. |
| `LIBRARY_TIMEZONE` | `Asia/Kolkata` | Configures local timezone for borrowing, renewals, and due dates. |

---

## Default Administrator Credentials

When the database is initialized on Railway for the first time, `scripts/auto_deploy_start.py` seeds a ready-to-use demo administrative account:

- **Login URL**: `https://<your-railway-domain>/auth/login`
- **Email**: `admin@library.demo`
- **Password**: `Admin@Demo123`
- **Role**: `admin` (Full access to Catalog, Issue/Return desk, Member management, Quality controls, and Audit reports)

> [!TIP]
> After logging in for the first time, navigate to your profile settings to change your password or create additional staff and student accounts.
