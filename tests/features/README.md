# Data Visibility Feature Files

This directory contains feature files documenting data visibility and access control requirements during the ongoing migration from AMPAPI's legacy model to NMSampleLocations' new design.

## Active Migration: Three Approaches

### 1. AMPAPI Legacy (`public_release.feature`)
**Model:** Single `PublicRelease` Boolean field
- `True` = public, `False`/`NULL` = private
- 21 scenarios, fully implemented with unit tests
- Binary decision: data is either public or not

### 2. NMSampleLocations Current (in codebase)
**Model:** Single `release_status` enum field (default: "draft")
- Values: draft, provisional, final, published, public, private, archived
- ⚠️ Field exists but filtering NOT implemented
- ⚠️ All data currently visible to all users
- Workflow stages implied but not enforced

### 3. NMSampleLocations Proposed (`data-visibility-and-review.feature`)
**Model:** Two separate fields for independent control
- `visibility`: "internal" | "public" (who can see it)
- `review_status`: "provisional" | "approved" (quality status)
- Both fields REQUIRED, no defaults
- Supports four combinations (e.g., public+provisional, internal+approved)

## Migration Path: Two-Field Design (Recommended)

**Adopt the two-field approach** - separates "who can see" from "data quality"

### Migration Mapping
```
Current release_status → (visibility, review_status)
----------------------------------------------------
draft          → (internal, provisional)
provisional    → (internal, provisional)
final          → (internal, approved)
published      → (public, approved)
public         → (public, approved)
private        → (internal, approved)
archived       → (internal, approved)
```

### Key Business Rules to Implement
From AMPAPI scenarios:
- Public users see only `visibility="public"` data
- Internal/staff users see ALL data regardless of visibility
- New data defaults to `internal + provisional` (safe default)
- Status changes tracked in audit log
- Filtering consistent across all endpoints (GET, GeoJSON, reports)

### Implementation Status
- [x] Schema design documented
- [x] Legacy scenarios documented (`public_release.feature`)
- [x] New design scenarios documented (`data-visibility-and-review.feature`)
- [ ] Add `visibility` and `review_status` columns to models
- [ ] Migrate existing `release_status` data to new fields
- [ ] Implement filtering in routers (public vs. internal users)
- [ ] Add unit tests for all scenarios
- [ ] Update API schemas
- [ ] Deprecate `release_status` field

## File Status

- **`public_release.feature`** - AMPAPI reference, 21 scenarios to adapt
- **`data-visibility-and-review.feature`** - Proposed design, 3 active scenarios
- Other .feature files - Existing NMSampleLocations integration tests (unrelated to visibility)

## Next Steps

1. Add new columns to ReleaseMixin
2. Create Alembic migration with data transformation
3. Implement router filtering based on `visibility`
4. Port AMPAPI unit test approach to validate scenarios
5. Update client apps (Ocotillo, Weaver) to use new fields
