# Admin Framework Evaluation for NMSampleLocations

## Project Context

**NMSampleLocations** is a production-oriented geospatial sample data management system for the New Mexico Bureau of Geology and Mineral Resources.

### Current Stack
- **Backend**: FastAPI / Starlette
- **ORM**: SQLAlchemy 2.0.43
- **Database**: PostgreSQL + PostGIS (geospatial)
- **Auth**: Role-based access control (Admin/Editor/Viewer)
- **Data Model**: 33+ SQLAlchemy models with complex relationships
- **Special Requirements**:
  - GeoAlchemy2 for geospatial data
  - Data visibility controls (`release_status` field)
  - Versioned data (SQLAlchemy-Continuum)
  - Complex domain: locations, things, samples, observations, sensors, deployments

---

## Executive Recommendation

**Primary Choice: Starlette Admin**

### Rationale

1. **Perfect ORM Fit**: Native SQLAlchemy support (you already use SQLAlchemy 2.0.43)
2. **Geospatial Ready**: Works with GeoAlchemy2 out of the box
3. **RBAC Built-in**: Matches your existing permission model (Admin/Editor/Viewer)
4. **Production Maturity**: Battle-tested, active maintenance
5. **Extensibility**: Can handle complex workflows and custom business logic
6. **Low Lock-in**: Uses standard SQLAlchemy models, easy to migrate away if needed

---

## Detailed Evaluation for NMSampleLocations

### Option 1: Starlette Admin ⭐ **RECOMMENDED**

**Installation**
```bash
pip install starlette-admin[i18n]
# Or with uv:
uv add starlette-admin[i18n]
```

**Why It's Perfect for You**

✅ **SQLAlchemy Integration**
- Works directly with your existing models
- No schema duplication needed
- Supports SQLAlchemy-Continuum (versioned data)

✅ **Geospatial Support**
```python
from starlette_admin.contrib.sqla import Admin, ModelView
from geoalchemy2 import Geometry

# Your Location model will work out of the box
class LocationAdmin(ModelView):
    fields = ['id', 'point', 'elevation', 'release_status', ...]
    # PostGIS geometry fields render properly
```

✅ **RBAC Implementation**
```python
from starlette_admin.auth import AdminUser, AuthProvider

class NMBGMRAuthProvider(AuthProvider):
    async def is_authenticated(self, request):
        # Your existing auth logic
        user = get_current_user(request)
        return user is not None

    async def get_admin_user(self, request):
        user = get_current_user(request)
        return AdminUser(
            username=user.name,
            roles=user.permissions  # ['Admin', 'Editor', 'Viewer']
        )

# In your admin views:
class LocationAdmin(ModelView):
    def can_create(self, request):
        return 'Admin' in request.state.user.roles

    def can_edit(self, request):
        return any(role in request.state.user.roles for role in ['Admin', 'Editor'])
```

✅ **Data Visibility Controls**
```python
class LocationAdmin(ModelView):
    # Override queryset based on user role
    async def get_list_query(self, request):
        query = select(Location)

        # Staff see all data
        if request.state.user:
            return query

        # Public see only public data
        return query.where(Location.release_status == 'public')
```

✅ **Custom Actions**
```python
class LocationAdmin(ModelView):
    actions = ['bulk_publish', 'export_geojson']

    async def bulk_publish(self, request, pks):
        # Bulk change release_status to 'public'
        await session.execute(
            update(Location)
            .where(Location.id.in_(pks))
            .values(release_status='public')
        )
```

**Example Implementation**
```python
# admin_setup.py
from starlette_admin import CustomView
from starlette_admin.contrib.sqla import Admin, ModelView
from starlette.applications import Starlette

from db import Location, Thing, Sample, Observation, Sensor
from db.engine import engine

# Create admin
admin = Admin(
    engine,
    title="NMSampleLocations Admin",
    base_url='/admin',
    auth_provider=NMBGMRAuthProvider()
)

# Register model views
admin.add_view(LocationAdmin(Location))
admin.add_view(ModelView(Thing))
admin.add_view(ModelView(Sample))
admin.add_view(ModelView(Observation))
admin.add_view(ModelView(Sensor))

# Mount to FastAPI
from fastapi import FastAPI
app = FastAPI()
admin.mount_to(app)
```

**Estimated Setup Time**: 1-2 days for basic CRUD, 1 week for full customization

**Pros**
- ✓ Works with all 33+ of your models immediately
- ✓ Handles complex relationships
- ✓ GeoJSON/PostGIS support
- ✓ Customizable per-model permissions
- ✓ Active community

**Cons**
- ⚠ UI is functional but not flashy (admin-focused, not customer-facing)
- ⚠ Requires custom views for complex workflows

**Best For**
- Internal staff tool for data management
- RBAC-driven access to all models
- Quick setup with room to grow

