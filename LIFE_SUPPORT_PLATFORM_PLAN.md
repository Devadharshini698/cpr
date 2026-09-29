# Unified life-support simulation platform — proposed scope

## Current decision: independently authored modules (supersedes course-branding plan below)

All five pathways use original cases, scenario text and faculty rubrics. Display names are Adult Resuscitation Simulation, Paediatric Emergency Simulation, Neonatal Resuscitation Simulation, Trauma Emergency Simulation and Obstetric Emergency Simulation. Existing internal keys are retained for compatibility, not as official course claims. Public clinical guidance is cited as evidence; proprietary course cases, examinations, manuals and logos are not embedded. No ERC profile is included.

The adult prototype now includes generation of post-ROSC, bradycardia and tachycardia pilots; these remain unvalidated faculty-review simulations. Every programme/subtopic has a viewable design outline, with patient requirements, differentiated assessment domains and difficulty design. Paediatric, neonatal, trauma and obstetric clinical launches remain gated pending implementation and faculty review; removing course branding does not supply validated physiology or clinical content.

Faculty assessments can be reviewed in the debrief page and exported as a separate confidential PDF addendum. Exports include observation provenance and private faculty feedback, and are restricted to the owning instructor. They are not included in the automated numerical score. Non-ACLS curriculum sessions explicitly bypass adult ACLS findings and grading. The PDF skill was used to render and visually check a synthetic assessment addendum.

Earlier sections below record the design history; references to authorised ALSO content are no longer prerequisites for the independent module. Publicly evidenced obstetric topics and original faculty assessments replace that dependency. Faculty clinical review is still required for all pathways.

Status: product and clinical-content plan, not implemented/certified course coverage.
Framework implementation update: programme/subtopic selectors and server-side draft launch gates are implemented. Only the existing adult arrest/peri-arrest prototype is enabled; other topics remain draft. Instructor and student **Assess** panels provide primary/secondary/reassessment requests, explicit finding disclosure and append-only faculty observations. Records are stored in the new `patient_assessments` table without modifying existing session data. Private findings/feedback are filtered from student API responses. The panels refresh every five seconds.

Limitations: the assessment template is adult/general only; no new age-specific physiology, course-approved rubrics, course certification, automated assessment scoring, or inclusion of these observations in debrief PDFs is claimed. Assessment requests are not evidence of performance. Ended-session records are read-only. Subsequent corrections are appended, not destructive edits.

Verification: 218 backend tests passed, frontend build passed, and local two-role QA confirmed private finding/feedback isolation, explicit reveal, prevention of student self-grading, three-phase persistence and draft generation/launch rejection. Existing bundle-size warning remains.
Lead clinical institution: PSG IMSR. Technical collaboration: PSG iTech.
Confirmed programme names: NALS means neonatal life support; TLS means trauma life support.

## Agreed reference framework

User-confirmed selection: no ERC profile or mixed ERC algorithms.

- ACLS: AHA 2025, including post-cardiac-arrest care.
- PALS: AHA/AAP 2025 paediatric resuscitation.
- NALS: AHA/AAP 2025 neonatal resuscitation and NRP 9th edition educational reference.
- TLS: ACS ATLS 11th edition.
- Obstetric Life Support: AAFP Advanced Life Support in Obstetrics (ALSO). Pin the exact manual revision and applicable updates from the institution's authorised materials before implementing clinical rules or scoring. AAFP publishes 10th-edition provider-course guidelines; do not assume that identifies every current manual revision.

Create original simulation scenarios aligned with these references, with faculty review. Do not represent this application as an official ALSO/ATLS/NRP/AHA course or certification, or reproduce proprietary course manuals, assessment banks or branding without appropriate authorisation. Reference selection is agreed; content implementation and validation remain pending.

## One platform, distinct curriculum packs

Shared workflow: programme → subtopic → patient profile → difficulty → clinical location/resources → team roles → faculty-reviewed scenario → prebrief → simulation → primary/secondary assessment and reassessment → evidence-linked debrief.

| Programme | Proposed scenario families (faculty review required) | Patient-specific requirements |
|---|---|---|
| ACLS | Deteriorating adult; shockable/non-shockable arrest; bradycardia; tachycardia; peri-arrest causes; post-ROSC care | Adult physiology, rhythm versus perfusion, explicit ROSC transition |
| PALS | Respiratory distress/failure; shock; bradycardia; tachyarrhythmia; arrest; post-resuscitation care | Age and weight, age-dependent vital ranges, paediatric assessment framework; no inherited adult dosing/scoring |
| NALS | Preparation at birth; transition; inadequate breathing; ventilation response; advanced resuscitation; post-resuscitation stabilisation | Gestational age, birth weight, time since birth, temperature and neonatal-specific assessment; do not force adult primary/secondary survey sequence |
| TLS | Major haemorrhage; airway/chest injury; head injury; multisystem trauma; deterioration and transfer | Mechanism, haemorrhage, appropriate precautions, primary survey with immediate treatment, secondary survey after stabilisation |
| Obstetric Life Support (AAFP ALSO-aligned) | Proposed topics to map against authorised ALSO materials: obstetric haemorrhage; hypertensive emergencies/eclampsia; sepsis; maternal collapse/arrest; escalation and transfer | Gestational/postpartum status, maternal physiology, obstetric findings and specialist escalation; faculty-approved maternal/fetal assessment scope |

