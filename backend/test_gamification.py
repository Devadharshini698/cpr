"""
test_gamification.py — Comprehensive Unit Tests for Gamification System
========================================================================
Validates XP formulas, level thresholds, badge conditions, idempotency,
and leaderboard ranking according to specification.
"""

import sys
import unittest
from pathlib import Path

# Add backend and debriefing directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent
DEBRIEF_DIR = BACKEND_DIR / "debriefing"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(DEBRIEF_DIR) not in sys.path:
    sys.path.insert(0, str(DEBRIEF_DIR))

from debriefing.scenarios.gamification import (
    calculate_xp,
    get_level_info,
    GamificationService,
    BADGE_CATALOGUE
)


class TestGamification(unittest.TestCase):

    def test_xp_calculation_beginner(self):
        res_100 = calculate_xp(base_xp=200, accuracy=100.0, deviation_count=0, level="beginner")
        self.assertEqual(res_100["xp_earned"], 260)
        self.assertEqual(res_100["base_xp"], 200)
        self.assertEqual(res_100["difficulty_multiplier"], 1.0)

        res_60_devs = calculate_xp(base_xp=200, accuracy=60.0, deviation_count=3, level="beginner")
        self.assertEqual(res_60_devs["xp_earned"], 206)
        self.assertEqual(res_60_devs["deviation_penalty"], 30)

    def test_xp_calculation_advanced(self):
        res = calculate_xp(base_xp=700, accuracy=90.0, deviation_count=2, level="advanced")
        self.assertEqual(res["xp_earned"], 1738)
        self.assertEqual(res["difficulty_multiplier"], 2.0)

    def test_xp_never_negative(self):
        res = calculate_xp(base_xp=200, accuracy=0.0, deviation_count=50, level="beginner")
        self.assertGreaterEqual(res["xp_earned"], 0)

    def test_level_thresholds(self):
        self.assertEqual(get_level_info(0)["level"], "Novice")
        self.assertEqual(get_level_info(499)["level"], "Novice")
        self.assertEqual(get_level_info(500)["level"], "Practitioner")
        self.assertEqual(get_level_info(1499)["level"], "Practitioner")
        self.assertEqual(get_level_info(1500)["level"], "Expert")
        self.assertEqual(get_level_info(2999)["level"], "Expert")
        self.assertEqual(get_level_info(3000)["level"], "Master Resuscitationist")
        self.assertEqual(get_level_info(4500)["level"], "Master Resuscitationist")
        self.assertTrue(get_level_info(3000)["is_max_level"])

    def test_badge_evaluation_rules(self):
        service = GamificationService()

        # 1. First scenario
        b1 = service.evaluate_badges(
            team_name="Team Alpha", existing_badges=[], recent_history=[], team_leader_count=0,
            session_data={"score": 80, "prediction_accuracy": 80, "level": "beginner", "total_deviations": 1}
        )
        self.assertIn("first_scenario", b1)

        # 2. Perfect score
        b2 = service.evaluate_badges(
            team_name="Team Alpha", existing_badges=["first_scenario"], recent_history=[], team_leader_count=0,
            session_data={"score": 96, "prediction_accuracy": 96, "level": "beginner", "total_deviations": 0}
        )
        self.assertIn("perfect_score", b2)
        self.assertIn("zero_deviations", b2)

        # 3. Advanced completer
        b3 = service.evaluate_badges(
            team_name="Team Alpha", existing_badges=[], recent_history=[], team_leader_count=0,
            session_data={"score": 85, "prediction_accuracy": 85, "level": "advanced", "total_deviations": 0}
        )
        self.assertIn("advanced_completer", b3)

        # 4. Debrief champion
        b4 = service.evaluate_badges(
            team_name="Team Alpha", existing_badges=[], recent_history=[], team_leader_count=0,
            session_data={"score": 82, "prediction_accuracy": 82, "level": "beginner", "ai_debriefed": True}
        )
        self.assertIn("debrief_champion", b4)

        b4_no_ai = service.evaluate_badges(
            team_name="Team Alpha", existing_badges=[], recent_history=[], team_leader_count=0,
            session_data={"score": 90, "prediction_accuracy": 90, "level": "beginner", "ai_debriefed": False}
        )
        self.assertNotIn("debrief_champion", b4_no_ai)

        # 5. Consistent performer (3 consecutive A/B grades)
        recent_history = [{"grade": "A"}, {"grade": "B"}]
        b5 = service.evaluate_badges(
            team_name="Team Alpha", existing_badges=[], recent_history=recent_history, team_leader_count=0,
            session_data={"score": 85, "grade": "A", "prediction_accuracy": 85, "level": "beginner"}
        )
        self.assertIn("consistent_performer", b5)

        recent_history_broken = [{"grade": "C"}, {"grade": "A"}]
        b5_broken = service.evaluate_badges(
            team_name="Team Alpha", existing_badges=[], recent_history=recent_history_broken, team_leader_count=0,
            session_data={"score": 85, "grade": "A", "prediction_accuracy": 85, "level": "beginner"}
        )
        self.assertNotIn("consistent_performer", b5_broken)

        # 6. Team Leader (5 qualifying scenarios)
        b6 = service.evaluate_badges(
            team_name="Team Alpha", existing_badges=[], recent_history=[], team_leader_count=4,
            session_data={"score": 85, "grade": "B", "is_team_leader": True}
        )
        self.assertIn("team_leader", b6)

    def test_idempotency(self):
        service = GamificationService()
        session_code = "TEST-IDEMPOTENT-SESSION-101"
        team_name = "Team Idempotent"

        # First call
        rec1 = service.record_session_sync(
            session_code=session_code,
            team_name=team_name,
            scenario_id="SCN-TEST-1",
            level="intermediate",
            score=92.0,
            grade="A",
            base_xp=400,
            total_deviations=0
        )
        self.assertGreater(rec1["xp_earned"], 0)
        first_total_xp = rec1["total_xp"]

        # Second call for SAME session_code
        rec2 = service.record_session_sync(
            session_code=session_code,
            team_name=team_name,
            scenario_id="SCN-TEST-1",
            level="intermediate",
            score=92.0,
            grade="A",
            base_xp=400,
            total_deviations=0
        )

        # Must be identical and not re-award XP
        self.assertEqual(rec2["total_xp"], first_total_xp)
        self.assertEqual(rec2["xp_earned"], rec1["xp_earned"])

    def test_leaderboard_sorting(self):
        import uuid
        uid = uuid.uuid4().hex[:6]
        service = GamificationService()
        rx = service.record_session_sync(session_code=f"SES-X-{uid}", team_name=f"Team X {uid}", score=95.0, level="advanced", base_xp=700)
        ry = service.record_session_sync(session_code=f"SES-Y-{uid}", team_name=f"Team Y {uid}", score=70.0, level="beginner", base_xp=200)
        lb = service.get_leaderboard_sync(limit=10)
        self.assertGreaterEqual(len(lb), 2)
        for i in range(len(lb) - 1):
            self.assertGreaterEqual(lb[i]["total_xp"], lb[i+1]["total_xp"])


if __name__ == "__main__":
    unittest.main()
