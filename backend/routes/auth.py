from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from passlib.context import CryptContext
from pymongo.errors import DuplicateKeyError

from backend.auth.jwt import create_access_token
from backend.db.models import LoginRequest, RegisterRequest
from backend.db.mongo import get_collection

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user: RegisterRequest):
    users = get_collection("users")
    if await users.find_one({"email": user.email}, {"_id": 1}):
        raise HTTPException(status_code=409, detail="Email already registered")

    user_doc = {
        "name": user.name.strip(),
        "email": user.email,
        "password": pwd_context.hash(user.password),
        "created_at": utc_now(),
    }
    try:
        result = await users.insert_one(user_doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Email already registered")

    return {"message": "User created", "user_id": str(result.inserted_id)}


@router.post("/login")
async def login(credentials: LoginRequest):
    users = get_collection("users")
    user = await users.find_one({"email": credentials.email})
    if not user or not pwd_context.verify(credentials.password, user.get("password", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"sub": str(user["_id"]), "email": user["email"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": str(user["_id"]), "name": user.get("name", ""), "email": user["email"]},
    }
