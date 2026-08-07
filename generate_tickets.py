#!/usr/bin/env python3
"""
Azure DevOps Ticket Generator for Data Engineering Projects

This script generates Azure DevOps work items (User Stories) for data engineering
projects following the medallion architecture pattern.

Usage:
    python generate_tickets.py --source CTRAX --env DEV
    python generate_tickets.py --source CTRAX --env DEV --input custom_tickets.json
    python generate_tickets.py --source CTRAX --env DEV --output tickets_output.json
    python generate_tickets.py --source CTRAX --env DEV --steps 1,2,3,4
    python generate_tickets.py --source CTRAX --env DEV --tier bronze,silver,gold
    python generate_tickets.py --source CTRAX --env DEV --format csv
"""

import argparse
import json
import csv
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional


# Default configuration file path (same directory as script)
DEFAULT_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tickets_config.json")


def load_ticket_config(config_path: str) -> Dict[str, Any]:
    """Load ticket configuration from JSON file."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file not found: {config_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in configuration file: {e}")
        sys.exit(1)


def replace_placeholders(text: str, source: str, env: str) -> str:
    """Replace placeholders in text with actual values."""
    if text is None:
        return ""
    return text.replace("{SOURCE}", source).replace("{ENV}", env)


def format_acceptance_criteria(criteria: List[str], source: str, env: str) -> str:
    """Format acceptance criteria as a numbered list."""
    formatted = []
    for i, criterion in enumerate(criteria, 1):
        replaced = replace_placeholders(criterion, source, env)
        formatted.append(f"{i}. {replaced}")
    return "\n".join(formatted)


def format_acceptance_criteria_markdown(criteria: List[str], source: str, env: str) -> str:
    """Format acceptance criteria as markdown checkboxes for Azure DevOps."""
    formatted = []
    for criterion in criteria:
        replaced = replace_placeholders(criterion, source, env)
        formatted.append(f"- [ ] {replaced}")
    return "\n".join(formatted)


def generate_ticket(ticket_config: Dict[str, Any], source: str, env: str, 
                    step_number: int, ticket_index: int,
                    custom_instructions: Optional[str] = None) -> Dict[str, Any]:
    """Generate a single ticket from configuration."""
    
    title_raw = replace_placeholders(ticket_config["title"], source, env)
    title = f"[{env}] {title_raw}"
    description = replace_placeholders(ticket_config["description"], source, env)
    acceptance_criteria = format_acceptance_criteria_markdown(
        ticket_config["acceptance_criteria"], source, env
    )

    custom_section = ""
    if custom_instructions and custom_instructions.strip():
        rendered = replace_placeholders(custom_instructions.strip(), source, env)
        custom_section = f"\n## Custom Instructions\n\n{rendered}\n"

    full_description = f"""{description}
{custom_section}
## Acceptance Criteria

