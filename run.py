"""
Main entry point. Runs the full pipeline and generates the report.

Usage:
    python run.py                      # deterministic analysis only
    python run.py --classify           # also run rules-based GW-OTHER reclassification
    python run.py --classify --llm     # also use LLM for ambiguous tickets (needs GEMINI_API_KEY)
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.pipeline import run_pipeline, compute_metrics, reconcile, OUTPUT_DIR
from src.classify import classify_gw_other
from src.report import generate_report


def main():
    parser = argparse.ArgumentParser(description='Vireo Audio refund analysis')
    parser.add_argument('--classify', action='store_true',
                        help='Run GW-OTHER reclassification (rules-based)')
    parser.add_argument('--llm', action='store_true',
                        help='Also use LLM for ambiguous tickets (needs GEMINI_API_KEY env var)')
    args = parser.parse_args()

    # --- Step 1: Run deterministic pipeline ---
    tickets, metrics = run_pipeline()

    # --- Step 2: Optional classification ---
    classification_summary = None

    if args.classify:
        api_key = os.environ.get('GEMINI_API_KEY') if args.llm else None
        if args.llm and not api_key:
            print("\nWARNING: --llm flag set but GEMINI_API_KEY not found in environment.")
            print("Running rules-based classification only.\n")

        tickets = classify_gw_other(tickets, api_key=api_key)

        # Recompute metrics with reclassified codes
        # Swap refund_reason_code with reclassified_code for reporting
        original_codes = tickets['refund_reason_code'].copy()
        tickets['refund_reason_code'] = tickets['reclassified_code']

        gw_original = (original_codes == 'GW-OTHER').sum()
        gw_remaining = (tickets['refund_reason_code'] == 'GW-OTHER').sum()
        reclassified = tickets[
            (original_codes == 'GW-OTHER') &
            (tickets['reclassified_code'] != 'GW-OTHER')
        ]

        classification_summary = {
            'total_gw': int(gw_original),
            'rules_classified': int((tickets['classify_method'] == 'rule-match').sum()),
            'llm_classified': int(tickets['classify_method'].isin(['llm']).sum()),
            'still_gw': int(gw_remaining),
            'reclassified_breakdown': reclassified['reclassified_code'].value_counts().to_dict(),
        }

        print("\n--- Recomputing metrics with reclassified codes ---")
        from src.pipeline import flag_policy_violations
        tickets = flag_policy_violations(tickets)
        old_cleaning = metrics.get('cleaning_log', {})
        metrics = compute_metrics(tickets)
        metrics['cleaning_log'] = old_cleaning
        recon = reconcile(metrics)
        metrics['reconciliation'] = recon

        # Save classification audit trail
        OUTPUT_DIR.mkdir(exist_ok=True)
        classify_audit = tickets[original_codes == 'GW-OTHER'][[
            'ticket_id', 'refund_reason_code', 'reclassified_code',
            'classify_method', 'classify_confidence', 'classify_evidence',
            'customer_message', 'agent_notes'
        ]].copy()
        classify_audit.rename(columns={'refund_reason_code': 'final_code'}, inplace=True)
        classify_audit['original_code'] = 'GW-OTHER'
        classify_audit.to_csv(OUTPUT_DIR / 'classification_audit.csv', index=False)
        print(f"Classification audit saved to {OUTPUT_DIR / 'classification_audit.csv'}")

    # --- Step 3: Generate report ---
    print("\n--- Generating HTML report ---")
    report_path = generate_report(metrics, classification_summary)

    # --- Step 4: Save final metrics ---
    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(OUTPUT_DIR / 'metrics.json', 'w') as f:
        json.dump(metrics, f, indent=2, default=str)

    # Save enriched refund tickets
    refund_df = tickets[tickets['refund_amount_inr'].notna()]
    refund_df.to_csv(OUTPUT_DIR / 'refund_tickets.csv', index=False)

    print(f"\n{'='*50}")
    print(f"Done. Open {report_path} in a browser to view the report.")
    print(f"{'='*50}")


if __name__ == '__main__':
    main()
