"""Faculty-only assessment addendum; no AI grade or certification claim."""
from io import BytesIO
from html import escape
from datetime import datetime, timezone
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether

def build_assessment_pdf(session_code, records, items, curriculum, active):
    buffer=BytesIO()
    styles=getSampleStyleSheet()
    styles['Heading1'].keepWithNext=True
    styles['Heading2'].keepWithNext=True
    def text(value):
        return escape(str(value or '')).replace('\n','<br/>')
    story=[Paragraph('Faculty assessment addendum',styles['Title']),
        Paragraph('CONFIDENTIAL - faculty observations and feedback',styles['Heading2']),
        Paragraph(f'Session: {text(session_code)} | Exported: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}',styles['Normal']),
        Paragraph(f'Programme: {text(curriculum.get("programme","Legacy adult prototype"))} | Reference: {text(curriculum.get("reference","Not recorded"))}',styles['Normal']),
        Paragraph('Live-session snapshot; entries may change.' if active else 'Ended-session observation record.',styles['Normal']),
        Spacer(1,0.4*cm),Paragraph('These are recorded faculty observations, not an automated clinical grade or course certificate. Student requests are not evidence of completed actions. All entries are retained chronologically; later corrections do not erase earlier entries. This addendum is separate from the automated debrief score.',styles['Normal'])]
    if not records:
        story.append(Paragraph('No assessment entries recorded. This does not establish that assessment was omitted.',styles['Heading2']))
    for phase,labels in items.items():
        phase_heading = [Spacer(1,0.4*cm),Paragraph(text(phase.replace('_',' ').title()),styles['Heading1'])]
        selected=[r for r in records if r['phase']==phase]
        if not selected: story.append(KeepTogether(phase_heading + [Paragraph('No entries recorded for this phase.',styles['Normal'])]))
        for index, r in enumerate(selected):
            entry = [Paragraph(text(labels.get(r['item'],r['item'])),styles['Heading2']),
                Paragraph(f'{text(r["created_at"])} UTC | {text(r["kind"])} | {text(r["status"].replace("_"," "))} | Actor ID: {text(r.get("observer_id"))}',styles['Normal']),
                Paragraph('Disclosure: '+('finding revealed to students' if r['revealed'] else 'private'),styles['Normal'])]
            for key,label in [('finding','Finding'),('feedback','Private faculty feedback')]:
                if r.get(key): entry.append(Paragraph(f'<b>{label}:</b> {text(r[key])}',styles['Normal']))
            entry.append(Spacer(1,0.25*cm))
            story.append(KeepTogether((phase_heading if index == 0 else []) + entry))
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont('Helvetica',8)
        canvas.drawString(1.8*cm,1.1*cm,'Research prototype | Faculty-only addendum | Not a certification')
        canvas.drawRightString(A4[0]-1.8*cm,1.1*cm,str(doc.page));canvas.restoreState()
    SimpleDocTemplate(buffer,pagesize=A4,rightMargin=1.8*cm,leftMargin=1.8*cm,topMargin=1.7*cm,bottomMargin=1.8*cm).build(story,onFirstPage=footer,onLaterPages=footer)
    return buffer.getvalue()
