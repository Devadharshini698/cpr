"""IMSR-facing facade. Persistence and scheduling belong to the FastAPI host."""
from debriefing.engine import DebriefEngine

class DebriefService:
    def __init__(self, **options):
        self.engine = DebriefEngine(**options)

    def generate_debrief(self, session_data):
        return self.engine.generate(session_data)

def generate_debrief(session_data):
    return DebriefService().generate_debrief(session_data)
