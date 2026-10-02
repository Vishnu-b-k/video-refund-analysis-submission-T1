"""
Core data pipeline for Vireo Audio refund analysis.

Loads raw CSVs, deduplicates migration artefacts, fixes legacy paise→rupee
amounts, joins reference tables, and computes all aggregated metrics.

Every number in the final output traces back to this file.
"""

import pandas as pd
import numpy as np
import json
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR = Path(__file__).parent.parent / "outputs"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_raw():
    """Load all raw CSVs. No cleaning yet."""
    tickets = pd.read_csv(DATA_DIR / "tickets.csv")
    agents = pd.read_csv(DATA_DIR / "agents.csv")
    orders = pd.read_csv(DATA_DIR / "orders.csv")
    customers = pd.read_csv(DATA_DIR / "customers.csv")
    products = pd.read_csv(DATA_DIR / "products.csv")
    return tickets, agents, orders, customers, products


# ---------------------------------------------------------------------------
# Cleaning & deduplication
# ---------------------------------------------------------------------------

def clean_tickets(tickets):
    """
    1. Deduplicate migration re-imports (helpdesk + legacy_fd pairs).
       Keep the helpdesk row because it stores money in rupees.
    2. For legacy-only tickets (no helpdesk counterpart), convert
       refund_amount_inr from paise to rupees (÷100).
    3. Parse dates.
    """
    raw_count = len(tickets)
    dup_count = tickets['ticket_id'].duplicated(keep=False).sum()

    # Sort so helpdesk rows come first, then drop duplicate ticket_ids
    tickets = tickets.sort_values('source_system', ascending=True)  # h < l
    tickets = tickets.drop_duplicates(subset='ticket_id', keep='first')
    dedup_count = len(tickets)

    # Fix legacy paise amounts
    legacy_refund_mask = (
        (tickets['source_system'] == 'legacy_fd') &
        (tickets['refund_amount_inr'].notna())
    )
    legacy_refund_count = legacy_refund_mask.sum()
    tickets = tickets.copy()
    tickets.loc[legacy_refund_mask, 'refund_amount_inr'] = (
        tickets.loc[legacy_refund_mask, 'refund_amount_inr'] / 100
    )

    # Parse dates
    for col in ['created_at', 'first_response_at', 'resolved_at']:
        tickets[col] = pd.to_datetime(tickets[col], errors='coerce')

    tickets['month'] = tickets['created_at'].dt.to_period('M')
    tickets['quarter'] = tickets['created_at'].dt.to_period('Q')

    cleaning_log = {
        'raw_rows': raw_count,
        'duplicate_rows_removed': raw_count - dedup_count,
        'unique_tickets': dedup_count,
        'legacy_amounts_converted': int(legacy_refund_count),
    }

    return tickets, cleaning_log


# ---------------------------------------------------------------------------
# Joins
# ---------------------------------------------------------------------------

def enrich_tickets(tickets, agents, orders, products, customers):
    """Join reference data onto tickets."""
    # Agent info
    tickets = tickets.merge(
        agents[['agent_id', 'name', 'site', 'team', 'tier']],
        on='agent_id', how='left', suffixes=('', '_agent')
    )
    tickets.rename(columns={'name': 'agent_name', 'team': 'agent_team'}, inplace=True)

    # Product info
    tickets = tickets.merge(
        products[['sku', 'product_name', 'unit_cost_inr', 'retail_price_inr']],
        left_on='product_sku', right_on='sku', how='left'
    )

    # Order value (for context)
    tickets = tickets.merge(
        orders[['order_id', 'order_value_inr', 'channel']].rename(
            columns={'channel': 'order_channel', 'order_value_inr': 'order_value'}
        ),
        on='order_id', how='left'
    )

    # Customer care_plus flag
    tickets = tickets.merge(
        customers[['customer_id', 'care_plus']],
        on='customer_id', how='left'
    )

    return tickets


# ---------------------------------------------------------------------------
# SLA breach detection
# ---------------------------------------------------------------------------

SLA_TARGETS_MINUTES = {
    'chat': 15,
    'email': 480,   # 8 hours
    'voice': 120,   # 2 hours
    'social': 240,  # 4 hours
}
SLA_BREACH_CREDIT = 350  # Rs per breach


def flag_sla_breaches(tickets):
    """Add a boolean column for SLA breaches."""
    tickets = tickets.copy()
    tickets['response_time_min'] = (
        (tickets['first_response_at'] - tickets['created_at'])
        .dt.total_seconds() / 60
    )

    def is_breach(row):
        target = SLA_TARGETS_MINUTES.get(row['channel'])
        if target is None or pd.isna(row['response_time_min']):
            return False
        return row['response_time_min'] > target

    tickets['sla_breach'] = tickets.apply(is_breach, axis=1)
    return tickets


# ---------------------------------------------------------------------------
# Policy violation detection
# ---------------------------------------------------------------------------

GOODWILL_CAP = 500  # Rs per ticket


