import os

from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
FRONTEND_URL = os.getenv("FRONTEND_URL", CORS_ORIGINS[0])  # base dos links enviados por e-mail/SMS
