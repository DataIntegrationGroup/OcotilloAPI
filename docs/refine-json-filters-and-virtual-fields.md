# Refine JSON filters and virtual association fields

This document explains why list endpoints accept repeated `filter` query parameters and why some filter `field` names bypass normal SQL columns. It complements the shorter comments at the top of [`services/query_helper.py`](../services/query_helper.py).

## Who this is for

Anyone changing list APIs that back the Ocotillo UI (Refine + DataGrid), adding new filterable columns that are backed by associations, or debugging **400 Invalid JSON**, **422 missing keys**, or **wrong row counts** after filtering.

## What problem we are solving

### 1. UI sends many logical filters as many HTTP parameters

The Ocotillo UI uses Refine’s `getList`, which builds query strings like:

```http
GET /contact?page=1&size=50&filter={"field":"things","operator":"contains","value":"DE"}
```

Each active DataGrid filter becomes **one** `filter=...` entry. FastAPI exposes that as **`list[str]`** when declared as `Query(alias="filter")`. Every JSON object is applied in sequence (see below). Older endpoints that accepted **only one** string `filter` silently dropped extra filters when the UI added a second column filter, which looked like bugs (totals vs rows mismatch).

So we standardize list routes on **`filter_params: list[str] | None`**, merged inside `order_sort_filter` instead of splitting behavior between “single filter string” vs “many”.

### 2. Some DataGrid columns are not database columns

The Contacts list shows **Associated Sites** by reading related `Thing` rows and joining names in the UI layer. On the backend, **`Contact.things`** is an **association proxy**, not a `String` column you can **`ILIKE`** in SQL.

If `_apply_json_filter_clause` tries `getattr(Contact, "things")` and treats it like a column, filtering fails at runtime (**400**) because:

- Proxies or relationships do not behave like **`Column`** objects for `ilike`.
- Even if they did, “contains” semantically means “match text across **zero to many** related sites”, which requires a join or subquery, not one scalar cell.

Therefore we declare **virtual filter fields**: string names agreed with the UI (`field` in JSON) that map to dedicated Python helpers. Those helpers express the intended semantics in SQL.

### 3. Inverse symmetry: wells vs contacts

Associations are stored in **`ThingContactAssociation`** (`thing_id`, `contact_id`).

| List resource | Virtual `field` | Meaning | Implementation sketch |
|---------------|------------------|---------|------------------------|
| Thing (wells) | `contacts` | “Does **any** linked contact’s **name** match?” | EXISTS over `ThingContactAssociation` joining `Contact`, predicate on **`Contact.name`** |
| Contact | `things` | “Does **any** linked monitoring site (**thing**) **name** match?” | EXISTS over **`ThingContactAssociation`** joining **`Thing`**, predicate on **`Thing.name`** |

We keep naming aligned with ORM accessors (`Thing.contacts`-style summaries in API responses use **contacts**, and **`Contact`** side uses **`things`** for parity with the association proxy).

### 4. Why `EXISTS (SELECT 1 …)` instead of joining in the outer query?

You could inner join `ThingContactAssociation` + `Thing` onto `Contact` and add `ILIKE` on **`Thing.name`**. That duplicates parent rows when one contact ties to multiple sites. Pagination counts and `LIMIT`/`OFFSET` then drift from what the UI expects (**one row per contact**).

`EXISTS` preserves one row per parent entity while still answering “**any** related row matches”. For negation (**ncontains**, **null**, **ne** where appropriate), we negate the **`EXISTS`** rather than multiplying rows.

### 5. Which text we search

For these virtual association filters we intentionally filter on **`Contact.name`** (things → contacts direction) and **`Thing.name`** (contacts → things direction).

We do **not** search **`organization`**, **`role`**, **`contact_type`**, coordinates, alternative IDs in the association table, or concatenated strings that the UI displays. If product needs those, extend the helpers with explicit, documented predicates so behavior stays predictable for API clients.

### 6. Operators and DataGrid wording

Operators come from Refine/MUI conventions:

- **contains**, **startswith**, **endswith**, **eq**, **ne**, **ncontains**: text predicates on **`name`** inside the **`EXISTS`** branch.
- **null** / **nnull**: empty vs non-empty association (no **`ILIKE`** value semantics). **`value`** may still appear in JSON (for example **`true`**); handler logic follows **operator**.

