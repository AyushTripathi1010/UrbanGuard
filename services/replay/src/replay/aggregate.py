"""Aggregate incidents from Postgres + rl_feedback.jsonl into a zone_stats parquet.

The output `zone_stats.parquet` is read by the next RL training run to anchor its
reward shaping against the realised incident distribution.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import structlog
from shared.settings import settings

log = structlog.get_logger("replay.aggregate")

_FEEDBACK_SINK = Path("data/processed/rl_feedback.jsonl")
_OUTPUT = Path("data/processed/zone_stats.parquet")


def _pg_url() -> str:
    return (
        f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )


def build_zone_stats(
    *,
    feedback_path: Path | None = None,
    output_path: Path | None = None,
    pg_dsn: str | None = None,
) -> Path:
    """Run the aggregation and write `zone_stats.parquet`. Returns the path written."""
    feedback_path = feedback_path or _FEEDBACK_SINK
    output_path = output_path or _OUTPUT
    pg_dsn = pg_dsn or _pg_url()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(":memory:")
    con.execute("INSTALL postgres; LOAD postgres;")
    con.execute(f"ATTACH '{pg_dsn}' AS pg (TYPE postgres, READ_ONLY)")

    # incidents per (zone_id, hour_of_day) over all time
    con.execute(
        """
        CREATE TEMP TABLE incidents_by_zone_hour AS
        SELECT
            zone_id,
            EXTRACT(HOUR FROM created_at)::INTEGER AS hour_of_day,
            COUNT(*) AS incident_count,
            SUM(CASE WHEN severity IN ('high', 'critical') THEN 1 ELSE 0 END) AS severe_count,
            AVG(COALESCE(route_eta_s, 0.0)) AS avg_eta_s
        FROM pg.incidents
        GROUP BY zone_id, EXTRACT(HOUR FROM created_at)::INTEGER
        """
    )

    if feedback_path.exists() and feedback_path.stat().st_size > 0:
        con.execute(
            f"""
            CREATE TEMP TABLE feedback_by_zone AS
            SELECT
                zone_id,
                SUM(CASE WHEN detected_early THEN 1 ELSE 0 END) AS detected_early,
                SUM(CASE WHEN was_false_alarm THEN 1 ELSE 0 END) AS false_alarms,
                SUM(CASE WHEN was_missed THEN 1 ELSE 0 END) AS misses,
                SUM(compute_frames_used) AS total_compute_frames
            FROM read_json('{feedback_path.as_posix()}', format='newline_delimited')
            GROUP BY zone_id
            """
        )
    else:
        con.execute(
            """
            CREATE TEMP TABLE feedback_by_zone AS
            SELECT
                CAST(NULL AS VARCHAR) AS zone_id,
                CAST(0 AS BIGINT) AS detected_early,
                CAST(0 AS BIGINT) AS false_alarms,
                CAST(0 AS BIGINT) AS misses,
                CAST(0 AS BIGINT) AS total_compute_frames
            WHERE 1 = 0
            """
        )

    con.execute(
        f"""
        COPY (
            SELECT
                i.zone_id,
                i.hour_of_day,
                i.incident_count,
                i.severe_count,
                i.avg_eta_s,
                COALESCE(f.detected_early, 0) AS detected_early,
                COALESCE(f.false_alarms, 0) AS false_alarms,
                COALESCE(f.misses, 0) AS misses,
                COALESCE(f.total_compute_frames, 0) AS total_compute_frames
            FROM incidents_by_zone_hour i
            LEFT JOIN feedback_by_zone f USING (zone_id)
            ORDER BY i.zone_id, i.hour_of_day
        ) TO '{output_path.as_posix()}' (FORMAT PARQUET)
        """
    )

    rows = con.execute(f"SELECT COUNT(*) FROM read_parquet('{output_path.as_posix()}')").fetchone()[
        0
    ]
    log.info("zone_stats.written", path=str(output_path), rows=rows)
    return output_path
