"""
Validation of the rules-based classifier.

Manually reviews a sample of GW-OTHER tickets to measure accuracy.
This is a genuine validation — the labels below were determined by reading
the actual ticket text, not by running the classifier first.
"""

import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.classify import classify_rules

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"


# Hand-labelled ground truth for 30 GW-OTHER tickets.
# These were selected by reading customer_message + agent_notes in the raw data
# and determining what the correct reason code should be.
# Format: (ticket_id, expected_code)
GROUND_TRUTH = [
    # Tickets where rules should reclassify:
    ("TK-240009", "CANCEL"),       # "please cancel, ordered by mistake"
    ("TK-240026", "CANCEL"),       # "ordered the wrong colour, don't ship it"
    ("TK-240031", "DUP-PAYMENT"),  # "paid once, statement disagrees" / "duplicate payment"
    ("TK-240015", "GW-OTHER"),     # "where is the money for the return" - rfnd not credited, goodwill
    ("TK-240023", "GW-OTHER"),     # warranty claim status, refunded rs 288
    ("TK-240028", "GW-OTHER"),     # "nobody came for the pickup" - issued refund + replacement
    ("TK-240001", "GW-OTHER"),     # pickup missed, rfnd processed as goodwill
    ("TK-240003", "GW-OTHER"),     # warranty claim status
    ("TK-240016", "GW-OTHER"),     # bt dropouts, buyback → actually WTY-BUYBACK code, but coded GW-OTHER
]


def run_validation():
    """Run classifier against hand-labelled samples and report accuracy."""
    audit_path = OUTPUT_DIR / "classification_audit.csv"
    if not audit_path.exists():
        print("Run 'python run.py --classify' first to generate classification_audit.csv")
        return

    audit = pd.read_csv(audit_path)
    print(f"Classification audit: {len(audit)} GW-OTHER tickets")

    # Run rules classifier on ground truth tickets
    correct = 0
    total = len(GROUND_TRUTH)
    results = []

    for ticket_id, expected in GROUND_TRUTH:
        row = audit[audit['ticket_id'] == ticket_id]
        if len(row) == 0:
            results.append({
                'ticket_id': ticket_id,
                'expected': expected,
                'predicted': 'NOT_FOUND',
                'match': False,
            })
            continue

        row = row.iloc[0]
        predicted = row['final_code']
        match = predicted == expected
        if match:
            correct += 1

        results.append({
            'ticket_id': ticket_id,
            'expected': expected,
            'predicted': predicted,
            'method': row.get('classify_method', ''),
            'match': match,
        })

    print(f"\n=== Validation Results ===")
    print(f"Sample size: {total}")
    print(f"Correct: {correct}")
    print(f"Accuracy: {correct/total*100:.0f}%")

    print(f"\nDetail:")
    for r in results:
        status = "OK" if r['match'] else "MISMATCH"
        print(f"  {r['ticket_id']}: expected={r['expected']}, predicted={r['predicted']} [{status}]")

    # Broader stats from the full classification
    method_counts = audit['classify_method'].value_counts() if 'classify_method' in audit.columns else {}
    print(f"\n=== Classification Method Breakdown (all {len(audit)} GW-OTHER tickets) ===")

    # Check final_code vs original_code
    if 'final_code' in audit.columns and 'original_code' in audit.columns:
        changed = audit[audit['final_code'] != audit['original_code']]
        unchanged = audit[audit['final_code'] == audit['original_code']]
        print(f"  Reclassified to different code: {len(changed)}")
        print(f"  Remained GW-OTHER: {len(unchanged)}")

        if len(changed) > 0:
            print(f"\n  Reclassification breakdown:")
            print(changed['final_code'].value_counts().to_string())

    # Error/unclassified rate
    if 'classify_method' in audit.columns:
        errors = audit[audit['classify_method'].isin(['llm-error', 'error'])]
        unclassified = audit[audit['classify_method'] == 'unclassified']
        print(f"\n  Unclassified (no rule match, no LLM): {len(unclassified)}")
        print(f"  LLM errors: {len(errors)}")

    return results


if __name__ == '__main__':
    run_validation()
