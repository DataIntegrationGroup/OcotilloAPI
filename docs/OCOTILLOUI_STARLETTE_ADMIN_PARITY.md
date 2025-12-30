# OcotilloUI → Starlette Admin Feature Parity Analysis

## Executive Summary

This document analyzes the feature gap between **OcotilloUI** (React + Refine.dev admin dashboard) and **Starlette Admin** (Python-based admin framework) for NMSampleLocations during the migration period from AMPAPI.

**Purpose**: Determine the minimum viable feature set required for Starlette Admin to temporarily replace OcotilloUI during the AMPAPI → NMSampleLocations database migration.

**Key Finding**: ~80% of OcotilloUI features are standard CRUD operations that Starlette Admin auto-generates. The remaining ~20% require custom implementation (map views, specialized forms, batch upload).

---

## OcotilloUI Current Feature Inventory

### Core Tech Stack

**Frontend:**
- React 18 + TypeScript
- Refine.dev 4.x (admin framework)
- Material UI 6.x (component library)
- Mapbox GL JS 3.x (mapping)
- TanStack Query (data fetching)
- React Hook Form + Zod (form validation)

**Backend API:**
- NMSampleLocations FastAPI (PostgreSQL + PostGIS)
- RESTful endpoints
- OpenAPI schema generation

**Authentication:**
- Authentik (OAuth/OIDC provider)
- Role-based access control

---

## Resource-by-Resource Comparison

### 1. Core Tables (Standard CRUD)

| Resource | OcotilloUI Pages | Starlette Admin Equivalent | Implementation Effort |
|----------|------------------|---------------------------|----------------------|
| **Asset** | List, Create, Edit, Show | `ModelView(Asset)` | ✅ **Trivial** - auto-generated |
| **Contact** | List, Create, Edit, Show | `ModelView(Contact)` | ✅ **Trivial** - auto-generated |
| **Location** | List, Create, Edit, Show | `ModelView(Location)` | ✅ **Trivial** - auto-generated |
| **Sensor** | List, Create, Edit, Show | `ModelView(Sensor)` | ✅ **Trivial** - auto-generated |
| **Sample** | List, Create, Edit, Show | `ModelView(Sample)` | ✅ **Trivial** - auto-generated |
| **Group** | List, Create, Edit, Show | `ModelView(Group)` | ✅ **Trivial** - auto-generated |

**Notes:**
- All six resources have identical CRUD patterns
- Starlette Admin auto-generates list views with pagination, search, sorting
- Form fields are auto-generated from SQLAlchemy models
- Relationships are handled automatically (foreign key dropdowns)

**Example Implementation:**
```python
# admin_setup.py
from starlette_admin.contrib.sqla import Admin, ModelView
from db import Asset, Contact, Location, Sensor, Sample, Group

admin = Admin(engine, title="NMSampleLocations Admin")

# Auto-generates full CRUD for each model
admin.add_view(ModelView(Asset))
admin.add_view(ModelView(Contact))
admin.add_view(ModelView(Location))
admin.add_view(ModelView(Sensor))
admin.add_view(ModelView(Sample))
admin.add_view(ModelView(Group))
```

**Effort**: **1-2 hours** total for all six resources

---

### 2. Thing Resources (Nested Models)

| Resource | OcotilloUI Implementation | Starlette Admin Approach | Effort |
|----------|---------------------------|-------------------------|--------|
| **Well** | Dedicated pages (List, Create, Edit, Show) | `ModelView(ThingWell)` with custom filters | ⚠️ **Easy** - minor customization |
| **Spring** | Dedicated pages (List, Create, Show) | `ModelView(ThingSpring)` with custom filters | ⚠️ **Easy** - minor customization |
| **Thing-ID-Link** | List, Create, Edit, Show | `ModelView(ThingIdLink)` | ✅ **Trivial** - auto-generated |
| **Well-Screen** | List, Create, Edit, Show | `ModelView(WellScreen)` | ✅ **Trivial** - auto-generated |

