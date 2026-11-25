# Collections Dictionary
EDR collections are broadly defined via a list of dictionaries in `core/pygeoapi.py` called `EDR_COLLECTIONS`. Each item in `EDR_COLLECTIONS` defines a collection. The dictionaries work as follows:

```python
{
  "id": "the id of the collection, which defines the route as /collections/{id}",
  "title": "the title of the collection",
  "description": "the description of the collection",
  "keywords": ["keyword 1", "keyword 2", ..., "keyword n"],
  "table": "the database table or view from which the collection's data is queried. It must start with 'ogc_' and have a matching 'ogc_internal_' view.",
  "parameter_columns": [
    {
      "name_column": "the column in the table or view that holds parameter names",
      "unit_column": "the column in the table or view that holds the parameters' units" | None,
      "value_column": "the column in the table or view that holds the values",
      "data_type": "string" | "integer" | "float",
      "lexicon_category": "the lexicon category associated with terms if the parameter is categorical" | None
    },
    ...
  ],
  "station_properties": [
    "property 1 to include in the properties for a feature in the FeatureCollection, must be a column in the database table or view",
    "property 2 to include in the properties for a feature in the FeatureCollection, must be a column in the database table or view",
    ...,
    "property n to include in the properties for a feature in the FeatureCollection, must be a column in the database table or view"
  ],
  "independent_axis": {
    "axis": "t" | "z",
    "column": "the column in the table or view that holds the independent axis values"
  },
  "instance_field": "the column in the table or view that holds in the instance values" | None
}
```

**Notes**
- `z` is planned as an independent axis value but not yet implemented.
- `parameter_columns` is a list because one row may contain multiple parameters (e.g. observation and qualifier) and each column may have multiple parameters (e.g. multiple analytes in a single column).

# Field Descriptions
Parameter names in EDR collections are discovered from the data. They are also described in `core/ogc-field-descriptions.yml`.
If a parameter name from a collection exists in the database, but is not described in `core/ogc-field-descriptions.yml`, then
the description and label in the CoverageCollection and the title and description in `/schema` default to the parameter name as it exists in the database. In this situation a `warning` level message will be logged describing what occurred and why. To have a different description and label than just the parameter name `core/ogc-field-descriptions.yml` will need to be updated for that collection and the API will need to be relaunched. The parameter name in `core/ogc-field-descriptions.yml` must match the parameter name that the backing view or table emits.

# Categories
Parameters that have restricted values - categories in a CoverageCollection - are determined from the lexicon tables. They are populated by the terms associated with a category. They are greedy, so *every* term associated with a category is used. If only a subset of terms are desired add a new category to the `lexicon_category` table and then associate the desired terms with that category. The lexicon term and category tables will need to be updated in `core/lexicon.json` and then in the database with `oco initialize-lexicon`. Afterward the `lexicon_category` in the `EDR_COLLECTIONS` dictionary needs to be updated to the new category, requiring the API to be relaunched.

# Parameters & Units
Each parameter can have one, and only one, unit. The units are defined in the database tables or backing views, nowhere else. If there are multiple units reported for a parameter then that parameter is dropped from the collection and a `warning` level message is logged. The data must be fixed; the API should not account for these edge cases.

# Duplicate Independent Axis Values
If two records share an independent axis value - e.g. the same timestamp - the record with the lowest `id` is kept whole and the other is skipped with a `warning` level message logged.