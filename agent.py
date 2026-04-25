"""Morning Briefing Agent.

Uses Strands Agents with LiteLLM to connect to OpenRouter and synthesize
a daily morning briefing from Gmail, Google Calendar, and Slack.
"""

import os
import datetime as dt
from dotenv import load_dotenv

from strands import Agent, tool
from strands.models.litellm import LiteLLMModel

# ── Google API imports ──────────────────────────────────────────────────────
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ── Slack SDK import ────────────────────────────────────────────────────────
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# ── Resolve paths relative to this script's directory ───────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Load environment variables ──────────────────────────────────────────────
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))

# Google OAuth scopes
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]

TOKEN_PATH = os.path.join(SCRIPT_DIR, "token.json")
CREDENTIALS_PATH = os.path.join(SCRIPT_DIR, "credentials.json")


# ═══════════════════════════════════════════════════════════════════════════
# Helper – Google OAuth
# ═══════════════════════════════════════════════════════════════════════════

def get_google_credentials() -> Credentials:
    """Handle the Google OAuth2 flow for Gmail and Calendar access.

    Reads cached credentials from token.json if they exist and are still
    valid. If expired, refreshes them automatically. If no cached token
    is found, launches the OAuth consent screen via a local server and
    saves the resulting credentials to token.json for future runs.

    Returns:
        google.oauth2.credentials.Credentials ready for API calls.
    """
    creds = None

    # 1. Try loading cached credentials
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, GOOGLE_SCOPES)

    # 2. Refresh or run the full OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_PATH):
                raise FileNotFoundError(
                    f"'{CREDENTIALS_PATH}' not found. Download your OAuth "
                    "client credentials from the Google Cloud Console and "
                    "place them in the project root."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, GOOGLE_SCOPES
            )
            creds = flow.run_local_server(port=0)

        # 3. Cache for next time
        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())

    return creds


# ═══════════════════════════════════════════════════════════════════════════
# Tool 1 – Gmail
# ═══════════════════════════════════════════════════════════════════════════

@tool
def check_gmail(hours_back: int = 12) -> str:
    """Fetch unread emails from Gmail received within the last N hours.

    Connects to the Gmail API and retrieves unread messages from the
    user's inbox. For each email it returns the sender, subject, date,
    and a 200-character snippet of the message body.

    Args:
        hours_back: How many hours into the past to search. Defaults to 12.

    Returns:
        A formatted string listing every unread email, or a message
        indicating the inbox is clear.
    """
    try:
        creds = get_google_credentials()
        service = build("gmail", "v1", credentials=creds)

        # Build the time-based search query
        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours_back)
        cutoff_epoch = int(cutoff.timestamp())
        query = f"is:unread after:{cutoff_epoch}"

        results = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=25)
            .execute()
        )
        messages = results.get("messages", [])

        if not messages:
            return f"✅ No unread emails in the last {hours_back} hours."

        output_lines: list[str] = []

        for msg_meta in messages:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=msg_meta["id"], format="full")
                .execute()
            )

            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
            sender = headers.get("From", "Unknown sender")
            subject = headers.get("Subject", "(no subject)")
            date = headers.get("Date", "Unknown date")
            snippet = msg.get("snippet", "")[:200]

            output_lines.append(
                f"• From: {sender}\n"
                f"  Subject: {subject}\n"
                f"  Date: {date}\n"
                f"  Preview: {snippet}\n"
            )

        header = f"📬 {len(messages)} unread email(s) in the last {hours_back}h:\n"
        return header + "\n".join(output_lines)

    except Exception as exc:
        return f"⚠️ Gmail error: {exc}"


# ═══════════════════════════════════════════════════════════════════════════
# Tool 2 – Google Calendar
# ═══════════════════════════════════════════════════════════════════════════

@tool
def check_calendar(hours_ahead: int = 24) -> str:
    """Fetch upcoming Google Calendar events within the next N hours.

    Connects to the Google Calendar API and retrieves events starting
    from now through the specified look-ahead window. For each event it
    returns the title, start time, end time, location, and attendees.

    Args:
        hours_ahead: How many hours into the future to look. Defaults to 24.

    Returns:
        A formatted string listing every upcoming event, or a message
        indicating the calendar is clear.
    """
    try:
        creds = get_google_credentials()
        service = build("calendar", "v3", credentials=creds)

        now = dt.datetime.now(dt.timezone.utc)
        time_min = now.isoformat()
        time_max = (now + dt.timedelta(hours=hours_ahead)).isoformat()

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                maxResults=20,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        if not events:
            return f"📭 No upcoming events in the next {hours_ahead} hours."

        output_lines: list[str] = []

        for event in events:
            title = event.get("summary", "(no title)")
            start = event["start"].get("dateTime", event["start"].get("date"))
            end = event["end"].get("dateTime", event["end"].get("date"))
            location = event.get("location", "No location specified")
            attendees_raw = event.get("attendees", [])
            attendees = ", ".join(
                a.get("email", "unknown") for a in attendees_raw
            ) or "Just you"

            output_lines.append(
                f"• {title}\n"
                f"  Start: {start}\n"
                f"  End:   {end}\n"
                f"  Location: {location}\n"
                f"  Attendees: {attendees}\n"
            )

        header = f"📅 {len(events)} event(s) in the next {hours_ahead}h:\n"
        return header + "\n".join(output_lines)

    except Exception as exc:
        return f"⚠️ Calendar error: {exc}"


