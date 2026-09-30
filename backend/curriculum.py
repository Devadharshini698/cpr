"""Versioned curriculum catalogue. Draft topics are not clinical algorithms."""
PROGRAMMES = {
    'ACLS': {'reference':'AHA 2025', 'topics':['Adult arrest and peri-arrest (existing prototype)', 'Post-ROSC care', 'Bradycardia', 'Tachycardia']},
    'PALS': {'reference':'AHA/AAP 2025', 'topics':['Respiratory distress/failure', 'Shock', 'Bradycardia', 'Tachyarrhythmia', 'Cardiac arrest', 'Post-resuscitation care']},
    'NALS': {'reference':'AHA/AAP 2025; NRP 9th edition', 'topics':['Preparation and transition at birth', 'Ventilation support', 'Advanced neonatal resuscitation', 'Post-resuscitation stabilisation']},
    'TLS': {'reference':'ACS ATLS 11th edition', 'topics':['Major haemorrhage', 'Airway and chest injury', 'Head injury', 'Multisystem trauma', 'Transfer and reassessment']},
    'ALSO': {'reference':'AAFP ALSO; exact authorised revision pending', 'topics':['Obstetric haemorrhage', 'Hypertensive emergencies', 'Maternal collapse', 'Other obstetric emergencies']},
}

INDEPENDENT_LABELS = {
    'ACLS':'Adult Resuscitation Simulation',
    'PALS':'Paediatric Emergency Simulation',
    'NALS':'Neonatal Resuscitation Simulation',
    'TLS':'Trauma Emergency Simulation',
    'ALSO':'Obstetric Emergency Simulation',
}
from debriefing.scenarios.adult_vf import TOPIC as VF_TOPIC
PROGRAMMES['ACLS']['topics'].append(VF_TOPIC)
from debriefing.scenarios.adult_arrest import TOPIC as ARREST_TOPIC
PROGRAMMES['ACLS']['topics'].append(ARREST_TOPIC)
from debriefing.scenarios.adult_megacode import TOPIC as MEGACODE_TOPIC
PROGRAMMES['ACLS']['topics'].append(MEGACODE_TOPIC)
from debriefing.scenarios.paediatric_megacode import TOPIC as PAEDIATRIC_MEGACODE_TOPIC
PROGRAMMES['PALS']['topics'].append(PAEDIATRIC_MEGACODE_TOPIC)
from debriefing.scenarios.neonatal_combined import TOPIC as NEONATAL_COMBINED_TOPIC
PROGRAMMES['NALS']['topics'].append(NEONATAL_COMBINED_TOPIC)
# Preserve internal keys for existing sessions. They are not course branding.
PROGRAMMES['NALS']['reference']='AHA/AAP 2025 neonatal clinical guidance; independently authored content'
PROGRAMMES['TLS']['reference']='Published ACS trauma assessment guidance; independently authored content'
PROGRAMMES['ALSO']['reference']='Published obstetric evidence, including WHO/FIGO/ICM 2025 PPH guidance; faculty review pending'
for _key,_label in INDEPENDENT_LABELS.items():
    PROGRAMMES[_key]['label']=_label
    PROGRAMMES[_key]['authorship']='Independent research prototype; no course endorsement or certification'

def available_topics(key):
    return PROGRAMMES[key]['topics'] if key in ('ACLS','PALS','TLS','NALS','ALSO') else []

def catalogue():
    return {key:{**value,'topics':[t for t in value['topics'] if t != VF_TOPIC], 'status':'prototype' if key=='ACLS' else 'draft',
        'generatable_topics':available_topics(key),
        'launchable_topics':available_topics(key)} for key,value in PROGRAMMES.items()}

def validate_selection(programme, topic, allow_case_draft=False):
    if programme not in PROGRAMMES or topic not in PROGRAMMES[programme]['topics']:
        raise ValueError('Select a valid programme and subtopic')
    if topic not in available_topics(programme):
        raise ValueError('This curriculum pack is draft and cannot launch until its clinical content is implemented and reviewed.')
    return {'programme':programme,'subtopic':topic,'reference':PROGRAMMES[programme]['reference'],
            'label':INDEPENDENT_LABELS[programme],'authorship':'independent',
            'version':'framework-1','status':'prototype — faculty review required'}