**Challenge**: OcotilloUI treats Wells and Springs as separate top-level resources, but they're actually subtypes of the polymorphic `Thing` model.

**Starlette Admin Solution:**
```python
class WellAdmin(ModelView):
    model = ThingWell
    name = "Wells"
    icon = "fa fa-tint"

    # Filter to show only wells
    def get_list_query(self, request):
        return select(ThingWell).where(Thing.thing_type == 'well')

    # Custom form to handle well-specific fields
    fields = [
        'name', 'description', 'location_id',
        'well_depth', 'casing_diameter', 'drill_date',  # well-specific
    ]

class SpringAdmin(ModelView):
    model = ThingSpring
    name = "Springs"

    def get_list_query(self, request):
        return select(ThingSpring).where(Thing.thing_type == 'spring')
```

**Effort**: **4-6 hours** (handling polymorphic models, custom filtering)

---

### 3. Observations (Time-Series Data)

| Resource | OcotilloUI Pages | Starlette Admin Approach | Effort |
|----------|------------------|-------------------------|--------|
| **Groundwater Level Observation** | List, Create (no Edit/Show) | `ModelView(GroundwaterLevelObservation)` | ⚠️ **Easy** - basic CRUD |

**Notes:**
- OcotilloUI only implements List + Create (observations are typically immutable)
- Starlette Admin can replicate this pattern with permission restrictions

**Implementation:**
```python
class GroundwaterLevelObservationAdmin(ModelView):
    model = GroundwaterLevelObservation
    name = "Groundwater Levels"

    # Allow create but not edit (observations are immutable)
    can_edit = False
    can_delete = False  # Or only for admins

    # Custom list display
    column_list = ['observation_date', 'water_level_value', 'sensor', 'location']
    column_sortable_list = ['observation_date', 'water_level_value']
    column_default_sort = ('observation_date', True)  # descending
```

**Effort**: **2-3 hours**

---

### 4. Lexicon (Controlled Vocabulary)

| Resource | OcotilloUI Implementation | Starlette Admin Approach | Effort |
|----------|---------------------------|-------------------------|--------|
| **Lexicon** | Hierarchical list (Categories → Terms) | Two `ModelView`s (Category, Term) | ⚠️ **Medium** - custom UI |
| **Term** | Create, Edit (nested under category) | `ModelView(LexiconTerm)` | ⚠️ **Easy** |
| **Category** | Create, Edit | `ModelView(LexiconCategory)` | ⚠️ **Easy** |

**OcotilloUI Pattern:**
- Single "Lexicon" page showing all categories
- Expandable/collapsible categories
- Inline term creation

**Starlette Admin Pattern:**
- Separate views for Categories and Terms
- Category dropdown in Term form (foreign key)
- Less hierarchical UI, more traditional CRUD

**Trade-off**: Starlette Admin won't replicate the nested expandable UI, but will provide functional CRUD.

```python
admin.add_view(ModelView(LexiconCategory, name="Lexicon Categories"))
admin.add_view(ModelView(LexiconTerm, name="Lexicon Terms"))
```

**Effort**: **2-3 hours** (acceptable UX difference)

---

### 5. Custom Forms (Complex Workflows)

| Form | OcotilloUI Implementation | Starlette Admin Feasibility | Recommendation |
|------|---------------------------|----------------------------|----------------|
| **Well Inventory Form** | Multi-step wizard (stepper UI), Mapbox geocoding, owner search dialog | ❌ **Not feasible** in Starlette Admin | **Defer** - keep as API endpoint, add later |
| **Groundwater Level Form** | Multi-step wizard, well selection, batch entry | ❌ **Not feasible** in Starlette Admin | **Defer** - use direct model CRUD instead |

**Analysis:**
These forms are **specialized data entry workflows** with:
- Multi-step wizards
- Real-time geocoding and validation
- Complex cross-model validation
- Custom UX optimizations

**Migration Strategy:**
1. **Phase 1 (Immediate)**: Skip custom forms, use direct CRUD on underlying models
   - Staff can create Wells directly via Well CRUD
   - Staff can create Observations directly via Observation CRUD
