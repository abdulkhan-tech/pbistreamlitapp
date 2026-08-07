# Azure DevOps Ticket Generator

Generate ready-to-import Azure DevOps tickets (JSON / CSV / Markdown) for data engineering projects following the medallion architecture (Bronze → Silver → Gold).

Two ways to use it:

1. **Hosted web app** on Streamlit Community Cloud — for Delivery Managers.
2. **Local** — clone this repo and run it yourself.

Both use the same code (`app.py`) and the same underlying generator (`generate_tickets.py`).

---

## Version 1 — Hosted on Streamlit Community Cloud

Anyone with the URL can generate tickets from a browser. No install needed.

### One-time deploy

1. Push this repo to GitHub (private or public).
2. Go to <https://share.streamlit.io> and sign in with GitHub.
3. Click **New app**, pick this repo/branch, set **Main file path** = `app.py`.
4. Click **Deploy**. First build takes ~1–2 minutes.
5. (Optional) In **Settings → Sharing**, set the app to *Private* and add DM email addresses so only they can access it.

### Update the app

Just `git push` to the deployed branch. Streamlit rebuilds automatically.

### Files needed (already in this repo)

- `app.py` — the Streamlit UI
- `generate_tickets.py` — the generator library
- `tickets_config.json` — default ticket templates
- `requirements.txt` — Python dependencies

---

## Version 2 — Run locally (clone & run)

For users who want to run it on their own machine (no hosting required).

### Prerequisites

- Python 3.9+
- `git`

### Steps

```bash
git clone <this-repo-url>
cd Generate_Tickets
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Streamlit opens `http://localhost:8501` in your browser.

### CLI (no web UI)

The original CLI still works and is useful for scripting / CI:

```bash
python generate_tickets.py --source CTRAX --env DEV
python generate_tickets.py --source CTRAX --env DEV --tier silver
python generate_tickets.py --source CTRAX --env DEV --steps 1,2,3
python generate_tickets.py --source CTRAX --env DEV --role developer
python generate_tickets.py --source CTRAX --env DEV --role reports_powerbi,uiux --steps 1,3
python generate_tickets.py --source CTRAX --env DEV --list-roles
python generate_tickets.py --source CTRAX --env DEV --instructions "Follow the {SOURCE} security checklist."
python generate_tickets.py --source CTRAX --env DEV --instructions ./notes.md
```

Outputs `.json`, `.csv`, and `.md` files next to the script.

---

## How the app works

Inputs the Delivery Manager provides:

- **Source** — free text (e.g. `CTRAX`, `Artiva`).
- **Environment** — `DEV` / `QA` / `PROD`.
- **Roles** — one or more of:
  - `data_engineer` — 5 medallion steps (Source Discovery, Platform Setup, Bronze, Silver, Gold).
  - `developer` — SDLC: Requirements & Design → Env Setup → Implementation → Testing → Deployment & Handover.
  - `reports_powerbi` — KPI Definition → Semantic Model → Report Dev → UAT → Publish & Handover.
  - `uiux` — Discovery/Research → IA/Wireframes → Visual Design/Prototype → Usability Testing → Design Handoff.
- **Steps** — any combination of 1–5, applied per role (step numbers are role-relative).
- **Tiers** — optional filter for `bronze` / `silver` / `gold` (applies to Data Engineer only).
- **Custom config** — optional upload of a modified `tickets_config.json`.
- **Custom Instructions** — free-form text appended to every ticket description. Supports `{SOURCE}` and `{ENV}` placeholders. Inserted verbatim — no LLM, no hallucination.

Outputs:

- JSON (structured), CSV (Azure DevOps import), Markdown (docs). All three are downloadable.
- Inline preview of every ticket.

---

## Editing ticket templates

`tickets_config.json` defines the templates. Each step has a list of tickets with `title`, `description`, `acceptance_criteria`, `tags`, and `owner`. `{SOURCE}` and `{ENV}` placeholders are substituted at generation time.

Edit that file (or upload a modified copy in the UI) to change what tickets get generated.
