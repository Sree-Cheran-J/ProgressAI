import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import Any
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pymongo.errors import DuplicateKeyError
from bson import ObjectId
from app.config import settings
from app.database import db, init_db, close_db
from app.schemas import RegisterIn, LoginIn, ProfilePatch, TaskCreate, TaskPatch, StatusPatch, ManagerTaskCreate, PredictionIn
from app.security import hash_password, verify_password, create_access_token
from app.deps import current_user, require_manager, public_user, object_id
from app.ml_service import ml_service, features
from app.reminders import start_scheduler, stop_scheduler

@asynccontextmanager
async def lifespan(app):
    try: await init_db()
    except Exception as exc: raise RuntimeError(f"MongoDB unavailable. Check MONGODB_URI: {exc}") from exc
    start_scheduler()
    yield
    stop_scheduler(); await close_db()
app=FastAPI(title=settings.app_name,version="1.0.0",lifespan=lifespan)
origins = [
    "https://progressai-frontend.vercel.app",
    "http://127.0.0.1:5500",
    "http://localhost:5500"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

def serial(v):
    if isinstance(v,ObjectId): return str(v)
    if isinstance(v,datetime): return v.isoformat()
    if isinstance(v,dict): return {k:serial(x) for k,x in v.items() if k!="_id" and k!="password_hash"}
    if isinstance(v,list): return [serial(x) for x in v]
    return v
async def event(task_id,actor_id,event_type,details=None):
    await db.task_events.insert_one({"task_id":task_id,"actor_id":actor_id,"event_type":event_type,"details":details or {},"created_at":datetime.now(timezone.utc)})
async def enrich_task(t):
    out=serial(t); out["id"]=str(t["_id"]); out["assigned_to"]=str(t["assigned_to"]); out["assigned_by"]=str(t["assigned_by"]) if t.get("assigned_by") else None
    pred=await db.predictions.find_one({"task_id":t["_id"]},sort=[("created_at",-1)])
    out["prediction"]=serial(pred.get("result")) if pred else None
    return out
async def allowed_task(task_id,user):
    t=await db.tasks.find_one({"_id":object_id(task_id)})
    if not t: raise HTTPException(404,"Task not found")
    if user["role"]!="manager" and t["assigned_to"]!=user["_id"]: raise HTTPException(403,"You cannot access this task")
    return t
async def predict_task(t):
    uid=t["assigned_to"]; done=list([x async for x in db.tasks.find({"assigned_to":uid,"status":"Completed","actual_duration_hours":{"$gt":0}}, {"actual_duration_hours":1})])
    avg=sum(x["actual_duration_hours"] for x in done)/len(done) if done else None
    count=await db.tasks.count_documents({"assigned_to":uid,"status":{"$in":["Planned","In Progress"]}})
    completed=await db.tasks.count_documents({"assigned_to":uid,"status":"Completed"}); ontime=await db.tasks.count_documents({"assigned_to":uid,"status":"Completed","$expr":{"$lte":["$completed_at","$deadline"]}})
    rate=ontime/completed if completed else None
    x=features(t.get("complexity",3),t.get("priority","Medium"),t.get("estimated_duration_hours",2),max(count-1,0),avg,rate)
    result=ml_service.predict(x,t.get("deadline")); result["recommendation"]=ml_service.recommend(x)
    await db.predictions.insert_one({"task_id":t["_id"],"user_id":uid,"features":{"complexity":t.get("complexity",3),"priority":t.get("priority","Medium"),"estimated_duration_hours":t.get("estimated_duration_hours",2),"active_tasks":max(count-1,0),"historical_avg_hours":avg,"on_time_rate":rate},"result":result,"created_at":datetime.now(timezone.utc)})
    await db.tasks.update_one({"_id":t["_id"]},{"$set":{"predicted_duration_hours":result["predicted_duration_hours"],"predicted_finish_at":datetime.fromisoformat(result["predicted_finish_at"])}})
    return result

@app.get("/health")
async def health(): return {"status":"ok","database":"connected"}
@app.post(settings.api_prefix+"/auth/register",status_code=201)
async def register(data:RegisterIn):
    email=str(data.email).lower().strip(); now=datetime.now(timezone.utc)
    doc={"full_name":data.full_name,"email":email,"password_hash":hash_password(data.password),"role":"employee","focus_goal":data.focus_goal,"is_active":True,"created_at":now,"updated_at":now}
    try: result=await db.users.insert_one(doc)
    except DuplicateKeyError: raise HTTPException(409,"An account with this email already exists")
    doc["_id"]=result.inserted_id
    return {"user":public_user(doc),"message":"Registration successful. New accounts are employees by default."}
@app.post(settings.api_prefix+"/auth/login")
async def login(data:LoginIn):
    user=await db.users.find_one({"email":str(data.email).lower().strip()})
    if not user or not user.get("is_active") or not verify_password(data.password,user["password_hash"]): raise HTTPException(401,"Invalid email or password")
    return {"access_token":create_access_token(str(user["_id"]),user["role"]),"token_type":"bearer","expires_in":settings.access_token_minutes*60,"user":public_user(user)}
@app.get(settings.api_prefix+"/auth/me")
async def auth_me(user=Depends(current_user)): return public_user(user)
@app.get(settings.api_prefix+"/users/me")
async def get_profile(user=Depends(current_user)): return public_user(user)
@app.patch(settings.api_prefix+"/users/me")
async def patch_profile(data:ProfilePatch,user=Depends(current_user)):
    changes=data.model_dump(exclude_unset=True)
    if changes.get("full_name") is not None: changes["full_name"]=changes["full_name"].strip()
    changes={k:v for k,v in changes.items() if v is not None}
    changes["updated_at"]=datetime.now(timezone.utc)
    await db.users.update_one({"_id":user["_id"]},{"$set":changes})
    updated=await db.users.find_one({"_id":user["_id"]}); return public_user(updated)
@app.get(settings.api_prefix+"/users")
async def employees(limit:int=Query(50,ge=1,le=100),user=Depends(require_manager)):
    cursor=db.users.find({"role":"employee","is_active":True},{"password_hash":0}).limit(limit)
    return {"items":[public_user(x) async for x in cursor]}
@app.get(settings.api_prefix+"/tasks")
async def list_tasks(status:str|None=None,limit:int=Query(100,ge=1,le=200),skip:int=Query(0,ge=0),user=Depends(current_user)):
    q={} if user["role"]=="manager" else {"assigned_to":user["_id"]}
    if status: q["status"]=status
    cursor=db.tasks.find(q).sort("created_at",-1).skip(skip).limit(limit)
    return {"items":[await enrich_task(t) async for t in cursor],"limit":limit,"skip":skip}
@app.post(settings.api_prefix+"/tasks",status_code=201)
async def create_task(data:TaskCreate,user=Depends(current_user)):
    now=datetime.now(timezone.utc); task=data.model_dump(); task.update({"assigned_to":user["_id"],"assigned_by":user["_id"] if user["role"]=="manager" else None,"created_at":now,"updated_at":now,"assigned_at":now,"actual_start_at":now if data.status=="In Progress" else None,"completed_at":now if data.status=="Completed" else None,"actual_duration_hours":None})
    if task.get("deadline") and task["deadline"].tzinfo is None: task["deadline"]=task["deadline"].replace(tzinfo=timezone.utc)
    result=await db.tasks.insert_one(task); task["_id"]=result.inserted_id; await event(result.inserted_id,user["_id"],"created",{"status":task["status"]}); await predict_task(task)
    return await enrich_task(await db.tasks.find_one({"_id":result.inserted_id}) )
@app.post(settings.api_prefix+"/manager/tasks",status_code=201)
async def manager_assign(data:ManagerTaskCreate,user=Depends(require_manager)):
    employee=await db.users.find_one({"email":str(data.employee_email).lower().strip(),"role":"employee","is_active":True})
    if not employee: raise HTTPException(404,"Active employee not found")
    now=datetime.now(timezone.utc); task=data.model_dump(exclude={"employee_email"}); task.update({"assigned_to":employee["_id"],"assigned_by":user["_id"],"status":"Planned","created_at":now,"updated_at":now,"assigned_at":now,"actual_start_at":None,"completed_at":None,"actual_duration_hours":None})
    if task.get("deadline") and task["deadline"].tzinfo is None: task["deadline"]=task["deadline"].replace(tzinfo=timezone.utc)
    res=await db.tasks.insert_one(task); task["_id"]=res.inserted_id; await event(res.inserted_id,user["_id"],"assigned",{"employee_id":str(employee["_id"])}); await predict_task(task)
    return await enrich_task(await db.tasks.find_one({"_id":res.inserted_id}))
@app.get(settings.api_prefix+"/tasks/{task_id}")
async def get_task(task_id:str,user=Depends(current_user)): return await enrich_task(await allowed_task(task_id,user))
@app.patch(settings.api_prefix+"/tasks/{task_id}")
async def patch_task(task_id:str,data:TaskPatch,user=Depends(current_user)):
    task=await allowed_task(task_id,user)
    if user["role"]!="manager" and any(k in data.model_fields_set for k in ("title","description","priority","complexity","deadline","estimated_duration_hours")): raise HTTPException(403,"Employees can update status only; ask a manager to edit task details")
    changes=data.model_dump(exclude_unset=True); changes["updated_at"]=datetime.now(timezone.utc)
    if changes.get("deadline") and changes["deadline"].tzinfo is None: changes["deadline"]=changes["deadline"].replace(tzinfo=timezone.utc)
    await db.tasks.update_one({"_id":task["_id"]},{"$set":changes}); await event(task["_id"],user["_id"],"updated",changes)
    fresh=await db.tasks.find_one({"_id":task["_id"]}); await predict_task(fresh); return await enrich_task(await db.tasks.find_one({"_id":task["_id"]}))
@app.patch(settings.api_prefix+"/tasks/{task_id}/status")
async def status_task(task_id:str,data:StatusPatch,user=Depends(current_user)):
    task=await allowed_task(task_id,user); now=datetime.now(timezone.utc); changes={"status":data.status,"updated_at":now}
    if data.status=="In Progress" and not task.get("actual_start_at"): changes["actual_start_at"]=now
    if data.status=="Completed":
        changes["completed_at"]=now
        start=task.get("actual_start_at") or task.get("assigned_at") or task["created_at"]
        changes["actual_duration_hours"]=max(0.01,(now-start).total_seconds()/3600)
    else: changes["completed_at"]=None
    await db.tasks.update_one({"_id":task["_id"]},{"$set":changes}); await event(task["_id"],user["_id"],"status_changed",changes)
    fresh=await db.tasks.find_one({"_id":task["_id"]}); await predict_task(fresh); return await enrich_task(await db.tasks.find_one({"_id":task["_id"]}))
@app.delete(settings.api_prefix+"/tasks/{task_id}",status_code=204)
async def delete_task(task_id:str,user=Depends(current_user)):
    task=await allowed_task(task_id,user)
    if user["role"]!="manager" and task["status"]=="Completed": raise HTTPException(403,"Employees cannot delete completed tasks")
    await event(task["_id"],user["_id"],"deleted",{}); await db.tasks.delete_one({"_id":task["_id"]})
@app.get(settings.api_prefix+"/dashboard/summary")
async def summary(user=Depends(current_user)):
    q={} if user["role"]=="manager" else {"assigned_to":user["_id"]}; total=await db.tasks.count_documents(q); done=await db.tasks.count_documents({**q,"status":"Completed"}); active=await db.tasks.count_documents({**q,"status":"In Progress"}); overdue=await db.tasks.count_documents({**q,"status":{"$ne":"Completed"},"deadline":{"$lt":datetime.now(timezone.utc)}})
    rate=round(done/total*100) if total else 0
    return {"total_tasks":total,"completed_tasks":done,"active_tasks":active,"remaining_tasks":total-done,"overdue_tasks":overdue,"completion_rate":rate,"insight":{"title":"You're on a roll!" if rate>=80 else "You're building momentum" if rate>=50 else "Your next step starts now","message":f"{overdue} overdue task(s). Prioritize the nearest deadline." if overdue else f"{total-done} task(s) remain. Focus on one next step."}}
@app.get(settings.api_prefix+"/analytics/weekly")
async def weekly(user=Depends(current_user)):
    now=datetime.now(timezone.utc); start=(now-timedelta(days=6)).replace(hour=0,minute=0,second=0,microsecond=0); q={} if user["role"]=="manager" else {"assigned_to":user["_id"]}; labels=[]; completed=[]; created=[]
    for i in range(7):
        day=start+timedelta(days=i); nxt=day+timedelta(days=1); labels.append(day.strftime("%a")); completed.append(await db.tasks.count_documents({**q,"completed_at":{"$gte":day,"$lt":nxt}})); created.append(await db.tasks.count_documents({**q,"created_at":{"$gte":day,"$lt":nxt}}))
    return {"labels":labels,"completed":completed,"created":created,"source":"MongoDB task timestamps; not synthetic chart data"}
@app.get(settings.api_prefix+"/analytics/employee-performance")
async def employee_performance(user=Depends(require_manager)):
    rows=[]
    async for emp in db.users.find({"role":"employee","is_active":True}):
        q={"assigned_to":emp["_id"]}; total=await db.tasks.count_documents(q); done=await db.tasks.count_documents({**q,"status":"Completed"}); rows.append({"employee_id":str(emp["_id"]),"full_name":emp["full_name"],"email":emp["email"],"total_tasks":total,"completed_tasks":done,"completion_rate":round(done/total*100) if total else 0})
    return {"items":rows}
@app.post(settings.api_prefix+"/predictions/estimate")
async def estimate(data:PredictionIn,user=Depends(current_user)):
    x=features(data.complexity,data.priority,data.estimated_duration_hours,data.active_tasks,data.historical_avg_hours,data.on_time_rate); result=ml_service.predict(x,datetime.now(timezone.utc)+timedelta(hours=data.hours_until_deadline) if data.hours_until_deadline is not None else None); result["recommendation"]=ml_service.recommend(x); return result
@app.get(settings.api_prefix+"/tasks/{task_id}/prediction")
async def task_prediction(task_id:str,user=Depends(current_user)):
    task=await allowed_task(task_id,user); p=await db.predictions.find_one({"task_id":task["_id"]},sort=[("created_at",-1)])
    if not p: result=await predict_task(task); return {"task_id":task_id,"result":result}
    return {"task_id":task_id,"result":serial(p["result"]),"created_at":serial(p["created_at"])}
@app.get(settings.api_prefix+"/ml/status")
async def ml_status(user=Depends(current_user)):
    return {"duration_model_loaded":"duration_rf" in ml_service.models,"risk_model_loaded":"risk_rf" in ml_service.models,"model_metadata":ml_service.metadata,"note":"Synthetic training data is for pipeline demonstration only; do not use for real employee decisions."}
@app.get(settings.api_prefix+"/notifications")
async def notifications(user=Depends(current_user),limit:int=Query(50,ge=1,le=100)):
    cursor=db.notifications.find({"user_id":user["_id"]}).sort("created_at",-1).limit(limit); items=[]
    async for n in cursor: n["id"]=str(n.pop("_id")); n["user_id"]=str(n["user_id"]); n["task_id"]=str(n["task_id"]) if n.get("task_id") else None; items.append(serial(n))
    return {"items":items}
@app.patch(settings.api_prefix+"/notifications/{notification_id}/read")
async def read_notification(notification_id:str,user=Depends(current_user)):
    oid=object_id(notification_id); res=await db.notifications.update_one({"_id":oid,"user_id":user["_id"]},{"$set":{"read":True}})
    if not res.matched_count: raise HTTPException(404,"Notification not found")
    return {"id":notification_id,"read":True}
@app.get(settings.api_prefix+"/manager/dashboard")
async def manager_dashboard(user=Depends(require_manager)):
    return await summary(user)
