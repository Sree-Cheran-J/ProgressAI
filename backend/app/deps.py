from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from bson import ObjectId
from app.security import decode_token
from app.database import db

bearer=HTTPBearer(auto_error=False)
async def current_user(credentials: HTTPAuthorizationCredentials|None=Depends(bearer)):
    if not credentials: raise HTTPException(401,"Authentication required")
    try: payload=decode_token(credentials.credentials); uid=payload.get("sub")
    except Exception: raise HTTPException(401,"Invalid or expired access token")
    if not uid or not ObjectId.is_valid(uid): raise HTTPException(401,"Invalid access token subject")
    user=await db.users.find_one({"_id":ObjectId(uid),"is_active":True})
    if not user: raise HTTPException(401,"User account is unavailable")
    return user

def require_manager(user=Depends(current_user)):
    if user.get("role")!="manager": raise HTTPException(403,"Manager role required")
    return user

def public_user(user):
    return {"id":str(user["_id"]),"full_name":user["full_name"],"email":user["email"],"role":user["role"],"focus_goal":user.get("focus_goal",""),"created_at":user["created_at"].isoformat()}

def object_id(value: str):
    if not ObjectId.is_valid(value): raise HTTPException(422,"Invalid ID format")
    return ObjectId(value)
