import os
os.environ["DATABASE_URL"] = "sqlite:///./test_tracker.db"
from fastapi.testclient import TestClient
from app.main import app

def test_all():
    with TestClient(app) as c:
        assert c.get("/api/health").json() == {"ok": True}
        s = c.get("/api/shipments/SHP-24817").json()
        assert len(s["legs"]) == 6 and any(not d["verified"] for d in s["documents"])
        assert c.get("/api/shipments/NOPE").status_code == 404
        missing = next(d for d in s["documents"] if not d["verified"])
        assert c.post(f"/api/shipments/SHP-24817/documents/{missing['id']}/verify").json()["ok"]
        assert all(d["verified"] for d in c.get("/api/shipments/SHP-24817").json()["documents"])
        k = c.get("/api/shipments/SHP-24817/track").json()
        assert len(k["trail"]) > 10 and {p["name"] for p in k["ports"]} == {"Walvis Bay", "Las Palmas", "Rotterdam"}
        assert c.get("/api/shipments/SHP-24790/track").status_code == 404
        assert len(c.get("/api/shipments?status=active").json()) == 4
        a = c.get("/api/analytics/summary").json()
        assert a["shipments"] > 50 and 0 <= a["on_time_rate"] <= 1 and a["by_route"]
