from __future__ import annotations

import json
import uuid
from pathlib import Path

import duckdb
from shared.testing import requires_postgres

from shared import RLFeedback


def _write_feedback_fixture(path: Path, n: int = 4) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for i in range(n):
            fb = RLFeedback(
                alert_id=f"a{i}",
                zone_id=("z-1" if i % 2 == 0 else "z-2"),
                detected_early=(i % 2 == 0),
                was_false_alarm=False,
                was_missed=(i == 3),
                compute_frames_used=10 + i,
            )
            f.write(json.dumps(fb.model_dump(mode="json"), separators=(",", ":")) + "\n")
    return path


@requires_postgres
def test_build_zone_stats_against_real_postgres(tmp_path: Path) -> None:
    # Seed incidents directly via DuckDB->Postgres so we don't need SQLAlchemy here.
    import asyncio

    from agents.nodes.memory import init_schema  # idempotent

    asyncio.run(init_schema())

    # Insert two synthetic rows via DuckDB postgres scanner.
    from shared.settings import settings as s

    pg_dsn = f"postgresql://{s.postgres_user}:{s.postgres_password}@{s.postgres_host}:{s.postgres_port}/{s.postgres_db}"
    con = duckdb.connect(":memory:")
    con.execute("INSTALL postgres; LOAD postgres;")
    con.execute(f"ATTACH '{pg_dsn}' AS pg (TYPE postgres)")
    rid1, rid2 = uuid.uuid4().hex, uuid.uuid4().hex
    con.execute(
        """
        INSERT INTO pg.incidents (
            incident_id, alert_id, camera_id, zone_id, severity, requires_dispatch,
            triage_rationale, route_target_type, route_target_name,
            route_distance_m, route_eta_s, notified_channels, created_at, raw_state
        ) VALUES
        (?, 'a-x1', 'cam-1', 'z-1', 'high', true,  'ok', 'hospital', 'H1', 1000.0, 120.0, '["log"]', NOW(), '{}'),
        (?, 'a-x2', 'cam-2', 'z-2', 'low',  false, 'ok', 'none',     NULL,    NULL,  NULL,  '[]',     NOW(), '{}')
        """,
        [rid1, rid2],
    )

    feedback = _write_feedback_fixture(tmp_path / "fb.jsonl", n=4)
    out_path = tmp_path / "zone_stats.parquet"

    from replay.aggregate import build_zone_stats

    written = build_zone_stats(feedback_path=feedback, output_path=out_path, pg_dsn=pg_dsn)
    assert written.exists()

    rows = (
        duckdb.connect(":memory:")
        .execute(
            f"SELECT zone_id, incident_count, detected_early, misses FROM read_parquet('{written.as_posix()}') ORDER BY zone_id, hour_of_day"
        )
        .fetchall()
    )
    zone_ids = {r[0] for r in rows}
    assert {"z-1", "z-2"} <= zone_ids
    # cleanup so this test stays idempotent across runs
    con.execute("DELETE FROM pg.incidents WHERE incident_id IN (?, ?)", [rid1, rid2])
