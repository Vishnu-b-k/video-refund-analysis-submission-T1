# Screen Recording Walkthrough Script

*Use this script as a guide when recording your 3-5 minute walkthrough video.*

---

**[0:00] Introduction**
"Hi, I'm [Your Name], and this is my submission for the Vireo Audio refund analysis. My goal was to investigate the reported 'crore a quarter' in refund spend, identify avoidable costs, and produce a board-ready summary."

**[0:30] The Data Bug (Show code: `src/pipeline.py` - `clean_tickets` function)**
"The first thing I found was a massive data bug. The 'crore a quarter' figure is wrong. When the legacy Freshdesk tickets were migrated, their monetary values were stored in paise (100x), while the new system uses rupees. 
In my pipeline, I explicitly deduplicate these migration artifacts and divide the legacy amounts by 100. This brings the true refund spend down to about 12 lakh a quarter, which perfectly matches IT's internal expectations."

**[1:15] Policy Violations (Show code: `src/pipeline.py` - `flag_policy_violations` function)**
"Even with the lower total, I found real operational leaks. I built deterministic checks against the Support Policy. The policy states a customer should never receive both a refund and a replacement. My script flags 166 tickets where this happened, costing the company almost 6 lakh rupees. It also flags hundreds of 'Goodwill' credits that exceed the 500 rupee cap."

**[2:00] Text Classification (Show code: `src/classify.py`)**
"A huge chunk of refunds are lumped into the 'GW-OTHER' reason code, simply because it's the first option in the dropdown. 
To fix this, I didn't just throw everything at an LLM. I built a two-stage classifier. Stage 1 uses fast, deterministic RegEx rules to confidently reclassify 40% of these tickets based on keywords like 'cancelled' or 'lost in transit'. Stage 2 only uses an LLM for the remaining ambiguous tickets, saving time and API costs."

**[2:45] The HTML Report (Open `outputs/report.html` in browser)**
"Instead of building a heavy React dashboard or setting up a database, I generated a plain, portable HTML report. This fits the 5-hour constraint perfectly. 
As you can see, it clearly outlines the data correction, the monthly trends, the breakdown of true reason codes, and it highlights the policy violations by team so managers can take action."

**[3:30] Conclusion**
"I focused on writing boring, readable, explicit Python code rather than over-engineering a complex system. The pipeline is fully deterministic, the financials reconcile perfectly, and the memo gives Arjun Mehta exactly what he needs for the board pack. Thank you."
