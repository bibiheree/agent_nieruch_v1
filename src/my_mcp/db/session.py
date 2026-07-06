import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

# Definiujemy ścieżkę do bazy w kontenerze Docker (/app/data/app.db)
BASE_DIR = "/app"
DB_PATH = os.path.join(BASE_DIR, "data", "app.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Konfiguracja silnika z obsługą future-flag dla SQLAlchemy 2.0+
engine = create_engine(DATABASE_URL, future=True)

# ---------------------------------------------------------------------
# SQLite WAL (Write-Ahead Logging) Mode
# Gwarantuje brak blokad "database is locked" przy jednoczesnych zapytaniach z n8n
# ---------------------------------------------------------------------
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)