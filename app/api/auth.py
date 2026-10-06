import os, hashlib, hmac, base64, json, time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from app.db import SessionLocal
from app.models import User
from app.config import APP_SECRET

router = APIRouter()

def make_token(username: str, ttl: int = 86400) -> str:
    body = base64.urlsafe_b64encode(json.dumps({"u": username, "exp": int(time.time()) + ttl}).encode()).decode()
    sig = hmac.new(APP_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"

def read_token(token: str):
    try:
        body, sig = token.split(".")
        if not hmac.compare_digest(sig, hmac.new(APP_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()):
            return None
        data = json.loads(base64.urlsafe_b64decode(body.encode()))
        return data["u"] if data["exp"] > time.time() else None
    except Exception:
        return None


class AuthRequest(BaseModel):
    username: str
    password: str

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return base64.b64encode(salt + digest).decode()

def verify_password(password: str, encoded: str) -> bool:
    raw = base64.b64decode(encoded.encode())
    salt, stored = raw[:16], raw[16:]
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return hmac.compare_digest(stored, digest)

@router.post("/register")
def register(req: AuthRequest):
    if len(req.password) < 8:
        raise HTTPException(400, "Password must contain at least 8 characters")
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.username == req.username))
        if existing:
            raise HTTPException(409, "Username already exists")
        user = User(username=req.username, password_hash=hash_password(req.password))
        db.add(user)
        db.commit()
        db.refresh(user)
        return {"id": user.id, "username": user.username}

@router.post("/login")
def login(req: AuthRequest):
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == req.username))
        if not user or not verify_password(req.password, user.password_hash):
            raise HTTPException(401, "Invalid credentials")
        return {"authenticated": True, "username": user.username, "token": make_token(user.username)}

@router.get("/me")
def me(token: str):
    u = read_token(token)
    if not u:
        raise HTTPException(401, "Invalid or expired token")
    return {"username": u}
