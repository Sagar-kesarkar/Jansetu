# Financial data provenance

## Current adapter inputs

Adapter names identify intended publishers, not verified live integrations.

| Adapter | Actual input in fetch_and_parse |
| --- | --- |
| maharashtra_finance | Hard-coded financial rows in Python |
| data_gov_in | Local investment_plans.csv with derived release/expenditure values |
| egramswaraj | Hard-coded release/payment examples |

The data_gov_in adapter calculates releases as allocation × 0.86 and expenditure as allocation × 0.86 × 0.80. These are constructed values, not retrieved transactions. URLs, publisher labels, approvals and VERIFIED flags do not independently validate the figures.

Treat financial views as demonstrations, not official accounts or a basis for spending decisions.

## Accounting model

Amounts use INR with explicit lakh/crore conversions. Revised estimates take precedence over budget estimates; actual expenditure takes precedence over provisional payments. Releases remain separate. Apply precedence within matching district, scheme, fiscal-year and accounting scope; reconcile sources before combining them.

## Before authoritative use

Replace demo inputs with documented downloads or APIs. Retain exact resource identifiers, publication/retrieval dates, licences, raw evidence and checksums. Validate units, geographic mappings, fiscal years and totals. Review records before publication.

Reference CSVs and synthetic grievance fixtures do not prove complete national coverage or indicator accuracy. Reconcile the data/reference and backend/data/reference copies when changing coverage.
