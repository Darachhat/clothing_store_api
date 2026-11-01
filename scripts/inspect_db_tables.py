import sys
sys.path.insert(0, "/app")

from sqlalchemy import create_engine, text
from app.core.config import settings

url = (
    f"postgresql+psycopg2://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
)
engine = create_engine(url)

with engine.connect() as conn:
    rows = conn.execute(text("""
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema IN ('public', 'base_data', 'data', 'auth', 'track')
        ORDER BY table_schema, table_name
    """)).fetchall()

    for s, t in rows:
        try:
            cnt = conn.execute(text(f'SELECT count(1) FROM "{s}"."{t}"')).scalar()
            if cnt > 0:
                print(f"{s}.{t}: {cnt} rows")
        except Exception as e:
            print(f"{s}.{t}: error: {e}")