2. **Phase 2 (Post-Migration)**: Re-implement forms as:
   - **Option A**: Custom Starlette Admin views (more work)
   - **Option B**: Separate React mini-app mounted alongside Starlette Admin
   - **Option C**: Restore OcotilloUI for forms only

**Effort**: **N/A** (out of scope for MVP)

---

### 6. Apps (Specialized Tools)

| App | OcotilloUI Implementation | Starlette Admin Feasibility | Recommendation |
|-----|---------------------------|----------------------------|----------------|
| **Hydrograph Corrector** | Interactive chart editing (ECharts), data correction UI | ❌ **Not feasible** | **Defer** - "Coming Soon" status in OcotilloUI |
| **Water Chemistry Import** | CSV upload, validation, preview, batch import | ⚠️ **Possible** with custom view | **Defer** or implement as custom action |

**Analysis:**
- **Hydrograph Corrector**: Currently "coming soon" in OcotilloUI, can remain deferred
- **Water Chemistry Import**: Also "coming soon", could be implemented as Starlette Admin custom action

**CSV Import Pattern (if needed):**
```python
from starlette_admin import action

class SampleAdmin(ModelView):
    @action(
        name="import_csv",
        text="Import CSV",
        confirmation="Upload and import samples from CSV?",
    )
    async def import_csv(self, request, pks):
        # Custom file upload and import logic
        pass
```

**Effort**: **8-12 hours** per app if implemented; **0 hours** if deferred

---

### 7. Map View (Geospatial Visualization)

| Feature | OcotilloUI Implementation | Starlette Admin Feasibility | Recommendation |
|---------|---------------------------|----------------------------|----------------|
| **Map View** | Mapbox GL JS, location markers, popups, spatial search | ❌ **Not feasible** natively | **Defer** or custom view |

**Analysis:**
OcotilloUI's map view provides:
- Interactive Mapbox map showing all locations
- Popup details on click
- Spatial search (draw polygon, query locations)
- Basemap selection

**Starlette Admin Limitations:**
- No built-in mapping UI
- Can display WKT/coordinates in forms, but not interactive maps

**Options:**
1. **Defer**: Staff can view coordinates in Location list view (lat/lon columns)
2. **Custom View**: Create custom Starlette Admin page with embedded Mapbox map
3. **External Tool**: Use QGIS or PostGIS queries for spatial analysis

**Effort**:
- Option 1: **0 hours** (acceptable for MVP)
- Option 2: **16-20 hours** (full custom view)
- Option 3: **N/A** (use existing tools)

---

## Feature Parity Matrix

| Feature Category | OcotilloUI Capability | Starlette Admin Capability | Gap | Priority |
|------------------|----------------------|---------------------------|-----|----------|
| **CRUD Operations** | ✅ Full CRUD for 10+ models | ✅ Auto-generated CRUD | ✅ **No gap** | **P0** |
| **Authentication** | ✅ Authentik OAuth | ✅ Custom auth provider | ✅ **No gap** (integration needed) | **P0** |
| **RBAC Permissions** | ✅ Role-based resource access | ✅ Can/Create/Edit/Delete per model | ✅ **No gap** | **P0** |
| **Search/Filter** | ✅ Full-text search, column filters | ✅ Built-in search and filters | ✅ **No gap** | **P0** |
| **Pagination** | ✅ DataGrid pagination | ✅ Built-in pagination | ✅ **No gap** | **P0** |
| **Relationships** | ✅ Foreign key dropdowns | ✅ Auto-generated selects | ✅ **No gap** | **P0** |
| **Data Validation** | ✅ Zod schemas | ✅ Pydantic/SQLAlchemy validation | ✅ **No gap** (server-side) | **P0** |
| **Map Visualization** | ✅ Interactive Mapbox maps | ❌ Not supported | ⚠️ **Major gap** | **P2** (defer) |
| **Multi-Step Forms** | ✅ Well Inventory, GW Level wizards | ❌ Not supported | ⚠️ **Major gap** | **P2** (defer) |
| **CSV Import/Export** | ✅ Chemistry import app | ⚠️ Possible via custom actions | ⚠️ **Moderate gap** | **P2** (defer) |
| **Chart Editing** | ✅ Hydrograph corrector | ❌ Not supported | ⚠️ **Major gap** | **P3** (coming soon) |
| **Batch Operations** | ⚠️ Limited | ✅ Built-in bulk actions | ✅ **Better in SA** | **P1** |
| **Audit Logging** | ❌ Not implemented | ⚠️ Possible via custom logic | ⚠️ **No gap** (neither has it) | **P3** |

