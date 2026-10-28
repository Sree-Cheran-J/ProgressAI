"""Optional API integration tests. Run only against a disposable MongoDB database."""
import os, uuid
import pytest

pytestmark = pytest.mark.skipif(os.getenv("RUN_API_INTEGRATION") != "1", reason="Set RUN_API_INTEGRATION=1 and use a disposable MONGODB_DATABASE")

def test_register_login_and_private_tasks():
    from fastapi.testclient import TestClient
    from app.main import app
    email=f"test-{uuid.uuid4().hex}@example.test"
    with TestClient(app) as client:
        r=client.post("/api/auth/register",json={"full_name":"Integration Test","email":email,"password":"TestPass!234"})
        assert r.status_code==201, r.text
        login=client.post("/api/auth/login",json={"email":email,"password":"TestPass!234"})
        assert login.status_code==200, login.text
        token=login.json()["access_token"]
        headers={"Authorization":f"Bearer {token}"}
        me=client.get("/api/auth/me",headers=headers)
        assert me.status_code==200 and me.json()["role"]=="employee"
        task=client.post("/api/tasks",headers=headers,json={"title":"Test task","status":"Planned","priority":"Medium","complexity":2,"estimated_duration_hours":1.5})
        assert task.status_code==201, task.text
        task_id=task.json()["id"]
        listed=client.get("/api/tasks",headers=headers)
        assert listed.status_code==200 and any(t["id"]==task_id for t in listed.json()["items"])
        changed=client.patch(f"/api/tasks/{task_id}/status",headers=headers,json={"status":"In Progress"})
        assert changed.status_code==200 and changed.json()["status"]=="In Progress"
        deleted=client.delete(f"/api/tasks/{task_id}",headers=headers)
        assert deleted.status_code==204
