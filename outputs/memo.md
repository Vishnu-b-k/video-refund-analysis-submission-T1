# Memo: Support Refund Analysis

**To:** Arjun Mehta, Finance Controller  
**From:** Data Engineering  
**Date:** October 2026  
**Subject:** Q1-Q2 2026 Support Refunds Deep-Dive & Correction

### Executive Summary
The headline figure of "over ₹1 crore a quarter" in support refunds is incorrect due to a data migration bug. The true refund spend is approximately **₹12 lakh per quarter** (₹67.1 lakh total over the 18-month period). 

While the total spend is much lower than feared, our analysis of the 2,340 refund tickets revealed two critical policy violations costing the company roughly **₹6 lakh**:
1. **₹5.74L** lost due to agents issuing *both* a refund and a replacement on the same ticket (166 incidents).
2. **₹29.1L** spent under the "Goodwill/Other" category, which is the default dropdown option and heavily overused. A large portion of these exceed the ₹500 goodwill cap.

### Key Findings & Corrections

**1. The "Crore a Quarter" Data Bug**
When migrating from Freshdesk to the new helpdesk in Sept 2025, legacy tickets were re-imported. Freshdesk stored monetary values in paise, while the new system uses rupees. The raw data exports contained these unadjusted legacy values (inflated by 100x), causing the ₹1 crore/quarter illusion. Once deduplicated and converted, the true spend aligns with IT's internal reporting.

**2. Policy Violations: Double Compensation**
Policy explicitly forbids issuing both a refund and a replacement for the same order. We flagged 166 tickets where this occurred, costing ₹5.74L. The Chat Frontline (50 tickets) and Logistics (48 tickets) teams are the primary sources of this error.

**3. The "Goodwill" Black Hole**
The `GW-OTHER` reason code accounts for 43% of all refund spend (₹29.1L). Because it is the first option in the agent dropdown, it is being used as a catch-all for laziness or uncertainty. By parsing the actual customer messages and agent notes, we confidently reclassified 400 of these tickets into standard categories (like Cancelled Orders, Lost in Transit, and Duplicate Payments). The remaining ambiguous tickets require tighter managerial review, as 879 of the 991 `GW-OTHER` tickets exceeded the ₹500 policy cap.

**4. Agent & Team Performance**
The Returns Desk processes the highest volume of refunds (40-50% rate), which is expected by design. However, certain frontline agents have elevated refund rates compared to their peers. We have provided a detailed dashboard ranking agents by total refund spend to help Team Leads target their QA efforts.

### Next Steps & Recommendations
1. **System Fix:** Reconfigure the helpdesk dropdown to remove `GW-OTHER` as the default first option. Force agents to select a specific reason, or require a text justification for goodwill credits over ₹500.
2. **Process Control:** Implement a hard system block preventing an agent from triggering a refund API if a replacement has already been processed for that `order_id` (and vice-versa).
3. **Reporting:** Use the attached automated pipeline (`run.py`) to generate this board-ready report monthly. It automatically handles the legacy data conversion and flags ongoing policy violations.

*The full interactive data report is attached for the upcoming board pack.*
