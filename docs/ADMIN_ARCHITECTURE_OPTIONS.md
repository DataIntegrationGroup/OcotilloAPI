# Admin UI Architecture Options for NMSampleLocations

## Context

**Current Situation:**
- AMPAPI (SQL Server) data needs to migrate to NMSampleLocations (PostgreSQL)
- OcotilloUI (React + Refine.dev) is the current admin interface
- Proposal: Temporarily replace OcotilloUI with Starlette Admin during migration

**Two Critical Questions:**
1. **Do we need to consider Starlette Admin alternatives?**
2. **Can Starlette Admin exist within NMSampleLocations as a monolithic repo?**

---

## Question 1: Starlette Admin vs. Alternatives

### Full Spectrum of Options

We've evaluated framework-based solutions, but let's consider the **complete architectural spectrum**:

| Option | Description | Pros | Cons | Effort |
|--------|-------------|------|------|--------|
| **1. Starlette Admin** | Python admin framework mounted to FastAPI | Native SQLAlchemy, GeoAlchemy2 support | Less flashy UI, custom views need work | 32-42 hrs |
| **2. Keep OcotilloUI** | Continue using React + Refine.dev | Already built, familiar to staff | Requires maintaining React frontend | 0 hrs (status quo) |
| **3. Simplify OcotilloUI** | Remove unused features, focus on CRUD | Familiar UI, less maintenance | Still requires React/Node.js stack | 16-24 hrs |
| **4. Django Admin (microservice)** | Separate Django service sharing PostgreSQL | Enterprise-grade admin, battle-tested | Additional service to deploy/maintain | 40-60 hrs |
| **5. SQLAdmin** | Lightweight SQLAlchemy admin for FastAPI | Simpler than Starlette Admin | Weaker RBAC, limited geospatial | 24-32 hrs |
| **6. No Admin UI** | Direct database access (psql, pgAdmin, DBeaver) | Zero development effort | Not user-friendly for non-technical staff | 0 hrs |
| **7. Custom FastAPI Endpoints** | Build minimal admin API, no UI | Full control, lightweight | Staff need Postman/curl | 8-12 hrs |
| **8. React Admin (custom)** | Build from scratch with react-admin/Refine | Perfect fit for needs | 3-4 months development time | 300-400 hrs |

---

### Decision Matrix: When to Use Each Option

#### ✅ **Use Starlette Admin If:**
- You want a **temporary solution** during migration (2-6 months)
- Core CRUD is sufficient for 80% of workflows
- You can defer maps/custom forms to later
- You want Python-only stack (no Node.js)
- Timeline: **2-4 weeks**

**Verdict**: **Best for migration MVP** - balances speed, functionality, low risk

---

#### ✅ **Keep OcotilloUI If:**
- Staff **cannot tolerate** deferred features (maps, forms)
- Well Inventory Form or Groundwater Level Form are **critical path**
- React expertise is available for maintenance
- You're comfortable maintaining dual stack (Python + Node.js)

**Verdict**: **Safest option** - no changes, no risk, but doesn't reduce complexity

---

#### ✅ **Simplify OcotilloUI If:**
- You want to **reduce OcotilloUI complexity** but keep React
- Custom forms are critical, but dashboard/apps are not
- You want to keep the map view
- Timeline: **2-3 weeks** to strip down features

**Pros**:
- Keep the 20% of features you actually use (maps, forms)
- Remove the 80% you don't (coming soon apps, experimental features)

**Cons**:
- Still maintaining React frontend
- Doesn't help with AMPAPI migration directly

**Verdict**: **Consider if Starlette Admin fails UAT**

---

#### ✅ **Use Django Admin (Microservice) If:**
- You need **enterprise-grade admin** long-term
- Team has Django expertise
- You're okay with microservice complexity
- Timeline: **6-8 weeks**

**Architecture**:
```
┌─────────────────┐         ┌─────────────────┐
│  Django Admin   │         │ NMSampleLocations│
│  (Port 8001)    │────────▶│ PostgreSQL DB    │
│  Admin UI only  │ Shares  │                  │
└─────────────────┘  DB     └─────────────────┘
                              ▲
                              │
                     ┌────────┴────────┐
                     │  FastAPI API    │
                     │  (Port 8000)    │
                     └─────────────────┘
```

