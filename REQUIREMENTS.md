# Freight Control: Requirements

Working document. Items marked [Open] need a decision.

## 1. Purpose
An admin dashboard for [Company name] to track shipments end to end (road, border, port, sea), spot delays early, keep documents complete, and learn from past performance.

## 2. Users and default views
| Role | Default view | Main job |
|---|---|---|
| Operations | Live map | Monitor many shipments, react to weather, congestion, signal loss |
| Documentation and customs | Focused (Documents tab) | Chase missing or unverified paperwork |
| Customer service | Story | Explain progress to clients, share a tracking link |
| Finance and planning | Data | Compare legs, variance and delay costs |

## 3. MVP (built in this prototype)
- One shipment record shown through four views, with role-based defaults
- Legs table covering road, border, port and sea
- Document checklist with upload and verify
- Activity log
- Light, dark and auto themes
- Python API with a seeded database

## 4. Wishlist
### 4.1 Historical analysis (priority)
- Browse and search all past shipments, not just active ones
- Filters: date range, route, customer, carrier, vessel, cargo type, border post
- KPIs: on-time rate, average delay, ETA accuracy (planned vs actual), transit time per route
- Dwell time per port and per border crossing, with trends by month and season
- Delay causes (weather, port congestion, documents, customs hold) and their share of total delay
- Compare routes and carriers side by side
- Export to CSV and Excel
- Print or PDF summary for management
- Reefer temperature excursions per shipment and per route

### 4.2 Operations
- Live vessel positions from an AIS provider [Open: provider]
- Weather and port congestion layers from real sources
- Alerts for delay, signal loss over 6 hours, and missing documents
- Split shipments across vessels (leg picker)

### 4.3 Customers and access
- Public tracking link with limited fields
- Real login, role permissions, audit log
- Notifications by email and WhatsApp [Open]

## 5. Non-functional
- Works on a phone and on a large control-room screen
- Time zones shown clearly (Africa/Gaborone, vessel local time)
- English first; Setswana labels [Open]
- Data stays portable: standard database, exportable at any time
- Keeps working with sample data when live feeds are down

## 6. Open questions
1. Company name, branding and the cargo types you move most
2. Which corridors and modes matter (Trans-Kalahari, Durban, Maputo, rail)
3. Where real shipment data will come from (ERP, carrier portals, spreadsheets)
4. Who approves documents, and what counts as "delayed" for your customers
