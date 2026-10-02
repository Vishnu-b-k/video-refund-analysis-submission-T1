"""
GW-OTHER ticket reclassification.

Two-stage approach:
  1. Rules-based: catches obvious cases from keywords in text (fast, free, deterministic)
  2. LLM-assisted: for tickets the rules can't confidently classify (optional, needs API key)

This separation is deliberate — the rules handle ~40-50% of cases reliably,
and we only send ambiguous tickets to the LLM.
"""

import re
import json
import time
import pandas as pd
from pathlib import Path

from src.prompts import CLASSIFY_FINAL

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"

VALID_CODES = {
    'DOA-REPL', 'LOST-TRANSIT', 'DUP-PAYMENT', 'CANCEL',
    'PRICE-ADJ', 'RETURN-QC-OK', 'WTY-BUYBACK', 'GW-OTHER'
}


# ---------------------------------------------------------------------------
# Stage 1: Rules-based classification
# ---------------------------------------------------------------------------

# Patterns checked against combined (customer_message + agent_notes), lowercased.
# Order matters — first match wins.
RULES = [
    # Cancellations
    (r'\bcancel', 'CANCEL'),
    (r'\bcancellation\b', 'CANCEL'),
    (r'\bcancelled before dispatch\b', 'CANCEL'),

    # Duplicate / double payment
    (r'\bduplicate payment\b', 'DUP-PAYMENT'),
    (r'\bdouble charge\b', 'DUP-PAYMENT'),
    (r'\bcharged twice\b', 'DUP-PAYMENT'),
    (r'\bduplicate txn\b', 'DUP-PAYMENT'),
    (r'\bpaid twice\b', 'DUP-PAYMENT'),
    (r'\bdup.*(?:payment|charge)\b', 'DUP-PAYMENT'),

    # Lost in transit / not delivered
    (r'\blost in transit\b', 'LOST-TRANSIT'),
    (r'\bnot delivered\b', 'LOST-TRANSIT'),
    (r'\bnever delivered\b', 'LOST-TRANSIT'),
    (r'\bnot received\b', 'LOST-TRANSIT'),
    (r'\bshipment not received\b', 'LOST-TRANSIT'),
    (r'\bpackage.*(?:lost|missing)\b', 'LOST-TRANSIT'),

    # Dead on arrival / damaged
    (r'\bdead on arrival\b', 'DOA-REPL'),
    (r'\bdamaged.*(?:box|transit|delivery)\b', 'DOA-REPL'),
    (r'\btransit damage\b', 'DOA-REPL'),
    (r'\bcrushed\b.*\b(?:box|package)\b', 'DOA-REPL'),
    (r'\bbroken on arrival\b', 'DOA-REPL'),
    (r'\bdoa\b', 'DOA-REPL'),

    # Price / coupon adjustment
    (r'\bcoupon\b', 'PRICE-ADJ'),
    (r'\bdiscount.*(?:not applied|missing)\b', 'PRICE-ADJ'),
    (r'\bprice.*(?:match|differ|wrong)\b', 'PRICE-ADJ'),
    (r'\bpricing error\b', 'PRICE-ADJ'),
    (r'\bfestive offer\b', 'PRICE-ADJ'),
    (r'\boffer.*(?:vanish|not applied)\b', 'PRICE-ADJ'),

    # Return QC
    (r'\breturn.*(?:qc|quality check)\b', 'RETURN-QC-OK'),
    (r'\breverse pickup\b.*\brefund\b', 'RETURN-QC-OK'),
    (r'\bpickup.*refund\b', 'RETURN-QC-OK'),
    (r'\breturn.*(?:processed|completed)\b', 'RETURN-QC-OK'),

    # Warranty buyback
    (r'\bbuyback\b', 'WTY-BUYBACK'),
    (r'\bwarranty.*refund\b', 'WTY-BUYBACK'),
]


def classify_rules(customer_message, agent_notes):
    """Try to classify a GW-OTHER ticket using keyword rules.
    Returns (code, confidence) or (None, None) if no rule matches."""
    text = f"{customer_message or ''} {agent_notes or ''}".lower()

    for pattern, code in RULES:
        if re.search(pattern, text):
            return code, 'rule-match'

    return None, None


# ---------------------------------------------------------------------------
# Stage 2: LLM classification (optional)
# ---------------------------------------------------------------------------

