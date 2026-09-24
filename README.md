# LangGraph WhatsApp Sales Agent

A **LangGraph-powered WhatsApp Business agent** that handles customer DMs, responds to enquiries, de-escalates complaints, and closes sales — 24/7 — on behalf of any business. Built to be sold to business owners as a done-for-you automation service.

---

## What It Does

| Customer Message | Agent Response |
|---|---|
| "How much is the property?" | Answers with product details + price, asks qualifying question |
| "Can you do ₦80m?" | Negotiates within allowed discount range, doesn't break price floor |
| "I'm not happy with your service" | Empathizes, offers resolution, escalates if unresolved |
| "I'd like to book a viewing" | Confirms interest, collects lead info, works toward booking |
| Random off-topic messages | Politely redirects to business topics |

**Guardrails always active:**
- Never quotes a price below the configured minimum
- Never uses forbidden phrases set by the business owner
- Escalates to the human owner after a set number of turns
- Logs every conversation for the owner to review

---

## Setup Guide

### Step 1: Clone & Install

```bash
cd langgraph-wa-agent
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 2: Set Up Your Environment

```bash
cp .env.example .env
```

Open `.env` and fill in:
- `OPENROUTER_API_KEY` — get free key at https://openrouter.ai/keys
- `WHATSAPP_PHONE_NUMBER_ID` — from Meta dashboard → Your App → WhatsApp → API Setup
- `WHATSAPP_ACCESS_TOKEN` — generate a permanent token (see below)
- `WHATSAPP_VERIFY_TOKEN` — make up any secret string (e.g. `my_secret_123`)

### Step 3: Configure the Business

Edit `config/business_config.yaml` with the client's:
- Business name, products, prices
- Tone of voice
- FAQs
- Guardrails (forbidden phrases, price floors, discount limits)
- Owner's WhatsApp number for escalation alerts

### Step 4: Run the Server

```bash
python app.py
```

Server starts on `http://localhost:8000`.

### Step 5: Expose to Internet (Demo Mode)

Install ngrok: https://ngrok.com/download

```bash
ngrok http 8000
```

Copy the HTTPS URL (e.g. `https://abc123.ngrok.io`).

### Step 6: Configure Meta Webhook

1. Go to: Meta Dashboard → CartIO App → WhatsApp → Configuration
2. Set **Callback URL**: `https://abc123.ngrok.io/webhook`
3. Set **Verify Token**: same value as `WHATSAPP_VERIFY_TOKEN` in your `.env`
4. Click **Verify and Save**
5. Subscribe to: `messages`

### Step 7: Test It

Send a WhatsApp message to your business test number. Watch the terminal logs.

---

## Getting a Permanent WhatsApp Access Token

The default token from Meta expires in 24 hours. For the demo, that's fine.
For production (paying clients), use the **System User** method:

1. Meta Business Suite → Business Settings → System Users → Add System User
2. Assign WhatsApp app with `whatsapp_business_messaging` permission
3. Generate token → never expires

---

## Swapping Clients

To configure this agent for a different client:
1. Copy `config/business_config.yaml` to `config/client_name_config.yaml`
2. Fill in their business details
3. Update `.env`: `BUSINESS_CONFIG_PATH=config/client_name_config.yaml`
4. Restart the server

No code changes needed. This is your **productized delivery mechanism**.

---

## Project Structure

```
langgraph-wa-agent/
├── app.py                        # FastAPI webhook server (entry point)
├── config/
│   └── business_config.yaml      # ← Client configuration (swap per client)
├── src/
│   ├── state.py                  # LangGraph conversation state schema
│   ├── graph.py                  # LangGraph StateGraph definition
│   ├── llm.py                    # OpenRouter LLM client
│   ├── whatsapp.py               # WhatsApp Cloud API client
│   ├── config_loader.py          # Business config reader & helpers
│   └── nodes/
│       ├── classify_intent.py    # Intent classifier (LLM)
│       ├── handle_enquiry.py     # Product enquiry + sales closer (LLM)
│       ├── handle_complaint.py   # Complaint handler (LLM)
│       ├── apply_guardrails.py   # Rule enforcement (deterministic)
│       └── send_reply.py         # WhatsApp sender + logger
├── requirements.txt
├── .env.example
└── conversations.jsonl           # Auto-created: audit log of all conversations
```

---

## Pitch Talking Points

When presenting to a business owner:

> *"Right now, your team manually responds to every WhatsApp enquiry. Some messages get delayed, some replies are inconsistent, and late-night messages go unanswered. This agent handles all of that — instantly, consistently, 24/7. And every reply follows your rules exactly — it will never quote the wrong price or make promises you haven't approved."*

> *"You stay in control. If a conversation gets complicated, the agent automatically pings you on WhatsApp so you can step in personally."*

> *"I configure it for your business — your products, your prices, your tone. Setup takes 2 days. I can show you a live demo right now."*
