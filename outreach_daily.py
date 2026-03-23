"""
TeroAI - Daily Outreach Script
Processes BATCH_SIZE leads per run, saves progress, creates Gmail drafts.
Usage:
  python outreach_daily.py
Set before running:
  set ANTHROPIC_API_KEY=sk-ant-...
  Place credentials.json in ~/.teroai/credentials.json
"""
import csv
import json
import base64
import os
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import anthropic

# -- Config -------------------------------------------------------------------
LEADS_FILE    = "leads/leads.csv"
PROGRESS_FILE = os.path.expanduser("~/.teroai_progress.json")
TOKEN_FILE    = os.path.expanduser("~/.teroai/token.json")
CREDS_FILE    = os.path.expanduser("~/.teroai/credentials.json")
BATCH_SIZE    = 100
SHEET_ID      = "1_Nc_DL1gkW5ZoPtIRpdPNXG4TokDoyfaS3t-XLQQh-M"
SHEET_NAME    = "Q1 Lead List"
SCOPES        = [
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.settings.basic",
    "https://www.googleapis.com/auth/spreadsheets",
]
SENDER_NAME  = "Ryan Ramirez"
SENDER_TITLE = "Head of Sales"
WEBSITE      = "teroai.co"

# -- Text helpers -------------------------------------------------------------
def clean(text: str) -> str:
    """Remove em dashes and common encoding artifacts from any string."""
    return (
        text
        .replace("\u2014", ",")   # em dash
        .replace("\u2013", "-")   # en dash
        .replace("â€"", ",")      # mojibake em dash
        .replace("â€"", "-")      # mojibake en dash
    )

# -- TeroAI system context ----------------------------------------------------
TEROAI_SYSTEM = """
You are a sales outreach specialist for TeroAI.
TeroAI makes geospatial and location data accessible to everyone. Geographic
data has always existed but has been locked away - only usable by specialists
with expensive tools and years of technical training.
TeroAI's flagship product, the TeroAtlas Data Terminal, is a revolutionary
geospatial data platform that aggregates location data across multiple publishers,
hierarchies, and formats into a single, unified repository. Users query it in
plain English - no GIS expertise, no data science background, no complex setup
required. It delivers a single source of truth for location data, eliminating
silos and generating insights on demand. Available via an intuitive front-end
chat interface or a developer-friendly SDK and API.
TeroAI also offers TeroCompass Technology Licensing - a patented geospatial data
processing system designed for companies building consumer-facing and B2B2C
platforms. TeroCompass allows businesses to embed sophisticated location
intelligence directly into their own products at scale. It is model-agnostic,
meaning it works across AI architectures, and it solves one of AI's biggest blind
spots: the inability to reason accurately about geographic data. Used in retail,
real estate, media, social platforms, and more.
TeroAI's technology is patented. NYC-based. The team has deep expertise in
geography, economics, and artificial intelligence.
Three ways TeroAI works with clients:
- TeroAtlas Data Terminal: direct subscription access to unified geospatial data
  via plain English chat, SDK, or API
- TeroCompass Licensing: embed patented geospatial intelligence into your own
  platform or AI system
- Professional services: hands-on consulting and research for specific geographic
  questions or projects
Target audience: Political organizations, PR firms, marketing & advertising
agencies, management consultants, financial services firms, research
organizations, non-profits, government relations firms, trade associations, and
lobbying firms - all with 1-500 employees in the United States.
Your job is to write highly personalized, specific, and concise outreach copy.
Never be generic. Never use filler. Always ground the message in real details
about the company and the individual's role.
IMPORTANT: Never use em dashes (--) or en dashes in your writing. Use commas or rewrite instead.
"""

# -- Title-to-angle mapping ---------------------------------------------------
TITLE_ANGLES = {
    "ceo":                  "strategic decision-making powered by geographic intelligence - understanding markets, constituencies, and opportunities at a geographic level",
    "founder":              "strategic decision-making powered by geographic intelligence - understanding markets, constituencies, and opportunities at a geographic level",
    "president":            "strategic decision-making powered by geographic intelligence - understanding markets, constituencies, and opportunities at a geographic level",
    "managing director":    "strategic geographic insights that inform high-level decisions across markets, regions, and constituencies",
    "principal":            "geographic intelligence that sharpens analysis and strengthens client deliverables",
    "vp sales":             "territory analysis, market sizing, and identifying high-opportunity regions without needing a data team",
    "vp operations":        "location-based operational intelligence - understanding where demand is, where gaps exist, and where to focus resources",
    "operations":           "location-based operational intelligence - understanding where demand is, where gaps exist, and where to focus resources",
    "sales":                "territory analysis, market sizing, and identifying high-opportunity regions without needing a data team",
    "political":            "voter data, district-level demographics, and behavioral patterns that used to require a specialized team and expensive tools",
    "campaign":             "voter targeting, district analysis, and real-time geographic intelligence to sharpen campaign strategy",
    "grassroots":           "community-level geographic data - understanding neighborhood demographics, turnout patterns, and local economic conditions",
    "direct mail":          "geographic targeting and list optimization - knowing exactly which areas, districts, and demographics to reach",
    "advertising":          "location-based audience intelligence - geographic targeting, market analysis, and regional performance insights",
    "marketing":            "location-based audience intelligence - geographic targeting, market analysis, and regional performance insights",
    "public relations":     "geographic context that strengthens narratives - understanding the places and communities behind the stories",
    "communications":       "geographic context that strengthens narratives - understanding the places and communities behind the stories",
    "policy":               "geographic policy impact analysis - understanding how legislation, programs, and decisions affect specific places and populations",
    "lobbying":             "district and constituent data - knowing exactly who lives where, what they earn, how they vote, and what they care about",
    "government":           "geographic data on constituents, districts, and communities - the kind of intelligence that drives effective policy and advocacy",
    "research":             "geographic data enrichment - adding location intelligence to research to uncover patterns, disparities, and opportunities",
    "data":                 "enriching existing datasets with geographic intelligence - without needing GIS expertise or expensive tooling",
    "analytics":            "enriching existing datasets with geographic intelligence - without needing GIS expertise or expensive tooling",
    "consulting":           "geographic intelligence that sharpens client analysis and opens new service offerings around location data",
    "financial":            "geographic market analysis - identifying regional opportunities, economic trends, and location-based risk",
    "trade":                "geographic intelligence on industries, supply chains, and regional economic activity across the country",
    "association":          "geographic intelligence on industries, supply chains, and regional economic activity across the country",
    "non-profit":           "geographic program targeting - understanding where your populations are, what they need, and where resources are most needed",
    "nonprofit":            "geographic program targeting - understanding where your populations are, what they need, and where resources are most needed",
}

def get_title_angle(title: str) -> str:
    title_lower = title.lower()
    for keyword, angle in TITLE_ANGLES.items():
        if keyword in title_lower:
            return angle
    return "geographic intelligence that turns location data into clear, actionable answers - without needing technical expertise"

# -- Progress tracking --------------------------------------------------------
def load_progress() -> dict:
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {"last_row": 0}

def save_progress(row_index: int):
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"last_row": row_index}, f)

