"""Shared, faculty-delivered teaching adaptation; never changes patient physiology."""
from copy import deepcopy

ROLES = {
    'doctor': ('Physician / Registrar', 'Integrate assessment and differential diagnosis, coordinate a clinical plan, and seek procedural/specialist expertise beyond confirmed competence.'),
    'nurse': ('Staff Nurse / Charge Nurse', 'Lead serial observations, communicate deterioration, coordinate equipment and prescribed/protocol-authorised care within confirmed competence.'),
    'physiotherapist': ('Physiotherapist', 'Contribute respiratory and functional assessment within confirmed acute-care competence; recognise deterioration and request the appropriate emergency team.'),
    'allied': ('Allied Health Professional', 'Clarify the actual profession and emergency competencies; recognise danger, activate help and contribute agreed assessment, equipment or communication tasks.'),
}
LEVELS = {
    'beginner': ('Guided recognition and first response', 'Offer a cue after an assessment attempt or pause; disclose requested findings explicitly. Coach task allocation and reassessment. Never withhold urgent safety information.',
                 ['Identify the immediate problem and verbalise the first priorities with faculty support', 'Allocate one clear task per team member and report completion', 'Repeat the relevant assessment after the first intervention']),
    'intermediate': ('Independent prioritisation and reassessment', 'Do not volunteer coaching prompts initially. Provide requested findings and ask learners to justify priorities and reassess their response. Rescue prompts remain available.',
                     ['Independently prioritise competing findings and explain the working differential', 'Close the communication loop and revise the plan after reassessment', 'Identify missing expertise and initiate a structured escalation without prompting']),
    'advanced': ('Competing priorities and contingency planning', 'Use the optional faculty challenges below one at a time after the initial plan. Ask for contingency decisions and explicit trade-offs; do not alter physiology or resource availability without stating the teaching assumption.',
                 ['Integrate competing threats and justify a coordinated plan with explicit task ownership', 'Reprioritise after new information while maintaining essential care', 'Develop and communicate a contingency plan for unavailable expertise or definitive care']),
}

def topic_focus(spec):
    topic=spec.get('curriculum',{}).get('subtopic','')
    programme=spec.get('curriculum',{}).get('programme','ACLS')
    if programme=='NALS': return 'birth preparation, breathing and tone, thermal care, time-dependent transition and timely neonatal escalation'
    if 'Transfer' in topic: return 'transport readiness, unresolved threats and receiving-team handover'
    if 'Multisystem' in topic or 'megacode' in topic.lower(): return 'competing threats, repeated assessment and transitions between phases'
    if 'Head injury' in topic: return 'serial neurological findings despite apparently improved vital signs'
    if 'Airway and chest' in topic: return 'airway protection, chest findings and respiratory versus circulatory compromise'
    if 'haemorrhage' in topic or topic=='Shock': return 'perfusion trends, the cause of shock and response to support'
    if 'respiratory' in topic.lower(): return 'respiratory effort, effective ventilation and signs of fatigue'
    if 'brady' in topic.lower(): return 'pulse, perfusion, reversible causes and reassessment of a slow rhythm'
    if 'tachy' in topic.lower(): return 'compensatory sinus tachycardia versus primary arrhythmia and perfusion'
    if 'post-' in topic.lower(): return 'ongoing oxygenation, ventilation, perfusion and neurological reassessment'
    return 'rhythm, actual circulation, reversible causes and coordinated resuscitation' if programme=='ACLS' or 'arrest' in topic.lower() else 'systematic assessment and escalation'

def apply_teaching_design(spec):
    case=deepcopy(spec)
    level=case.get('level','beginner')
    selected=case.get('discipline',['doctor'])
    if level not in LEVELS or not isinstance(selected,list) or not selected or any(not isinstance(r,str) or r not in ROLES for r in selected):
        raise ValueError('Select valid difficulty and healthcare roles for the teaching plan')
    selected=list(dict.fromkeys(selected))
    title,delivery,objectives=LEVELS[level]
    focus=topic_focus(case)
    # Idempotent when a generated/saved case is adapted again at launch.
    case['checklist']=[i for i in case.get('checklist',[]) if i.get('source')!='teaching_design']
    core_actions=[i['action'] for i in case['checklist'] if i.get('action')]
    tasks=[dict(role=key,label=ROLES[key][0],expectation=ROLES[key][1],focus=focus) for key in selected]
    escalation=[]
    if 'doctor' not in selected:
        escalation.append('No physician role is selected: activate the appropriate emergency/medical team, provide immediate care within demonstrated competence and prepare a concise handover; do not assume independent diagnostic or procedural authority.')
    if 'nurse' not in selected:
        escalation.append('No nurse role is selected: explicitly assign observation, equipment and treatment-recording tasks to competent available personnel and request additional nursing support where needed.')
    escalation.append('Confirm who can provide the scenario-specific airway, resuscitation, procedural and definitive-care skills. A selected profession does not establish individual competence or specialist availability.')
    challenge=[]
    if level!='beginner':
        challenge.append(dict(trigger='After the first intervention or stage change',prompt='Ask for an independent repeat assessment of '+focus+'. What improved, what remains unresolved, and what would change the plan?',expected='Learners seek relevant findings and revise their plan rather than equating a better number with recovery.'))
    if level=='advanced':
        challenge.extend([
            dict(trigger='After learners request definitive help',prompt='Faculty may declare that the requested expert is not immediately available. State this assumption explicitly and ask for a safe interim plan and alternative escalation.',expected='Team states competence limits, maintains essential support and identifies an alternative without inventing unavailable resources.'),
            dict(trigger='Before handover or the final stage',prompt='Ask a second team member to challenge one assumption about '+focus+' and request a contingency plan if the patient deteriorates again.',expected='Leader invites cross-checking, resolves conflicting interpretations and communicates who will do what next.')])
    plan=dict(version='teaching-design-1',level=level,title=title,delivery=delivery,clinical_focus=focus,
        objectives=objectives,team_tasks=tasks,escalation=escalation,faculty_challenges=challenge,
        scope='Faculty assesses selected roles within locally confirmed competencies. Clinical checklist items are team-level: assess recognition, safe support, escalation or delegation when definitive action is outside the learner role. Do not require an unauthorised procedure to pass.',
        roster_note='Selected entries are professional categories, not headcount. Confirm actual people, experience and competencies with the instructor.',
        progression='All clinical presets remain available for safety and faculty control. Difficulty changes facilitation, decision tasks and assessment, not automatic physiology. Challenges are delivered manually, not timed clinical events.')
    case['teaching_plan']=plan
    case['discipline']=selected
    case['discipline_labels']=[ROLES[r][0] for r in selected]
    case['team_roles']=case['discipline_labels']
    case['team_size']=None
    case['team_size_note']=plan['roster_note']
    case['hints']=core_actions[:3] if level=='beginner' else []
    for action in objectives:
        case['checklist'].append(dict(action=f'{level.title()} teaching: {action}; focus on {focus}',critical=False,window_sec=0,source='teaching_design'))
    for task in tasks:
        case['checklist'].append(dict(action=f'Role assessment — {task["label"]}: {task["expectation"]} Apply this to {focus}.',critical=False,window_sec=0,source='teaching_design'))
    for action in escalation:
        case['checklist'].append(dict(action=action,critical=False,window_sec=0,source='teaching_design'))
    case.setdefault('teaching_notes',{})['difficulty']=title+'. '+delivery
    case['teaching_notes']['team_scope']=plan['scope']
    return case
