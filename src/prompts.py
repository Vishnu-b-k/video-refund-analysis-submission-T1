"""
Prompt templates for GW-OTHER reclassification.

Kept in one file so they can be shown during the screen recording walkthrough.
"""

# v1 - initial attempt, too open-ended (discarded: model invented new categories)
CLASSIFY_V1 = """Classify this support ticket into a refund reason category.
Ticket: {text}
Categories: {categories}
"""

# v2 - tighter constraints, structured output, explicit "unsure" option
CLASSIFY_V2 = """You are classifying a customer support ticket for an electronics company.
The ticket was coded as "Goodwill/Other" but may actually belong to a more specific category.

Given the customer message and agent notes below, pick the BEST matching reason code.
If the ticket genuinely describes a goodwill gesture (e.g. compensation for inconvenience,
SLA breach credit, one-time courtesy) or you are not confident, output GW-OTHER.

REASON CODES:
- DOA-REPL: Dead on arrival — product was defective/damaged out of box, refund chosen over replacement
- LOST-TRANSIT: Package lost or never delivered
- DUP-PAYMENT: Customer was charged twice or payment failed but money deducted
- CANCEL: Order cancelled before dispatch
- PRICE-ADJ: Price match, coupon not applied, or pricing error adjustment
- RETURN-QC-OK: Customer returned the product and it passed quality check
- WTY-BUYBACK: Warranty buy-back — product returned under warranty for refund instead of repair
- GW-OTHER: Genuine goodwill credit, compensation, or does not fit any above category

CUSTOMER MESSAGE:
{customer_message}

AGENT NOTES:
{agent_notes}

Respond with ONLY a JSON object: {{"reason_code": "<CODE>", "confidence": "high|medium|low", "evidence": "<brief reason>"}}
"""

# Final prompt used in production
CLASSIFY_FINAL = CLASSIFY_V2