# -- AI generation ------------------------------------------------------------
def generate_outreach_paragraph(client: anthropic.Anthropic, row: dict) -> str:
    first_name  = row.get("first_name") or row.get("First Name", "")
    title       = row.get("title") or row.get("Title", "")
    company     = row.get("company") or row.get("Company Name for Emails") or row.get("Company Name", "")
    industry    = row.get("industry") or row.get("Industry", "")
    keywords    = (row.get("Keywords", "") or "")[:600]
    title_angle = get_title_angle(title)

    prompt = f"""
Write exactly 1 sentence to complete this thought in a cold outreach email:

"What tends to resonate most is how quickly teams can go from question to insight,
without relying on multiple tools, analysts, or stitched datasets. [YOUR SENTENCE HERE]"

Your sentence should make this feel personally relevant to this specific person at
this specific company. Reference something real about what they do or care about.

LEAD:
- Name: {first_name}
- Title: {title}
- Company: {company}
- Industry: {industry}
- Company keywords/tags: {keywords}
ROLE ANGLE for "{title}":
{title_angle}

RULES:
1. Exactly 1 sentence. Conversational, not pitchy.
2. Do NOT reintroduce TeroAI or include a CTA.
3. Do NOT start with "I" or "TeroAI".
4. Do NOT use em dashes or en dashes. Use commas or rewrite instead.
5. Peer-to-peer tone. No filler.
"""
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=150,
        system=TEROAI_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return clean(response.content[0].text.strip())

