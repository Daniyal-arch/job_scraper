from __future__ import annotations

from sources.base import Job


def filter_new(jobs: list[Job], existing_hashes: set[str]) -> list[Job]:
    """Keep only jobs whose dedup hash hasn't already been written to the sheet."""
    new_jobs = []
    seen_this_run: set[str] = set()
    for job in jobs:
        h = job.dedup_hash()
        if h in existing_hashes or h in seen_this_run:
            continue
        seen_this_run.add(h)
        new_jobs.append(job)
    return new_jobs