**Pros**:
- Best-in-class admin experience (Django Admin is gold standard)
- Automatic admin for all models
- Built-in user management, permissions, audit logs
- Geospatial admin via django.contrib.gis

**Cons**:
- **Two separate services** to deploy and maintain
- **Duplicate model definitions** (SQLAlchemy → Django ORM conversion)
- **Authentication sync** complexity
- More moving parts in production

**Verdict**: **Overkill for temporary migration** - consider for long-term if Starlette Admin proves insufficient

---

#### ✅ **Use SQLAdmin If:**
- You want **simpler** alternative to Starlette Admin
- You don't need complex RBAC
- Geospatial fields are not a priority
- Timeline: **3-4 weeks**

**Key Differences from Starlette Admin**:

| Feature | Starlette Admin | SQLAdmin |
|---------|----------------|----------|
| RBAC | ✅ Built-in flexible system | ⚠️ Basic, manual |
| GeoAlchemy2 | ✅ Native support | ⚠️ Basic (shows WKT) |
| Custom Actions | ✅ Decorator-based | ⚠️ Limited |
| UI Customization | ✅ Extensive | ⚠️ Basic |
| File Uploads | ✅ Supported | ✅ Supported |

**Verdict**: **Fallback if Starlette Admin is too complex** - but unlikely given your needs

---

#### ✅ **No Admin UI If:**
- Users are **highly technical** (can use psql, pgAdmin, DBeaver)
- Data entry volume is **very low** (< 10 records/week)
- You have **strict timeline** (need admin access immediately)

**Tools**:
- **psql**: Command-line PostgreSQL client
- **pgAdmin 4**: GUI database browser
- **DBeaver**: Universal database tool with PostGIS support

**Pros**:
- Zero development effort
- Direct database access (no abstraction bugs)
- Full SQL power for complex queries

**Cons**:
- Not suitable for non-technical staff
- Easy to make mistakes (no validation)
- No audit trail
- No business logic enforcement

**Verdict**: **Only for developers** - not suitable for data stewards/staff

---

#### ✅ **Custom FastAPI Endpoints If:**
- You need **minimal admin API** for scripts/automation
- No UI needed (staff use Postman, curl, or scripts)
- Timeline: **1 week**

**Example**:
```python
# api/admin_operations.py
from fastapi import APIRouter, Depends
from schemas.admin import BulkPublishRequest

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/bulk-publish")
async def bulk_publish(
    request: BulkPublishRequest,
    user: User = Depends(require_admin)
):
    """Bulk change release_status to 'public' for given location IDs."""
    await session.execute(
        update(Location)
        .where(Location.id.in_(request.location_ids))
        .values(release_status='public')
    )
    return {"updated": len(request.location_ids)}
```

**Staff Usage**:
```bash
# Via curl
curl -X POST http://localhost:8000/admin/bulk-publish \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"location_ids": ["uuid1", "uuid2", "uuid3"]}'

# Via Python script
import requests
response = requests.post(
    "http://localhost:8000/admin/bulk-publish",
    json={"location_ids": ["uuid1", "uuid2", "uuid3"]},
    headers={"Authorization": f"Bearer {token}"}
)
```

**Verdict**: **Supplement to any admin UI** - useful for automation, not replacement

---

#### ❌ **Custom React Admin (from scratch)**
- **Development Time**: 3-4 months
- **Effort**: 300-400 hours
- **Verdict**: **Not recommended** - too slow for migration timeline

---

### Recommendation: Decision Tree

```
START: Do you need admin UI immediately (< 2 weeks)?
├─ YES → No Admin UI (use pgAdmin/psql temporarily)
└─ NO → Continue

Can staff tolerate deferred features (maps, forms) for 2-4 months?
├─ NO → Keep OcotilloUI (safest, no changes)
└─ YES → Continue

Do you want Python-only stack (no Node.js)?
├─ YES → Starlette Admin ⭐ RECOMMENDED
└─ NO → Simplify OcotilloUI (strip unused features)

If Starlette Admin proves insufficient after MVP:
├─ Short-term fix → Restore OcotilloUI for missing features
├─ Long-term solution → Django Admin microservice
└─ Hybrid approach → Starlette Admin + custom React forms
```

