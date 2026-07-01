# Setup Guide

Step-by-step instructions to get **PSX Market Watch Signals** running on your own n8n instance.

---

## Prerequisites

| Requirement | Version | Purpose |
|:-----------|:--------|:--------|
| **n8n** | v1.40+ | Workflow automation platform |
| **Google Cloud project** | — | OAuth2 credentials for Sheets + Gmail |
| **OpenAI account** | — | API key for email formatting |
| **Google Sheets** spreadsheet | — | Portfolio data store |

---

## Step 1: Set Up Google Cloud Credentials

### 1.1 Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (e.g., `psx-signals`)
3. Enable these APIs:
   - **Google Sheets API**
   - **Gmail API**

### 1.2 Create OAuth2 Credentials

1. Navigate to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth 2.0 Client ID**
3. Application type: **Web application**
4. Add the n8n OAuth callback URL:
   - Self-hosted: `http://localhost:5678/rest/oauth2-credential/callback`
   - n8n Cloud: `https://your-instance.app.n8n.cloud/rest/oauth2-credential/callback`
5. Download the JSON credentials file

---

## Step 2: Create the Google Sheets Spreadsheet

Create a new Google Spreadsheet with **4 tabs** (names must match exactly):

### Tab 1: `Holding`

| Column | Type | Description |
|:-------|:-----|:-----------|
| `symbol` | Text | PSX stock ticker (e.g., `MEBL`, `OGDC`) |
| `lot_id` | Text | Unique lot identifier (e.g., `lot-1`) |
| `shares` | Number | Number of shares held in this lot |
| `avg_price` | Number | Average purchase price per share (PKR) |
| `max_trade_value` | Number | Maximum trade value for this symbol (PKR) |
| `lot_size` | Number | Minimum tradeable lot size |

### Tab 2: `Cash`

| Column | Type | Description |
|:-------|:-----|:-----------|
| `amount` | Number | Available cash (PKR). Multiple rows are summed. |

### Tab 3: `Settings`

| Column | Type | Description |
|:-------|:-----|:-----------|
| `key` | Text | Setting name (see [Configuration](CONFIGURATION.md)) |
| `value` | Text/Number | Setting value |

Minimum required settings:

```
recipient          → your-email@gmail.com
min_change_pct_buy → 1
min_change_pct_sell → -1
openai_model       → gpt-4o-mini
```

### Tab 4: `Watchlist` *(optional)*

| Column | Type | Description |
|:-------|:-----|:-----------|
| `symbol` | Text | PSX stock ticker to watch |
| `max_trade_value` | Number | Maximum trade value (PKR) |
| `lot_size` | Number | Lot size for this symbol |

---

## Step 3: Import the Workflow

1. Open your n8n editor
2. Click the **≡** menu → **Import from File**
3. Select `workflow/psx-market-watch-signals.json`
4. The workflow should appear with 8 nodes

---

## Step 4: Configure n8n Credentials

### 4.1 Google Sheets OAuth2

1. In n8n, go to **Settings → Credentials**
2. Click **Add Credential → Google Sheets OAuth2 API**
3. Enter the Client ID and Client Secret from Step 1
4. Click **Connect** and authorize access to your Google account

### 4.2 OpenAI API Key

1. Get your API key from [OpenAI Platform](https://platform.openai.com/api-keys)
2. In n8n, create a **Header Auth** credential:
   - **Name**: `Authorization`
   - **Value**: `Bearer sk-your-api-key-here`

### 4.3 Gmail OAuth2

1. In n8n, go to **Settings → Credentials**
2. Click **Add Credential → Gmail OAuth2 API**
3. Enter the same Client ID and Client Secret from Step 1
4. Click **Connect** and authorize Gmail access

---

## Step 5: Update Node References

Open each Google Sheets node in the workflow and update:

1. **Document ID** — Replace `YOUR_GOOGLE_SHEET_ID` with your spreadsheet's ID
   - The ID is the long string in the URL: `docs.google.com/spreadsheets/d/{THIS_PART}/edit`
2. **Credentials** — Select the credentials you created in Step 4

Nodes to update:
- `Read Holdings`
- `Read Cash`
- `Read Settings`

---

## Step 6: Test the Workflow

1. Click **Execute workflow** in the n8n editor
2. Verify each node shows a green checkmark with data counts:
   - `Read Holdings` → your holdings count
   - `Read Cash` → 1+ items
   - `Read Settings` → your settings count
   - `Fetch PSX Market Watch` → 1 item (HTML response)
   - `Build Signals` → 1 item (aggregated signals)
   - `OpenAI Format Signals` → 1 item (API response)
   - `Extract Email` → 1 item (formatted email)
   - `Send Signal Email` → 1 item (sent)

3. Check your inbox for the signal email

---

## Step 7: Schedule *(optional)*

To run the workflow on a schedule:

1. Replace the **Manual Trigger** node with a **Schedule Trigger** node
2. Set the cron expression for PSX trading hours:
   - PSX opens at 9:30 AM PKT, closes at 3:30 PM PKT
   - Recommended: `0 10,12,14 * * 1-5` (10 AM, 12 PM, 2 PM, Mon–Fri)
3. **Activate** the workflow (toggle in the top-right)

---

## Troubleshooting

| Issue | Solution |
|:------|:--------|
| `Read Holdings` returns empty | Check the Sheet tab name is exactly `Holding` (not `Holdings`) |
| `Fetch PSX Market Watch` fails | PSX website may be down; the workflow handles this gracefully |
| OpenAI returns error | Check API key and balance; the fallback email template will still generate |
| Gmail send fails | Re-authorize Gmail OAuth2 credentials; check Gmail API is enabled |
| `Build Signals` shows 0 market rows | PSX market may be closed; run during trading hours |

---

## Security Notes

- **Never commit credentials** — The workflow JSON in this repo has all credential IDs replaced with placeholders
- **Google Sheets acts as your database** — No external database needed; all data stays in your Google account
- **OpenAI sees portfolio data** — The signal data (symbols, quantities, prices) is sent to OpenAI for formatting. Review the [OpenAI data usage policy](https://openai.com/policies/api-data-usage-policies) if this is a concern
