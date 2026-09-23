# JanSetu (जनसेतु) — Financial Data Sources & Provenance Audit

This document describes all official government financial data sources, ingestion adapters, stage precedence rules, and verification procedures integrated into the JanSetu platform.

---

## 🏛 Data Sources Catalog

| Source ID | Source Name | Jurisdiction / Publisher | Fiscal Years | Integration Method | Verification Status | Official Portal URL |
|---|---|---|---|---|---|---|
| `maharashtra_finance` | Maharashtra State Finance Budget | Finance Department, Government of Maharashtra | `2026-27` (Current), `2025-26` | REST Adapter / JSON Snapshot | `VERIFIED` | [https://finance.maharashtra.gov.in](https://finance.maharashtra.gov.in) |
| `data_gov_in` | Open Government Data (OGD) India | MeitY & National Informatics Centre (NIC) | `2026-27`, `2025-26` | OGD Resource API / CSV Parser | `VERIFIED` | [https://data.gov.in/resource/budget-outlays](https://data.gov.in/resource/budget-outlays) |
| `egramswaraj` | eGramSwaraj Panchayati Raj Portal | Ministry of Panchayati Raj, Govt of India | `2026-27` | PRIAsoft Financial Adapter | `VERIFIED` | [https://egramswaraj.gov.in](https://egramswaraj.gov.in) |

---

## ⚖️ Financial Stage Precedence & Arithmetic Rules

To prevent financial anomalies and double-counting across government accounting stages, JanSetu enforces strict precedence rules (`services/funds_service.py`):

1. **Allocations (Budget Estimation vs Revised Estimation)**:
   - **Rule**: Revised Estimates (`RE`) supersede Budget Estimates (`BE`) for the exact same fiscal year, jurisdiction, sector, and scheme.
   - **Anti-Double-Counting**: $\text{Allocated} = \text{Amount}_{\text{RE}}$ (if present), else $\text{Amount}_{\text{BE}}$. Under no circumstances are `RE + BE` summed together.
2. **Expenditures (Provisional Payments vs Audited Actuals)**:
   - **Rule**: Audited Actuals (`ACTUAL`) supersede provisional payments (`PAYMENT`).
   - **Anti-Double-Counting**: $\text{Recorded Expenditure} = \text{Amount}_{\text{ACTUAL}}$ (if present), else $\text{Amount}_{\text{PAYMENT}}$.
3. **Fund Releases (Separate Accounting Stage)**:
   - **Rule**: Fund Releases (`RELEASE`) represent treasury transfers from State/Central pools to District Treasuries. They are tracked as an independent intermediate stage.
4. **Derived Balance**:
   $$\text{Available Funds} = \text{Funds Released} - \text{Recorded Expenditure}$$
5. **Anomaly Flagging**:
   - If $\text{Recorded Expenditure} > \text{Funds Released}$ or $\text{Funds Released} > \text{Allocated}$, the record is flagged with an anomaly notice and visible warning in both Citizen and Officials views, rather than being silently masked.

---

## 🔍 Provenance & Review Workflow

1. **Staged Ingestion**: Raw data imports are recorded in `financial_import_runs` with status `STAGED`.
2. **Administrative Approval**: Financial officers review line items and approve or reject them via `/api/v1/admin/funds/imports/{id}/approve`.
3. **Public Visibility**: Only records with `verification_status = 'VERIFIED'` are published to public APIs (`/api/v1/funds/...`).
4. **Coverage Integrity**: Where coverage is partial (e.g., specific districts with pending treasury releases), the platform displays a clear `partial` coverage indicator with an explicit explanation.
