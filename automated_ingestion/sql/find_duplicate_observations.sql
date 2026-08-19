-- Find duplicate transducer observations before adding the unique constraint.
--
-- The migration that adds UNIQUE (deployment_id, parameter_id,
-- observation_datetime) will fail on a table that already violates it, and
-- failing halfway through a production migration is worse than not starting.
-- Run this first, on every environment the migration will touch.
--
--   psql "..." -f automated_ingestion/sql/find_duplicate_observations.sql
--
-- No rows means the migration is safe to run. Rows mean a decision is needed
-- about which copy to keep, and that decision belongs to someone who knows the
-- data -- deleting the higher id is a guess, not a rule, because the rows may
-- differ in `value` rather than being true duplicates.

\echo '== Duplicate groups =='
SELECT
    deployment_id,
    parameter_id,
    observation_datetime,
    count(*)             AS copies,
    count(DISTINCT value) AS distinct_values,
    min(id)              AS lowest_id,
    max(id)              AS highest_id
FROM transducer_observation
GROUP BY deployment_id, parameter_id, observation_datetime
HAVING count(*) > 1
ORDER BY copies DESC, observation_datetime
LIMIT 100;

\echo ''
\echo '== Totals =='
-- `distinct_values > 1` is the interesting case: those are not redundant copies
-- but disagreeing measurements, and collapsing them silently would discard a
-- reading somebody recorded.
SELECT
    count(*)                                        AS duplicate_groups,
    sum(copies) - count(*)                          AS rows_above_the_first,
    count(*) FILTER (WHERE distinct_values > 1)     AS groups_that_disagree
FROM (
    SELECT count(*) AS copies, count(DISTINCT value) AS distinct_values
    FROM transducer_observation
    GROUP BY deployment_id, parameter_id, observation_datetime
    HAVING count(*) > 1
) g;
