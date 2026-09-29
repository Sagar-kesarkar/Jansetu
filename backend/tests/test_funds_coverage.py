"""Release regression: coverage must work with empty and state-only ledgers."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import Base
from app.db.models import District
from app.db.financial_models import FinancialRecord
from app.services.funds_service import FundsService


@pytest.mark.parametrize('kind', ['empty', 'state', 'district', 'unverified'])
def test_coverage_with_reference_districts(kind):
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            db.add_all([
                District(code='MH_PUNE', name='Pune', state='Maharashtra'),
                District(code='TN_CHENNAI', name='Chennai', state='Tamil Nadu'),
            ])
            if kind != 'empty':
                db.add(FinancialRecord(
                    import_run_id=1, source_id=1, state_code='MH',
                    district_code='MH_PUNE' if kind == 'district' else None,
                    financial_stage='BE', fiscal_year='2026-27', amount_inr=100,
                    verification_status='PENDING_REVIEW' if kind == 'unverified' else 'VERIFIED',
                ))
            db.commit()
            result = FundsService.get_coverage(db)
            assert result['covered_states'] == (['Maharashtra'] if kind in ('state', 'district') else [])
            assert result['covered_districts'] == (['Pune'] if kind == 'district' else [])
            assert result['covered_district_codes'] == (['MH_PUNE'] if kind == 'district' else [])
    finally:
        engine.dispose()