**Final Recommendation**: **Start with Starlette Admin** for 3 reasons:
1. **Speed**: 2-4 weeks to MVP vs. 6-8 weeks for Django Admin
2. **Low Risk**: Can fall back to OcotilloUI if it fails
3. **Low Lock-in**: Uses your existing SQLAlchemy models

---

## Question 2: Monolithic vs. Separate Repository

### Can Starlette Admin Live in NMSampleLocations Repo?

**Short Answer**: ✅ **YES** - Starlette Admin can (and should) live in the NMSampleLocations monolithic repo.

### Current NMSampleLocations Architecture

**Repo Structure**:
```
NMSampleLocations/
├── main.py                 # FastAPI entry point
├── core/
│   ├── app.py              # FastAPI app initialization
│   └── initializers.py     # Route registration
├── api/                    # REST API endpoints
│   ├── location.py
│   ├── sensor.py
│   ├── sample.py
│   └── ...
├── db/                     # SQLAlchemy models (50+ models)
│   ├── location.py
│   ├── sensor.py
│   └── ...
├── schemas/                # Pydantic schemas
└── services/               # Business logic
```

**Current Pattern**: **Monolithic FastAPI application**
- All API routes registered in `core/initializers.py`
- Single deployment unit
- Shared database session management

---

### Option A: Monolithic (Admin in Same Repo) ⭐ **RECOMMENDED**

**Structure**:
```
NMSampleLocations/
├── main.py                 # Mount both API and admin
├── core/
│   ├── app.py
│   └── initializers.py     # Register API routes AND admin
├── api/                    # REST API endpoints
│   ├── location.py
│   └── ...
├── admin/                  # ← NEW: Starlette Admin
│   ├── __init__.py
│   ├── auth.py             # Auth provider for admin
│   ├── views.py            # Custom ModelViews
│   └── actions.py          # Bulk actions (publish, export)
├── db/                     # Shared SQLAlchemy models
├── schemas/                # Pydantic schemas (API only)
└── services/               # Shared business logic
```

**Updated `core/initializers.py`**:
```python
def register_routes(app):
    # Existing API routes
    from api.location import router as location_router
    from api.sensor import router as sensor_router
    # ... (all existing routers)

    app.include_router(location_router)
    app.include_router(sensor_router)
    # ...

    # NEW: Mount admin interface
    from admin import create_admin
    admin = create_admin()
    admin.mount_to(app)  # Mounts at /admin by default
```

**New `admin/__init__.py`**:
```python
from starlette_admin.contrib.sqla import Admin, ModelView
from db import Location, Sensor, Sample, Contact, Asset, Group
from db.engine import engine
from .auth import NMBGMRAuthProvider
from .views import (
    LocationAdmin, SensorAdmin, SampleAdmin,
    ContactAdmin, AssetAdmin, GroupAdmin
)

def create_admin():
    admin = Admin(
        engine,
        title="NMSampleLocations Admin",
        base_url="/admin",
        auth_provider=NMBGMRAuthProvider()
    )

    # Register model views
    admin.add_view(LocationAdmin(Location))
    admin.add_view(SensorAdmin(Sensor))
    admin.add_view(SampleAdmin(Sample))
    admin.add_view(ContactAdmin(Contact))
    admin.add_view(AssetAdmin(Asset))
    admin.add_view(GroupAdmin(Group))

    return admin
```

**Deployment**:
```bash
# Single service
uvicorn main:app --host 0.0.0.0 --port 8000

# Routes available:
# - http://localhost:8000/docs      → OpenAPI (public)
# - http://localhost:8000/docs-auth → OpenAPI (authenticated)
# - http://localhost:8000/location  → REST API
# - http://localhost:8000/admin     → Starlette Admin UI ← NEW
```

**Docker Compose** (unchanged):
```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://...
    # Single container runs both API and admin
```

---

### Option B: Separate Repository (Admin as Microservice)

