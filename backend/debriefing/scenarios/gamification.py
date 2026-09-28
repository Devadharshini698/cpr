"""
scenarios/gamification.py — Canonical Gamification Service
============================================================
Authoritative gamification engine managing XP calculations, levels, badges,
session gamification records, and team leaderboards backed by MySQL.

XP Level Thresholds
--------------------
  0–499     Novice
  500–1499  Practitioner
  1500–2999 Expert
  3000+     Master Resuscitationist

Badges (8 Canonical Badges)
----------------------------
  first_scenario        First Responder         Completed first scenario
  perfect_score         Perfect Performance     Prediction/performance accuracy ≥ 95%
  advanced_completer    Advanced Operator       Completed an Advanced-level scenario
  rapid_responder       Rapid Responder         All critical steps performed within time windows
  debrief_champion      Debrief Champion        Scored ≥ 80% in an AI-debriefed session
  consistent_performer  Consistent Performer    3 consecutive sessions with grade ≥ B
  team_leader           Team Leader             5 scenarios completed as designated team leader
  zero_deviations       Zero Deviations         Session completed with no protocol deviations
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_XP_LEVELS = [
    (0,    "Novice"),
    (500,  "Practitioner"),
    (1500, "Expert"),
    (3000, "Master Resuscitationist"),
]

BADGE_CATALOGUE = {
    "first_scenario": {
        "id": "first_scenario",
        "label": "First Responder",
        "icon": "🏁",
        "description": "Completed your first scenario.",
        "condition": "Complete your first clinical simulation session."
    },
    "perfect_score": {
        "id": "perfect_score",
        "label": "Perfect Performance",
        "icon": "⭐",
        "description": "Prediction accuracy ≥ 95%.",
        "condition": "Achieve a final accuracy/performance score of 95% or higher."
    },
    "advanced_completer": {
        "id": "advanced_completer",
        "label": "Advanced Operator",
        "icon": "🔥",
        "description": "Completed an Advanced-level scenario.",
        "condition": "Successfully complete a simulation scenario rated at Advanced difficulty."
    },
    "rapid_responder": {
        "id": "rapid_responder",
        "label": "Rapid Responder",
        "icon": "⚡",
        "description": "All critical steps performed within required time windows.",
        "condition": "Execute all critical checklist actions on time with zero delays."
    },
    "debrief_champion": {
        "id": "debrief_champion",
        "label": "Debrief Champion",
        "icon": "🎤",
        "description": "Scored ≥ 80% in an AI-debriefed session.",
        "condition": "Earn an overall score of 80% or higher with an AI-generated debrief report."
    },
    "consistent_performer": {
        "id": "consistent_performer",
        "label": "Consistent Performer",
        "icon": "📈",
        "description": "3 consecutive sessions with grade ≥ B.",
        "condition": "Maintain high performance across 3 consecutive sessions with grade A or B."
    },
    "team_leader": {
        "id": "team_leader",
        "label": "Team Leader",
        "icon": "👑",
        "description": "5 scenarios completed as designated physician/team leader.",
        "condition": "Complete 5 scenarios in the designated Team Leader role."
    },
    "zero_deviations": {
        "id": "zero_deviations",
        "label": "Zero Deviations",
        "icon": "✅",
        "description": "Completed a session with no protocol deviations.",
        "condition": "Finish a scenario with zero ACLS/PALS guideline deviations."
    },
}

_FILE_BACKUP_PATH = Path("data/leaderboard.json")


def calculate_xp(
    base_xp: Optional[int],
    accuracy: float,
    deviation_count: int,
    level: Optional[str]
) -> Dict[str, Any]:
    """
    Canonical XP Calculation based on OutcomePredictor logic:
      - Scenario difficulty multiplier (beginner: 1.0, intermediate: 1.5, advanced: 2.0)
      - Deviation penalty: min(deviation_count * 10, base_xp * 0.5)
      - Performance bonus: base_xp * (accuracy / 100) * 0.3
      - Total XP earned: max(0, int((base_xp - deviation_penalty + performance_bonus) * multiplier))
    """
    level_str = (level or "beginner").lower().strip()
    multiplier = {"beginner": 1.0, "intermediate": 1.5, "advanced": 2.0}.get(level_str, 1.0)

    if not base_xp or base_xp <= 0:
        base_xp = {"beginner": 200, "intermediate": 400, "advanced": 700}.get(level_str, 200)

    accuracy_clamped = max(0.0, min(100.0, float(accuracy)))
    deviation_penalty = int(min(deviation_count * 10, base_xp * 0.5))
    performance_bonus = int(base_xp * (accuracy_clamped / 100.0) * 0.3)

    raw_xp = int((base_xp - deviation_penalty + performance_bonus) * multiplier)
    xp_earned = max(0, raw_xp)

    return {
        "base_xp": base_xp,
        "difficulty_multiplier": multiplier,
        "performance_score": round(accuracy_clamped, 1),
        "deviation_penalty": deviation_penalty,
        "performance_bonus": performance_bonus,
        "xp_earned": xp_earned,
    }


def get_level_info(total_xp: int) -> Dict[str, Any]:
    """
    Calculate level label and progress stats towards the next level threshold.
    """
    total_xp = max(0, int(total_xp))
    if total_xp >= 3000:
        return {
            "level": "Master Resuscitationist",
            "current_level_xp": 3000,
            "next_level_xp": 3000,
            "xp_into_level": total_xp - 3000,
            "xp_remaining": 0,
            "progress_percent": 100.0,
            "is_max_level": True
        }
    elif total_xp >= 1500:
        level = "Expert"
        curr_thresh = 1500
        next_thresh = 3000
    elif total_xp >= 500:
        level = "Practitioner"
        curr_thresh = 500
        next_thresh = 1500
    else:
        level = "Novice"
        curr_thresh = 0
        next_thresh = 500

    span = next_thresh - curr_thresh
    xp_into_level = total_xp - curr_thresh
    xp_remaining = next_thresh - total_xp
    progress_percent = round((xp_into_level / span) * 100.0, 2)

    return {
        "level": level,
        "current_level_xp": curr_thresh,
        "next_level_xp": next_thresh,
        "xp_into_level": xp_into_level,
        "xp_remaining": xp_remaining,
        "progress_percent": progress_percent,
        "is_max_level": False
    }


class GamificationService:
    """
    Canonical Gamification Service.
    Thread-safe and supports MySQL persistence via aiomysql/pymysql or fallback storage.
    """

    _lock = threading.Lock()

    def __init__(self):
        _FILE_BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)

    # ── Badge Evaluation ──────────────────────────────────────────────────────

    def evaluate_badges(
        self,
        team_name: str,
        existing_badges: List[str],
        recent_history: List[Dict[str, Any]],
        team_leader_count: int,
        session_data: Dict[str, Any]
    ) -> List[str]:
        """
        Evaluate which new badges are earned for a completed session.
        """
        earned: List[str] = []
        badges_set = set(existing_badges)

        score = float(session_data.get("score", 0.0))
        accuracy = float(session_data.get("prediction_accuracy", score))
        level = str(session_data.get("level", "beginner")).lower().strip()
        total_deviations = int(session_data.get("total_deviations", 0))
        ai_debriefed = bool(session_data.get("ai_debriefed", False))
        critical_misses = session_data.get("critical_misses") or []
        checklist_items = session_data.get("checklist_items") or []
        is_team_leader = bool(session_data.get("is_team_leader", False))

        # 1. First Responder
        if "first_scenario" not in badges_set:
            earned.append("first_scenario")

        # 2. Perfect Performance (accuracy >= 95%)
        if accuracy >= 95.0 and "perfect_score" not in badges_set:
            earned.append("perfect_score")

        # 3. Advanced Operator
        if level == "advanced" and "advanced_completer" not in badges_set:
            earned.append("advanced_completer")

        # 4. Rapid Responder
        if "rapid_responder" not in badges_set:
            # Check checklist timing data if present
            timing_valid = True
            if checklist_items:
                critical_items = [c for c in checklist_items if c.get("critical")]
                if critical_items:
                    for item in critical_items:
                        st = str(item.get("status", "")).lower()
                        delay = int(item.get("delay_seconds", 0))
                        if st != "completed" or delay > 0:
                            timing_valid = False
                            break
                else:
                    if len(critical_misses) > 0:
                        timing_valid = False
            else:
                if len(critical_misses) > 0:
                    timing_valid = False

            if timing_valid:
                earned.append("rapid_responder")

        # 5. Debrief Champion (scored >= 80% in an AI-debriefed session)
        if ai_debriefed and score >= 80.0 and "debrief_champion" not in badges_set:
            earned.append("debrief_champion")

        # 6. Zero Deviations
        if total_deviations == 0 and "zero_deviations" not in badges_set:
            earned.append("zero_deviations")

        # 7. Consistent Performer (3 consecutive sessions with grade A or B)
        if "consistent_performer" not in badges_set:
            # Combine past 2 session grades with current session grade
            all_recent_grades = [r.get("grade", "C") for r in recent_history[:2]]
            current_grade = session_data.get("grade", "C")
            three_grades = [current_grade] + all_recent_grades
            if len(three_grades) >= 3 and all(g in ("A", "B") for g in three_grades[:3]):
                earned.append("consistent_performer")

        # 8. Team Leader (5 qualifying scenarios as designated team leader)
        if "team_leader" not in badges_set:
            new_leader_count = team_leader_count + (1 if is_team_leader else 0)
            if new_leader_count >= 5:
                earned.append("team_leader")

        return earned

    # ── Session Recording (Idempotent) ────────────────────────────────────────

    def record_session_sync(
        self,
        session_code: str,
        team_name: str,
        scenario_id: str = "",
        scenario_name: str = "Clinical Simulation",
        level: str = "beginner",
        score: float = 80.0,
        prediction_accuracy: Optional[float] = None,
        grade: str = "B",
        base_xp: Optional[int] = None,
        total_deviations: int = 0,
        critical_misses: Optional[List[str]] = None,
        ai_debriefed: bool = False,
        checklist_items: Optional[List[dict]] = None,
        team_leader: Optional[str] = None,
        is_team_leader: bool = False
    ) -> Dict[str, Any]:
        """
        Synchronously record a completed scenario session in MySQL (with fallback).
        Ensures strict idempotency using session_code.
        """
        session_code = str(session_code).strip()
        team_name = str(team_name or "Resus Team").strip()
        accuracy = float(prediction_accuracy if prediction_accuracy is not None else score)
        score = float(score)

        if not team_leader and is_team_leader:
            team_leader = team_name

        with self._lock:
            # 1. Try fetching existing record for idempotency
            existing = self._get_session_record_sync(session_code)
            if existing:
                logger.info(f"[Gamification] Returning existing record for session_code: {session_code}")
                return existing

            # 2. Get current team summary and session history
            team_summary = self._get_team_summary_sync(team_name)
            recent_history = self._get_recent_history_sync(team_name, limit=5)
            team_leader_count = self._get_team_leader_count_sync(team_name)

            existing_badges = team_summary.get("badges", [])

            # 3. Calculate XP & breakdown
            breakdown = calculate_xp(base_xp, accuracy, total_deviations, level)
            xp_earned = breakdown["xp_earned"]
            old_total_xp = team_summary.get("total_xp", 0)
            new_total_xp = old_total_xp + xp_earned

            old_level_info = get_level_info(old_total_xp)
            new_level_info = get_level_info(new_total_xp)
            levelled_up = new_level_info["level"] != old_level_info["level"]

            # 4. Evaluate Badges
            session_eval_data = {
                "score": score,
                "prediction_accuracy": accuracy,
                "level": level,
                "total_deviations": total_deviations,
                "ai_debriefed": ai_debriefed,
                "critical_misses": critical_misses or [],
                "checklist_items": checklist_items or [],
                "grade": grade,
                "is_team_leader": bool(is_team_leader or team_leader),
            }
            newly_earned_badges = self.evaluate_badges(
                team_name=team_name,
                existing_badges=existing_badges,
                recent_history=recent_history,
                team_leader_count=team_leader_count,
                session_data=session_eval_data
            )

            all_badges = list(set(existing_badges + newly_earned_badges))
            best_score = max(team_summary.get("best_score", 0.0), score)
            session_count = team_summary.get("session_count", 0) + 1
            completed_at = datetime.now(timezone.utc).isoformat()

            gamification_result = {
                "session_code": session_code,
                "team_name": team_name,
                "scenario_id": scenario_id,
                "scenario_name": scenario_name,
                "difficulty": level,
                "performance_score": round(score, 1),
                "prediction_accuracy": round(accuracy, 1),
                "grade": grade,
                "base_xp": breakdown["base_xp"],
                "xp_earned": xp_earned,
                "total_xp": new_total_xp,
                "level": new_level_info["level"],
                "levelled_up": levelled_up,
                "level_info": new_level_info,
                "deviation_count": total_deviations,
                "critical_misses": critical_misses or [],
                "ai_debriefed": ai_debriefed,
                "badges_earned": newly_earned_badges,
                "badge_details": [BADGE_CATALOGUE[b] for b in newly_earned_badges if b in BADGE_CATALOGUE],
                "all_badges": all_badges,
                "team_leader": team_leader or "",
                "xp_breakdown": breakdown,
                "completed_at": completed_at,
            }

            # 5. Persist to MySQL or Fallback
            self._save_session_and_update_leaderboard_sync(gamification_result)
            return gamification_result

    # ── Database Operations ───────────────────────────────────────────────────

    def _get_session_record_sync(self, session_code: str) -> Optional[Dict[str, Any]]:
        """Fetch session gamification record by session_code from MySQL or fallback file."""
        try:
            import pymysql
            from database import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, DB_NAME, ssl_ctx
            conn = pymysql.connect(
                host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER, password=MYSQL_PASSWORD,
                database=DB_NAME, ssl=ssl_ctx, autocommit=True, cursorclass=pymysql.cursors.DictCursor
            )
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT * FROM gamification_session_records WHERE session_code = %s",
                        (session_code,)
                    )
                    row = cur.fetchone()
                    if row:
                        total_xp = row["total_xp_after"]
                        level_info = get_level_info(total_xp)
                        critical_misses = json.loads(row["critical_misses"]) if row.get("critical_misses") else []
                        badges_earned = json.loads(row["badges_earned"]) if row.get("badges_earned") else []
                        
                        # Get all badges for team
                        cur.execute("SELECT badge_id FROM gamification_badges WHERE team_name = %s", (row["team_name"],))
                        b_rows = cur.fetchall()
                        all_badges = [b["badge_id"] for b in b_rows]

                        breakdown = calculate_xp(row.get("base_xp", 200), row["prediction_accuracy"], row["deviation_count"], row["difficulty"])
                        breakdown["xp_earned"] = row["xp_earned"]

                        return {
                            "session_code": row["session_code"],
                            "team_name": row["team_name"],
                            "scenario_id": row.get("scenario_id", ""),
                            "scenario_name": row.get("scenario_name", ""),
                            "difficulty": row.get("difficulty", "beginner"),
                            "performance_score": float(row["performance_score"]),
                            "prediction_accuracy": float(row["prediction_accuracy"]),
                            "grade": row["grade"],
                            "base_xp": row.get("base_xp", 200),
                            "xp_earned": row["xp_earned"],
                            "total_xp": total_xp,
                            "level": level_info["level"],
                            "levelled_up": False,
                            "level_info": level_info,
                            "deviation_count": row["deviation_count"],
                            "critical_misses": critical_misses,
                            "ai_debriefed": bool(row["ai_debriefed"]),
                            "badges_earned": badges_earned,
                            "badge_details": [BADGE_CATALOGUE[b] for b in badges_earned if b in BADGE_CATALOGUE],
                            "all_badges": all_badges,
                            "team_leader": row.get("team_leader", ""),
                            "xp_breakdown": breakdown,
                            "completed_at": row["completed_at"].isoformat() if hasattr(row["completed_at"], "isoformat") else str(row["completed_at"]),
                        }
            finally:
                conn.close()
        except Exception as e:
            logger.debug(f"[Gamification DB Warning] mysql read fallback: {e}")

        # Fallback file check
        file_data = self._load_file_backup()
        for entry in file_data.get("entries", []):
            if entry.get("session_code") == session_code or entry.get("scenario_id") == session_code:
                return entry
        return None

    def _get_team_summary_sync(self, team_name: str) -> Dict[str, Any]:
        """Fetch summary for a team from MySQL or fallback file."""
        try:
            import pymysql
            from database import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, DB_NAME, ssl_ctx
            conn = pymysql.connect(
                host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER, password=MYSQL_PASSWORD,
                database=DB_NAME, ssl=ssl_ctx, autocommit=True, cursorclass=pymysql.cursors.DictCursor
            )
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT total_xp, level, session_count, best_score, badges FROM gamification_leaderboard WHERE team_name = %s",
                        (team_name,)
                    )
                    row = cur.fetchone()
                    if row:
                        badges = json.loads(row["badges"]) if row.get("badges") else []
                        return {
                            "team_name": team_name,
                            "total_xp": row["total_xp"],
                            "level": row["level"],
                            "session_count": row["session_count"],
                            "best_score": float(row["best_score"]),
                            "badges": badges
                        }
            finally:
                conn.close()
        except Exception as e:
            logger.debug(f"[Gamification DB Warning] summary query: {e}")

        # Fallback file summary
        fb = self._load_file_backup()
        return fb.get("team_summaries", {}).get(team_name, {
            "team_name": team_name, "total_xp": 0, "level": "Novice",
            "session_count": 0, "best_score": 0.0, "badges": []
        })

    def _get_recent_history_sync(self, team_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Fetch recent session records for team."""
        try:
            import pymysql
            from database import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, DB_NAME, ssl_ctx
            conn = pymysql.connect(
                host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER, password=MYSQL_PASSWORD,
                database=DB_NAME, ssl=ssl_ctx, autocommit=True, cursorclass=pymysql.cursors.DictCursor
            )
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT grade, performance_score, completed_at FROM gamification_session_records WHERE team_name = %s ORDER BY id DESC LIMIT %s",
                        (team_name, limit)
                    )
                    return cur.fetchall() or []
            finally:
                conn.close()
        except Exception:
            pass
        return []

    def _get_team_leader_count_sync(self, team_name: str) -> int:
        """Count sessions where team was designated leader."""
        try:
            import pymysql
            from database import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, DB_NAME, ssl_ctx
            conn = pymysql.connect(
                host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER, password=MYSQL_PASSWORD,
                database=DB_NAME, ssl=ssl_ctx, autocommit=True, cursorclass=pymysql.cursors.DictCursor
            )
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT COUNT(*) as c FROM gamification_session_records WHERE team_name = %s AND team_leader IS NOT NULL AND team_leader != ''",
                        (team_name,)
                    )
                    r = cur.fetchone()
                    return r["c"] if r else 0
            finally:
                conn.close()
        except Exception:
            return 0

    def _save_session_and_update_leaderboard_sync(self, record: Dict[str, Any]) -> None:
        """Persist session record, badges, and team summary in MySQL + fallback JSON."""
        team_name = record["team_name"]
        session_code = record["session_code"]
        now_dt = datetime.utcnow()

        try:
            import pymysql
            from database import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, DB_NAME, ssl_ctx
            conn = pymysql.connect(
                host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER, password=MYSQL_PASSWORD,
                database=DB_NAME, ssl=ssl_ctx, autocommit=True, cursorclass=pymysql.cursors.DictCursor
            )
            try:
                with conn.cursor() as cur:
                    # 1. Insert session record
                    cur.execute("""
                        INSERT INTO gamification_session_records
                        (session_code, team_name, scenario_id, scenario_name, difficulty, performance_score,
                         prediction_accuracy, grade, base_xp, xp_earned, total_xp_after, deviation_count,
                         critical_misses, ai_debriefed, badges_earned, team_leader, completed_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        performance_score = VALUES(performance_score),
                        prediction_accuracy = VALUES(prediction_accuracy),
                        grade = VALUES(grade),
                        xp_earned = VALUES(xp_earned),
                        total_xp_after = VALUES(total_xp_after)
                    """, (
                        session_code, team_name, record.get("scenario_id", ""), record.get("scenario_name", ""),
                        record.get("difficulty", "beginner"), record["performance_score"], record["prediction_accuracy"],
                        record["grade"], record["base_xp"], record["xp_earned"], record["total_xp"],
                        record["deviation_count"], json.dumps(record["critical_misses"]), record["ai_debriefed"],
                        json.dumps(record["badges_earned"]), record.get("team_leader", ""), now_dt
                    ))

                    # 2. Insert new badges safely
                    for badge_id in record["badges_earned"]:
                        try:
                            cur.execute("""
                                INSERT IGNORE INTO gamification_badges (team_name, badge_id, session_code, awarded_at, metadata)
                                VALUES (%s, %s, %s, %s, %s)
                            """, (team_name, badge_id, session_code, now_dt, json.dumps({"session_code": session_code})))
                        except Exception as b_err:
                            logger.debug(f"[Badge Save Warning] {badge_id}: {b_err}")

                    # 3. Update or Insert team leaderboard row
                    badges_json = json.dumps(record["all_badges"])
                    cur.execute("""
                        INSERT INTO gamification_leaderboard
                        (team_name, total_xp, level, session_count, best_score, badges, last_session_at)
                        VALUES (%s, %s, %s, 1, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        total_xp = %s,
                        level = %s,
                        session_count = session_count + 1,
                        best_score = GREATEST(COALESCE(best_score, 0), %s),
                        badges = %s,
                        last_session_at = %s
                    """, (
                        team_name, record["total_xp"], record["level"], record["performance_score"], badges_json, now_dt,
                        record["total_xp"], record["level"], record["performance_score"], badges_json, now_dt
                    ))

            finally:
                conn.close()
        except Exception as db_err:
            print(f"[Gamification DB Save Error] {db_err}")
            logger.warning(f"[Gamification DB Save Warning] {db_err}")

        # Update JSON backup
        try:
            fb = self._load_file_backup()
            fb.setdefault("entries", []).append(record)
            fb.setdefault("team_summaries", {})[team_name] = {
                "total_xp": record["total_xp"],
                "level_label": record["level"],
                "all_badges": record["all_badges"],
                "session_count": fb["team_summaries"].get(team_name, {}).get("session_count", 0) + 1,
                "last_session": now_dt.isoformat(),
                "best_score": max(fb["team_summaries"].get(team_name, {}).get("best_score", 0), record["performance_score"])
            }
            self._save_file_backup(fb)
        except Exception:
            pass

    # ── Leaderboard & Catalogue Public APIs ───────────────────────────────────

    def get_leaderboard_sync(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch top N teams sorted by total_xp DESC, best_score DESC."""
        try:
            import pymysql
            from database import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, DB_NAME, ssl_ctx
            conn = pymysql.connect(
                host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER, password=MYSQL_PASSWORD,
                database=DB_NAME, ssl=ssl_ctx, autocommit=True, cursorclass=pymysql.cursors.DictCursor
            )
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT team_name, total_xp, level, session_count, best_score, badges, last_session_at
                        FROM gamification_leaderboard
                        ORDER BY total_xp DESC, best_score DESC, session_count DESC
                        LIMIT %s
                    """, (limit,))
                    rows = cur.fetchall()
                    result = []
                    for idx, row in enumerate(rows, start=1):
                        badges = json.loads(row["badges"]) if row.get("badges") else []
                        last_at = row["last_session_at"].isoformat() if row.get("last_session_at") and hasattr(row["last_session_at"], "isoformat") else str(row.get("last_session_at") or "")
                        result.append({
                            "rank": idx,
                            "team_name": row["team_name"],
                            "total_xp": row["total_xp"],
                            "level": row["level"],
                            "session_count": row["session_count"],
                            "best_score": float(row["best_score"]),
                            "badges": badges,
                            "badge_count": len(badges),
                            "last_session_at": last_at,
                        })
                    return result
            finally:
                conn.close()
        except Exception as e:
            logger.debug(f"[Leaderboard DB Warning] {e}")

        # Fallback file query
        fb = self._load_file_backup()
        summaries = fb.get("team_summaries", {})
        sorted_teams = sorted(
            [{"team_name": k, **v} for k, v in summaries.items()],
            key=lambda x: (x.get("total_xp", 0), x.get("best_score", 0)),
            reverse=True
        )
        res = []
        for idx, t in enumerate(sorted_teams[:limit], start=1):
            res.append({
                "rank": idx,
                "team_name": t["team_name"],
                "total_xp": t.get("total_xp", 0),
                "level": t.get("level_label", t.get("level", "Novice")),
                "session_count": t.get("session_count", 0),
                "best_score": t.get("best_score", 0.0),
                "badges": t.get("all_badges", t.get("badges", [])),
                "badge_count": len(t.get("all_badges", t.get("badges", []))),
                "last_session_at": t.get("last_session", ""),
            })
        return res

    def get_badge_catalogue(self, team_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return full badge catalogue with earned status for team_name if provided."""
        earned_badges_map = {}
        if team_name:
            try:
                import pymysql
                from database import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, DB_NAME, ssl_ctx
                conn = pymysql.connect(
                    host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER, password=MYSQL_PASSWORD,
                    database=DB_NAME, ssl=ssl_ctx, autocommit=True, cursorclass=pymysql.cursors.DictCursor
                )
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT badge_id, awarded_at FROM gamification_badges WHERE team_name = %s", (team_name,))
                        for row in cur.fetchall():
                            awarded_str = row["awarded_at"].isoformat() if hasattr(row["awarded_at"], "isoformat") else str(row["awarded_at"])
                            earned_badges_map[row["badge_id"]] = awarded_str
                finally:
                    conn.close()
            except Exception:
                pass

        result = []
        for badge_id, defn in BADGE_CATALOGUE.items():
            is_earned = badge_id in earned_badges_map if team_name else False
            result.append({
                "id": defn["id"],
                "label": defn["label"],
                "icon": defn["icon"],
                "description": defn["description"],
                "condition": defn["condition"],
                "earned": is_earned,
                "earned_at": earned_badges_map.get(badge_id) if is_earned else None,
            })
        return result

    def get_team_profile_sync(self, team_name: str) -> Dict[str, Any]:
        """Return comprehensive team gamification profile."""
        team_name = str(team_name or "Resus Team").strip()
        summary = self._get_team_summary_sync(team_name)
        total_xp = summary.get("total_xp", 0)
        level_info = get_level_info(total_xp)
        badge_list = self.get_badge_catalogue(team_name)
        earned_badges = [b["id"] for b in badge_list if b.get("earned")]

        # Determine leaderboard rank
        leaderboard = self.get_leaderboard_sync(limit=100)
        rank = None
        for item in leaderboard:
            if item["team_name"].lower() == team_name.lower():
                rank = item["rank"]
                break

        return {
            "team_name": team_name,
            "total_xp": total_xp,
            "level": level_info["level"],
            "current_level_xp": level_info["current_level_xp"],
            "next_level_xp": level_info["next_level_xp"],
            "xp_into_level": level_info["xp_into_level"],
            "xp_remaining": level_info["xp_remaining"],
            "progress_percent": level_info["progress_percent"],
            "session_count": summary.get("session_count", 0),
            "best_score": round(summary.get("best_score", 0.0), 1),
            "badges": earned_badges,
            "badge_count": len(earned_badges),
            "badge_catalogue": badge_list,
            "leaderboard_rank": rank or len(leaderboard) + 1,
        }

    # ── Legacy Helpers ────────────────────────────────────────────────────────

    def _load_file_backup(self) -> dict:
        if _FILE_BACKUP_PATH.exists():
            try:
                with open(_FILE_BACKUP_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"entries": [], "team_summaries": {}}

    def _save_file_backup(self, data: dict) -> None:
        try:
            with open(_FILE_BACKUP_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass


# Singleton Gamification Engine / Service Instance
GamificationEngine = GamificationService
canonical_gamification_service = GamificationService()
