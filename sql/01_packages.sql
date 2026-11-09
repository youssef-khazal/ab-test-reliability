-- One row per package (a headline/image version shown in a test), from the archive CSV.
-- {csv} is filled in by abtr.db with the path of the sample being analysed.
create or replace table packages as
select
    clickability_test_id                     as test_id,
    created_at,
    headline,
    excerpt,                                 -- shown under the headline
    eyecatcher_id                            as image_id,
    lede,                                    -- first sentence of the article
    share_text,                              -- text suggested for social media; varied in some 2014-2015 tests
    square,                                  -- image that goes with the share text
    impressions,
    clicks,
    clicks::double / impressions             as ctr,
    significance,
    first_place,
    winner,
    test_week
from read_csv_auto('{csv}', header = true)
where impressions > 0;
