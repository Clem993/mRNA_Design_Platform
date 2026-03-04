"""
Initialize the Railway PostgreSQL database with demo tables and data.

Reads connection details from environment variables (PGHOST, PGPORT, etc.)
or accepts a DATABASE_URL.

Usage:
    python demo/init_railway_db.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine, text


def get_database_url() -> str:
    """Build a PostgreSQL URL from environment variables."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return url

    host = os.environ.get("PGHOST", "localhost")
    port = os.environ.get("PGPORT", "5432")
    db = os.environ.get("PGDATABASE", "railway")
    user = os.environ.get("PGUSER", "postgres")
    pw = os.environ.get("PGPASSWORD", "")
    return f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{db}"


def main() -> None:
    url = get_database_url()
    safe_url = url.split("@")[-1] if "@" in url else url
    print(f"Connecting to: ...@{safe_url}")

    engine = create_engine(url)

    sql_path = os.path.join(os.path.dirname(__file__), "init_postgres.sql")
    with open(sql_path) as f:
        sql = f.read()

    # Remove the GRANT lines (Railway uses postgres user, not demo_user)
    lines = [
        line for line in sql.splitlines()
        if not line.strip().startswith("GRANT ")
    ]
    sql_clean = "\n".join(lines)

    with engine.begin() as conn:
        # Drop existing tables first (safe re-run)
        conn.execute(text("DROP TABLE IF EXISTS mrna_sequences CASCADE"))
        conn.execute(text("DROP TABLE IF EXISTS plasmid_backbones CASCADE"))
        print("Dropped existing tables (if any)")

        # Execute each statement
        for statement in sql_clean.split(";"):
            stmt = statement.strip()
            if stmt and not stmt.startswith("--"):
                conn.execute(text(stmt))

    # Verify
    with engine.connect() as conn:
        seq_count = conn.execute(text("SELECT COUNT(*) FROM mrna_sequences")).scalar()
        bb_count = conn.execute(text("SELECT COUNT(*) FROM plasmid_backbones")).scalar()

    print(f"Done! Created:")
    print(f"  mrna_sequences:   {seq_count} rows")
    print(f"  plasmid_backbones: {bb_count} rows")


if __name__ == "__main__":
    main()