# ═══════════════════════════════════════════════════════════════════════════
# Tool 3 – Slack
# ═══════════════════════════════════════════════════════════════════════════

@tool
def check_slack(hours_back: int = 12, max_channels: int = 5) -> str:
    """Fetch recent Slack messages from the most recently active channels.

    Uses the Slack SDK to list channels the bot has access to, sorted by
    latest activity, then pulls the most recent messages from each one.

    Args:
        hours_back: How many hours into the past to search. Defaults to 12.
        max_channels: Maximum number of channels to scan. Defaults to 5.

    Returns:
        A formatted string with channel names and up to 5 recent messages
        per channel, or a message if nothing new was found.
    """
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        return "⚠️ SLACK_BOT_TOKEN not set in .env — skipping Slack check."

    try:
        client = WebClient(token=token)
        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours_back)
        cutoff_ts = str(cutoff.timestamp())

        # Fetch channels the bot is a member of
        channels_response = client.conversations_list(
            types="public_channel,private_channel",
            exclude_archived=True,
            limit=200,
        )
        channels = channels_response.get("channels", [])

        if not channels:
            return "📭 No accessible Slack channels found."

        # Sort by most recently active (latest message timestamp)
        channels_with_activity = [
            ch for ch in channels if ch.get("is_member")
        ]
        channels_with_activity.sort(
            key=lambda ch: float(ch.get("updated", 0) or 0), reverse=True
        )
        top_channels = channels_with_activity[:max_channels]

        if not top_channels:
            return "📭 Bot is not a member of any channels."

        output_lines: list[str] = []

        for channel in top_channels:
            channel_name = channel.get("name", "unknown-channel")
            channel_id = channel["id"]

            try:
                history = client.conversations_history(
                    channel=channel_id,
                    oldest=cutoff_ts,
                    limit=5,
                )
                messages = history.get("messages", [])

                if not messages:
                    output_lines.append(f"• #{channel_name}: No new messages\n")
                    continue

                msg_summaries: list[str] = []
                for msg in messages:
                    user = msg.get("user", "unknown")
                    text = msg.get("text", "")[:150]
                    ts = msg.get("ts", "")
                    try:
                        time_str = dt.datetime.fromtimestamp(
                            float(ts), tz=dt.timezone.utc
                        ).strftime("%H:%M UTC")
                    except (ValueError, OSError):
                        time_str = "??:??"
                    msg_summaries.append(f"    [{time_str}] <{user}>: {text}")

                output_lines.append(
                    f"• #{channel_name} ({len(messages)} msg):\n"
                    + "\n".join(msg_summaries)
                    + "\n"
                )

            except SlackApiError as chan_err:
                output_lines.append(
                    f"• #{channel_name}: ⚠️ {chan_err.response['error']}\n"
                )

        header = f"💬 Slack activity (last {hours_back}h, top {max_channels} channels):\n"
        return header + "\n".join(output_lines)

    except SlackApiError as exc:
        return f"⚠️ Slack error: {exc.response['error']}"
    except Exception as exc:
        return f"⚠️ Slack error: {exc}"


# ═══════════════════════════════════════════════════════════════════════════
# System Prompt
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """\
You are a Morning Briefing Agent. Your job is to give the user a concise,
actionable summary of everything they missed while they were away.

When the user asks for their morning briefing you MUST:
1. Call check_gmail(hours_back=12) to get unread emails.
2. Call check_calendar(hours_ahead=24) to get upcoming events.
3. Call check_slack(hours_back=12, max_channels=5) to get Slack activity.

After receiving all three tool results, synthesize them into a briefing
with EXACTLY these five sections (use the headers as shown):

## URGENT
Items that need immediate attention — important emails, meetings starting
soon, or critical Slack messages.

## UPCOMING EVENTS
A chronological list of today's meetings and events with times and attendees.

## SLACK HIGHLIGHTS
Key conversations and decisions from Slack channels.

## OTHER EMAILS
Non-urgent emails summarized briefly.

## SUGGESTED ACTIONS
A prioritized to-do list based on everything above.

Keep the briefing concise, scannable, and actionable. Use bullet points.
If a data source returned an error or had no results, note it briefly and
move on — never skip a section entirely.
"""


# ═══════════════════════════════════════════════════════════════════════════
# Agent Runner
# ═══════════════════════════════════════════════════════════════════════════

def run() -> None:
    """Create the Morning Briefing Agent and request a briefing."""
    model = LiteLLMModel(
        model_id="openrouter/openrouter/free",
        client_args={
            "api_key": os.environ.get("OPENROUTER_API_KEY"),
            "api_base": "https://openrouter.ai/api/v1",
        },
        params={
            "max_tokens": 4096,
        },
    )

    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[check_gmail, check_calendar, check_slack],
    )

    response = agent("What did I miss? Give me my morning briefing.")
    print(response)


if __name__ == "__main__":
    run()
