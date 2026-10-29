import math, os, random
from datetime import date, datetime, timedelta
from sqlalchemy import JSON, ForeignKey, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

# Swap DATABASE_URL for PostgreSQL later (e.g. postgresql+psycopg://user:pw@host/db). Nothing else changes.
URL = os.getenv("DATABASE_URL", "sqlite:///./tracker.db")
engine = create_engine(URL, connect_args={"check_same_thread": False} if URL.startswith("sqlite") else {})
Session = sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Shipment(Base):
    __tablename__ = "shipments"
    id: Mapped[str] = mapped_column(primary_key=True)
    route: Mapped[str]
    vessel: Mapped[str]
    status: Mapped[str]            # active | delivered
    planned_eta: Mapped[date]
    actual_eta: Mapped[date]       # latest estimate, or actual arrival once delivered
    delay_hours: Mapped[float]
    stops: Mapped[list | None] = mapped_column(JSON, nullable=True)       # port names on the route
    segments: Mapped[list | None] = mapped_column(JSON, nullable=True)    # [{"mode": "road|sea", "points": [[lon, lat], ...]}]
    legs: Mapped[list["Leg"]] = relationship(order_by="Leg.seq", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship(order_by="Document.id", cascade="all, delete-orphan")
    events: Mapped[list["Event"]] = relationship(order_by="Event.ts.desc()", cascade="all, delete-orphan")

class Leg(Base):
    __tablename__ = "legs"
    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id"))
    seq: Mapped[int]
    route: Mapped[str]
    mode: Mapped[str]              # Road | Border | Port | Sea | Rail
    planned: Mapped[date]
    actual: Mapped[date]
    variance_h: Mapped[float]

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id"))
    name: Mapped[str]
    verified: Mapped[bool]
    updated: Mapped[str]

class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id"))
    ts: Mapped[datetime]
    text: Mapped[str]

class Port(Base):
    __tablename__ = "ports"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    country: Mapped[str]
    lat: Mapped[float]
    lon: Mapped[float]
    congestion: Mapped[str]        # low | medium | high
    waiting: Mapped[int]           # vessels waiting to berth

class Position(Base):
    __tablename__ = "positions"
    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id"))
    ts: Mapped[datetime]
    lat: Mapped[float]
    lon: Mapped[float]
    speed_kn: Mapped[float]

# Illustrative route for the demo (approximate, not a navigational chart). Points are [longitude, latitude].
ROAD = [[25.91, -24.65], [22.7, -23.7], [21.7, -21.7], [20.0, -22.25], [17.08, -22.56], [16.9, -21.98], [15.85, -21.94], [14.53, -22.68], [14.50, -22.95]]
SEA = [[14.50, -22.95], [11.0, -21.0], [8.0, -12.0], [5.0, -3.0], [1.0, 1.5], [-3.0, 3.0], [-8.0, 3.5], [-15.0, 8.0], [-18.5, 13.0],
       [-18.0, 20.0], [-17.0, 25.5], [-15.8, 28.3], [-13.5, 32.0], [-11.5, 37.0], [-10.5, 43.0], [-6.0, 48.0], [-3.0, 49.9], [1.7, 51.0], [3.0, 51.7], [3.95, 51.95]]
VESSEL = [-10.9, 40.0]            # current position, between SEA[13] and SEA[14]
DONE = SEA[:14] + [VESSEL]

PORTS = [("Walvis Bay", "Namibia", -22.95, 14.50, "low", 1), ("Las Palmas", "Spain", 28.14, -15.41, "high", 5),
         ("Rotterdam", "Netherlands", 51.95, 4.05, "medium", 4)]

ROUTES = {  # route: (mean delay h, spread) -- sample figures for demo data only
    "Gaborone to Rotterdam": (10, 12), "Gaborone to Durban": (4, 8),
    "Gaborone to Singapore": (14, 16), "Gaborone to Dubai": (6, 10),
}

def along(path, n):
    """n points evenly spaced along a polyline."""
    d = [0.0]
    for a, b in zip(path, path[1:]):
        d.append(d[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    out = []
    for i in range(n):
        t = d[-1] * i / (n - 1)
        j = max(k for k in range(len(d) - 1) if d[k] <= t)
        f = (t - d[j]) / ((d[j + 1] - d[j]) or 1)
        out.append([path[j][0] + f * (path[j + 1][0] - path[j][0]), path[j][1] + f * (path[j + 1][1] - path[j][1])])
    return out

def seed():
    with Session() as s:
        if s.scalar(select(Shipment.id).limit(1)):
            return
        live = Shipment(id="SHP-24817", route="Gaborone to Rotterdam", vessel="MV Kalahari Star", status="active",
                        planned_eta=date(2026, 11, 11), actual_eta=date(2026, 11, 12), delay_hours=14,
                        stops=["Walvis Bay", "Las Palmas", "Rotterdam"],
                        segments=[{"mode": "road", "points": ROAD}, {"mode": "sea", "points": SEA}])
        legs = [("Gaborone to Mamuno border", "Road", (10, 15), (10, 15), 0), ("Mamuno border crossing", "Border", (10, 16), (10, 16), 0),
                ("Mamuno to Walvis Bay", "Road", (10, 20), (10, 20), 0), ("Walvis Bay terminal dwell", "Port", (10, 22), (10, 22), 0),
                ("Walvis Bay to Las Palmas", "Sea", (10, 25), (10, 26), 14), ("Las Palmas to Rotterdam", "Sea", (11, 11), (11, 12), 14)]
        live.legs = [Leg(seq=i + 1, route=r, mode=m, planned=date(2026, *p), actual=date(2026, *a), variance_h=v) for i, (r, m, p, a, v) in enumerate(legs)]
        live.documents = [Document(name=n, verified=ok, updated=u) for n, ok, u in [
            ("Bill of lading", True, "22 Oct"), ("Packing list", True, "21 Oct"),
            ("Export declaration", True, "21 Oct"), ("Commercial invoice", False, "Not uploaded")]]
        live.events = [Event(ts=datetime(2026, 10, *d), text=t) for d, t in [
            ((28, 9, 12), "Position update received. Speed 14.2 kn."), ((27, 16, 30), "Weather alert raised for planned lane."),
            ((26, 3, 40), "Delay at Las Palmas. ETA recalculated and customer notified."), ((22, 14, 5), "Departed Walvis Bay.")]]
        s.add(live)
        start, end, n = datetime(2026, 10, 22, 14, 5), datetime(2026, 10, 28, 9, 12), 24
        for i, (lon, lat) in enumerate(along(DONE, n)):
            s.add(Position(shipment_id="SHP-24817", ts=start + (end - start) * i / (n - 1), lat=lat, lon=lon, speed_kn=14.2))
        s.add_all([Port(name=a, country=b, lat=c, lon=d, congestion=e, waiting=f) for a, b, c, d, e, f in PORTS])
        for sid, route, eta, delay in [("SHP-24790", "Gaborone to Singapore", date(2026, 11, 20), 0), ("SHP-24761", "Gaborone to Dubai", date(2026, 11, 18), 9),
                                       ("SHP-24755", "Gaborone to Durban", date(2026, 11, 3), 0)]:
            s.add(Shipment(id=sid, route=route, vessel="[Vessel]", status="active", planned_eta=eta, actual_eta=eta, delay_hours=delay))
        rng, today = random.Random(42), date(2026, 10, 28)
        for i in range(90):  # historical delivered shipments (sample data)
            route = rng.choice(list(ROUTES)); mu, sd = ROUTES[route]
            delay = round(max(-12, rng.gauss(mu, sd)), 1)
            eta = today - timedelta(days=rng.randint(5, 360))
            s.add(Shipment(id=f"SHP-{23000 + i}", route=route, vessel="[Vessel]", status="delivered",
                           planned_eta=eta, actual_eta=eta + timedelta(hours=delay), delay_hours=delay))
        s.commit()