**Legend:**
- **P0**: Critical for MVP (must have)
- **P1**: High value (should have)
- **P2**: Nice to have (can defer)
- **P3**: Future enhancement

---

## MVP Feature Set for Starlette Admin

### Phase 1: Core CRUD (Week 1) - **P0**

**Goal**: Replace OcotilloUI for basic data management

**Deliverables:**
1. ✅ Authentication integration (existing NMSampleLocations auth)
2. ✅ CRUD for 10 core models:
   - Asset, Contact, Location, Sensor, Sample, Group
   - ThingWell, ThingSpring, ThingIdLink, WellScreen
3. ✅ Groundwater Level Observation (list + create only)
4. ✅ Lexicon (categories + terms as separate views)

**Estimated Effort**: **8-12 hours**

**Acceptance Criteria:**
- [ ] Staff can log in with existing credentials
- [ ] All 10 models have list, create, edit, show pages
- [ ] Relationships render as dropdowns (e.g., Sample → Location)
- [ ] Search and pagination work on all list views
- [ ] Data validation prevents invalid entries

---

### Phase 2: Authorization & Data Visibility (Week 2) - **P0**

**Goal**: Match OcotilloUI's permission model

**Deliverables:**
1. ✅ Role-based access control (Admin, Editor, Viewer)
   - Admin: Full CRUD on all models
   - Editor: Create/Edit/View, no delete
   - Viewer: Read-only access
2. ✅ Data visibility controls (`release_status` field)
   - Public-released data visible to all
   - Provisional/internal data visible to staff only
3. ✅ Per-model permission overrides

**Implementation:**
```python
from starlette_admin.auth import AuthProvider

class NMBGMRAuthProvider(AuthProvider):
    async def get_admin_user(self, request):
        user = get_current_user(request)
        return AdminUser(
            username=user.name,
            roles=user.permissions  # ['admin', 'editor', 'viewer']
        )

class LocationAdmin(ModelView):
    def can_delete(self, request):
        return 'admin' in request.state.user.roles

    def can_edit(self, request):
        return 'admin' in request.state.user.roles or 'editor' in request.state.user.roles
```

**Estimated Effort**: **6-8 hours**

**Acceptance Criteria:**
- [ ] Viewers cannot create/edit/delete any records
- [ ] Editors can create/edit but not delete
- [ ] Admins have full access
- [ ] Non-authenticated users see only public-released data

---

### Phase 3: Custom Actions (Week 3) - **P1**

**Goal**: Add bulk operations and export functionality

**Deliverables:**
1. ✅ Bulk publish/unpublish (change `release_status`)
2. ✅ GeoJSON export for locations
3. ✅ CSV export for all models

**Implementation:**
```python
class LocationAdmin(ModelView):
    actions = ['bulk_publish', 'export_geojson']

    @action(
        name="bulk_publish",
        text="Publish Selected",
        confirmation="Make selected locations public?",
    )
    async def bulk_publish(self, request, pks):
        await session.execute(
            update(Location)
            .where(Location.id.in_(pks))
            .values(release_status='public')
        )

    @action(
        name="export_geojson",
        text="Export GeoJSON",
    )
    async def export_geojson(self, request, pks):
        # Generate GeoJSON FeatureCollection
        pass
```

**Estimated Effort**: **8-10 hours**

---

### Phase 4: Polish & Optimization (Week 4) - **P1/P2**

