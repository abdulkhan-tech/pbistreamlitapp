"""Streamlit UI for the Azure DevOps Ticket Generator.

Runs identically on Streamlit Community Cloud and locally:
    streamlit run app.py
"""

import io
import csv
import json
from datetime import datetime
from pathlib import Path

import streamlit as st

from generate_tickets import (
    load_ticket_config,
    generate_all_tickets,
    DEFAULT_CONFIG_FILE,
)

STEP_LABELS = {
    1: "Step 1 — Source Discovery",
    2: "Step 2 — Platform Setup",
    3: "Step 3 — Bronze Ingestion",
    4: "Step 4 — Silver Core",
    5: "Step 5 — Gold Analytics",
}

TIER_TO_STEP = {"bronze": 3, "silver": 4, "gold": 5}


st.set_page_config(page_title="Azure DevOps Ticket Generator", page_icon="🎫", layout="wide")

st.title("🎫 Azure DevOps Ticket Generator")
st.caption("Delivery Manager tool — generate ready-to-import ADO tickets for a data source.")

with st.sidebar:
    st.header("Inputs")

    source = st.text_input("Source system", value="CTRAX", help="e.g. CTRAX, Artiva, Casemix, ESL").strip()
    env = st.selectbox("Environment", ["DEV", "QA", "PROD"], index=0)

    st.markdown("**Scope**")
    selected_steps = st.multiselect(
        "Steps to include",
        options=[1, 2, 3, 4, 5],
        default=[1, 2, 3, 4, 5],
        format_func=lambda s: STEP_LABELS[s],
    )
    selected_tiers = st.multiselect(
        "Medallion tiers (optional filter)",
        options=["bronze", "silver", "gold"],
        default=[],
        help="If set, restricts tier-specific steps to only these tiers.",
    )

    st.markdown("**Config**")
    uploaded_config = st.file_uploader(
        "Custom tickets_config.json (optional)",
        type=["json"],
        help="Leave empty to use the bundled default config.",
    )

st.subheader("Custom Instructions")
st.caption(
    "Free-form text appended to every ticket's description under a **Custom Instructions** section. "
    "Placeholders `{SOURCE}` and `{ENV}` are substituted. No LLM — text is inserted verbatim."
)
custom_instructions = st.text_area(
    "Instructions / notes for the team",
    height=160,
    placeholder=(
        "Example:\n"
        "- Follow the {SOURCE} security review checklist before merging.\n"
        "- Coordinate {ENV} deploys with the platform team on Thursdays.\n"
        "- Add PII masking for columns listed in the data dictionary."
    ),
)

generate = st.button("Generate tickets", type="primary")

if generate:
    if not source:
        st.error("Source is required.")
        st.stop()
    if not selected_steps and not selected_tiers:
        st.error("Select at least one step or tier.")
        st.stop()

    try:
        if uploaded_config is not None:
            config = json.loads(uploaded_config.getvalue().decode("utf-8"))
        else:
            config = load_ticket_config(DEFAULT_CONFIG_FILE)
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON in uploaded config: {e}")
        st.stop()
    except FileNotFoundError:
        st.error(f"Default config not found at {DEFAULT_CONFIG_FILE}.")
        st.stop()

    steps_arg = selected_steps if selected_steps else None
    tiers_arg = selected_tiers if selected_tiers else None

    tickets = generate_all_tickets(
        config=config,
        source=source,
        env=env,
        steps=steps_arg,
        tiers=tiers_arg,
        custom_instructions=custom_instructions or None,
    )

    if not tickets:
        st.warning("No tickets matched the selected steps/tiers.")
        st.stop()

    st.success(f"Generated {len(tickets)} ticket(s).")

    counts = {}
    for t in tickets:
        counts[t["step"]] = counts.get(t["step"], 0) + 1
    cols = st.columns(len(counts) or 1)
    for col, step_num in zip(cols, sorted(counts)):
        col.metric(STEP_LABELS.get(step_num, f"Step {step_num}"), counts[step_num])

    json_bytes = json.dumps(
        {"generated_at": datetime.now().isoformat(), "total_tickets": len(tickets), "tickets": tickets},
        indent=2,
    ).encode("utf-8")

    csv_buf = io.StringIO()
    fieldnames = [
        "Work Item Type", "Title", "Owner", "Description", "Tags",
        "Acceptance Criteria", "Source", "Environment", "Step", "Tier",
    ]
    writer = csv.DictWriter(csv_buf, fieldnames=fieldnames)
    writer.writeheader()
    for t in tickets:
        writer.writerow({
            "Work Item Type": t["type"],
            "Title": t["title"],
            "Owner": t.get("owner", "Data Engineer"),
            "Description": t["description"],
            "Tags": "; ".join(t["tags"]),
            "Acceptance Criteria": t["acceptance_criteria_formatted"],
            "Source": t["source"],
            "Environment": t["environment"],
            "Step": t["step"],
            "Tier": t.get("tier") or "N/A",
        })
    csv_bytes = csv_buf.getvalue().encode("utf-8")

    md_lines = [
        "# Azure DevOps Tickets",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Source: {source} | Environment: {env} | Total: {len(tickets)}",
        "",
        "---",
        "",
    ]
    current_step = None
    for t in tickets:
        if t["step"] != current_step:
            current_step = t["step"]
            md_lines += [f"## {STEP_LABELS.get(current_step, f'Step {current_step}')}", ""]
        md_lines += [
            f"### {t['ticket_id']}: {t['title']}",
            "",
            f"**Type:** {t['type']}  ",
            f"**Owner:** {t.get('owner', 'Data Engineer')}  ",
            f"**Tags:** {', '.join(t['tags'])}",
            "",
            t["description"],
            "",
            "---",
            "",
        ]
    md_bytes = "\n".join(md_lines).encode("utf-8")

    base = f"{source}_{env}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    dcols = st.columns(3)
    dcols[0].download_button("Download JSON", json_bytes, file_name=f"{base}.json", mime="application/json")
    dcols[1].download_button("Download CSV",  csv_bytes,  file_name=f"{base}.csv",  mime="text/csv")
    dcols[2].download_button("Download Markdown", md_bytes, file_name=f"{base}.md", mime="text/markdown")

    st.subheader("Preview")
    for t in tickets:
        with st.expander(f"{t['ticket_id']} — {t['title']}"):
            st.markdown(f"**Owner:** {t.get('owner', 'Data Engineer')}  |  **Tags:** {', '.join(t['tags'])}")
            st.markdown(t["description"])
else:
    st.info("Fill in the sidebar and click **Generate tickets**.")
