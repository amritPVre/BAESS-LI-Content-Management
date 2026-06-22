# Zoho Mail OAuth — step-by-step (inbox reply sync)

This enables **Sync replies (Zoho Mail)** on the **Email Campaigns** page. The app reads your Zoho Mail **Inbox** and marks outreach rows as **replied** when the sender email matches a contact you emailed.

**Important:** Use the same mailbox as `ZEPTOMAIL_REPLY_TO` in secrets (e.g. `konnect@baesslabs.com`).

---

## Which Zoho data center?

| Your mail login URL | `ZOHO_ACCOUNTS_BASE` | `ZOHO_MAIL_API_BASE` |
|---------------------|----------------------|----------------------|
| mail.zoho.com | `https://accounts.zoho.com` | `https://mail.zoho.com/api` |
| mail.zoho.in | `https://accounts.zoho.in` | `https://mail.zoho.in/api` |
| mail.zoho.eu | `https://accounts.zoho.eu` | `https://mail.zoho.eu/api` |

Use the same region for API Console, OAuth URLs, and secrets.

---

## Step 1 — Create a Zoho API client

1. Open [Zoho API Console](https://api-console.zoho.com/) (or [api-console.zoho.in](https://api-console.zoho.in) for India).
2. Click **Add Client** → **Server-based Applications**.
3. Fill in:
   - **Client Name:** `BAESS Outreach Reply Sync`
   - **Homepage URL:** `https://baess.app` (or any valid URL)
   - **Authorized Redirect URI:** `http://localhost:8080` (only needed once to get the refresh token)
4. Click **Create**.
5. Copy **Client ID** and **Client Secret** → save for secrets as `ZOHO_CLIENT_ID` and `ZOHO_CLIENT_SECRET`.

---

## Step 2 — Choose OAuth scopes

When generating the authorization URL (Step 3), include these scopes (comma-separated):

```
ZohoMail.accounts.READ,ZohoMail.messages.READ
```

- `ZohoMail.accounts.READ` — list mail accounts (to get `accountId`)
- `ZohoMail.messages.READ` — read Inbox messages for reply matching

---

## Step 3 — Get an authorization code (browser, one time)

Replace `YOUR_CLIENT_ID` and pick the correct accounts host (`.com`, `.in`, or `.eu`).

**US (.com):**

```
https://accounts.zoho.com/oauth/v2/auth?scope=ZohoMail.accounts.READ,ZohoMail.messages.READ&client_id=YOUR_CLIENT_ID&response_type=code&access_type=offline&prompt=consent&redirect_uri=http://localhost:8080
```

**India (.in):**

```
https://accounts.zoho.in/oauth/v2/auth?scope=ZohoMail.accounts.READ,ZohoMail.messages.READ&client_id=YOUR_CLIENT_ID&response_type=code&access_type=offline&prompt=consent&redirect_uri=http://localhost:8080
```

1. Paste the URL into your browser while logged into the **Zoho account that owns `konnect@baesslabs.com`**.
2. Click **Accept**.
3. Browser redirects to `http://localhost:8080/?code=1000.xxxx...` (page may not load — that is OK).
4. Copy the **`code`** query parameter from the address bar (everything after `code=` and before `&` if present).

`access_type=offline` and `prompt=consent` are required so Zoho returns a **refresh token**.

---

## Step 4 — Exchange code for refresh token

Run in terminal (PowerShell). Replace region, client values, and `PASTE_CODE_HERE`.

**US (.com):**

```powershell
$code = "PASTE_CODE_HERE"
$clientId = "YOUR_CLIENT_ID"
$clientSecret = "YOUR_CLIENT_SECRET"
$uri = "https://accounts.zoho.com/oauth/v2/token?code=$code&client_id=$clientId&client_secret=$clientSecret&redirect_uri=http://localhost:8080&grant_type=authorization_code"
Invoke-RestMethod -Uri $uri -Method Post
```

**India (.in):** use `https://accounts.zoho.in/oauth/v2/token?...` instead.

Response JSON includes:

- `access_token` — short-lived (use for Step 5 now)
- `refresh_token` — **save this** as `ZOHO_REFRESH_TOKEN` in secrets (shown only on first consent)

---

## Step 5 — Get your Zoho Mail account ID

Use the `access_token` from Step 4 (valid ~1 hour).

**US (.com):**

```powershell
$token = "PASTE_ACCESS_TOKEN"
Invoke-RestMethod -Uri "https://mail.zoho.com/api/accounts" -Headers @{ Authorization = "Zoho-oauthtoken $token" }
```

**India (.in):** use `https://mail.zoho.in/api/accounts`.

In the response, find the account for `konnect@baesslabs.com` and copy **`accountId`** → `ZOHO_ACCOUNT_ID` in secrets.

Example shape:

```json
{
  "data": [
    {
      "accountId": "1234567890123456789",
      "primaryEmailAddress": "konnect@baesslabs.com"
    }
  ]
}
```

---

## Step 6 — Add to Streamlit secrets

Local: `.streamlit/secrets.toml`  
Cloud: Streamlit **App settings → Secrets**

```toml
ZOHO_CLIENT_ID = "1000.xxxx"
ZOHO_CLIENT_SECRET = "xxxx"
ZOHO_REFRESH_TOKEN = "1000.xxxx"
ZOHO_ACCOUNT_ID = "1234567890123456789"
ZOHO_MAIL_API_BASE = "https://mail.zoho.com/api"
ZOHO_ACCOUNTS_BASE = "https://accounts.zoho.com"
```

Restart the app (or redeploy on Cloud).

---

## Step 7 — Test in the app

1. Open **Outreach → Email Campaigns → Sync status**.
2. Click **Sync replies (Zoho Mail)**.
3. You should see: `Scanned N inbox message(s); M matched as replies.`

If you get an auth error:

- Wrong data center → fix `ZOHO_ACCOUNTS_BASE` / `ZOHO_MAIL_API_BASE`
- Expired refresh token → repeat Steps 3–4 with `prompt=consent`
- Wrong mailbox → `ZOHO_ACCOUNT_ID` must match the inbox that receives replies to `ZEPTOMAIL_REPLY_TO`

---

## How matching works

- Only **`sent`** outreach rows (not bounced, not already replied) are checked.
- Inbox sender email is compared to the **contact email** you originally sent to.
- Replies to **`ZEPTOMAIL_REPLY_TO`** land in this inbox — that is why the account must match.

Bounces are handled separately via **Sync delivery status** (ZeptoMail logs), not Zoho Mail.

---

## Security notes

- Never commit `secrets.toml` or paste live tokens into `secrets.example.toml`.
- Rotate the refresh token if it is ever exposed.
- The refresh token does not expire unless revoked; the app exchanges it for a new access token on each sync.
