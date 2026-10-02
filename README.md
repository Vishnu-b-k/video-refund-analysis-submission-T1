# Vireo Audio Refund Analysis

This project processes customer support data to identify avoidable refund costs, flag policy violations, and provide an accurate financial picture for the board.

## The Problem
The Finance Controller reported support refunds running at "over a crore a quarter." Initial investigation revealed this was a **data migration bug**: legacy Freshdesk tickets stored monetary values in paise, which were re-imported without conversion, artificially inflating the totals by 100x. The true spend is ~₹12 lakh per quarter.

Despite the lower overall spend, there are real operational leaks:
1. Double compensation (refund + replacement issued on the same ticket).
2. Rampant misuse of the `GW-OTHER` (Goodwill) reason code, which is the default dropdown option.

## Solution Architecture
To stick to the 5-hour constraint, this project prioritizes **deterministic, explicit Python code** over complex frameworks. 

- **No databases**: Data easily fits in memory (pandas).
- **No over-engineering**: Simple scripts, no microservices, no React.
- **Two-stage classification**: 
  - Stage 1 uses RegEx rules to confidently reclassify 40% of the miscoded `GW-OTHER` tickets based on customer text.
  - Stage 2 (optional) uses an LLM for the remaining ambiguous tickets.
- **Static HTML Reporting**: Generates a clean, portable HTML report using Chart.js for the board pack.

## Repository Structure
```
.
├── data/                  # Place raw CSVs here
├── outputs/               # Generated reports and data exports
├── src/
│   ├── pipeline.py        # Core data cleaning, joins, and metric calculations
│   ├── classify.py        # GW-OTHER text classification (Rules + LLM)
│   ├── prompts.py         # LLM prompt templates
│   └── report.py          # HTML report generation
├── tests/
│   └── validate_classifier.py  # Ground-truth validation script
└── run.py                 # Main entry point
```

## Setup & Usage

### 1. Install Dependencies
```bash
pip install pandas numpy 
# Optional, for LLM classification:
pip install google-generativeai 
```

### 2. Add Data
Ensure the following files are in the `data/` directory:
- `tickets.csv`
- `agents.csv`
- `orders.csv`
- `customers.csv`
- `products.csv`

### 3. Run the Pipeline

**Option A: Fast, deterministic run (No AI)**
Cleans data, fixes the legacy paise bug, flags policy violations, and generates the report.
```bash
python run.py
```

**Option B: Rules-based reclassification**
Also attempts to reclassify `GW-OTHER` tickets using regex keyword matching on the ticket text.
```bash
python run.py --classify
```

**Option C: Full LLM reclassification (requires API key)**
Uses Gemini to classify ambiguous tickets that the rules couldn't catch.
```bash
export GEMINI_API_KEY="your-api-key"
python run.py --classify --llm
```

### 4. View Results
Open `outputs/report.html` in your browser. The cleaned audit trails are saved as CSVs in the `outputs/` directory.

## Testing
Run the validation script to check the accuracy of the rules-based classifier against a hand-labelled ground truth sample:
```bash
python tests/validate_classifier.py
```