This list is a starting catalogue, not a complete curriculum. Programme availability must distinguish draft, faculty reviewed and validated; no accreditation claims.

## Instructor and student separation

- Instructor: full case, diagnosis, hidden findings, scenario progression, complete physiology, pulse/ROSC control, reveal permissions and scoring rubric.
- Student: presenting information only; request examination findings, monitoring or investigations. No diagnosis/title leakage.
- Instructor supplies/reveals findings after observation or student request; typed and push-to-talk requests are equivalent requests, not proof that an action happened.
- Reveal groups should extend beyond monitor readings to examination findings and investigations. Track who revealed what and when.
- An organised ECG can coexist with absent pulse. ROSC is an explicit faculty decision, not an inference from the rhythm name or a student's spoken assertion.

## Patient assessment model

Store assessment records separately from vital signs and transcript:

`session_id, programme_version, phase, item_id, requested_at, observed_at, observer_id, finding, revealed_at, performance_status, feedback, evidence_refs`

- Primary assessment: immediate impression and programme-appropriate structured assessment; allow urgent interventions and reassessment rather than requiring completion of a form first.
- Adult/general emergency draft domains: airway, breathing, circulation, disability, exposure. Trauma adaptations and haemorrhage priority must follow the selected curriculum.
- Secondary assessment: relevant history (e.g. SAMPLE), focused/head-to-toe examination, selected investigations and differential synthesis when appropriate.
- Reassessment: repeat relevant findings after intervention, record deterioration, handover and disposition.
- Neonatal pack: dedicated birth/resuscitation assessment sequence rather than generic adult survey requirements.
- Status choices: not observed, requested only, performed, partially performed, omitted, not applicable. Never mark a skill performed solely because it was mentioned in audio.
- Instructor ratings and AI suggestions remain visibly separate. Missing evidence is not an automatic failure; teachers confirm assessment.

## Required scenario contract

Each pack needs a versioned schema with: programme/subtopic, guideline source/year, approval status/reviewer, patient demographics (appropriate age/weight/gestation), presenting problem, learning objectives, resources/personnel, initial physiology, hidden findings, possible progression states, intervention responses, disclosure rules, primary/secondary assessment rubric, expected evidence and debrief prompts.

Initial values and progression must be mutually consistent across ECG, pulse, pressure, pleth, ventilation and clinical findings. Use configurable age-/context-specific physiology and alarm limits. Do not simply copy adult normal values, medication doses, defibrillation energy or scoring thresholds into paediatric/neonatal/obstetric packs.

## Delivery order and acceptance gates

1. Stabilise current monitor/ROSC controls and disclosure workflow. Verify every edit persists or returns an actionable error, including reconnect and separate student role.
2. Implement programme/subtopic selection and versioned curriculum-pack schema, with unavailable packs clearly blocked from launch. Preserve existing sessions and reports.
3. Implement patient-assessment request/reveal and instructor evidence recording. Test primary assessment, secondary assessment and reassessment with two independent users.
4. Develop one end-to-end faculty-reviewed pilot per programme, including beginner/intermediate/advanced variants and resource/team differences. Validate physiology, expected interventions and inappropriate-action handling before adding more topics.
5. Replace ACLS-specific grading assumptions with programme-specific reviewed rubrics and evidence provenance. Validate against faculty-scored cases; do not market AI grading as clinical validation.
6. Package offline/local deployment and optional institutional LAN access with authentication, encrypted transport, microphone-compatible secure browser context, role checks, backups and consent/retention policies. “Anywhere” is a deployment goal, not permission to expose the laptop publicly.

Before curriculum implementation: pin exact source revisions (especially ALSO), local adaptations, learner groups, clinical reviewers, and first pilot subtopic in each programme. Programme definitions and reference bodies are now agreed.

## Source anchors for clinical design (not implementation validation)

- AHA 2025 resuscitation algorithms: https://cpr.heart.org/en/resuscitation-science/cpr-and-ecc-guidelines/algorithms
- AHA neonatal resuscitation: https://cpr.heart.org/en/resuscitation-science/cpr-and-ecc-guidelines/neonatal-resuscitation
- AHA post-cardiac arrest care: https://cpr.heart.org/en/resuscitation-science/cpr-and-ecc-guidelines/post-cardiac-arrest-care
- AAFP ALSO programme: https://www.aafp.org/cme-and-events/topics/maternity-reproductive-womens-health/also
- ACS ATLS 11: https://www.facs.org/quality-programs/trauma/education/advanced-trauma-life-support/atls-11/
- WHO/ICRC Basic Emergency Care (structured ABCDE and SAMPLE assessment): https://www.who.int/publications/i/item/basic-emergency-care-approach-to-the-acutely-ill-and-injured

These references support the design direction only. WHO BEC is background assessment context, not a replacement for the agreed course frameworks. Obstetric and trauma content must be mapped to the selected ALSO and ATLS curricula and reviewed by faculty before implementation.