def classify_llm_batch(tickets_df, api_key=None, model='gemini-2.0-flash'):
    """
    Classify tickets using Google Gemini API.
    Falls back gracefully if no API key is provided.

    Returns a list of dicts with: ticket_id, predicted_code, confidence, evidence, method
    """
    if not api_key:
        print("  No API key provided, skipping LLM classification.")
        return []

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        llm = genai.GenerativeModel(model)
    except ImportError:
        print("  google-generativeai not installed. Run: pip install google-generativeai")
        return []

    results = []
    failed = 0
    total = len(tickets_df)

    for i, (_, row) in enumerate(tickets_df.iterrows()):
        if (i + 1) % 50 == 0:
            print(f"  Classifying {i+1}/{total}...")

        prompt = CLASSIFY_FINAL.format(
            customer_message=row.get('customer_message', ''),
            agent_notes=row.get('agent_notes', ''),
        )

        try:
            response = llm.generate_content(prompt)
            text = response.text.strip()

            # Extract JSON from response (handle markdown code blocks)
            if '```' in text:
                text = text.split('```')[1]
                if text.startswith('json'):
                    text = text[4:]
                text = text.strip()

            parsed = json.loads(text)
            code = parsed.get('reason_code', 'GW-OTHER')
            confidence = parsed.get('confidence', 'low')
            evidence = parsed.get('evidence', '')

            # Validate the output
            if code not in VALID_CODES:
                code = 'GW-OTHER'
                confidence = 'invalid-output'

            results.append({
                'ticket_id': row['ticket_id'],
                'predicted_code': code,
                'confidence': confidence,
                'evidence': evidence,
                'method': 'llm',
            })

        except Exception as e:
            failed += 1
            results.append({
                'ticket_id': row['ticket_id'],
                'predicted_code': 'GW-OTHER',
                'confidence': 'error',
                'evidence': str(e)[:100],
                'method': 'llm-error',
            })

        # Basic rate limiting
        time.sleep(0.3)

    if failed > 0:
        print(f"  LLM classification: {failed}/{total} failures")

    return results


# ---------------------------------------------------------------------------
# Main classification entry point
# ---------------------------------------------------------------------------

def classify_gw_other(tickets, api_key=None):
    """
    Reclassify GW-OTHER tickets. Returns the tickets df with new columns:
      - reclassified_code: the new reason code (or GW-OTHER if unchanged)
      - classify_method: 'rule-match', 'llm', 'llm-error', or 'unclassified'
      - classify_confidence: confidence level
      - classify_evidence: supporting text
    """
    tickets = tickets.copy()

    # Initialize new columns
    tickets['reclassified_code'] = tickets['refund_reason_code']
    tickets['classify_method'] = 'original'
    tickets['classify_confidence'] = ''
    tickets['classify_evidence'] = ''

    # Only reclassify GW-OTHER tickets
    gw_mask = tickets['refund_reason_code'] == 'GW-OTHER'
    gw_tickets = tickets[gw_mask].copy()
    print(f"\nClassifying {len(gw_tickets)} GW-OTHER tickets...")

    # Stage 1: Rules
    rule_results = []
    for idx, row in gw_tickets.iterrows():
        code, method = classify_rules(row['customer_message'], row['agent_notes'])
        if code:
            tickets.loc[idx, 'reclassified_code'] = code
            tickets.loc[idx, 'classify_method'] = method
            tickets.loc[idx, 'classify_confidence'] = 'high'
            rule_results.append(idx)

    rule_count = len(rule_results)
    remaining = gw_tickets.drop(index=rule_results)
    print(f"  Rules classified: {rule_count}/{len(gw_tickets)}")
    print(f"  Remaining for LLM: {len(remaining)}")

    # Stage 2: LLM (only for unresolved tickets)
    if len(remaining) > 0 and api_key:
        llm_results = classify_llm_batch(remaining, api_key=api_key)
        for res in llm_results:
            mask = tickets['ticket_id'] == res['ticket_id']
            tickets.loc[mask, 'reclassified_code'] = res['predicted_code']
            tickets.loc[mask, 'classify_method'] = res['method']
            tickets.loc[mask, 'classify_confidence'] = res['confidence']
            tickets.loc[mask, 'classify_evidence'] = res['evidence']
    elif len(remaining) > 0:
        tickets.loc[remaining.index, 'classify_method'] = 'unclassified'

    # Summary
    reclassified = tickets[gw_mask & (tickets['reclassified_code'] != 'GW-OTHER')]
    print(f"\n  Reclassified away from GW-OTHER: {len(reclassified)}")
    print(f"  Still GW-OTHER: {len(gw_tickets) - len(reclassified)}")

    if len(reclassified) > 0:
        print("\n  Reclassification breakdown:")
        print(reclassified['reclassified_code'].value_counts().to_string())

    return tickets
