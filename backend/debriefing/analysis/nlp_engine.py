"""Optional communication analysis. Missing providers return an explicit status."""
import os

class NLPEngine:
    def __init__(self, llm=None):
        self.llm = llm

    def format_segments_for_nlp(self, segments):
        lines = []
        for seg in segments or []:
            if not isinstance(seg, dict): seg = vars(seg)
            seconds = int(seg.get("timestamp_ms", seg.get("start_ms", 0))) // 1000
            role = seg.get("actor_role", seg.get("role", "unknown"))
            role = getattr(role, "value", role)
            speaker = seg.get("speaker_label", seg.get("speaker", "unknown"))
            lines.append(f"[{seconds//60:02d}:{seconds%60:02d}] {speaker} ({role}): {seg.get('text', '')}")
        return "\n".join(lines)

    def process(self, session_id="session", segments=None, **kwargs):
        segments = segments if segments is not None else kwargs.get("leader_segments", []) + kwargs.get("ceiling_segments", [])
        text = self.format_segments_for_nlp(segments)
        result = {"nlp_analysis": {}, "raw_transcript": text, "status": "disabled"}
        if not text: return {**result, "status": "insufficient_data"}
        if self.llm is None and os.getenv("ENABLE_OLLAMA_DEBRIEF", "false").lower() != "true": return result
        try:
            from .communication_agents.agent import SupervisingAgent
            if self.llm is None:
                from langchain_ollama import ChatOllama
                self.llm = ChatOllama(model=os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b"),
                    base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434"), temperature=0.2,
                    client_kwargs={"timeout": 30.0})
            state = SupervisingAgent(llm_instance=self.llm).run(session_id=session_id, input_data=text)
            return {**result, "nlp_analysis": state.get("combined_result", {}), "status": "completed"}
        except Exception as exc:
            return {**result, "status": "unavailable", "error": type(exc).__name__}
