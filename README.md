# ☀️ Morning Briefing Agent

An AI-powered morning briefing agent built with [Strands Agents](https://github.com/strands-agents/sdk-python) and [OpenRouter](https://openrouter.ai/). It pulls data from **Gmail**, **Google Calendar**, and **Slack**, then synthesizes everything into a concise, actionable daily briefing.

## What It Does

When you run the agent, it:

1. **Checks Gmail** — fetches unread emails from the last 12 hours
2. **Checks Google Calendar** — pulls upcoming events for the next 24 hours
3. **Checks Slack** — scans the 5 most active channels for recent messages

Then it synthesizes all that data into a structured briefing with five sections:

| Section | Purpose |
|---------|---------|
| **URGENT** | Items needing immediate attention |
| **UPCOMING EVENTS** | Chronological list of today's meetings |
| **SLACK HIGHLIGHTS** | Key conversations and decisions |
| **OTHER EMAILS** | Non-urgent emails summarized briefly |
| **SUGGESTED ACTIONS** | Prioritized to-do list based on everything above |

## Tech Stack

- **Agent Framework**: [Strands Agents SDK](https://github.com/strands-agents/sdk-python)
- **LLM Provider**: [OpenRouter](https://openrouter.ai/) via [LiteLLM](https://docs.litellm.ai/)
- **Model**: `openrouter/openrouter/free`
- **Gmail & Calendar**: Google APIs with OAuth 2.0
- **Slack**: Slack SDK (Bot User OAuth Token)
- **Python**: 3.10+

## Project Structure

```
openrouter-v1/
├── agent.py            # Main agent with 3 tools + system prompt
├── requirements.txt    # Python dependencies
├── .gitignore          # Keeps secrets out of version control
├── .env                # API keys (not tracked by git)
├── credentials.json    # Google OAuth client credentials (not tracked)
├── token.json          # Cached Google auth token (auto-generated, not tracked)
└── .venv/              # Python virtual environment (not tracked)
```

## Setup

### Prerequisites

- Python 3.10 or higher
- An [OpenRouter](https://openrouter.ai/) account and API key
- A [Google Cloud](https://console.cloud.google.com/) project with Gmail and Calendar APIs enabled
- A [Slack](https://api.slack.com/apps) app with bot token scopes

### 1. Clone the repo

```bash
git clone https://github.com/jp-bmn/openrouter-v1.git
cd openrouter-v1
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
# Paste your real OpenRouter API key here
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# Paste your Slack Bot OAuth token here (starts with xoxb-)
SLACK_BOT_TOKEN=xoxb-your-token-here
```

### 5. Set up Google OAuth

1. Go to [Google Cloud Console → APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials)
2. Create an **OAuth 2.0 Client ID** (Desktop app type)
3. Download the JSON and save it as `credentials.json` in the project root
4. Make sure the **Gmail API** and **Google Calendar API** are both [enabled](https://console.cloud.google.com/apis/library)

> On the first run, a browser window will open for you to authorize access. After that, a `token.json` is cached so you won't need to re-authorize.

### 6. Set up Slack

1. Create a Slack app at [api.slack.com/apps](https://api.slack.com/apps)
2. Under **OAuth & Permissions**, add these **Bot Token Scopes**:
   - `channels:read`
   - `channels:history`
   - `channels:join`
   - `groups:read`
   - `groups:history`
3. Install the app to your workspace
4. Copy the **Bot User OAuth Token** (`xoxb-...`) into your `.env` file
5. The bot will auto-join public channels when it runs

## Usage

### Run the full briefing

```bash
source .venv/bin/activate
python agent.py
```

### Test individual tools

```bash
# Gmail — check unread emails from the last 24 hours
python -c "from agent import check_gmail; print(check_gmail(hours_back=24))"

# Calendar — check upcoming events for the next 24 hours
python -c "from agent import check_calendar; print(check_calendar(hours_ahead=24))"

# Slack — check recent messages from the last 24 hours
python -c "from agent import check_slack; print(check_slack(hours_back=24))"
```

## Example Output

```
## URGENT
- Security Alert — Unrecognized device signed into your OpenRouter account.

## UPCOMING EVENTS
- No events scheduled for the next 24 hours.

## SLACK HIGHLIGHTS
- #general — New member joined the channel.
- #random — Positive engagement: "This resonates deeply with me"
  and "exactly the kind of tool I wish existed when I was coming up."

## OTHER EMAILS
- No other unread emails.

## SUGGESTED ACTIONS
1. Review the OpenRouter security alert immediately.
2. Follow up in #random on the positive feedback.
3. No calendar conflicts — open time to catch up on priorities.
```

## Security

The following files are **never committed** to version control:

- `.env` — API keys and tokens
- `credentials.json` — Google OAuth client secrets
- `token.json` — Cached Google auth token

## License

MIT
