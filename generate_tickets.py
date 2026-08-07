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


def generate_all_tickets(config: Dict[str, Any], source: str, env: str, 
                         steps: Optional[List[int]] = None,
                         tiers: Optional[List[str]] = None,
                         custom_instructions: Optional[str] = None) -> List[Dict[str, Any]]:
    """Generate all tickets from configuration.
    
    Args:
        config: Ticket configuration dictionary
        source: Source system name
        env: Environment (DEV, QA, PROD)
        steps: List of steps to generate (1-5). If None, generates based on tiers.
        tiers: List of medallion tiers (bronze, silver, gold). If None, generates all.
    """
    
    all_tickets = []
    
    # Step mapping with tier association
    step_mapping = {
        1: {"key": "step_1_source_discovery", "tier": None},      # Pre-tier (always included unless filtered by steps)
        2: {"key": "step_2_platform_setup", "tier": None},        # Pre-tier (always included unless filtered by steps)
        3: {"key": "step_3_bronze_ingestion", "tier": "bronze"},
        4: {"key": "step_4_silver_core", "tier": "silver"},
        5: {"key": "step_5_gold_analytics", "tier": "gold"}
    }
    
    # Determine which steps to include based on tiers and steps arguments
    steps_to_include = []
    
    if steps is not None:
        # If steps are explicitly provided, use them directly
        steps_to_include = steps
    elif tiers is not None:
        # If only tiers are provided, include pre-tier steps (1, 2) plus tier-specific steps
        steps_to_include = [1, 2]  # Always include discovery and platform setup
        tier_to_step = {"bronze": 3, "silver": 4, "gold": 5}
        for tier in tiers:
            if tier.lower() in tier_to_step:
                steps_to_include.append(tier_to_step[tier.lower()])
        steps_to_include = sorted(set(steps_to_include))
    else:
        # Default to all steps
        steps_to_include = [1, 2, 3, 4, 5]
    
    # If both steps and tiers are provided, filter steps by tiers
    if steps is not None and tiers is not None:
        filtered_steps = []
        for step_num in steps:
            step_info = step_mapping.get(step_num)
            if step_info:
                step_tier = step_info["tier"]
                # Include if step has no tier (pre-tier steps) or tier is in the requested tiers
                if step_tier is None or step_tier.lower() in [t.lower() for t in tiers]:
                    filtered_steps.append(step_num)
        steps_to_include = filtered_steps
    
    for step_num in steps_to_include:
        step_info = step_mapping.get(step_num)
        if step_info and step_info["key"] in config:
            step_config = config[step_info["key"]]
            for idx, ticket_config in enumerate(step_config.get("tickets", []), 1):
                ticket = generate_ticket(ticket_config, source, env, step_num, idx, custom_instructions)
                # Add tier information to ticket
                ticket["tier"] = step_info["tier"]
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
        "Work Item Type", "Title", "Owner", "Description", "Tags", 
        "Acceptance Criteria", "Source", "Environment", "Step", "Tier"
    ]
    
    rows = []
    for ticket in tickets:
        rows.append({
            "Work Item Type": ticket["type"],
            "Title": ticket["title"],
            "Owner": ticket.get("owner", "Data Engineer"),
            "Description": ticket["description"],
            "Tags": "; ".join(ticket["tags"]),
            "Acceptance Criteria": ticket["acceptance_criteria_formatted"],
            "Source": ticket["source"],
            "Environment": ticket["environment"],
            "Step": ticket["step"],
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
    
    current_step = None
    step_names = {
        1: "Step 1: Source Discovery",
        2: "Step 2: Platform Setup/Sprint Zero",
        3: "Step 3: Bronze Ingestion",
        4: "Step 4: Silver Core Development"
    }
    
    for ticket in tickets:
        if ticket["step"] != current_step:
            current_step = ticket["step"]
            lines.append(f"## {step_names.get(current_step, f'Step {current_step}')}")
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

    tickets = generate_all_tickets(config, args.source, args.env, steps, tiers, custom_instructions)
    
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
