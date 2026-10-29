from contextlib import asynccontextmanager
import math
from datetime import date, datetime
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from .db import Base, engine, Session, Shipment, Document, Event, Port, Position, seed

ON_TIME_TOLERANCE_H = 6   # delivered within this many hours of plan counts as on time

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    seed()
    yield

app = FastAPI(title="Freight Control API", lifespan=lifespan)
day = lambda d: d.strftime("%d %b")

def brief(x):
    return {"id": x.id, "route": x.route, "vessel": x.vessel, "status": x.status,
            "planned_eta": x.planned_eta.isoformat(), "actual_eta": x.actual_eta.isoformat(), "delay_hours": x.delay_hours}

@app.get("/api/health")
def health():
    return {"ok": True}

@app.get("/api/shipments")
def shipments(status: str | None = None):
    with Session() as s:
        q = select(Shipment).order_by(Shipment.planned_eta.desc())
        if status:
            q = q.where(Shipment.status == status)
        return [brief(x) for x in s.scalars(q)]

@app.get("/api/shipments/{sid}")
def shipment(sid: str):
    with Session() as s:
        x = s.get(Shipment, sid)
        if not x:
            raise HTTPException(404, "Shipment not found")
        return {**brief(x),
                "legs": [{"seq": l.seq, "route": l.route, "mode": l.mode, "planned": day(l.planned), "actual": day(l.actual), "variance_h": l.variance_h} for l in x.legs],
                "documents": [{"id": d.id, "name": d.name, "verified": d.verified, "updated": d.updated} for d in x.documents],
                "events": [{"ts": e.ts.strftime("%d %b %H:%M"), "text": e.text} for e in x.events]}

@app.get("/api/shipments/{sid}/track")
def track(sid: str):
    with Session() as s:
        x = s.get(Shipment, sid)
        if not x:
            raise HTTPException(404, "Shipment not found")
        pos = list(s.scalars(select(Position).where(Position.shipment_id == sid).order_by(Position.ts)))
        if not x.segments or not pos:
            raise HTTPException(404, "No tracking data for this shipment")
        a, b = (pos[-2] if len(pos) > 1 else pos[-1]), pos[-1]
        heading = round(math.degrees(math.atan2((b.lon - a.lon) * math.cos(math.radians(b.lat)), b.lat - a.lat)) % 360)
        ports = s.scalars(select(Port).where(Port.name.in_(x.stops or [])))
        return {"segments": x.segments, "trail": [[p.lon, p.lat] for p in pos],
                "vessel": {"lat": b.lat, "lon": b.lon, "heading": heading, "speed_kn": b.speed_kn, "ts": b.ts.isoformat()},
                "ports": [{"name": p.name, "country": p.country, "lat": p.lat, "lon": p.lon, "congestion": p.congestion, "waiting": p.waiting} for p in ports]}

@app.post("/api/shipments/{sid}/documents/{did}/verify")
def verify(sid: str, did: int):
    with Session() as s:
        d = s.get(Document, did)
        if not d or d.shipment_id != sid:
            raise HTTPException(404, "Document not found")
        d.verified, d.updated = True, day(date.today())
        s.add(Event(shipment_id=sid, ts=datetime.now(), text=f"{d.name} uploaded and verified."))
        s.commit()
        return {"ok": True}

@app.get("/api/analytics/summary")
def analytics():
    df = pd.read_sql("SELECT route, planned_eta, delay_hours FROM shipments WHERE status = 'delivered'", engine, parse_dates=["planned_eta"])
    if df.empty:
        return {"shipments": 0}
    df["on_time"] = df["delay_hours"] <= ON_TIME_TOLERANCE_H
    by_route = df.groupby("route").agg(shipments=("route", "size"), avg_delay_h=("delay_hours", "mean"), on_time_rate=("on_time", "mean")).round(2).reset_index()
    df["month"] = df["planned_eta"].dt.to_period("M").astype(str)
    monthly = df.groupby("month").agg(shipments=("month", "size"), avg_delay_h=("delay_hours", "mean")).round(2).reset_index()
    return {"shipments": int(len(df)), "on_time_rate": round(float(df["on_time"].mean()), 3), "avg_delay_h": round(float(df["delay_hours"].mean()), 1),
            "tolerance_h": ON_TIME_TOLERANCE_H, "by_route": by_route.to_dict("records"), "monthly": monthly.to_dict("records")}

app.mount("/", StaticFiles(directory="static", html=True), name="static")