**Structure**:
```
NMSampleLocations/          # Existing FastAPI API
├── api/
├── db/
└── ...

NMSampleLocations-Admin/    # NEW: Separate admin service
├── main.py
├── admin/
│   ├── views.py
│   └── auth.py
├── db/                     # ← DUPLICATED models
│   ├── location.py         # Same as NMSampleLocations/db/location.py
│   └── ...
└── requirements.txt
```

**Deployment**:
```yaml
services:
  api:
    build: ./NMSampleLocations
    ports:
      - "8000:8000"

  admin:
    build: ./NMSampleLocations-Admin
    ports:
      - "8001:8000"

  db:
    image: postgis/postgis
    # Both services connect to same database
```

**Routes**:
- API: `http://localhost:8000/location`
- Admin: `http://localhost:8001/admin`

---

### Comparison: Monolithic vs. Microservice

| Aspect | Monolithic (Option A) | Microservice (Option B) |
|--------|----------------------|------------------------|
| **Code Duplication** | ✅ No duplication (shared models) | ❌ Models duplicated across repos |
| **Deployment** | ✅ Single service | ⚠️ Two services to deploy |
| **Development** | ✅ Single repo, single environment | ⚠️ Two repos, sync models manually |
| **Authentication** | ✅ Shared auth logic | ⚠️ Auth sync complexity |
| **Database Migrations** | ✅ Single Alembic migration | ⚠️ Must coordinate migrations |
| **Independent Scaling** | ❌ Can't scale admin separately | ✅ Can scale admin independently |
| **Technology Lock-in** | ⚠️ Admin tied to FastAPI | ✅ Can use different framework |
| **CI/CD Complexity** | ✅ Single pipeline | ⚠️ Two pipelines |
| **Monitoring** | ✅ Single service to monitor | ⚠️ Two services to monitor |
| **Ease of Swapping** | ⚠️ Harder to replace admin | ✅ Easy to replace admin service |

---

### Hybrid Option C: Monolithic with Admin Toggle

**Best of Both Worlds**: Admin lives in same repo but can be **optionally disabled** via environment variable.

```python
# core/initializers.py
def register_routes(app):
    # Always register API routes
    from api.location import router as location_router
    # ...
    app.include_router(location_router)

    # Conditionally mount admin
    if settings.ENABLE_ADMIN:  # ← Environment variable
        from admin import create_admin
        admin = create_admin()
        admin.mount_to(app)
```

**.env**:
```bash
# Production API deployment (no admin)
ENABLE_ADMIN=false

# Development or admin-only deployment
ENABLE_ADMIN=true
```

**Deployment Flexibility**:
```yaml
# Option 1: Combined deployment
services:
  app:
    environment:
      - ENABLE_ADMIN=true  # Both API and admin

# Option 2: Separate deployments (same codebase!)
services:
  api:
    environment:
      - ENABLE_ADMIN=false  # API only

  admin:
    environment:
      - ENABLE_ADMIN=true   # Admin only
```

**Benefits**:
- ✅ Single codebase, shared models
- ✅ Flexibility to deploy separately later
- ✅ Easy to disable admin in production if needed
- ✅ Can scale admin separately if using separate deployments

---

## Architectural Recommendation

### For AMPAPI Migration: **Option A (Monolithic)** ⭐

**Rationale**:

1. **Simplicity**: NMSampleLocations is already monolithic - adding admin doesn't change architecture
2. **Speed**: No need to set up separate repo, CI/CD, deployment
3. **Code Sharing**: Admin views use existing SQLAlchemy models, no duplication
4. **Easy Testing**: Test both API and admin in single pytest suite
5. **Migration Focus**: Reduces complexity during critical migration period

**Implementation Path**:
```bash
# Week 1: Add admin to existing repo
cd NMSampleLocations
mkdir admin
touch admin/__init__.py admin/auth.py admin/views.py

# Week 2-4: Implement admin views
# (No separate repo, no separate deployment)

# Production: Single deployment, both API and admin
docker build -t nmsamplelocations .
docker run -p 8000:8000 nmsamplelocations
# → http://localhost:8000/location (API)
# → http://localhost:8000/admin (Admin UI)
```

**Future Flexibility**: If you later decide admin needs to be separate:
1. Move `admin/` directory to new repo
2. Copy `db/` models (or use shared package)
3. Deploy as separate service