def generate_followup_sentence(client: anthropic.Anthropic, row: dict) -> str:
    first_name  = row.get("first_name") or row.get("First Name", "")
    title       = row.get("title") or row.get("Title", "")
    company     = row.get("company") or row.get("Company Name for Emails") or row.get("Company Name", "")
    industry    = row.get("industry") or row.get("Industry", "")
    keywords    = (row.get("Keywords", "") or "")[:400]
    title_angle = get_title_angle(title)

    prompt = f"""
Write exactly 1 sentence for a follow-up partnership email.
This sentence appears right after the intro line "Wanted to resurface this in case
it got buried, and share a bit more on what TeroAI actually does in practice."
and just before three structured sections covering what the platform can do.
Its job is to make the email feel personally relevant to this specific person.
LEAD:
- Name: {first_name}
- Title: {title}
- Company: {company}
- Industry: {industry}
- Keywords: {keywords}
ROLE ANGLE for "{title}":
{title_angle}
RULES:
1. Exactly 1 sentence. Warm and specific, not a pitch.
2. Reference something real about {company} or this person's role.
3. Do NOT reintroduce TeroAI or include a CTA.
4. Do NOT start with "I" or "TeroAI".
5. Do NOT use em dashes or en dashes. Use commas instead.
6. Conversational, peer-to-peer tone.
"""
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=150,
        system=TEROAI_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return clean(response.content[0].text.strip())

# -- Vertical mapping ---------------------------------------------------------
VERTICAL_MAP = {
    "political":            "political organization",
    "government":           "government relations",
    "lobbying":             "government relations",
    "public affairs":       "government relations",
    "civic":                "civic & social organization",
    "social organization":  "civic & social organization",
    "trade association":    "civic & social organization",
    "association":          "civic & social organization",
    "non-profit":           "nonprofit organization management",
    "nonprofit":            "nonprofit organization management",
    "public relations":     "public relations & communication",
    "communications":       "public relations & communication",
    "communication":        "public relations & communication",
    "marketing":            "marketing & advertising",
    "advertising":          "marketing & advertising",
    "consulting":           "management consulting",
    "financial":            "financial services",
    "research":             "research",
}

def get_vertical(industry: str) -> str:
    industry_lower = industry.lower()
    for keyword, vertical in VERTICAL_MAP.items():
        if keyword in industry_lower:
            return vertical
    return ""

# -- Google Sheets ------------------------------------------------------------
def log_to_sheet(sheets_service, row: dict, fname: str, lname: str, email: str, company: str):
    if not SHEET_ID:
        return
    industry = row.get("industry") or row.get("Industry", "")
    vertical = get_vertical(industry)
    contact  = f"{fname} {lname}".strip()
    SEPARATOR = "  |  "

    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f"{SHEET_NAME}!A:I",
    ).execute()
    existing_rows = result.get("values", [])

    for i, sheet_row in enumerate(existing_rows):
        if not sheet_row:
            continue
        existing_company = sheet_row[0].strip() if len(sheet_row) > 0 else ""
        if existing_company.lower() == company.lower():
            existing_contact = sheet_row[1] if len(sheet_row) > 1 else ""
            existing_email   = sheet_row[2] if len(sheet_row) > 2 else ""
            if email in existing_email:
                return
            new_contact = f"{existing_contact}{SEPARATOR}{contact}" if existing_contact else contact
            new_email   = f"{existing_email}{SEPARATOR}{email}" if existing_email else email
            row_number  = i + 1
            sheets_service.spreadsheets().values().update(
                spreadsheetId=SHEET_ID,
                range=f"{SHEET_NAME}!B{row_number}:C{row_number}",
                valueInputOption="RAW",
                body={"values": [[new_contact, new_email]]},
            ).execute()
            return

    values = [[
        company, contact, email, "", "", vertical, "", "Ryan", "Initial Outreach"
    ]]
    sheets_service.spreadsheets().values().append(
        spreadsheetId=SHEET_ID,
        range=f"{SHEET_NAME}!A:I",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": values},
    ).execute()

# -- Gmail --------------------------------------------------------------------
def authenticate():
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return creds

def get_gmail_signature(service) -> str:
    try:
        result = service.users().settings().sendAs().list(userId="me").execute()
        for send_as in result.get("sendAs", []):
            if send_as.get("isPrimary"):
                return send_as.get("signature", "")
    except Exception as e:
        print(f"  [could not fetch signature: {e}]")
    return ""