---

### Option 2: SQLAlchemy Admin (SQLAdmin)

**Why Consider It**

Simpler alternative if you don't need geospatial UI features or complex RBAC.

✅ **Strengths**
- Lightweight, minimal configuration
- Clean UI
- Works with your SQLAlchemy models

❌ **Limitations for Your Project**
- Less flexible permission system
- Weaker geospatial rendering
- Limited custom action support

**Verdict**: Good for simple admin needs, but Starlette Admin is more future-proof for your use case.

---

### Option 3: FastAPI Amis Admin

**Why It Might Appeal**

If you want a highly customizable, dashboard-heavy admin with charts and complex forms.

✅ **Strengths**
- Beautiful, modern UI
- Supports complex dashboards
- Works with SQLAlchemy

❌ **Limitations for Your Project**
- Steeper learning curve (AMIS schema DSL)
- Overkill for internal tooling
- More maintenance overhead

**Verdict**: Consider if you need public-facing dashboards or complex visualization. Not recommended for internal-only admin.

---

### ❌ Options to Avoid

**FastAPI Admin**: Requires Tortoise ORM (you use SQLAlchemy)
**Piccolo Admin**: Requires Piccolo ORM (you use SQLAlchemy)

---

## Comparison Matrix for NMSampleLocations

| Criteria | Starlette Admin | SQLAdmin | Amis Admin |
|----------|----------------|----------|------------|
| **SQLAlchemy Support** | ✅ Native | ✅ Native | ✅ Native |
| **GeoAlchemy2/PostGIS** | ✅ Built-in | ⚠ Basic | ⚠ Basic |
| **RBAC Implementation** | ✅ Flexible | ⚠ Manual | ✅ Good |
| **Complex Relationships** | ✅ Excellent | ✅ Good | ✅ Good |
| **Custom Actions** | ✅ Easy | ⚠ Limited | ✅ Flexible |
| **Setup Time** | Medium | Fast | Slow |
| **Maintenance Burden** | Low | Very Low | Medium-High |
| **Future-Proof** | ✅ High | ✅ Medium | ⚠ Medium |

---

## Implementation Roadmap

### Phase 1: Core Setup (Week 1)
1. Install Starlette Admin
2. Create basic ModelViews for top 5 models (Location, Thing, Sample, Observation, Sensor)
3. Implement authentication provider using existing permissions.py
4. Test geospatial field rendering

### Phase 2: Authorization (Week 2)
1. Implement role-based view filtering
2. Add per-model permission checks (can_create, can_edit, can_delete)
3. Apply data visibility rules (release_status filtering)

### Phase 3: Custom Actions (Week 3)
1. Bulk publish/unpublish actions
2. GeoJSON export action
3. Data quality validation actions

### Phase 4: Advanced Features (Week 4+)
1. Custom dashboard views
2. Audit log integration
3. Advanced search/filtering
4. Workflow automation (e.g., provisional → approved status transitions)

---

## Alternatives if Starlette Admin Doesn't Work

### Plan B: Django Admin (Separate Service)
If you need enterprise-grade features:
- Run Django admin as separate microservice
- Share PostgreSQL database
- Use for admin only, keep FastAPI for API

**Tradeoff**: Added complexity, but best-in-class admin experience.

### Plan C: Custom React Admin
If internal team has strong frontend capacity:
- React + Refine.dev or React-Admin
- Full control over UX
- More work upfront, but maximum flexibility

**Tradeoff**: 2-3x development time, but perfect fit for your needs.

---

## Final Recommendation

**Start with Starlette Admin.** It's the best fit for:
- Your current tech stack (FastAPI + SQLAlchemy + PostGIS)
- Your permission model (Admin/Editor/Viewer RBAC)
- Your data model complexity (33+ models, geospatial, versioned)
- Your timeline (production-ready admin in 2-4 weeks)

If requirements evolve beyond CRUD (e.g., complex workflows, customer-facing dashboards), you can:
1. Keep Starlette Admin for internal data management
2. Build custom UI for specific workflows
3. Migrate to Django Admin or custom solution

**Low risk, high value, production-ready.**

---

## Next Steps

1. **Prototype**: Spend 1 day building basic Starlette Admin setup for Location model
2. **Evaluate**: Test with real data and your auth system
3. **Decide**: If it works, expand to all models. If not, try SQLAdmin as backup.
4. **Document**: Update this doc with learnings and final choice

---

## Resources

- [Starlette Admin Documentation](https://jowilf.github.io/starlette-admin/)
- [Starlette Admin + GeoAlchemy2 Example](https://github.com/jowilf/starlette-admin/tree/main/examples/sqla)
- [SQLAlchemy Admin (SQLAdmin)](https://aminalaee.dev/sqladmin/)
- [FastAPI Amis Admin](https://docs.amis.work/)