ASSESSMENT_ITEMS = {
    'primary': {'airway':'Airway', 'breathing':'Breathing', 'circulation':'Circulation', 'disability':'Disability', 'exposure':'Exposure'},
    'secondary': {'history':'Relevant history / SAMPLE', 'examination':'Focused / head-to-toe examination', 'investigations':'Relevant investigations'},
    'reassessment': {'response':'Response to intervention', 'repeat':'Repeat assessment / vital signs', 'handover':'Handover and disposition'},
}
STATUSES = ('not_observed','performed','partially_performed','omitted','not_applicable')

def assessment_items(programme='ACLS'):
    from copy import deepcopy
    items=deepcopy(ASSESSMENT_ITEMS)
    if programme=='TLS':
        items['primary']={'haemorrhage':'Exsanguinating external haemorrhage',**items['primary']}
        items['secondary']['mechanism']='Mechanism, injuries and relevant precautions'
    elif programme=='PALS':
        items['primary']={'impression':'Initial appearance, breathing and circulation impression',**items['primary']}
        items['secondary']['age_weight']='Age, weight and caregiver history'
    elif programme=='NALS':
        items={'initial_birth_assessment':{'preparation':'Preparation, risk factors and team roles','transition':'Breathing, tone and transition','heart_rate':'Heart rate assessment','temperature':'Temperature and thermal care'},
               'focused_assessment':{'ventilation':'Ventilation response and reassessment','birth_context':'Gestational age, birth weight and perinatal history','perfusion':'Perfusion and circulatory reassessment','glucose':'Measured glucose and repeat assessment','neurology':'Activity, tone and neurological concerns'},
               'reassessment':{'response':'Response to support','stabilisation':'Post-resuscitation stabilisation','handover':'Handover'}}
    elif programme=='ALSO':
        items['primary']['bleeding']='Quantified bleeding and haemodynamic assessment'
        items['secondary']['uterine_placental']='Uterine tone, genital tract and placental assessment'
        items['secondary']['laboratory']='Haematology, coagulation and transfusion investigations'
        items['secondary']['obstetric_context']='Gestational / postpartum status and obstetric history'
        items['secondary']['maternal_fetal']='Maternal and fetal assessment as appropriate'
    return items

def curriculum_draft(programme,topic):
    if programme not in PROGRAMMES or topic not in PROGRAMMES[programme]['topics']:
        raise ValueError('Select a valid programme and subtopic')
    requirements={
        'ACLS':['Adult age, weight, presenting problem and relevant history'],
        'PALS':['Exact age and weight','Caregiver history','Age-specific physiological limits and equipment'],
        'NALS':['Gestational age and birth weight','Time since birth','Perinatal history and thermal context','Neonatal-specific monitor and alarm behaviour'],
        'TLS':['Age, weight and injury mechanism','Bleeding and injury findings','Available trauma resources and transfer pathway'],
        'ALSO':['Gestational age or postpartum interval','Maternal history and obstetric findings','Original faculty rubric with cited public clinical evidence'],
    }
    return {'programme':programme,'subtopic':topic,'reference':PROGRAMMES[programme]['reference'],
            'label':INDEPENDENT_LABELS[programme],
            'status':'Draft design outline - not an executable clinical scenario',
            'patient_requirements':requirements[programme], 'assessment_domains':assessment_items(programme),
            'pending':['Faculty-authored patient findings and consistent vital states','Reviewed progression and intervention responses','Evidence-linked rubric and clinical sign-off'],
            'difficulty_design':{'beginner':'Faculty prompts and focused objectives','intermediate':'Reduced prompts and reassessment','advanced':'Team coordination, competing priorities and resource constraints'}}

def validate_assessment(body, instructor, programme='ACLS'):
    items=assessment_items(programme)
    phase,item=body.get('phase'),body.get('item')
    if phase not in items or item not in items[phase]:
        raise ValueError('Select a valid assessment phase and item')
    if instructor:
        if body.get('status') not in STATUSES or type(body.get('revealed')) is not bool:
            raise ValueError('Select a performance status and explicit disclosure choice')
        if any(not isinstance(body.get(k,''),str) or len(body.get(k,''))>2000 for k in ('finding','feedback')):
            raise ValueError('Findings and feedback must be text of at most 2000 characters')
    return phase,item

def public_assessment(row):
    """Never send hidden findings, grading or private feedback to a learner."""
    return {k:row[k] for k in ('id','phase','item','created_at','kind')} | {
        'revealed':bool(row['revealed']), 'finding':row['finding'] if row['revealed'] else None}
