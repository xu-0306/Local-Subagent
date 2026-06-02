from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from local_subagent.domain import (
    ExportRecord,
    MessageRecord,
    ReviewRecord,
    RunRecord,
    ToolRequestRecord,
    ToolResultRecord,
)


def _format_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )


def _dump_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _load_json(value: str) -> Any:
    return json.loads(value)


class SQLiteRepository:
    def __init__(self, database_path: Path | str) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self._database_path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._initialize_schema()

    def close(self) -> None:
        self._connection.close()

    def create_run(self, run: RunRecord) -> RunRecord:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO runs (
                    run_id, task, model_name, runtime_profile_json, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.task,
                    run.model_name,
                    _dump_json(run.runtime_profile),
                    run.status,
                    _format_datetime(run.created_at),
                    _format_datetime(run.updated_at),
                ),
            )
        return run

    def update_run_status(
        self, run_id: str, *, status: str, updated_at: datetime
    ) -> RunRecord:
        with self._connection:
            self._connection.execute(
                """
                UPDATE runs
                SET status = ?, updated_at = ?
                WHERE run_id = ?
                """,
                (status, _format_datetime(updated_at), run_id),
            )
        run = self.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        return run

    def get_run(self, run_id: str) -> RunRecord | None:
        row = self._connection.execute(
            "SELECT * FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_run(row)

    def list_runs(self) -> list[RunRecord]:
        rows = self._connection.execute(
            "SELECT * FROM runs ORDER BY created_at, run_id"
        ).fetchall()
        return [self._row_to_run(row) for row in rows]

    def add_message(self, message: MessageRecord) -> MessageRecord:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO messages (
                    message_id, run_id, role, content, sequence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    message.message_id,
                    message.run_id,
                    message.role,
                    message.content,
                    message.sequence,
                    _format_datetime(message.created_at),
                ),
            )
        return message

    def list_messages(self, run_id: str) -> list[MessageRecord]:
        rows = self._connection.execute(
            "SELECT * FROM messages WHERE run_id = ? ORDER BY sequence",
            (run_id,),
        ).fetchall()
        return [self._row_to_message(row) for row in rows]

    def add_tool_request(self, request: ToolRequestRecord) -> ToolRequestRecord:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO tool_requests (
                    tool_request_id,
                    run_id,
                    message_id,
                    tool_name,
                    arguments_json,
                    reason,
                    risk_label,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.tool_request_id,
                    request.run_id,
                    request.message_id,
                    request.tool_name,
                    _dump_json(request.arguments),
                    request.reason,
                    request.risk_label,
                    _format_datetime(request.created_at),
                ),
            )
        return request

    def list_tool_requests(self, run_id: str) -> list[ToolRequestRecord]:
        rows = self._connection.execute(
            "SELECT * FROM tool_requests WHERE run_id = ? ORDER BY created_at",
            (run_id,),
        ).fetchall()
        return [self._row_to_tool_request(row) for row in rows]

    def get_tool_request(self, tool_request_id: str) -> ToolRequestRecord | None:
        row = self._connection.execute(
            "SELECT * FROM tool_requests WHERE tool_request_id = ?",
            (tool_request_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_tool_request(row)

    def add_tool_result(self, result: ToolResultRecord) -> ToolResultRecord:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO tool_results (
                    tool_result_id,
                    run_id,
                    tool_request_id,
                    decision,
                    observation,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    result.tool_result_id,
                    result.run_id,
                    result.tool_request_id,
                    result.decision,
                    result.observation,
                    _format_datetime(result.created_at),
                ),
            )
        return result

    def list_tool_results(self, run_id: str) -> list[ToolResultRecord]:
        rows = self._connection.execute(
            "SELECT * FROM tool_results WHERE run_id = ? ORDER BY created_at",
            (run_id,),
        ).fetchall()
        return [self._row_to_tool_result(row) for row in rows]

    def get_tool_result_for_request(
        self,
        tool_request_id: str,
    ) -> ToolResultRecord | None:
        row = self._connection.execute(
            "SELECT * FROM tool_results WHERE tool_request_id = ?",
            (tool_request_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_tool_result(row)

    def add_review(self, review: ReviewRecord) -> ReviewRecord:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO reviews (
                    review_id,
                    run_id,
                    score,
                    errors_json,
                    improvements_json,
                    missing_parts_json,
                    corrected_response,
                    chosen,
                    rejected,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review.review_id,
                    review.run_id,
                    review.score,
                    _dump_json(review.errors),
                    _dump_json(review.improvements),
                    _dump_json(review.missing_parts),
                    review.corrected_response,
                    review.chosen,
                    review.rejected,
                    _format_datetime(review.created_at),
                ),
            )
        return review

    def get_review(self, run_id: str) -> ReviewRecord | None:
        row = self._connection.execute(
            "SELECT * FROM reviews WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_review(row)

    def replace_review(self, review: ReviewRecord) -> ReviewRecord:
        with self._connection:
            cursor = self._connection.execute(
                """
                UPDATE reviews
                SET
                    review_id = ?,
                    score = ?,
                    errors_json = ?,
                    improvements_json = ?,
                    missing_parts_json = ?,
                    corrected_response = ?,
                    chosen = ?,
                    rejected = ?,
                    created_at = ?
                WHERE run_id = ?
                """,
                (
                    review.review_id,
                    review.score,
                    _dump_json(review.errors),
                    _dump_json(review.improvements),
                    _dump_json(review.missing_parts),
                    review.corrected_response,
                    review.chosen,
                    review.rejected,
                    _format_datetime(review.created_at),
                    review.run_id,
                ),
            )
        if cursor.rowcount == 0:
            raise KeyError(review.run_id)
        return review

    def add_export(self, export: ExportRecord) -> ExportRecord:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO exports (
                    export_id,
                    run_id,
                    format,
                    path,
                    record_count,
                    filters_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    export.export_id,
                    export.run_id,
                    export.format,
                    export.path,
                    export.record_count,
                    _dump_json(export.filters),
                    _format_datetime(export.created_at),
                ),
            )
        return export

    def list_exports(self, run_id: str | None = None) -> list[ExportRecord]:
        if run_id is None:
            rows = self._connection.execute(
                "SELECT * FROM exports ORDER BY created_at"
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT * FROM exports WHERE run_id = ? ORDER BY created_at",
                (run_id,),
            ).fetchall()
        return [self._row_to_export(row) for row in rows]

    def _initialize_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                task TEXT NOT NULL,
                model_name TEXT NOT NULL,
                runtime_profile_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tool_requests (
                tool_request_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
                message_id TEXT NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
                tool_name TEXT NOT NULL,
                arguments_json TEXT NOT NULL,
                reason TEXT,
                risk_label TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tool_results (
                tool_result_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
                tool_request_id TEXT NOT NULL REFERENCES tool_requests(tool_request_id) ON DELETE CASCADE,
                decision TEXT NOT NULL,
                observation TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reviews (
                review_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL UNIQUE REFERENCES runs(run_id) ON DELETE CASCADE,
                score INTEGER,
                errors_json TEXT NOT NULL,
                improvements_json TEXT NOT NULL,
                missing_parts_json TEXT NOT NULL,
                corrected_response TEXT,
                chosen TEXT,
                rejected TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS exports (
                export_id TEXT PRIMARY KEY,
                run_id TEXT REFERENCES runs(run_id) ON DELETE CASCADE,
                format TEXT NOT NULL,
                path TEXT NOT NULL,
                record_count INTEGER NOT NULL,
                filters_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        self._ensure_column(
            "runs",
            "runtime_profile_json",
            "TEXT NOT NULL DEFAULT '{}'",
        )

    def _ensure_column(self, table_name: str, column_name: str, definition: str) -> None:
        existing_columns = {
            row["name"]
            for row in self._connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name in existing_columns:
            return

        with self._connection:
            self._connection.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
            )

    def _row_to_run(self, row: sqlite3.Row) -> RunRecord:
        return RunRecord(
            run_id=row["run_id"],
            task=row["task"],
            model_name=row["model_name"],
            runtime_profile=_load_json(row["runtime_profile_json"]),
            status=row["status"],
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
        )

    def _row_to_message(self, row: sqlite3.Row) -> MessageRecord:
        return MessageRecord(
            message_id=row["message_id"],
            run_id=row["run_id"],
            role=row["role"],
            content=row["content"],
            sequence=row["sequence"],
            created_at=_parse_datetime(row["created_at"]),
        )

    def _row_to_tool_request(self, row: sqlite3.Row) -> ToolRequestRecord:
        return ToolRequestRecord(
            tool_request_id=row["tool_request_id"],
            run_id=row["run_id"],
            message_id=row["message_id"],
            tool_name=row["tool_name"],
            arguments=_load_json(row["arguments_json"]),
            reason=row["reason"],
            risk_label=row["risk_label"],
            created_at=_parse_datetime(row["created_at"]),
        )

    def _row_to_tool_result(self, row: sqlite3.Row) -> ToolResultRecord:
        return ToolResultRecord(
            tool_result_id=row["tool_result_id"],
            run_id=row["run_id"],
            tool_request_id=row["tool_request_id"],
            decision=row["decision"],
            observation=row["observation"],
            created_at=_parse_datetime(row["created_at"]),
        )

    def _row_to_review(self, row: sqlite3.Row) -> ReviewRecord:
        return ReviewRecord(
            review_id=row["review_id"],
            run_id=row["run_id"],
            score=row["score"],
            errors=_load_json(row["errors_json"]),
            improvements=_load_json(row["improvements_json"]),
            missing_parts=_load_json(row["missing_parts_json"]),
            corrected_response=row["corrected_response"],
            chosen=row["chosen"],
            rejected=row["rejected"],
            created_at=_parse_datetime(row["created_at"]),
        )

    def _row_to_export(self, row: sqlite3.Row) -> ExportRecord:
        return ExportRecord(
            export_id=row["export_id"],
            run_id=row["run_id"],
            format=row["format"],
            path=row["path"],
            record_count=row["record_count"],
            filters=_load_json(row["filters_json"]),
            created_at=_parse_datetime(row["created_at"]),
        )
