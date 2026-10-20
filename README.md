# Mega-Cap Options Yield Screener (US & Europe)

A Python project that pulls live financial fundamentals and options chains for American and European mega-cap stocks, filters for profitable companies (`P/E Ratio > 0`), calculates annualized **Cash-Secured Put (CSP)** and **Covered Call (CC)** yields, and outputs both a clean **CSV** and an interactive **HTML / Streamlit Dashboard**.

---

## Project Structure

```text
megacap-options-screener/
├── pyproject.toml           # Package metadata & dependencies
├── requirements.txt         # Pip requirements
├── app.py                   # Interactive Streamlit web dashboard
├── screener/
│   ├── __init__.py
│   ├── universe.py          # Curated US & European Mega-Cap stock universe
│   ├── analytics.py         # Fundamental filtering, option chain selection & yield math
│   ├── exporter.py          # CSV & standalone interactive HTML dashboard generator
│   └── cli.py               # Rich CLI runner
└── tests/
    └── test_analytics.py    # Unit tests for option yield calculations & strike selection
```

---

## Yield Methodology

For each ticker passing `P/E > 0`, the screener selects the expiration date closest to `--dte` (default `30` days) and finds Out-of-the-Money (OTM) strikes closest to `--otm` (default `5%` OTM):

1. **Cash-Secured Put (CSP) Annualized Yield**:
   $$\text{CSP Annualized Yield (\%)} = \left(\frac{\text{Put Premium}}{\text{Put Strike}}\right) \times \left(\frac{365}{\text{DTE}}\right) \times 100$$

2. **Covered Call (CC) Static Annualized Yield**:
   $$\text{CC Annualized Yield (\%)} = \left(\frac{\text{Call Premium}}{\text{Spot Price}}\right) \times \left(\frac{365}{\text{DTE}}\right) \times 100$$

3. **Covered Call (CC) If-Called Annualized Return**:
   $$\text{CC If-Called Return (\%)} = \left(\frac{\text{Call Premium} + \max(0, \text{Call Strike} - \text{Spot Price})}{\text{Spot Price}}\right) \times \left(\frac{365}{\text{DTE}}\right) \times 100$$

> **Note on European Mega-Caps:** Standard free Yahoo Finance endpoints provide full OCC options chains for European mega-caps via their liquid US-listed shares/ADRs (`NVO`, `ASML`, `SAP`, `AZN`, `NVS`, `SHEL`, `LIN`, `TTE`, `HSBC`, `UL`, `SNY`, `ARM`).

---

## Quick Start

### 1. Install Dependencies

```powershell
cd C:\Users\User\.gemini\antigravity\scratch\megacap-options-screener
pip install -r requirements.txt
```

### 2. Run the CLI Screener (Generates Terminal Table + CSV + Standalone HTML Dashboard)

```powershell
python -m screener.cli --dte 30 --otm 0.05 --min-pe 0
```

Options:
- `--region {ALL,US,EU}`: Filter by US or European mega-caps
- `--dte 30`: Target Days to Expiration
- `--otm 0.05`: Target Out-of-the-Money distance (`0.05` = 5% OTM)
- `--csv output/megacap_options_yields.csv`: Output CSV path
- `--html output/dashboard.html`: Output standalone interactive HTML dashboard

### 3. Launch the Streamlit Dashboard (Optional)

```powershell
streamlit run app.py
```