def flag_policy_violations(tickets):
    """
    Flag two known policy violations:
    1. Refund AND replacement both issued on the same ticket.
    2. GW-OTHER refunds exceeding the Rs 500 goodwill cap.
    """
    tickets = tickets.copy()

    # Violation 1: refund + replacement
    tickets['violation_refund_and_replacement'] = (
        (tickets['refund_amount_inr'].notna()) &
        (tickets['replacement_issued'] == 'Y')
    )

    # Violation 2: goodwill over cap
    tickets['violation_gw_over_cap'] = (
        (tickets['refund_reason_code'] == 'GW-OTHER') &
        (tickets['refund_amount_inr'] > GOODWILL_CAP)
    )

    return tickets


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def compute_metrics(tickets):
    """Compute all aggregate metrics for the report."""
    refund_tickets = tickets[tickets['refund_amount_inr'].notna()].copy()
    total_refund = refund_tickets['refund_amount_inr'].sum()

    # --- Summary ---
    summary = {
        'total_tickets': len(tickets),
        'refund_tickets': len(refund_tickets),
        'refund_rate_pct': round(len(refund_tickets) / len(tickets) * 100, 1),
        'total_refund_amount': round(total_refund, 2),
        'replacement_tickets': int((tickets['replacement_issued'] == 'Y').sum()),
        'date_range_start': str(tickets['created_at'].min().date()),
        'date_range_end': str(tickets['created_at'].max().date()),
    }

    # --- By month ---
    by_month = (
        refund_tickets.groupby('month')
        .agg(count=('refund_amount_inr', 'count'),
             total=('refund_amount_inr', 'sum'))
        .reset_index()
    )
    by_month['month'] = by_month['month'].astype(str)
    by_month_list = by_month.to_dict('records')

    # Also get total tickets per month for refund rate
    all_by_month = tickets.groupby('month').size().reset_index(name='all_tickets')
    all_by_month['month'] = all_by_month['month'].astype(str)
    for row in by_month_list:
        m = row['month']
        all_t = all_by_month.loc[all_by_month['month'] == m, 'all_tickets']
        row['all_tickets'] = int(all_t.values[0]) if len(all_t) > 0 else 0
        row['refund_rate_pct'] = round(row['count'] / row['all_tickets'] * 100, 1) if row['all_tickets'] > 0 else 0

    # --- By quarter ---
    by_quarter = (
        refund_tickets.groupby('quarter')
        .agg(count=('refund_amount_inr', 'count'),
             total=('refund_amount_inr', 'sum'))
        .reset_index()
    )
    by_quarter['quarter'] = by_quarter['quarter'].astype(str)
    by_quarter_list = by_quarter.to_dict('records')

    # --- By reason code ---
    by_reason = (
        refund_tickets.groupby('refund_reason_code')
        .agg(count=('refund_amount_inr', 'count'),
             total=('refund_amount_inr', 'sum'),
             avg=('refund_amount_inr', 'mean'))
        .sort_values('total', ascending=False)
        .reset_index()
    )
    by_reason['pct_of_total'] = round(by_reason['total'] / total_refund * 100, 1)
    by_reason_list = by_reason.to_dict('records')

    # --- By agent ---
    by_agent = (
        refund_tickets.groupby('agent_id')
        .agg(refund_count=('refund_amount_inr', 'count'),
             refund_total=('refund_amount_inr', 'sum'))
        .reset_index()
    )
    all_by_agent = tickets.groupby('agent_id').size().reset_index(name='total_tickets')
    by_agent = by_agent.merge(all_by_agent, on='agent_id', how='left')

    agent_info = tickets[['agent_id', 'agent_name', 'agent_team']].drop_duplicates('agent_id')
    by_agent = by_agent.merge(agent_info, on='agent_id', how='left')

    by_agent['refund_rate_pct'] = round(
        by_agent['refund_count'] / by_agent['total_tickets'] * 100, 1
    )
    by_agent['avg_refund'] = round(by_agent['refund_total'] / by_agent['refund_count'], 2)
    by_agent = by_agent.sort_values('refund_total', ascending=False)
    by_agent_list = by_agent.to_dict('records')

    # --- By team ---
    by_team = (
        refund_tickets.groupby('assigned_team')
        .agg(refund_count=('refund_amount_inr', 'count'),
             refund_total=('refund_amount_inr', 'sum'))
        .reset_index()
    )
    all_by_team = tickets.groupby('assigned_team').size().reset_index(name='total_tickets')
    by_team = by_team.merge(all_by_team, on='assigned_team', how='left')
    by_team['refund_rate_pct'] = round(
        by_team['refund_count'] / by_team['total_tickets'] * 100, 1
    )
    by_team = by_team.sort_values('refund_total', ascending=False)
    by_team_list = by_team.to_dict('records')

    # --- Policy violations ---
    v1 = tickets[tickets['violation_refund_and_replacement']]
    v2 = tickets[tickets['violation_gw_over_cap']]

    violations = {
        'refund_and_replacement': {
            'count': len(v1),
            'total_refund': round(v1['refund_amount_inr'].sum(), 2),
            'by_team': (
                v1.groupby('assigned_team')['refund_amount_inr']
                .agg(['count', 'sum'])
                .sort_values('sum', ascending=False)
                .reset_index()
                .to_dict('records')
            ),
        },
        'goodwill_over_cap': {
            'count': len(v2),
            'total_amount': round(v2['refund_amount_inr'].sum(), 2),
            'amount_over_cap': round(
                (v2['refund_amount_inr'] - GOODWILL_CAP).sum(), 2
            ),
        },
    }

    # --- SLA breaches ---
    breaches = tickets[tickets['sla_breach']]
    sla_summary = {
        'total_breaches': len(breaches),
        'total_cost': len(breaches) * SLA_BREACH_CREDIT,
        'by_channel': (
            breaches.groupby('channel').size()
            .reset_index(name='count')
            .to_dict('records')
        ),
    }

    return {
        'summary': summary,
        'by_month': by_month_list,
        'by_quarter': by_quarter_list,
        'by_reason': by_reason_list,
        'by_agent': by_agent_list,
        'by_team': by_team_list,
        'violations': violations,
        'sla': sla_summary,
    }


