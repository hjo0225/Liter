"""
P11 세션 데이터 CSV 출력 스크립트.

사용법:
    python scripts/export_session.py <session_id>

출력 파일:
    {session_id}_messages.csv
    {session_id}_director_calls.csv
    {session_id}_llm_calls.csv
    {session_id}_session_events.csv

실행 전 환경변수 설정 필요:
    SUPABASE_URL, SUPABASE_SERVICE_KEY
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (backend/ 에서 실행 시)
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.supabase import supabase  # noqa: E402


def _flatten_jsonb(value: object) -> str:
    """JSONB 컬럼 → JSON 문자열."""
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def export_table(session_id: str, table: str, *, order_col: str = "created_at") -> int:
    """테이블에서 session_id 행을 가져와 CSV로 저장. 저장된 행 수 반환."""
    res = (
        supabase.table(table)
        .select("*")
        .eq("session_id", session_id)
        .order(order_col)
        .execute()
    )
    rows: list[dict] = res.data or []
    if not rows:
        print(f"  {table}: 데이터 없음")
        return 0

    out_path = Path(f"{session_id}_{table}.csv")
    headers = list(rows[0].keys())

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            # JSONB 컬럼은 JSON 문자열로 직렬화
            writer.writerow({k: _flatten_jsonb(v) if isinstance(v, (dict, list)) else v for k, v in row.items()})

    print(f"  {table}: {len(rows)}행 → {out_path}")
    return len(rows)


def main() -> None:
    if len(sys.argv) < 2:
        print("사용법: python scripts/export_session.py <session_id>")
        sys.exit(1)

    session_id = sys.argv[1].strip()
    print(f"세션 ID: {session_id}")
    print("내보내는 중...")

    tables = [
        ("messages", "created_at"),
        ("director_calls", "created_at"),
        ("llm_calls", "created_at"),
        ("session_events", "created_at"),
    ]

    total = 0
    for table, order_col in tables:
        try:
            total += export_table(session_id, table, order_col=order_col)
        except Exception as e:
            print(f"  {table}: 오류 — {e}")

    print(f"\n완료: 총 {total}행 내보냄")


if __name__ == "__main__":
    main()
