from __future__ import annotations

import logging

from dedup import filter_new
from sheets_writer import append_jobs, get_existing_hashes, get_worksheet
from sources import arbeitsagentur, fraunhofer_iosb, indeed, kit_karriere, linkedin, xing

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("main")

SOURCES = [
    arbeitsagentur,
    fraunhofer_iosb,
    kit_karriere,
    linkedin,
    xing,
    indeed,
]


def run() -> None:
    all_jobs = []
    for source in SOURCES:
        name = source.__name__.rsplit(".", 1)[-1]
        try:
            found = source.run()
            log.info("%s: found %d relevant job(s)", name, len(found))
            all_jobs.extend(found)
        except Exception:
            log.exception("%s: scraper failed, skipping", name)

    worksheet = get_worksheet()
    existing_hashes = get_existing_hashes(worksheet)
    new_jobs = filter_new(all_jobs, existing_hashes)

    log.info("Total found: %d, new (not yet in sheet): %d", len(all_jobs), len(new_jobs))
    append_jobs(worksheet, new_jobs)


if __name__ == "__main__":
    run()