{acceptance_criteria}
"""
    
    return {
        "id": f"S{step_number}-{ticket_index:02d}",
        "ticket_id": ticket_config["id"],
        "title": title,
        "type": ticket_config.get("type", "User Story"),
        "owner": ticket_config.get("owner", "Data Engineer"),
        "description": full_description,
        "acceptance_criteria_raw": ticket_config["acceptance_criteria"],
        "acceptance_criteria_formatted": acceptance_criteria,
        "tags": [replace_placeholders(tag, source, env) for tag in ticket_config.get("tags", [])],
        "source": source,
        "environment": env,
        "step": step_number,
        "created_date": datetime.now().isoformat()
    }


# Role registry. Each role has:
#   label       — human-friendly name
#   step_labels — {step_number: label}
#   step_source — "top_level" (keys live at config root, e.g. step_1_source_discovery)
#                 or "roles"  (keys live under config["roles"][role_id])
#   step_keys   — {step_number: key_in_config}
#   tier_map    — {step_number: "bronze"|"silver"|"gold"} (optional, DE only today)
ROLES: Dict[str, Dict[str, Any]] = {
    "data_engineer": {
        "label": "Data Engineer",
        "step_source": "top_level",
        "step_labels": {
            1: "Source Discovery",
            2: "Platform Setup",
            3: "Bronze Ingestion",
            4: "Silver Core",
            5: "Gold Analytics",
        },
        "step_keys": {
            1: "step_1_source_discovery",
            2: "step_2_platform_setup",
            3: "step_3_bronze_ingestion",
            4: "step_4_silver_core",
            5: "step_5_gold_analytics",
        },
        "tier_map": {3: "bronze", 4: "silver", 5: "gold"},
    },
    "developer": {
        "label": "Developer",
        "step_source": "roles",
        "step_labels": {
            1: "Requirements & Technical Design",
            2: "Environment & Repository Setup",
            3: "Implementation",
            4: "Testing (Unit, Integration, QA)",
            5: "Deployment & Handover",
        },
        "step_keys": {1: "step_1", 2: "step_2", 3: "step_3", 4: "step_4", 5: "step_5"},
        "tier_map": {},
    },
    "reports_powerbi": {
        "label": "Reports - Power BI",
        "step_source": "roles",
        "step_labels": {
            1: "Reporting Requirements & KPI Definition",
            2: "Data Source Connection & Semantic Model",
            3: "Report & Dashboard Development",
            4: "Testing & UAT",
            5: "Publish, Security & Handover",
        },
        "step_keys": {1: "step_1", 2: "step_2", 3: "step_3", 4: "step_4", 5: "step_5"},
        "tier_map": {},
    },
    "uiux": {
        "label": "UI/UX Team",
        "step_source": "roles",
        "step_labels": {
            1: "Discovery & User Research",
            2: "Information Architecture & Wireframes",
            3: "Visual Design & Interactive Prototype",
            4: "Usability Testing & Iteration",
            5: "Design Handoff & QA Support",
        },
        "step_keys": {1: "step_1", 2: "step_2", 3: "step_3", 4: "step_4", 5: "step_5"},
        "tier_map": {},
    },
}


def _get_step_config(config: Dict[str, Any], role_id: str, step_num: int) -> Optional[Dict[str, Any]]:
    """Return the step block for a role from the loaded config, or None if missing."""
    role = ROLES.get(role_id)
    if not role:
        return None
    key = role["step_keys"].get(step_num)
    if not key:
        return None
    if role["step_source"] == "top_level":
        return config.get(key)
    return config.get("roles", {}).get(role_id, {}).get(key)


def generate_all_tickets(config: Dict[str, Any], source: str, env: str,
                         steps: Optional[List[int]] = None,
                         tiers: Optional[List[str]] = None,
                         custom_instructions: Optional[str] = None,
                         roles: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Generate all tickets from configuration.

    Args:
        config: Ticket configuration dictionary
        source: Source system name
        env: Environment (DEV, QA, PROD)
        steps: List of steps to generate (1-5). If None, generates based on tiers.
        tiers: List of medallion tiers (bronze, silver, gold). Only applies to the
               data_engineer role. If None, generates all.
        custom_instructions: Optional text appended to every ticket description.
        roles: List of role IDs to generate for. Defaults to ["data_engineer"] for
               backward compatibility.
    """

    if not roles:
        roles = ["data_engineer"]

    all_tickets: List[Dict[str, Any]] = []

    for role_id in roles:
        role = ROLES.get(role_id)
        if not role:
            continue

        tier_map = role.get("tier_map") or {}
        role_step_numbers = sorted(role["step_keys"].keys())
    
        # Determine which steps to include based on tiers and steps arguments
        if steps is not None:
            steps_to_include = [s for s in steps if s in role_step_numbers]
        elif tiers is not None and tier_map:
            steps_to_include = [1, 2] if 1 in role_step_numbers and 2 in role_step_numbers else []
            step_by_tier = {v: k for k, v in tier_map.items()}
            for tier in tiers:
                st = step_by_tier.get(tier.lower())
                if st is not None:
                    steps_to_include.append(st)
            steps_to_include = sorted(set(steps_to_include))
        else:
            steps_to_include = list(role_step_numbers)

        # Apply tier filter on top of explicit steps (data_engineer only)
        if steps is not None and tiers is not None and tier_map:
            tiers_lower = {t.lower() for t in tiers}
            steps_to_include = [
                s for s in steps_to_include
                if s not in tier_map or tier_map[s] in tiers_lower
            ]

        for step_num in steps_to_include:
            step_config = _get_step_config(config, role_id, step_num)
            if not step_config:
                continue
            for idx, ticket_config in enumerate(step_config.get("tickets", []), 1):
                ticket = generate_ticket(ticket_config, source, env, step_num, idx, custom_instructions)
                ticket["tier"] = tier_map.get(step_num)
                ticket["role"] = role_id
                ticket["role_label"] = role["label"]
                ticket["step_label"] = role["step_labels"].get(step_num, f"Step {step_num}")
                all_tickets.append(ticket)

    return all_tickets


