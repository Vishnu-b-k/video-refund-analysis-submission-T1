"""
Generates a static HTML report from pipeline metrics.
Uses Chart.js (CDN) for a few useful charts, plain HTML tables for the rest.
"""

import json
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"


def fmt_inr(amount):
    """Format INR amount in lakhs for readability."""
    if amount >= 100000:
        return f"₹{amount/100000:.1f}L"
    return f"₹{amount:,.0f}"


def fmt_num(n):
    """Comma-separated number."""
    if isinstance(n, float):
        return f"{n:,.2f}"
    return f"{n:,}"


def generate_report(metrics, classification_summary=None):
    """Generate report.html from metrics dict."""

    s = metrics['summary']
    by_month = metrics['by_month']
    by_quarter = metrics['by_quarter']
    by_reason = metrics['by_reason']
    by_agent = metrics['by_agent']
    by_team = metrics['by_team']
    violations = metrics['violations']
    recon = metrics['reconciliation']
    cleaning = metrics['cleaning_log']

    # Prepare chart data
    month_labels = json.dumps([r['month'] for r in by_month])
    month_amounts = json.dumps([round(r['total']) for r in by_month])
    month_counts = json.dumps([r['count'] for r in by_month])

    reason_labels = json.dumps([r['refund_reason_code'] for r in by_reason])
    reason_amounts = json.dumps([round(r['total']) for r in by_reason])

    # Build agent table rows
    agent_rows = ""
    for a in by_agent[:20]:  # Top 20
        agent_rows += f"""<tr>
            <td>{a.get('agent_id','')}</td>
            <td>{a.get('agent_name','')}</td>
            <td>{a.get('agent_team','')}</td>
            <td class="num">{a.get('total_tickets',0)}</td>
            <td class="num">{a.get('refund_count',0)}</td>
            <td class="num">{a.get('refund_rate_pct',0)}%</td>
            <td class="num">₹{a.get('refund_total',0):,.0f}</td>
            <td class="num">₹{a.get('avg_refund',0):,.0f}</td>
        </tr>"""

    # Build reason table rows
    reason_rows = ""
    for r in by_reason:
        reason_rows += f"""<tr>
            <td>{r['refund_reason_code']}</td>
            <td class="num">{r['count']}</td>
            <td class="num">₹{r['total']:,.0f}</td>
            <td class="num">{r['pct_of_total']}%</td>
            <td class="num">₹{r['avg']:,.0f}</td>
        </tr>"""

    # Build monthly table rows
    month_rows = ""
    for m in by_month:
        month_rows += f"""<tr>
            <td>{m['month']}</td>
            <td class="num">{m.get('all_tickets',0)}</td>
            <td class="num">{m['count']}</td>
            <td class="num">{m.get('refund_rate_pct',0)}%</td>
            <td class="num">₹{m['total']:,.0f}</td>
        </tr>"""

    # Team table rows
    team_rows = ""
    for t in by_team:
        team_rows += f"""<tr>
            <td>{t['assigned_team']}</td>
            <td class="num">{t.get('total_tickets',0)}</td>
            <td class="num">{t['refund_count']}</td>
            <td class="num">{t.get('refund_rate_pct',0)}%</td>
            <td class="num">₹{t['refund_total']:,.0f}</td>
        </tr>"""

    # Violation detail
    v1 = violations['refund_and_replacement']
    v2 = violations['goodwill_over_cap']

    v1_team_rows = ""
    for t in v1['by_team']:
        v1_team_rows += f"<tr><td>{t['assigned_team']}</td><td class='num'>{t['count']}</td><td class='num'>₹{t['sum']:,.0f}</td></tr>"

    # Reconciliation rows
    recon_rows = ""
    for c in recon:
        icon = "✓" if c['pass'] else "✗"
        cls = "pass" if c['pass'] else "fail"
        recon_rows += f"<tr class='{cls}'><td>{icon}</td><td>{c['check']}</td><td class='num'>{c['expected']}</td><td class='num'>{c['actual']}</td></tr>"

    # Classification summary section
    classify_section = ""
    if classification_summary:
        cs = classification_summary
        classify_section = f"""
        <section>
            <h2>GW-OTHER Reclassification</h2>
            <p>The default reason code GW-OTHER ("Goodwill / Other") is the first option in the
            helpdesk dropdown. {cs['total_gw']} tickets were coded GW-OTHER; many appear to be miscoded.</p>

            <table>
                <thead><tr><th>Method</th><th>Count</th></tr></thead>
                <tbody>
                    <tr><td>Rules-based classification</td><td class="num">{cs.get('rules_classified', 0)}</td></tr>
                    <tr><td>LLM-assisted classification</td><td class="num">{cs.get('llm_classified', 0)}</td></tr>
                    <tr><td>Still GW-OTHER after reclassification</td><td class="num">{cs.get('still_gw', 0)}</td></tr>
                </tbody>
            </table>

            <h3>Reclassified Breakdown</h3>
            <table>
                <thead><tr><th>New Code</th><th>Count</th></tr></thead>
                <tbody>{''.join(f"<tr><td>{k}</td><td class='num'>{v}</td></tr>" for k,v in cs.get('reclassified_breakdown', {}).items())}</tbody>
            </table>
        </section>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vireo Audio — Refund Analysis</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #1a1a1a; background: #f8f8f8; padding: 2rem; max-width: 1100px; margin: 0 auto; line-height: 1.5; }}
        h1 {{ font-size: 1.5rem; margin-bottom: 0.25rem; }}
        h2 {{ font-size: 1.15rem; margin: 2rem 0 0.75rem; border-bottom: 1px solid #ddd; padding-bottom: 0.3rem; }}
        h3 {{ font-size: 1rem; margin: 1.2rem 0 0.5rem; }}
        p {{ margin-bottom: 0.75rem; color: #444; font-size: 0.9rem; }}
        .subtitle {{ color: #666; font-size: 0.85rem; margin-bottom: 1.5rem; }}
        .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin: 1rem 0; }}
        .metric {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 6px; padding: 1rem; }}
        .metric .value {{ font-size: 1.4rem; font-weight: 600; color: #1a1a1a; }}
        .metric .label {{ font-size: 0.78rem; color: #666; margin-top: 0.2rem; }}
        table {{ width: 100%; border-collapse: collapse; margin: 0.5rem 0 1.5rem; font-size: 0.82rem; background: #fff; }}
        th {{ background: #f0f0f0; text-align: left; padding: 0.5rem 0.75rem; font-weight: 600; border-bottom: 2px solid #ddd; }}
        td {{ padding: 0.4rem 0.75rem; border-bottom: 1px solid #eee; }}
        .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
        .chart-container {{ background: #fff; border: 1px solid #e0e0e0; border-radius: 6px; padding: 1rem; margin: 1rem 0; }}
        .chart-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }}
        canvas {{ max-height: 300px; }}
        .flag {{ background: #fff3cd; border-left: 4px solid #e6a817; padding: 0.75rem 1rem; margin: 0.75rem 0; font-size: 0.85rem; }}
        .flag strong {{ color: #856404; }}
        .pass td {{ color: #155724; }}
        .fail td {{ color: #721c24; font-weight: 600; }}
        .note {{ font-size: 0.8rem; color: #888; font-style: italic; }}
        @media print {{ body {{ padding: 0.5rem; }} .chart-container {{ page-break-inside: avoid; }} }}
    </style>
</head>
<body>
    <h1>Vireo Audio — Refund Analysis</h1>
    <p class="subtitle">Data: {s['date_range_start']} to {s['date_range_end']} · {s['total_tickets']:,} tickets · Generated from support export</p>

    <section>
        <h2>Summary</h2>
        <div class="metrics">
            <div class="metric">
                <div class="value">{s['total_tickets']:,}</div>
                <div class="label">Total Tickets</div>
            </div>
            <div class="metric">
                <div class="value">{s['refund_tickets']:,}</div>
                <div class="label">Refund Tickets ({s['refund_rate_pct']}%)</div>
            </div>
            <div class="metric">
                <div class="value">₹{s['total_refund_amount']:,.0f}</div>
                <div class="label">Total Refund Amount</div>
            </div>
            <div class="metric">
                <div class="value">{s['replacement_tickets']:,}</div>
                <div class="label">Replacements Issued</div>
            </div>
        </div>

        <div class="flag">
            <strong>Data correction applied:</strong> {cleaning['duplicate_rows_removed']} duplicate rows from migration
            re-import were removed. {cleaning['legacy_amounts_converted']} legacy-system refund amounts were converted
            from paise to rupees (÷100). The raw export total of ~₹1 crore/quarter was incorrect.
        </div>
    </section>

    <section>
        <h2>Refunds by Month</h2>
        <div class="chart-row">
            <div class="chart-container">
                <canvas id="monthAmountChart"></canvas>
            </div>
            <div class="chart-container">
                <canvas id="monthCountChart"></canvas>
            </div>
        </div>
        <table>
            <thead><tr><th>Month</th><th>All Tickets</th><th>Refund Tickets</th><th>Refund Rate</th><th>Refund Amount</th></tr></thead>
            <tbody>{month_rows}</tbody>
        </table>
    </section>

    <section>
        <h2>Refunds by Reason Code</h2>
        <div class="chart-container" style="max-width: 550px;">
            <canvas id="reasonChart"></canvas>
        </div>
        <table>
            <thead><tr><th>Reason Code</th><th>Count</th><th>Total Amount</th><th>% of Total</th><th>Avg Amount</th></tr></thead>
            <tbody>{reason_rows}</tbody>
        </table>
        <p class="note">GW-OTHER is the default dropdown option; a large share may be miscoded. See reclassification section below.</p>
    </section>

    {classify_section}

    <section>
        <h2>Refunds by Team</h2>
        <table>
            <thead><tr><th>Team</th><th>Total Tickets</th><th>Refund Tickets</th><th>Refund Rate</th><th>Refund Amount</th></tr></thead>
            <tbody>{team_rows}</tbody>
        </table>
    </section>

    <section>
        <h2>Refunds by Agent (Top 20)</h2>
        <p>Sorted by total refund amount. Refund rate accounts for each agent's ticket volume.</p>
        <table>
            <thead><tr><th>ID</th><th>Name</th><th>Team</th><th>Tickets</th><th>Refunds</th><th>Rate</th><th>Total</th><th>Avg</th></tr></thead>
            <tbody>{agent_rows}</tbody>
        </table>
        <p class="note">High refund amounts for Returns Desk and Billing agents are expected given their role.
        Frontline agents with elevated refund rates may warrant review.</p>
    </section>

    <section>
        <h2>Policy Violations Flagged</h2>

        <h3>1. Refund + Replacement Both Issued</h3>
        <p>Policy §5 states: "In no case is a customer to receive both a refund and a replacement."</p>
        <div class="flag">
            <strong>{v1['count']} tickets</strong> had both a refund and a replacement issued,
            totalling <strong>₹{v1['total_refund']:,.0f}</strong> in refund costs.
        </div>
        <table>
            <thead><tr><th>Team</th><th>Count</th><th>Refund Amount</th></tr></thead>
            <tbody>{v1_team_rows}</tbody>
        </table>

        <h3>2. Goodwill Credits Exceeding ₹500 Cap</h3>
        <p>Policy §5 caps goodwill credits at ₹500/ticket with Team Lead approval.</p>
        <div class="flag">
            <strong>{v2['count']} GW-OTHER refunds</strong> exceed ₹500.
            Total: <strong>₹{v2['total_amount']:,.0f}</strong>.
            Amount over the ₹500 cap: <strong>₹{v2['amount_over_cap']:,.0f}</strong>.
        </div>
        <p class="note">Most of these are likely miscoded (should be a different reason code, not goodwill).
        The true goodwill overspend is much smaller — but cannot be determined without reclassification.</p>
    </section>

    <section>
        <h2>Reconciliation</h2>
        <p>Automated checks verifying that report totals are internally consistent.</p>
        <table>
            <thead><tr><th></th><th>Check</th><th>Expected</th><th>Actual</th></tr></thead>
            <tbody>{recon_rows}</tbody>
        </table>
    </section>

    <script>
        // Monthly refund amount trend
        new Chart(document.getElementById('monthAmountChart'), {{
            type: 'line',
            data: {{
                labels: {month_labels},
                datasets: [{{
                    label: 'Refund Amount (₹)',
                    data: {month_amounts},
                    borderColor: '#2563eb',
                    backgroundColor: 'rgba(37,99,235,0.08)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 3,
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ display: false }}, title: {{ display: true, text: 'Monthly Refund Amount (₹)' }} }},
                scales: {{ y: {{ beginAtZero: true }} }}
            }}
        }});

        // Monthly refund count
        new Chart(document.getElementById('monthCountChart'), {{
            type: 'bar',
            data: {{
                labels: {month_labels},
                datasets: [{{
                    label: 'Refund Count',
                    data: {month_counts},
                    backgroundColor: '#64748b',
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ display: false }}, title: {{ display: true, text: 'Monthly Refund Count' }} }},
                scales: {{ y: {{ beginAtZero: true }} }}
            }}
        }});

        // Reason code breakdown
        new Chart(document.getElementById('reasonChart'), {{
            type: 'bar',
            data: {{
                labels: {reason_labels},
                datasets: [{{
                    label: 'Amount (₹)',
                    data: {reason_amounts},
                    backgroundColor: ['#e6a817','#2563eb','#10b981','#6366f1','#f43f5e','#8b5cf6','#f59e0b','#06b6d4'],
                }}]
            }},
            options: {{
                indexAxis: 'y',
                responsive: true,
                plugins: {{ legend: {{ display: false }}, title: {{ display: true, text: 'Refund Amount by Reason Code (₹)' }} }},
                scales: {{ x: {{ beginAtZero: true }} }}
            }}
        }});
    </script>
</body>
</html>"""

    output_path = OUTPUT_DIR / "report.html"
    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Report saved to {output_path}")
    return output_path