# ---------------------------------------------------------------------------
# Reconciliation checks
# ---------------------------------------------------------------------------

def reconcile(metrics):
    """Verify that totals add up. Returns list of check results."""
    checks = []

    total = metrics['summary']['total_refund_amount']

    # Monthly totals should equal overall total
    monthly_sum = sum(r['total'] for r in metrics['by_month'])
    checks.append({
        'check': 'Sum of monthly refund totals = total refund amount',
        'expected': total,
        'actual': round(monthly_sum, 2),
        'pass': abs(monthly_sum - total) < 0.01,
    })

    # Reason totals should equal overall total
    reason_sum = sum(r['total'] for r in metrics['by_reason'])
    checks.append({
        'check': 'Sum of reason-code totals = total refund amount',
        'expected': total,
        'actual': round(reason_sum, 2),
        'pass': abs(reason_sum - total) < 0.01,
    })

    # Agent totals should equal overall total
    agent_sum = sum(r['refund_total'] for r in metrics['by_agent'])
    checks.append({
        'check': 'Sum of agent refund totals = total refund amount',
        'expected': total,
        'actual': round(agent_sum, 2),
        'pass': abs(agent_sum - total) < 0.01,
    })

    # Ticket count consistency
    refund_count = metrics['summary']['refund_tickets']
    monthly_count = sum(r['count'] for r in metrics['by_month'])
    checks.append({
        'check': 'Sum of monthly refund counts = total refund tickets',
        'expected': refund_count,
        'actual': monthly_count,
        'pass': monthly_count == refund_count,
    })

    return checks


# ---------------------------------------------------------------------------
# Main pipeline entry point
# ---------------------------------------------------------------------------

def run_pipeline():
    """Run the full deterministic pipeline. Returns (enriched_df, metrics, cleaning_log, reconciliation)."""
    print("Loading data...")
    tickets, agents, orders, customers, products = load_raw()

    print("Cleaning & deduplicating...")
    tickets, cleaning_log = clean_tickets(tickets)

    print("Enriching with reference data...")
    tickets = enrich_tickets(tickets, agents, orders, products, customers)

    print("Flagging SLA breaches...")
    tickets = flag_sla_breaches(tickets)

    print("Flagging policy violations...")
    tickets = flag_policy_violations(tickets)

    print("Computing metrics...")
    metrics = compute_metrics(tickets)

    print("Reconciling totals...")
    recon = reconcile(metrics)
    all_pass = all(c['pass'] for c in recon)
    print(f"  Reconciliation: {'ALL PASS' if all_pass else 'FAILURES DETECTED'}")
    for c in recon:
        status = 'PASS' if c['pass'] else 'FAIL'
        print(f"  {status} {c['check']}: expected={c['expected']}, actual={c['actual']}")

    metrics['reconciliation'] = recon
    metrics['cleaning_log'] = cleaning_log

    return tickets, metrics


if __name__ == '__main__':
    tickets, metrics = run_pipeline()

    OUTPUT_DIR.mkdir(exist_ok=True)

    # Save metrics as JSON for the report
    with open(OUTPUT_DIR / 'metrics.json', 'w') as f:
        json.dump(metrics, f, indent=2, default=str)
    print(f"\nMetrics saved to {OUTPUT_DIR / 'metrics.json'}")

    # Save enriched refund tickets for audit
    refund_df = tickets[tickets['refund_amount_inr'].notna()]
    refund_df.to_csv(OUTPUT_DIR / 'refund_tickets.csv', index=False)
    print(f"Refund tickets saved to {OUTPUT_DIR / 'refund_tickets.csv'}")

    print(f"\nSummary:")
    print(f"  Total tickets: {metrics['summary']['total_tickets']}")
    print(f"  Refund tickets: {metrics['summary']['refund_tickets']}")
    print(f"  Total refund amount: Rs {metrics['summary']['total_refund_amount']:,.2f}")
