from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
import smtplib, logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pymongo.errors import DuplicateKeyError
from app.config import settings
from app.database import db
logger=logging.getLogger("progressai.reminders")
scheduler=AsyncIOScheduler(timezone="UTC")

def send_email(to_email,subject,body):
    if not (settings.smtp_host and settings.smtp_from_email): return False
    msg=EmailMessage(); msg["Subject"]=subject; msg["From"]=settings.smtp_from_email; msg["To"]=to_email; msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=10) as server:
            if settings.smtp_use_tls: server.starttls()
            if settings.smtp_username: server.login(settings.smtp_username,settings.smtp_password)
            server.send_message(msg)
        return True
    except Exception: logger.exception("Email delivery failed"); return False

async def reminder_job():
    now=datetime.now(timezone.utc); upcoming=now+timedelta(hours=settings.reminder_hours_before_deadline)
    cursor=db.tasks.find({"status":{"$ne":"Completed"},"deadline":{"$gt":now,"$lte":upcoming}})
    async for task in cursor:
        uid=task.get("assigned_to"); dedupe=f"deadline:{task['_id']}:{task['deadline'].isoformat()}"
        user=await db.users.find_one({"_id":uid,"is_active":True})
        if not user: continue
        try:
            await db.notifications.insert_one({"user_id":uid,"title":"Upcoming deadline","message":f"{task['title']} is due by {task['deadline'].isoformat()}","task_id":task["_id"],"read":False,"created_at":now,"dedupe_key":dedupe})
            send_email(user["email"],"ProgressAI: upcoming task deadline",f"Your task '{task['title']}' is due by {task['deadline'].isoformat()}.")
        except DuplicateKeyError: pass
    cursor=db.tasks.find({"status":{"$ne":"Completed"},"deadline":{"$lt":now}})
    async for task in cursor:
        uid=task.get("assigned_to"); dedupe=f"overdue:{task['_id']}:{task['deadline'].isoformat()}"
        try:
            await db.notifications.insert_one({"user_id":uid,"title":"Task overdue","message":f"{task['title']} is past its deadline.","task_id":task["_id"],"read":False,"created_at":now,"dedupe_key":dedupe})
        except DuplicateKeyError: pass

def start_scheduler():
    if settings.enable_scheduler and not scheduler.running: scheduler.add_job(reminder_job,"interval",minutes=settings.reminder_interval_minutes,id="progressai-reminders",replace_existing=True); scheduler.start()
def stop_scheduler():
    if scheduler.running: scheduler.shutdown(wait=False)