**Deliverables:**
1. ⚠️ Custom dashboard (summary stats, recent activity)
2. ⚠️ Advanced search (full-text across all models)
3. ⚠️ Custom list columns (show related data)
4. ⚠️ Improved geospatial field rendering (show coordinates)

**Estimated Effort**: **10-12 hours**

---

## Deferred Features (Post-Migration)

### Not Included in MVP

| Feature | Reason for Deferral | Future Plan |
|---------|---------------------|------------|
| **Map View** | Complex custom UI required | Option 1: Custom Starlette view<br>Option 2: Keep OcotilloUI for maps only<br>Option 3: Use QGIS |
| **Well Inventory Form** | Multi-step wizard not in SA core | Re-implement as custom form or restore OcotilloUI |
| **Groundwater Level Form** | Multi-step wizard not in SA core | Use direct Observation CRUD for now |
| **Hydrograph Corrector** | Already "coming soon" in OcotilloUI | Build as separate tool when needed |
| **Water Chemistry Import** | Already "coming soon" in OcotilloUI | Implement as SA custom action later |

**Rationale**: These features represent **~20% of usage** but **~80% of implementation effort**. Deferring allows for faster migration and validation of core functionality.

---

## Implementation Roadmap

### Week 1: Core CRUD Setup
- **Day 1-2**: Install Starlette Admin, create basic setup, test with 2-3 models
- **Day 3-4**: Add all 10 core models, test CRUD operations
- **Day 5**: QA testing, bug fixes

**Milestone**: Staff can perform basic CRUD on all models

---

### Week 2: Authorization
- **Day 1-2**: Implement auth provider integration
- **Day 3**: Add role-based permissions
- **Day 4**: Add data visibility controls
- **Day 5**: QA testing with different user roles

**Milestone**: Permission model matches OcotilloUI

---

### Week 3: Custom Actions
- **Day 1-2**: Bulk publish/unpublish actions
- **Day 3**: GeoJSON export
- **Day 4**: CSV export
- **Day 5**: QA testing, documentation

**Milestone**: Staff can perform bulk operations

---

### Week 4: Polish & Launch
- **Day 1-3**: Dashboard, advanced search, custom columns
- **Day 4**: User acceptance testing
- **Day 5**: Production deployment, monitor for issues

**Milestone**: Starlette Admin replaces OcotilloUI for core workflows

---

## Success Criteria

### MVP Launch Checklist

- [ ] All 10 core models have full CRUD functionality
- [ ] Authentication works with existing NMSampleLocations users
- [ ] Role-based permissions match OcotilloUI
- [ ] Data visibility controls enforce public/provisional status
- [ ] Search, filter, pagination work correctly
- [ ] Foreign key relationships render as dropdowns
- [ ] Bulk publish/unpublish actions work
- [ ] CSV export works for all models
- [ ] GeoJSON export works for locations
- [ ] No data loss during migration
- [ ] Performance is acceptable (< 2s page load)

### Post-Launch Metrics

**Measure after 2 weeks of use:**
- User adoption rate (% of staff using Starlette Admin vs. OcotilloUI)
- User satisfaction score (survey)
- Bug reports per week
- Feature requests vs. deferred features list

---

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| **Staff reject Starlette Admin UX** | High | Medium | Conduct UAT before full cutover; keep OcotilloUI available as backup |
| **Missing critical workflow** | High | Low | Identify all workflows upfront; defer non-critical features |
| **Performance issues with large datasets** | Medium | Low | Add pagination, indexing; test with production data volume |
| **Auth integration complexity** | Medium | Medium | Test auth early; use existing NMSampleLocations auth code |
| **Geospatial field rendering issues** | Low | Medium | Acceptable to show WKT/coords as text for MVP |

---

## Decision: Go/No-Go for Starlette Admin

### ✅ Proceed with Starlette Admin If:
- Core CRUD needs are met (10 models)
- Staff can tolerate deferred features (maps, forms) for 2-4 weeks
- MVP can be delivered in 2-3 weeks

