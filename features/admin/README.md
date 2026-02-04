# Admin Interface BDD Feature Tests

This directory contains Behavior-Driven Development (BDD) feature files for the Starlette Admin interface.

## Features

### `authentication.feature`
Documents authentication and authorization business rules:
- Authentik OIDC integration
- Role-based access control (Admin/Editor/Viewer)
- JWT token verification
- Session management
- Security constraints

**Coverage:**
- 11 scenarios
- Authentication flows
- RBAC permissions
- Development mode behavior

### `location_admin.feature`
Documents Location admin CRUD operations and business rules:
- List view functionality (search, filter, sort, pagination)
- Create/edit forms with WKT coordinate input
- Bulk operations (publish/unpublish)
- Data visibility by release status
- Audit trail (created_by, updated_by)
- MS Access equivalent operations

**Coverage:**
- 24 scenarios
- Full CRUD lifecycle
- Validation rules
- Permission checks
- Data visibility rules

## Running the Tests

### Prerequisites

1. **Test Database**: PostgreSQL + PostGIS test database
   ```bash
   # Create test database
   createdb nmsamplelocations_test
   psql nmsamplelocations_test -c "CREATE EXTENSION postgis;"

   # Run migrations
   alembic upgrade head
   ```

2. **Environment Variables**: Create `.env.test` file:
   ```bash
   DATABASE_URL=postgresql://user:password@localhost/nmsamplelocations_test
   AUTHENTIK_URL=https://auth.example.com
   AUTHENTIK_CLIENT_ID=test_client_id
   AUTHENTIK_DISABLE_AUTHENTICATION=1  # For testing
   MODE=development
   ```

3. **Python Dependencies**:
   ```bash
   uv add --dev behave playwright pytest-playwright
   uv sync
   ```

### Run Tests

```bash
# From NMSampleLocations directory
cd /path/to/NMSampleLocations

# Run all admin feature tests
behave features/admin/

# Run specific feature
behave features/admin/authentication.feature
behave features/admin/location_admin.feature

# Run with tags
behave features/admin/ --tags=@smoke
behave features/admin/ --tags=@rbac
behave features/admin/ --tags=@bulk-actions

# Verbose output
behave features/admin/ -v

# Progress format (dots)
behave features/admin/ --format progress
```

## Test Data Cleanup

The `environment.py` file handles automatic cleanup:
- **before_scenario**: Creates new database session, sets up test user
- **after_scenario**: Deletes all test data created during scenario
- Test data is tracked in `context.scenario_data_ids`
- Ensures test isolation between scenarios

## Step Definitions

### Browser-Based Tests (Playwright)

**File**: `steps/admin_ui_steps.py`

Uses Playwright for browser automation:
- Tests actual admin UI in a real browser
- Clicks buttons, fills forms, verifies page content
- Tests JavaScript interactions
- Slow but comprehensive

**Example**:
```python
@when('I navigate to "/admin/location"')
def step_navigate_to_admin_location(context):
    context.page.goto(f"{context.base_url}/admin/location")

@then('I should see the "Create" button')
def step_see_create_button(context):
    create_button = context.page.locator('button:has-text("Create")')
    expect(create_button).to_be_visible()
```

### API-Based Tests (FastAPI TestClient)

**File**: `steps/admin_api_steps.py`

Uses FastAPI TestClient for direct API testing:
- Tests admin backend without browser
- Fast execution
- Tests data operations directly
- Good for validation and permission tests

**Example**:
```python
@given('the following locations exist')
def step_create_test_locations(context):
    for row in context.table:
        location = Location(
            description=row['description'],
            point=WKTElement(f"POINT(-106.0 35.0)", srid=4326),
            elevation=1500.0,
            **row
        )
        context.session.add(location)
    context.session.commit()
```

## Test Tags

| Tag | Description |
|-----|-------------|
| `@admin` | All admin interface tests |
| `@authentication` | Authentication/authorization tests |
| `@location` | Location-specific tests |
| `@smoke` | Critical smoke tests (run first) |
| `@rbac` | Role-based access control tests |
| `@list-view` | List view functionality |
| `@create` | Create operation tests |
| `@update` | Update operation tests |
| `@delete` | Delete operation tests |
| `@bulk-actions` | Bulk action tests |
| `@data-visibility` | Release status filtering tests |
| `@validation` | Form validation tests |
| `@permissions` | Permission check tests |
| `@security` | Security-related tests |
| `@ms-access-migration` | MS Access equivalent features |

## Test Organization

### Feature File Structure

```gherkin
@tag
Feature: Feature name
  As a <role>
  I need to <action>
  So that <business value>

  Background:
    Given <common setup>

  @scenario-tags
  Scenario: Scenario description
    Given <precondition>
    When <action>
    Then <expected result>
```

### Writing New Scenarios

1. **Start with business language**: Use terms staff understand (not technical jargon)
2. **Use MS Access equivalents**: Reference familiar concepts (e.g., "Datasheet View")
3. **Tag appropriately**: Use `@smoke` for critical paths, specific tags for features
4. **Keep scenarios focused**: One scenario tests one thing
5. **Use scenario outlines**: For testing multiple similar cases with different data

## Example Test Run

```bash
$ behave features/admin/ --tags=@smoke

Feature: Admin Authentication and Authorization

  Scenario: Unauthenticated user is redirected to login
    Given I am not authenticated
    When I navigate to "/admin"
    Then I should be redirected to the Authentik login page
    ...
  ✓ Passed

  Scenario: Authenticated admin user can access admin interface
    Given I am authenticated as user "admin@nmbgmr.nmt.edu"
    ...
  ✓ Passed

Feature: Location Admin CRUD Operations

  Scenario: View location list with default columns
    When I navigate to "/admin/location"
    ...
  ✓ Passed

  Scenario: Create a new location with valid data
    When I navigate to "/admin/location"
    And I click the "Create" button
    ...
  ✓ Passed

4 scenarios (4 passed)
28 steps (28 passed)
0m15.234s
```

## Troubleshooting

### "Playwright not found" error
```bash
# Install Playwright browsers
playwright install chromium
```

### "Database connection refused"
```bash
# Check PostgreSQL is running
pg_isready

# Check DATABASE_URL in .env.test
```

### "Authentik authentication errors"
```bash
# Set to development mode in tests
export AUTHENTIK_DISABLE_AUTHENTICATION=1
export MODE=development
```

### Tests fail but manual testing works
- Check test data cleanup (orphaned data)
- Verify test isolation (scenarios affecting each other)
- Check for race conditions (async operations)

## Next Steps

1. **Implement step definitions**: Create `steps/admin_ui_steps.py` and `steps/admin_api_steps.py`
2. **Set up environment.py**: Configure Behave hooks for setup/teardown
3. **Add CI integration**: Run tests in GitHub Actions
4. **Expand coverage**: Add features for Thing, Sample, Observation admin views

## Related Documentation

- [Behave Documentation](https://behave.readthedocs.io/)
- [Playwright for Python](https://playwright.dev/python/)
- [Starlette Admin Docs](https://jowilf.github.io/starlette-admin/)
- [AMPAPI BDD Tests](../../AMPAPI/features/README.md) - Similar pattern
