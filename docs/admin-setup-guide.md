# Super-admin setup guide

Everything a super admin needs to know to onboard a new organization from
scratch, verify each channel works, and hand it off to the org's staff.

Read this if you're the platform operator setting up the first few orgs.
If you're an org's staff member, see `docs/org-staff-guide.md` instead.

---

## Table of contents

1. [Prerequisites](#prerequisites)
2. [Creating your first org](#creating-your-first-org)
3. [Walking the 9-step setup wizard](#walking-the-9-step-setup-wizard)
4. [Verifying channels in the Test Center](#verifying-channels-in-the-test-center)
5. [Adding org staff and handing off](#adding-org-staff-and-handing-off)
6. [Daily operations](#daily-operations)
7. [When things go wrong](#when-things-go-wrong)

---

## Prerequisites

Before creating an org you should have:

- **Business info from the customer** — company name, industry, timezone, address, phone, contact email.
- **Working hours** — day-by-day open/close times, plus any holidays for the next 12 months.
- **LLM provider API keys for the customer's account** — at least one of:
  - Anthropic (get from console.anthropic.com)
  - OpenAI (get from platform.openai.com)
  - Cohere (get from dashboard.cohere.com)
  - Store these securely; you'll paste them into the setup wizard's API Keys step.
- **Channel credentials** for whichever channels the customer wants:
  - **Web chat**: no external credentials needed — needs at least one LLM key.
  - **WhatsApp**: Meta Business Manager access — a WABA (WhatsApp Business Account) with an approved phone number, the permanent access token, and the phone_number_id.
  - **Voice**: A Retell account (retellai.com) and its API key. You'll create the actual agent later from the Test Center.
- **Google Calendar** (optional, only if booking is enabled): the customer must share their Google Calendar with the platform service account. Get the calendar ID from the calendar's settings page.
- **Knowledge base content**: at minimum a website URL for the crawler to ingest; ideally also a CSV or Markdown file with FAQ pairs.

## Creating your first org

1. Log in to the super-admin panel using the SUPER_ADMIN_EMAIL configured in the deployment.
2. Navigate to **Organizations** in the sidebar.
3. Click **Add Organization** (top right).
4. Fill in:
   - **Name** — as the customer wants it displayed to their own customers.
   - **Industry** — pick from the dropdown. Determines default prompt suggestions later.
   - **Timezone** — IANA name (e.g. `America/New_York`, `Europe/Amsterdam`).
5. Click **Create Organization**. The org row appears in the list with **Setup Status = Not Started**.
6. Click **Setup** on the row to open the wizard.

## Walking the 9-step setup wizard

Each step saves independently — you can back-navigate and edit any prior step without losing later ones.

### 1. Basic Info

You've already filled the required fields at creation. Add optional contact details (address, phone, email) here — these show up in the AI's replies and on customer-facing surfaces.

### 2. Working Hours

Set open/close per weekday. The AI uses this to route out-of-hours conversations differently (typically to escalation or a "we'll get back to you" message).

Holidays are optional but recommended — the AI will proactively let a caller know if today is a holiday.

### 3. Channels

Toggle on the channels the customer wants: **Web chat**, **WhatsApp**, **Voice**. You can turn any of these back on later from the Test Center.

### 4. API Keys

Paste the customer's LLM provider keys. **Keys are encrypted per-org with a key derived from `MASTER_ENCRYPTION_KEY` + the org's UUID** — a database dump alone can't decrypt them.

**Recommended:** enable at least two providers (e.g. Anthropic + OpenAI) so the fallback path activates if one provider has an outage.

If WhatsApp is enabled: also paste the WhatsApp permanent access token and phone_number_id. If Voice is enabled: paste the Retell API key.

### 5. Knowledge Base

Three ways to fill the KB:

- **Crawl a website** — paste the customer's homepage URL. The crawler follows internal links up to a depth of 2, extracts readable text, chunks it, embeds it. Best for company info, services, hours.
- **Bulk import a file** — click **Bulk import** and upload a CSV (one column of text, or two columns: title, content) or a Markdown file (chunks split on H2 headings) or a PDF (parsed client-side into text). Use this for FAQ documents, policies, or product catalogs.
- **Manual chunks** — for tuning specific answers by hand. Use sparingly; the automated methods scale better.

Aim for **50-200 chunks total**. Too few and the RAG hits the confidence threshold and escalates too often. Too many and retrieval accuracy degrades.

### 6. Booking (optional)

Only relevant if the customer wants the AI to schedule appointments.

- **Services** — list the bookable services with duration.
- **Calendar** — enable Google Calendar integration. Requires the customer to have shared their calendar with the platform service account and pasted their calendar ID.

### 7. System Prompts

The AI's voice, guardrails, and personality. Four required fields plus one optional:

- **Greeting message** — the first thing the AI says on a new conversation.
- **Personality** — tone descriptor (`warm and professional`, `energetic and friendly`, etc.).
- **Escalation rules** — when to hand off to a human. Common: distressed callers, medical emergencies, billing disputes, explicit requests for a human.
- **Off-topic handling** — what to say when a message isn't about the business.
- **Custom system prompt** (optional) — extra guardrails, brand voice, industry-specific rules. Click **Load template** to seed from one of the 10 pre-built industry templates (Dental, Medical, Salon, Legal, Real Estate, Home Services, Fitness, Veterinary, Retail, Software, Generic). Placeholders like `{{org_name}}` are auto-substituted from Basic Info.

### 8. Staff Access

Add staff email addresses. Each becomes an `org_staff` user who can log in via OTP and access the org's inbox, appointments, and settings. Org staff can invite additional teammates themselves once the org is active.

### 9. Review & Activate

Confirm every step shows green. Click **Activate**. The org's `is_active` flips to true; the AI receptionist goes live on every enabled channel.

## Verifying channels in the Test Center

After activation, open **Organizations → [org row] → Test** (right of the Setup button). The Test Center shows one card per enabled channel with real-time verification.

### Web chat

- Shows a live embed of the widget on a blank preview page. Click the chat bubble in the corner and start a conversation the way an end user would.
- **What to verify**: greeting matches your System Prompts setting, RAG returns accurate answers to questions about the customer's business, off-topic questions get the off-topic response, escalation triggers work (try "I need to speak to someone").
- **What to copy for the customer**: the embed code snippet below the widget. They paste this on their website.

### WhatsApp

- Verify status shows **Configured** (WhatsApp API key active) and **Verified** (Meta's webhook signature check working).
- Send a real WhatsApp message from your phone to their number. Watch the message stream through the widget below.
- If not receiving: check that the webhook URL registered with Meta matches `{APP_PUBLIC_URL}/api/public/webhooks/whatsapp` exactly.

### Voice

- **Retell Agent ID** shows the ID pushed by the provisioner.
- **Custom LLM URL** status:
  - ✅ **Provisioned** = Retell will call our backend on this org's WebSocket URL.
  - ⚠ **Not Provisioned** = the agent's URL in Retell doesn't match — click **Re-provision Agent**.
  - **Unknown** = we couldn't check (missing RETELL_API_KEY, Retell down).
- **Test in Retell Dashboard** opens Retell's own test-call interface. Use it to make a real call to the AI.
- **Re-provision Agent** re-pushes the correct URLs from `APP_PUBLIC_URL`. Use this after `APP_PUBLIC_URL` changes (e.g. after moving from ngrok to Railway).
- **Create New Agent** creates a fresh Retell agent already wired to our backend and saves its ID. Use when a hand-made Retell agent misbehaves.

## Adding org staff and handing off

Once the customer's basic staff are added in step 8, hand off:

1. Send each staff member their login email + the platform URL.
2. Have them log in via OTP.
3. They'll land on the org-staff dashboard, not the super-admin panel.
4. Walk them through the **Inbox** (live conversations), **Escalations** (things flagged for human attention), **Appointments** (bookings from the AI), **Contacts** (customer directory), and **Knowledge Base** (they can add/edit chunks).
5. Show them the **Team** section in Settings — they can invite additional teammates themselves.
6. Point them at `docs/org-staff-guide.md` for their day-to-day workflows.

## Daily operations

### Monitoring

- **Super-admin Dashboard** — platform-wide metrics: messages/day, top orgs by volume, channel breakdown, escalation rate, estimated LLM cost. Refresh at the top-right, or change the time window (7d / 30d / 90d).
- **Per-org Analytics** — same view scoped to a single org. Available under Organizations → [org row] → View Details.
- **Sentry** — for exceptions and unusual error rates. Set alert rules for anything you want notified about.
- **Railway logs** — for the raw structured JSON stream when Sentry doesn't paint the whole picture.

### Common ops tasks

- **Rotate an org's LLM key** — Settings wizard → API Keys → paste new value → save. Old key is discarded.
- **Change an org's plan** — [not yet in the UI; edit `organizations.plan` in the DB directly for now, or use the API].
- **Deactivate an org** — Organizations list → row action menu → Delete. This is a soft delete — the org's data is retained; only `is_active` flips to false. Reactivate the same way.
- **Deactivate a user** — Users tab → row action menu → Deactivate. Immediately invalidates their refresh token.
- **Export audit logs** for compliance — Audit Logs page → **Export CSV** button.

### Weekly

- Skim the **Audit Logs** page for anything unexpected (unfamiliar IPs, high volume of key rotations, unusual invite patterns).
- Review the **Analytics Dashboard's** per-org table. Any org with an escalation rate above 20% needs attention — either their KB is too thin or their escalation rules are too aggressive.

### Monthly

- Run the [backup-restore drill](backup-restore-runbook.md) against a scratch DB.
- Rotate `JWT_SECRET_KEY` (optional but good hygiene). Every user has to re-login after.

## When things go wrong

### OTP emails not arriving

1. Check `SUPER_ADMIN_EMAIL` (or the affected org staff email) is spelled exactly right in the DB.
2. Check Brevo dashboard → Transactional → Logs for the message. If nothing there, Brevo rejected the send.
3. Check the app logs for `brevo_send_failed` events. The `response_body` field shows Brevo's exact rejection reason.
4. Common causes: unactivated Brevo account, unverified sender domain, quota exhausted, invalid API key.

### Voice test webhook returns 404

Almost always means the Custom LLM URL registered in Retell doesn't match the current backend origin.

1. Check `APP_PUBLIC_URL` on Railway — it should match the deployed backend's URL.
2. In the Test Center, click **Re-provision Agent**. This pushes the corrected URL to Retell.
3. If still 404, verify the agent's Custom LLM URL in Retell's dashboard is exactly `wss://<APP_PUBLIC_URL>/api/public/retell/llm/{org_id}`.

### An org's AI is escalating too often

1. Check the **KB size** — under 30 chunks and it will escalate on almost anything.
2. Check the **confidence threshold** in the RAG pipeline — default is 0.25. Above 0.30 gets very picky.
3. Check the **escalation rules** in System Prompts — overly broad rules like "escalate if the customer asks a question" fire on everything.

### An org's AI is answering wrong questions

1. Check the KB for stale content — if you re-crawled the website recently, the string-cache invalidator (`invalidate_org`) should have cleared old cached answers. If not, wait 5 minutes for the cache TTL, or manually flush Redis: `redis-cli --scan --pattern 'voice_qcache:{org_id}:*' | xargs redis-cli del`.
2. Check the org's system prompt hasn't drifted from what the KB actually contains.
3. Check the RAG confidence gate isn't set too low — if it's serving weak matches, the answers will feel wrong even when the KB is fine.

### Locked out of super-admin

If the super_admin's refresh token is invalidated and they can't get an OTP (e.g. Brevo is down):

1. Read the OTP straight from Redis:
   ```
   redis-cli GET "otp:<email>"
   ```
2. Or, temporarily set `APP_ENV=development` on Railway — this exposes `/api/debug/otp?email=<email>` (dev-only endpoint) so you can fetch the OTP over HTTP.
3. **Remember to set `APP_ENV=production` back after.** Development mode exposes `/docs` and logs OTP codes to structured logs.

### Everything's on fire

Roll back:

1. Railway → backend service → Deployments → last known good deploy → **Redeploy**.
2. Never disable Sentry or CI to unblock a deploy — they exist to catch exactly this class of decision.