**Low lock-in**: Adding admin to monolith doesn't prevent future microservice split.

---

### When to Use Separate Repository (Option B)

✅ **Use microservice approach if:**

1. **Admin is long-term** (not temporary for migration)
2. **Different scaling needs** (admin has different load pattern than API)
3. **Different teams** (separate admin team, separate API team)
4. **Different tech stacks** (e.g., Django Admin for admin, FastAPI for API)
5. **Security isolation** (admin on internal network, API public)

❌ **Don't use microservice if:**
- Admin is **temporary** during migration
- You have **limited DevOps resources**
- You want **fast iteration** (monolith is faster to develop)

---

## Migration Strategy with Monolithic Admin

### Phase 1: Add Admin to Monolith (Week 1)
```python
# NMSampleLocations/admin/__init__.py
from starlette_admin.contrib.sqla import Admin
from db.engine import engine

def create_admin():
    admin = Admin(engine, title="NM Sample Locations")
    # Start with 3 models for testing
    from admin.views import LocationAdmin, SensorAdmin, ContactAdmin
    admin.add_view(LocationAdmin)
    admin.add_view(SensorAdmin)
    admin.add_view(ContactAdmin)
    return admin
```

### Phase 2: Expand Models (Week 2)
- Add remaining 7 models (10 total)
- Implement auth provider
- Add RBAC permissions

### Phase 3: Custom Features (Week 3-4)
- Bulk actions
- Export functionality
- Custom dashboards

### Phase 4: Production (Week 5)
- Deploy single service with both API and admin
- Monitor usage
- Gather feedback

### Post-Migration: Reevaluate Architecture
**After 3-6 months of usage**, decide:
- ✅ Keep monolithic admin (if working well)
- ↔️ Split into microservice (if scaling/isolation needed)
- ↩️ Restore OcotilloUI (if Starlette Admin insufficient)
- ⏩ Build custom React admin (if long-term investment justified)

---

## Final Recommendations

### Question 1: Starlette Admin vs. Alternatives?

**Answer**: ✅ **Starlette Admin is the right choice** for these reasons:

1. **Speed**: 2-4 weeks vs. 6-8 weeks (Django Admin) or 3-4 months (custom React)
2. **Low Risk**: Can fall back to OcotilloUI if it fails UAT
3. **Python-Only**: No Node.js, simpler stack
4. **Native Integration**: Works directly with your SQLAlchemy models
5. **Temporary Intent**: Perfect for migration period, not over-engineering

**Alternative to Consider**: Keep OcotilloUI if staff reject Starlette Admin during UAT.

---

### Question 2: Monolithic vs. Separate Repo?

**Answer**: ✅ **Monolithic (admin in NMSampleLocations repo)** for these reasons:

1. **Already Monolithic**: NMSampleLocations is single-service architecture
2. **Code Sharing**: No model duplication, single source of truth
3. **Simple Deployment**: Single Docker container, single CI/CD pipeline
4. **Migration Focus**: Reduces complexity during critical period
5. **Future Flexibility**: Can split later if needed (low lock-in)

**Implementation**:
```
NMSampleLocations/
├── api/                 # Existing REST API
├── admin/               # ← NEW: Starlette Admin views
├── db/                  # Shared SQLAlchemy models
├── core/initializers.py # Register both API routes and admin
└── main.py              # Single entry point
```

---

## Next Steps

1. ✅ **Approve Starlette Admin** as temporary admin framework
2. ✅ **Confirm monolithic approach** (admin in NMSampleLocations repo)
3. ⏭️ **Build prototype** (Week 1): Add 2-3 models to admin UI
4. ⏭️ **User acceptance testing** (Week 2): Show to staff, gather feedback
5. ⏭️ **Full implementation** (Week 3-4): Add all models, auth, custom actions
6. ⏭️ **Production deployment** (Week 5): Single service with API + admin
7. ⏭️ **Post-migration review** (3-6 months): Keep, replace, or enhance admin

**Timeline**: **4-5 weeks** from decision to production-ready admin UI.

**Risk**: **Low** - can keep OcotilloUI running in parallel as safety net.