def output_as_json(tickets: List[Dict[str, Any]], output_path: Optional[str] = None) -> None:
    """Output tickets as JSON."""
    output = {
        "generated_at": datetime.now().isoformat(),
        "total_tickets": len(tickets),
        "tickets": tickets
    }
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)
        print(f"✅ Generated {len(tickets)} tickets to: {output_path}")
    else:
        print(json.dumps(output, indent=2))


def output_as_csv(tickets: List[Dict[str, Any]], output_path: Optional[str] = None) -> None:
    """Output tickets as CSV for Azure DevOps import."""
    
    if not tickets:
        print("No tickets to output")
        return
    
    fieldnames = [
        "Work Item Type", "Title", "Owner", "Role", "Description", "Tags",
        "Acceptance Criteria", "Source", "Environment", "Step", "Step Name", "Tier"
    ]

    rows = []
    for ticket in tickets:
        rows.append({
            "Work Item Type": ticket["type"],
            "Title": ticket["title"],
            "Owner": ticket.get("owner", "Data Engineer"),
            "Role": ticket.get("role_label", "Data Engineer"),
            "Description": ticket["description"],
            "Tags": "; ".join(ticket["tags"]),
            "Acceptance Criteria": ticket["acceptance_criteria_formatted"],
            "Source": ticket["source"],
            "Environment": ticket["environment"],
            "Step": ticket["step"],
            "Step Name": ticket.get("step_label", ""),
            "Tier": ticket.get("tier", "N/A") or "N/A"
        })
    
    if output_path:
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"✅ Generated {len(tickets)} tickets to: {output_path}")
    else:
        import io
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        print(output.getvalue())


def output_as_markdown(tickets: List[Dict[str, Any]], output_path: Optional[str] = None) -> None:
    """Output tickets as Markdown for documentation."""
    
    lines = [
        f"# Azure DevOps Tickets",
        f"",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"",
        f"Total Tickets: {len(tickets)}",
        f"",
        f"---",
        f""
    ]
    
    current_role = None
    current_step = None
    for ticket in tickets:
        role_label = ticket.get("role_label", "Data Engineer")
        if role_label != current_role:
            current_role = role_label
            current_step = None
            lines.append(f"# Role: {role_label}")
            lines.append("")
        if ticket["step"] != current_step:
            current_step = ticket["step"]
            step_label = ticket.get("step_label", f"Step {current_step}")
            lines.append(f"## Step {current_step}: {step_label}")
            lines.append("")
        
        lines.append(f"### {ticket['ticket_id']}: {ticket['title']}")
        lines.append("")
        lines.append(f"**Type:** {ticket['type']}")
        lines.append(f"**Owner:** {ticket.get('owner', 'Data Engineer')}")
        lines.append(f"**Tags:** {', '.join(ticket['tags'])}")
        lines.append("")
        lines.append(ticket['description'])
        lines.append("")
        lines.append("---")
        lines.append("")
    
    content = "\n".join(lines)
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Generated {len(tickets)} tickets to: {output_path}")
    else:
        print(content)


