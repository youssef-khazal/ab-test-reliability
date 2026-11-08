-- One row per test. "window" marks the period the archive authors flag as possibly not randomized
-- (25 June 2013 to 10 January 2014, see their 2024 update).
create or replace table tests as
select
    test_id,
    min(created_at)                                         as started_at,
    count(*)                                                as n_packages,
    count(distinct headline)                                as n_headlines,
    count(distinct image_id)                                as n_images,
    sum(impressions)                                        as impressions,
    sum(clicks)                                             as clicks,
    sum(clicks)::double / sum(impressions)                  as ctr,
    -- chi-square statistic for "every package got the same number of impressions"
    (sum(impressions * impressions) - sum(impressions) * sum(impressions) / count(*))
        / (sum(impressions)::double / count(*))             as srm_chisq,
    sum(winner::int)                                        as n_winners,
    min(created_at) >= timestamp '2013-06-25'
        and min(created_at) < timestamp '2014-01-11'        as in_flagged_window
from packages
group by test_id;