## Sorting non-column list fields (virtual `sort` parameters)

The DataGrid passes **`sort`** and **`order`** the same way as filters. **`order_sort_filter`** must never call **`getattr(Thing, sort).asc()`** for:

- Python **`@property`** attributes (no mapped column).
- **`AssociationProxy`** collections (**`contacts`**, **`aquifers`** in the API payload).

Those paths previously raised **500**. Virtual sorts are implemented in **`_apply_thing_virtual_sort`** and **`_apply_contact_virtual_sort`** in **`services/query_helper.py`**.

### Thing (`GET /thing/...` lists)

| `sort` value | SQL idea (tied with `Thing.id`) |
|--------------|----------------------------------|
| `monitoring_status`, `well_status`, `datalogger_suitability_status` | Same “latest open” **`StatusHistory.status_value`** subquery as filters; **`lower(...)`**, **`nulls_last`** |
| `site_name` | **`ThingIdLink.alternate_id`** where **`alternate_organization = 'NMBGMR'`**, smallest link **`id`** (matches **`Thing.site_name`**) |
| `contacts` | **`min(lower(Contact.name))`** over **`ThingContactAssociation`** (first name alphabetically among linked contacts) |
| `aquifers` | **`min(lower(AquiferSystem.name))`** over **`ThingAquiferAssociation`** |
| `open_status` | Latest open **“Open Status”** row; rank **Open** before **Closed**, then unknown strings, then no row |
| `measuring_point_height` | Latest **`MeasuringPointHistory`** row with non-null height (**`start_date` desc**, limit 1) |

### Contact (`GET /contact`)

| `sort` value | SQL idea |
|--------------|----------|
| `things` | **`min(lower(Thing.name))`** over linked sites (**`ThingContactAssociation`**) |

**Semantic note:** For multi-valued columns, “sort” uses a **scalar summary** (minimum name, latest status text, etc.). That order can differ from how the UI joins labels with commas. Align copy in column **`description`** text with this behavior.

## How filters combine

Inside `order_sort_filter`, each decoded JSON dict is applied in order via `_apply_json_filter_clause`. Combined filters are **`AND`** together. Changing this would require coordinated UI and API changes.

## Wire format reminder

Each filter **must** include **`field`**, **`operator`**, and **`value`** keys (Refine convention). Omitting keys yields **422** from `_apply_json_filter_clause`.

## Where code lives

| Piece | Location |
|-------|-----------|
| Merge **`filter_`** + **`filters`**, sorting, pagination hook | **`order_sort_filter`** in **`services/query_helper.py`** |
| Dispatch virtual fields | **`_apply_json_filter_clause`** in **`services/query_helper.py`** |
| **`Thing` + contacts** | **`_apply_thing_contacts_filter`** |
| **`Contact` + things** | **`_apply_contact_things_filter`** |
| Contact list accepts repeated **`filter`** | **`GET`** **`/contact`** in **`api/contact.py`**, **`get_db_contacts`** in **`services/contact_helper.py`** |
| Wells list pattern (reference) | **`GET`** **`/thing/water-well`** in **`api/thing.py`**, **`get_db_things`** in **`services/thing_helper.py`** |
| Sort by derived / virtual columns | **`_apply_thing_virtual_sort`**, **`_apply_contact_virtual_sort`**, **`THING_VIRTUAL_SORT_FIELDS`** in **`services/query_helper.py`** |

## Tests worth reading

- **`tests/test_contact_filters.py`**: **`things`** filters, **`things`** sort, multiple **`filter`** params on **`GET /contact`**.
- **`tests/test_thing.py`** (contacts on wells): **`contacts`** **`contains`**, **`ncontains`**, **`nnull`**, and **`sort`** on **`monitoring_status`**, **`site_name`**, **`contacts`**, **`aquifers`**, etc.

## When you change this

1. Keep UI **`field`** names and API virtual branches in sync (**`things`** vs typo **`associated_sites`** breaks filtering).
2. Prefer **`EXISTS`** for “any related row matches” filters to avoid duplicate parents.
3. Extend operators only with tests that lock semantics (especially **negation**).
4. If you add virtual fields for other routes, document them here and in the **`query_helper`** header block.