def make_mime(to_email: str, subject: str, body: str, signature_html: str) -> str:
    html_body = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html_body = html_body.replace("\n", "<br>\n")
    full_html = f"<div>{html_body}</div><br>{signature_html}"
    msg = MIMEMultipart("alternative")
    msg["to"] = to_email
    msg["subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    msg.attach(MIMEText(full_html, "html"))
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()

def create_draft(service, to_email: str, subject: str, body: str, signature_html: str) -> str:
    raw    = make_mime(to_email, subject, body, signature_html)
    result = service.users().drafts().create(
        userId="me", body={"message": {"raw": raw}}
    ).execute()
    return result.get("message", {}).get("threadId", "")

def create_reply_draft(service, to_email: str, subject: str, body: str, thread_id: str, signature_html: str):
    raw = make_mime(to_email, f"Re: {subject}", body, signature_html)
    service.users().drafts().create(
        userId="me", body={"message": {"raw": raw, "threadId": thread_id}}
    ).execute()

# -- Main ---------------------------------------------------------------------
def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ERROR: ANTHROPIC_API_KEY not set. Run: set ANTHROPIC_API_KEY=sk-ant-...")

    ai_client = anthropic.Anthropic(api_key=api_key)
    progress  = load_progress()
    start_row = progress["last_row"]

    with open(LEADS_FILE, newline="", encoding="utf-8-sig") as f:
        all_rows = list(csv.DictReader(f))

    total = len(all_rows)
    if start_row >= total:
        print("All leads processed. Delete ~/.teroai_progress.json to start over.")
        return

    batch           = all_rows[start_row : start_row + BATCH_SIZE]
    remaining_after = max(0, total - start_row - len(batch))
    print(f"Today: rows {start_row + 1}-{start_row + len(batch)} of {total}")
    print(f"Remaining after today: {remaining_after}\n")

    creds          = authenticate()
    service        = build("gmail", "v1", credentials=creds)
    sheets_service = build("sheets", "v4", credentials=creds) if SHEET_ID else None
    signature_html = get_gmail_signature(service)

    drafted = 0
    skipped = 0
    errors  = 0

    for i, row in enumerate(batch):
        abs_row = start_row + i
        email   = (row.get("email") or row.get("Email", "")).strip()
        fname   = (row.get("first_name") or row.get("First Name", "there")).strip()
        lname   = (row.get("last_name") or row.get("Last Name", "")).strip()
        company = (row.get("company") or row.get("Company Name for Emails") or row.get("Company Name", "")).strip()
        subject = f"TeroAI + {company}"
        status  = row.get("status", "new").strip().lower()

        if not email:
            print(f"  [{i+1}/{len(batch)}] SKIP (no email): {fname} @ {company}")
            save_progress(abs_row + 1)
            skipped += 1
            continue

        if status in ("replied", "unsubscribed", "done", "paused"):
            print(f"  [{i+1}/{len(batch)}] SKIP (status={status}): {fname} @ {company}")
            save_progress(abs_row + 1)
            skipped += 1
            continue

        print(f"  [{i+1}/{len(batch)}] {fname} @ {company} - {row.get('title') or row.get('Title', '')}")

        try:
            paragraph = generate_outreach_paragraph(ai_client, row)
        except Exception as e:
            print(f"    ERROR generating paragraph: {e}")
            save_progress(abs_row + 1)
            errors += 1
            continue

        # -- Email 1 ----------------------------------------------------------
        body1 = (
            f"Hello {fname},\n\n"
            "I lead sales at TeroAI, a geospatial data platform built to make complex "
            "location-based insights accessible without the need for GIS expertise or "
            "heavy infrastructure.\n\n"
            "We've developed a patented system that unifies fragmented geographic, "
            "demographic, and economic data into a single interface, allowing teams to "
            "query and act on it in plain language or integrate it directly via API. "
            "In practice, this means faster decision-making across areas like site "
            "selection, market analysis, targeting, and localized strategy.\n\n"
            "What tends to resonate most is how quickly teams can go from question to "
            "insight, without relying on multiple tools, analysts, or stitched datasets. "
            f"{paragraph}\n\n"
            f"On paper it feels like we'd be a value-add for {company}. If you agree "
            "or think it makes sense to learn a bit more, would you be open to a 15-20 "
            "minute intro sometime this week or early next?\n\n"
            "Best,\n\nRyan\n"
            "Geospatial Insights without the complexity\n"
        )

        create_draft(service, email, subject, body1, signature_html)

        if sheets_service:
            try:
                log_to_sheet(sheets_service, row, fname, lname, email, company)
            except Exception as e:
                print(f"    WARNING: could not update sheet: {e}")

        drafted += 1
        save_progress(abs_row + 1)
        time.sleep(0.75)

    print(f"\n-- Summary ------------------------------------------")
    print(f"  Drafted:  {drafted}")
    print(f"  Skipped:  {skipped}")
    print(f"  Errors:   {errors}")
    print(f"  Progress: row {start_row + len(batch)} of {total}")
    print(f"  Run again for the next {BATCH_SIZE}.")

if __name__ == "__main__":
    main()
