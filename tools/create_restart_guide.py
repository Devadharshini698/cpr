from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "final_imsr_restart_guide.pdf"
PROJECT = r"C:\Users\devad\Documents\Codex\2026-09-23\https-github-com-devadharshini698-cpr-debriefing\work\final_imsr"


def code(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build() -> Path:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("title", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=19,
                           leading=23, textColor=colors.HexColor("#173b5e"), spaceAfter=4)
    subtitle = ParagraphStyle("subtitle", parent=styles["Normal"], fontSize=9.5, leading=13,
                              textColor=colors.HexColor("#526477"), spaceAfter=12)
    h = ParagraphStyle("h", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11.5,
                       leading=14, textColor=colors.HexColor("#0f6e56"), spaceBefore=9, spaceAfter=5)
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=9.2, leading=12.5, spaceAfter=3)
    small = ParagraphStyle("small", parent=body, fontSize=8.4, leading=10.8, textColor=colors.HexColor("#44546a"))
    mono = ParagraphStyle("mono", parent=styles["Code"], fontName="Courier", fontSize=7.1, leading=9.2,
                          textColor=colors.HexColor("#17212b"))

    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=1.55 * cm, rightMargin=1.55 * cm,
                            topMargin=1.35 * cm, bottomMargin=1.25 * cm, title="Final IMSR Restart Guide")
    story = [
        Paragraph("Final IMSR — Fresh Start Guide", title),
        Paragraph("Use this after shutting down or restarting the laptop. Start the services in the order below and keep the backend and frontend terminals open while using the system.", subtitle),
    ]

    steps = [
        ("1. Docker Desktop", "Open Docker Desktop and wait until it shows <b>Engine running</b>."),
        ("2. Terminal 1 — MySQL", "Start the database and confirm that its status is <b>healthy</b>."),
        ("3. Terminal 2 — Backend", "Starts the API, audio worker, diarization pipeline, PDF generator, and debrief worker."),
        ("4. Terminal 3 — Frontend", "Starts the MedSim AI web interface. Open the Vite URL it prints, normally <b>http://localhost:3000</b>."),
    ]
    commands = [
        None,
        f"cd {PROJECT}\ndocker compose -f docker-compose.dev.yml up -d mysql\ndocker compose -f docker-compose.dev.yml ps",
        f"cd {PROJECT}\\backend\n& ..\\.venv\\Scripts\\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000",
        f"cd {PROJECT}\\frontend\nnpm run dev",
    ]
    for index, (heading, description) in enumerate(steps):
        block = [Paragraph(heading, h), Paragraph(description, body)]
        if commands[index]:
            table = Table([[Paragraph(code(commands[index]).replace("\n", "<br/>"), mono)]], colWidths=[17.8 * cm])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            block += [table]
        story += [KeepTogether(block)]

    story += [
        Paragraph("Optional checks", h),
        Paragraph("FFmpeg must be available for uploaded audio. Ollama is optional: it improves narration, but a deterministic report is still generated if it is unavailable.", body),
    ]
    checks = [
        [Paragraph("Check", small), Paragraph("Command", small), Paragraph("Expected result", small)],
        [Paragraph("FFmpeg", body), Paragraph("ffmpeg -version", mono), Paragraph("Version information is displayed.", body)],
        [Paragraph("Ollama", body), Paragraph("Invoke-RestMethod http://127.0.0.1:11434/api/tags", mono), Paragraph("Installed model list is returned. If unavailable, use <font name='Courier'>wsl</font> then <font name='Courier'>ollama serve</font>. An ‘address already in use’ message means it is already running.", body)],
    ]
    check_table = Table(checks, colWidths=[2.2 * cm, 7.3 * cm, 8.3 * cm])
    check_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173b5e")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [check_table, Paragraph("Normal operating workflow", h)]
    workflow = "Sign in → create and run a simulation → end the session → open its debrief page → upload room/ceiling audio or use microphone recording → keep the backend terminal open while transcription and diarization run → refresh the debrief page → download the final PDF."
    story += [Paragraph(workflow, body), Spacer(1, 4), Paragraph("Keep these folders intact: <b>backend/.env</b>, <b>backend/uploads/model_cache</b>, and the Docker MySQL volume. They retain configuration, downloaded models, and saved sessions.", small)]
    doc.build(story)
    return OUTPUT


if __name__ == "__main__":
    print(build())
