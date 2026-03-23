# TeroAI Automated Outreach - Claude Context

## Project Overview
Cold outreach script that generates personalized Gmail drafts for TeroAI sales leads using Claude AI.

## Key Files
- `outreach_daily.py` - Main script (leads 1-100)
- `outreach_daily2.py` - Batch 2 script (leads 101-200), uses separate progress file
- `leads/leads.csv` - Lead list

## Running the Scripts
Scripts must be run from the folder containing `leads/`:
```
C:\Users\ryans\OneDrive\Desktop\Automated Outreach\TeroAI-Outreach\
```

Set API key before running:
```powershell
$env:ANTHROPIC_API_KEY="sk-ant-..."
python outreach_daily2.py
```

To reset and rerun a batch from a specific row:
```powershell
python outreach_daily2.py --start-row 100   # leads 101-200
python outreach_daily.py --start-row 0      # leads 1-100
```

## Progress Files
- `~/.teroai_progress.json` — tracks progress for `outreach_daily.py`
- `~/.teroai_progress2.json` — tracks progress for `outreach_daily2.py`

## Email Template
**Subject:** Geospatial Insights without the complexity

```
Hello {fname},

I lead sales at TeroAI, a geospatial data platform that makes location-based insights accessible without GIS expertise or heavy setup.

We've built a patented system that unifies geographic, demographic, and economic data into one interface, so teams can query in plain language or via API, without stitching datasets together.

What tends to resonate is how quickly teams can go from question to insight. {AI-generated personalized sentence}

On paper it feels like we'd be a value-add for {company}. Would you be open to a 15-minute intro this week or next?

Best,

Ryan
```

No trailing tagline. No em dashes.

## Sender Info
- Name: Ryan Ramirez
- Title: Head of Sales
- Website: teroai.co

## Google Sheets
- Sheet ID: `1_Nc_DL1gkW5ZoPtIRpdPNXG4TokDoyfaS3t-XLQQh-M`
- Sheet Name: Q1 Lead List
- Logs: Company, Contact, Email, Vertical, Owner (Ryan), Stage (Initial Outreach)

## Auth Files
- `~/.teroai/credentials.json` — Google OAuth credentials
- `~/.teroai/token.json` — auto-generated after first auth

## Git
- Branch: `claude/prepare-teroai-emails-QPhfN`
- Remotes: github.com/ryansito00/TeroAI-Automated-Outreach
