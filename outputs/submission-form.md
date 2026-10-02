# Vireo Audio Take-Home Submission

**Candidate Name:** [Your Name]
**Role:** Data / Software Engineer

### 1. The Business Goal
The Finance Controller was alarmed by a reported "crore a quarter" in support refunds. The numerical business goal was to:
1. Validate this figure (reduce the reported error rate to 0%).
2. Identify avoidable refund costs caused by operational leaks (target: reduce double-compensation from ~₹3L/quarter to ₹0).
3. Provide actionable visibility into the `GW-OTHER` black box.

### 2. The Core Insight
The "crore a quarter" was a data migration bug. Legacy Freshdesk tickets were re-imported with monetary values in paise, not rupees. The true spend is ~₹12 lakh/quarter. However, there are real operational leaks:
- Agents are violating policy by issuing both refunds AND replacements on the same ticket (costing ₹5.7L over 18 months).
- 43% of refund spend is lumped into `GW-OTHER` because it's the default dropdown option, obscuring true reasons.

### 3. Trade-offs and Engineering Decisions
- **No Database / Heavy Frameworks:** With a 5-hour constraint, setting up a database or React frontend is fake complexity. Pandas and simple Python scripts are more than capable of processing ~15,000 rows quickly and deterministically.
- **Two-Stage Classification:** I did not blindly throw every ticket at an LLM. I built a fast, free, deterministic RegEx rules engine that successfully reclassifies 40% of the miscoded tickets. The LLM is strictly reserved as an optional fallback for ambiguous text.
- **Static HTML Report:** I generated a plain HTML file with Chart.js. It's portable, instantly readable by non-technical stakeholders (like the Finance Controller), and requires no infrastructure to host.

### 4. What I would do with more time
- **Automated Dropdown Reordering:** Feed the text classification model back into the helpdesk so it suggests the correct reason code dynamically before the agent hits submit.
- **System Hardening:** Build an API middleware layer that outright rejects a refund request if a replacement exists for that `order_id` in the database.
- **Deeper Text Analysis:** Run sentiment analysis on the truly ambiguous `GW-OTHER` tickets to see if refunds are being used to de-escalate angry customers vs. proactively delighting them.
