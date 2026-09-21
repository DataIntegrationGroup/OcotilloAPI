"""
Data migrations that ran once and are no longer part of the registry.

``data_migrations/registry.py`` discovers migrations by walking
``data_migrations.migrations`` with ``pkgutil.iter_modules``, skipping packages
and any module whose name starts with ``_``. A module in this package is
therefore invisible to ``oco data-migrations list``, ``status``, ``run`` and
``run-all`` -- and to the Data Migrations workflow -- while its code and its
tests stay in the tree.

That is the point. The three group migrations here reached staging's ``group``
table through a sequence that is not reproducible on another database
(consolidation, the ArcGIS layer-18 import, then two parenting passes). Every
other environment gets that same end state from
``20260905_0003_group_table_parity_with_staging``, which carries a snapshot of
the result. Leaving these registered meant ``run-all`` would replay the
unreproducible path; deleting them would have cost the ~1100 lines of tests that
document what the consolidation actually does.

Databases that already applied one of these keep their ``data_migration_history``
row. ``get_status()`` reports per registered migration, so the row is simply not
listed any more -- it is not an error, and nothing tries to re-run it.

Nothing here should be run again. Read
``docs/bdms-1143-geographic-area-consolidation-runbook.md`` for what they did.
"""