def output_summary(tickets: List[Dict[str, Any]], source: str, env: str, tiers: Optional[List[str]] = None) -> None:
    """Output a summary of generated tickets."""
    
    step_names = {
        1: "Source Discovery",
        2: "Platform Setup",
        3: "Bronze Ingestion",
        4: "Silver Core",
        5: "Gold Analytics"
    }
    
    print("\n" + "="*70)
    print(f"  AZURE DEVOPS TICKET GENERATOR - SUMMARY")
    print("="*70)
    print(f"  Source: {source}")
    print(f"  Environment: {env}")
    if tiers:
        print(f"  Medallion Tiers: {', '.join([t.upper() for t in tiers])}")
    else:
        print(f"  Medallion Tiers: ALL (Bronze, Silver, Gold)")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # Count by step
    step_counts = {}
    for ticket in tickets:
        step = ticket["step"]
        step_counts[step] = step_counts.get(step, 0) + 1
    
    print("\n  TICKET BREAKDOWN:")
    print("-"*70)
    for step_num in sorted(step_counts.keys()):
        step_name = step_names.get(step_num, f"Step {step_num}")
        count = step_counts[step_num]
        print(f"    Step {step_num}: {step_name:<25} - {count:>3} ticket(s)")
    
    print("-"*70)
    print(f"    {'TOTAL':<35} - {len(tickets):>3} ticket(s)")
    print("="*70)
    
    # List all tickets
    print("\n  TICKET LIST:")
    print("-"*70)
    current_step = None
    for ticket in tickets:
        if ticket["step"] != current_step:
            current_step = ticket["step"]
            print(f"\n  [{step_names.get(current_step, f'Step {current_step}')}]")
        print(f"    • {ticket['ticket_id']}: {ticket['title'][:55]}...")
    
    print("\n" + "="*70 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate Azure DevOps tickets for data engineering projects",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --source CTRAX --env DEV
  %(prog)s --source CTRAX --env DEV --input custom_tickets.json
  %(prog)s --source CTRAX --env DEV --output my_tickets
  %(prog)s --source CTRAX --env DEV --step 3
  %(prog)s --source CTRAX --env DEV --steps 1
  %(prog)s --source CTRAX --env QA --steps 1,2
  %(prog)s --source CTRAX --env DEV --tier bronze
  %(prog)s --source CTRAX --env DEV --tier bronze,silver
  %(prog)s --source CTRAX --env DEV --tier gold --summary
        """
    )
    
    parser.add_argument(
        "--source", "-s",
        required=True,
        help="Source system name (e.g., CTRAX, SAP, ORACLE)"
    )
    
    parser.add_argument(
        "--env", "-e",
        required=True,
        choices=["DEV", "QA", "PROD"],
        help="Target environment (DEV, QA, PROD)"
    )
    
    parser.add_argument(
        "--input", "-i",
        default=DEFAULT_CONFIG_FILE,
        help=f"Input configuration file (default: {DEFAULT_CONFIG_FILE})"
    )
    
    parser.add_argument(
        "--output", "-o",
        help="Output file base name (without extension). All formats (json, csv, md) will be generated."
    )
    
    parser.add_argument(
        "--steps",
        help="Steps to generate: single step (1, 2, 3, 4, 5) or comma-separated (1,2,3,4,5)"
    )
    
    parser.add_argument(
        "--step",
        type=int,
        choices=[1, 2, 3, 4, 5],
        help="Single step to generate (1=Source Discovery, 2=Platform Setup, 3=Bronze, 4=Silver, 5=Gold)"
    )
    
    parser.add_argument(
        "--role", "-r",
        help=(
            "Comma-separated roles to generate for. Options: "
            + ", ".join(ROLES.keys())
            + ". Defaults to data_engineer."
        ),
    )

    parser.add_argument(
        "--list-roles",
        action="store_true",
        help="List available roles and their steps, then exit.",
    )

    parser.add_argument(
        "--tier", "-t",
        help="Comma-separated medallion tiers to generate (bronze, silver, gold). If not provided, generates all tiers."
    )
    
    parser.add_argument(
        "--instructions",
        help="Custom instructions text (or path to a .txt/.md file) injected into every ticket description. Supports {SOURCE} and {ENV} placeholders."
    )

    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print summary of generated tickets"
    )
    
    parser.add_argument(
        "--list-config",
        action="store_true",
        help="List available tickets in configuration"
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_ticket_config(args.input)
    
    # Handle --list-config
    if args.list_config:
        print("\n📋 Available Tickets in Configuration:\n")
        step_mapping = {
            "step_1_source_discovery": ("Step 1: Source Discovery", None),
            "step_2_platform_setup": ("Step 2: Platform Setup", None),
            "step_3_bronze_ingestion": ("Step 3: Bronze Ingestion", "BRONZE"),
            "step_4_silver_core": ("Step 4: Silver Core", "SILVER"),
            "step_5_gold_analytics": ("Step 5: Gold Analytics", "GOLD")
        }
        for step_key, (step_name, tier) in step_mapping.items():
            if step_key in config:
                tier_label = f" [{tier}]" if tier else ""
                print(f"\n  {step_name}{tier_label}")
                print("  " + "-"*50)
                for ticket in config[step_key].get("tickets", []):
                    print(f"    • {ticket['id']}: {ticket['title']}")
        print()
        return
    
    # Parse steps if provided (support both --step and --steps)
    steps = None
    if args.step:
        # Single step provided via --step
        steps = [args.step]
    elif args.steps:
        try:
            # Check if it's a single number or comma-separated
            if "," in args.steps:
                steps = [int(s.strip()) for s in args.steps.split(",")]
            else:
                steps = [int(args.steps.strip())]
            invalid_steps = [s for s in steps if s not in [1, 2, 3, 4, 5]]
            if invalid_steps:
                print(f"Error: Invalid steps: {invalid_steps}. Valid steps are 1, 2, 3, 4, 5")
                sys.exit(1)
        except ValueError:
            print("Error: Steps must be numbers (e.g., 1 or 1,2,3,4,5)")
            sys.exit(1)
    
    # Parse roles if provided
    roles_list: Optional[List[str]] = None
    if args.list_roles:
        print("\n👥 Available Roles:\n")
        for rid, r in ROLES.items():
            print(f"  • {rid}  —  {r['label']}")
            for sn in sorted(r["step_labels"]):
                print(f"      Step {sn}: {r['step_labels'][sn]}")
        print()
        return
    if args.role:
        roles_list = [x.strip().lower() for x in args.role.split(",") if x.strip()]
        invalid_roles = [x for x in roles_list if x not in ROLES]
        if invalid_roles:
            print(f"Error: Invalid roles: {invalid_roles}. Valid: {list(ROLES.keys())}")
            sys.exit(1)

    # Parse tiers if provided
    tiers = None
    if args.tier:
        tiers = [t.strip().lower() for t in args.tier.split(",")]
        valid_tiers = ["bronze", "silver", "gold"]
        invalid_tiers = [t for t in tiers if t not in valid_tiers]
        if invalid_tiers:
            print(f"Error: Invalid tiers: {invalid_tiers}. Valid tiers are: bronze, silver, gold")
            sys.exit(1)
    
    custom_instructions = None
    if args.instructions:
        if os.path.isfile(args.instructions):
            with open(args.instructions, 'r', encoding='utf-8') as f:
                custom_instructions = f.read()
        else:
            custom_instructions = args.instructions

    tickets = generate_all_tickets(
        config, args.source, args.env, steps, tiers, custom_instructions, roles_list
    )
    
    if not tickets:
        print("No tickets generated. Check your configuration and step selection.")
        sys.exit(1)
    
    # Output summary if requested
    if args.summary:
        output_summary(tickets, args.source, args.env, tiers)
    
    # Determine output file base name
    if args.output:
        # Use provided output path as base (remove extension if present)
        base_path = args.output
        for ext in ['.json', '.csv', '.md', '.markdown']:
            if base_path.lower().endswith(ext):
                base_path = base_path[:-len(ext)]
                break
    else:
        # Generate default base name
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        tier_suffix = f"_{'-'.join(tiers)}" if tiers else "_all"
        base_path = f"{args.source}_{args.env}{tier_suffix}_{timestamp}"
    
    # Always output all formats
    json_path = f"{base_path}.json"
    csv_path = f"{base_path}.csv"
    md_path = f"{base_path}.md"
    
    output_as_json(tickets, json_path)
    output_as_csv(tickets, csv_path)
    output_as_markdown(tickets, md_path)
    
    print(f"\n📁 All output files generated:")
    print(f"   • JSON:     {json_path}")
    print(f"   • CSV:      {csv_path}")
    print(f"   • Markdown: {md_path}")


if __name__ == "__main__":
    main()