### ❌ Use Alternative If:
- Map view is non-negotiable for daily work → **Keep OcotilloUI for maps**
- Well Inventory Form is critical path → **Keep OcotilloUI or build custom form**
- Staff need all current features → **Keep OcotilloUI, revisit after migration**

---

## Recommendation

**Proceed with Starlette Admin as temporary admin UI** with these caveats:

1. **MVP Scope**: 10 core models + auth + permissions + bulk actions (3-4 weeks)
2. **Deferred Features**: Maps, custom forms, specialized apps (re-add post-migration)
3. **Parallel Operation**: Keep OcotilloUI available as fallback for first month
4. **User Training**: Brief staff on UX differences and workarounds

**Total Estimated Effort**: **32-42 hours** (1 developer, 4 weeks part-time)

**Risk Level**: **Low-Medium** (core functionality is straightforward, deferred features are edge cases)

**Value**: **High** (unblocks AMPAPI migration, validates new database schema, reduces dependency on React frontend)

---

## Appendix: Model Mapping

### NMSampleLocations Models → Starlette Admin Views

From `db/__init__.py`, NMSampleLocations has **50+ models**. OcotilloUI currently exposes **~15 resources**. Here's the mapping:

| NMSampleLocations Model | OcotilloUI Resource | Starlette Admin Priority |
|------------------------|---------------------|-------------------------|
| `Asset` | ✅ asset | P0 - Core MVP |
| `Contact` | ✅ contact | P0 - Core MVP |
| `Location` | ✅ location | P0 - Core MVP |
| `Sensor` | ✅ sensor | P0 - Core MVP |
| `Sample` | ✅ sample | P0 - Core MVP |
| `Group` | ✅ group | P0 - Core MVP |
| `ThingWell` | ✅ well | P0 - Core MVP |
| `ThingSpring` | ✅ spring | P0 - Core MVP |
| `ThingIdLink` | ✅ thing-id-link | P0 - Core MVP |
| `WellScreen` | ✅ well-screen | P0 - Core MVP |
| `GroundwaterLevelObservation` | ✅ groundwater-level-observation | P0 - Core MVP |
| `LexiconCategory` | ✅ lexicon (category) | P0 - Core MVP |
| `LexiconTerm` | ✅ lexicon (term) | P0 - Core MVP |
| `Deployment` | ❌ Not in OcotilloUI | P1 - Add later |
| `Observation` | ❌ Not in OcotilloUI (base class) | P1 - Add later |
| `Thing` | ❌ Not in OcotilloUI (base class) | P1 - Add later |
| `Publication` | ❌ Not in OcotilloUI | P2 - Add later |
| `DataProvenance` | ❌ Not in OcotilloUI | P2 - Add later |
| `AquiferSystem` | ❌ Not in OcotilloUI | P2 - Add later |
| `GeologicFormation` | ❌ Not in OcotilloUI | P2 - Add later |
| *(35+ more models)* | ❌ Not exposed in OcotilloUI | P2/P3 - Future |

**Key Insight**: OcotilloUI only exposes **~25% of NMSampleLocations models**. Starlette Admin can initially match this subset, then expand to cover more models over time.

---

## Next Steps

1. **Review this document** with stakeholders (data managers, developers)
2. **Confirm MVP scope** - are deferred features acceptable?
3. **Prototype Starlette Admin** with 2-3 models (4-6 hours)
4. **User acceptance testing** - show prototype to staff, gather feedback
5. **Go/No-Go decision** based on UAT feedback
6. **Full implementation** if approved (follow 4-week roadmap)

---

## Resources

- [Starlette Admin Documentation](https://jowilf.github.io/starlette-admin/)
- [Starlette Admin SQLAlchemy Example](https://github.com/jowilf/starlette-admin/tree/main/examples/sqla)
- [ADMIN_FRAMEWORK_EVALUATION.md](./ADMIN_FRAMEWORK_EVALUATION.md) - Technical framework comparison
- [OcotilloUI Source Code](../../OcotilloUI/) - Current admin implementation
- [NMSampleLocations Models](../db/) - Database schema
