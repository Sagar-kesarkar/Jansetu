"""Run the feature preview locally against disposable synthetic data, never the user's DB."""
import os
from pathlib import Path
import secrets


def main():
    directory = Path(__file__).resolve().parent / '.local-preview'
    directory.mkdir(exist_ok=True)
    secret_file = directory / 'secret'
    if not secret_file.exists():
        secret_file.write_text(secrets.token_hex(32), encoding='utf-8')
    os.environ['SUBMISSION_SECRET'] = secret_file.read_text(encoding='utf-8').strip()
    os.environ['CITIZEN_REF_SALT'] = os.environ['SUBMISSION_SECRET']
    os.environ['DATABASE_URL'] = 'sqlite:///' + (directory / 'preview.db').as_posix()
    os.environ['EVIDENCE_DIR'] = str(directory / 'evidence')
    os.environ['GEMINI_API_KEY'] = ''
    os.environ['SUBMISSION_COOKIE_SECURE'] = 'false'
    os.environ['CORS_ORIGINS'] = 'http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174'
    from app.db.database import init_db, SessionLocal
    from app.db.seed import load_districts
    init_db()
    with SessionLocal() as db:
        load_districts(db)
        db.commit()
    import uvicorn
    uvicorn.run('app.main:app', host='127.0.0.1', port=8080, access_log=False)


if __name__ == '__main__':
    main()
