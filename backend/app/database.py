import os

try:
    import dotenv  # type: ignore[import-not-found]
except ImportError:  # python-dotenv pode não estar instalado no ambiente atual
    dotenv = None


def load_dotenv(*args, **kwargs):
    if dotenv is None:
        return False
    return dotenv.load_dotenv(*args, **kwargs)


try:
    from sqlalchemy import MetaData, create_engine  # type: ignore[import-not-found]
    from sqlalchemy.engine import URL  # type: ignore[import-not-found]
    from sqlalchemy.orm import DeclarativeBase, sessionmaker  # type: ignore[import-not-found]
except ImportError as exc:
    raise RuntimeError("Instale a dependência SQLAlchemy para que o banco funcione corretamente.") from exc

load_dotenv()  # lê o arquivo .env quando rodar fora do Docker

DB_HOST = os.getenv("DB_HOST", "")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")  # RNF05: nunca deixar senha no código
DB_SCHEMA = os.getenv("DB_SCHEMA", "unifit")

if not DB_HOST or not DB_PASSWORD:
    raise RuntimeError("Defina DB_HOST e DB_PASSWORD no arquivo .env (veja o .env.example).")

DATABASE_URL = URL.create(
    drivername="postgresql+psycopg2",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    query={"sslmode": "require"},  # o Supabase exige SSL
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 10},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    metadata = MetaData(schema=DB_SCHEMA)  # todas as tabelas ficam no schema "unifit"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
