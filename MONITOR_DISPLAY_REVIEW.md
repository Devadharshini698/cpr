# Pressure waveforms and student display

## September 2026 refinement

- ABP and PAP use bounded, continuous periodic teaching pulses. This removes the old truncated-gamma discontinuity at the end of each beat.
- The morphology has a systolic upstroke and peak, descending-limb notch and diastolic runoff. ABP and PAP use different illustrative peak/notch parameters and retain their separate pressure ranges, respiratory modulation and ECG-linked timing.
- With absent pulse output the pressure traces remain flat. The automatic pressure range is explicitly labelled in mmHg; equal on-screen heights do not imply equal pressure.
- These are synthetic research-prototype traces, **not clinically validated haemodynamic models**. The specific waveform contours, catheter-site effects, damping and extreme-rate behaviour require faculty review before assessment use. The changes do not add validated overdamping/underdamping or wedge-pressure simulation.

Clinical morphology references: [LHSC pulmonary artery waveform](https://www.lhsc.on.ca/critical-care-trauma-centre/critical-care-trauma-centre-90), [Computer model analysis of the radial artery pressure waveform](https://pubmed.ncbi.nlm.nih.gov/3681355/). These inform morphology review; they do not validate this implementation or its numerical coefficients.

## Instructor workflow

New scenarios now start with all student waves, numbers and alarms concealed. The instructor still sees the complete monitor. The student case panel does not show the scenario diagnosis/title.

Students can use **Requests** to select monitoring and send a typed request, or record a local push-to-talk request of up to 12 seconds. Recognised words remain editable and require explicit submission. Only the instructor can Reveal or Decline; a request never automatically reveals a measurement. Voice is not continuous listening, clinical-action detection or speaker identification. English/Tamil/auto transcription uses the existing offline Whisper-small model; channel suggestions currently recognise English monitoring terms, so manual selection remains available for Tamil/Tanglish or ambiguous speech.

Full-session debrief audio is separate: start **Record audio** on the instructor interface, select the correct microphone/language and check the input meter. The meter detects sound, not intelligible speech. Transcript accuracy and speaker attribution still require human review.

1. Open **Student display**, above the cuff/auxiliary panel.
2. Select individual waves and values, including ABP and PAP separately. Show all / Hide all are shortcuts.
3. Choose **Apply to students**. Wait for the server acknowledgement; the dialog remains open with an error if unconfirmed.
4. Reopen the panel and use **Preview saved student display** to inspect the same student presentation. Return to instructor does not end the session.

The instructor retains the full monitor. Choices are stored per session in `student_display`, broadcast to connected clients, and restored on joining/reconnecting. Hiding a waveform does not hide its number unless that separate selection is also unchecked. Hidden numeric channels suppress their associated student alarm banners/sound; all instructor alarms remain available. Students have no display-editing controls and the dedicated server event rejects student-role edits.

Display selections are **presentation controls, not data-security restrictions**: physiological values and waveform telemetry remain available to the connected client. They must not be used to protect confidential data.

## Verification

- September 29 follow-up: 198 backend tests and 3 display tests pass; frontend production build succeeds (existing bundle-size warning). Local two-role QA confirms concealed launch, pending requests, rejected student approval, selective instructor reveal and decline.
- Explicit simulated ROSC: select an organised rhythm, confirm **Pulse present / confirm simulated ROSC**, review pulse/BP/SpO2 settings and Apply. Changing ECG rhythm alone does not establish a pulse. Regression and local QA cover VF-to-ROSC pulse restoration and non-flat pleth generation. No original session data was rewritten.
- A preserved 12-second excerpt from GHFN8I returned HTTP 200 with locally recognised text in 6.3 seconds. Its first 12 seconds returned no intelligible speech. This is a saved-audio pipeline test, not verification of live microphone quality or transcript accuracy. The earlier full-session job completed with seven segments; missing words still require a fresh microphone/sample comparison.
- Backend regression tests cover pressure continuity/bounds/notches, absent-pulse traces at multiple rates, display validation and instructor-only editing.
- `node --test src/utils/studentDisplay.test.js` (from frontend) checks independent wave/value choices, instructor visibility and student alarms.
- Local QA tested two socket roles, persistence/reconnection, unchanged physiological values and saved-setting preview. No microphone, patient recording, cloud service or original session was used by these tests.
