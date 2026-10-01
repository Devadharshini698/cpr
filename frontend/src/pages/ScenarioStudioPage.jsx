import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  Volume2,
  RotateCcw,
  Play,
  AlertTriangle,
  ChevronDown,
  Users,
  ClipboardList,
  Sparkles,
  Award,
  BookOpen
} from "lucide-react";
import Navbar from "../components/dashboard/Navbar";
import TeachingPlan from '../components/instructor/TeachingPlan';
import Sidebar from "../components/dashboard/Sidebar";
import DashboardModals from "../components/dashboard/DashboardModals";
import "../components/dashboard/dashboard.css";
import './scenario-selectors.css';

const API = (import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

export default function ScenarioStudioPage() {
  const navigate = useNavigate();

  // Navigation / Shell State
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  const [activeModal, setActiveModal] = useState(null);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);

  // Config State Options with Local Fallbacks
  const [levels, setLevels] = useState(["beginner", "intermediate", "advanced"]);
  const [locations, setLocations] = useState({
    ER: { label: "Emergency Room", icon: "🚨" },
    ICU: { label: "Intensive Care Unit", icon: "💉" },
    Theatre: { label: "Operating Theatre", icon: "😷" },
    Ward_Medical: { label: "Medical Ward", icon: "🏥" },
    Ward_Surgical: { label: "Surgical Ward", icon: "🏥" },
    Ward_Ortho: { label: "Orthopaedic Ward", icon: "🏥" },
    Ward_Neuro: { label: "Neurological Ward", icon: "🏥" },
    Ward_Cardio: { label: "Cardiology Ward", icon: "🏥" }
  });
  const [specialities, setSpecialities] = useState({
    ER: "Emergency Medicine",
    ICU: "Intensive Care",
    Anaesthesia: "Anaesthesia",
    Cardio: "Cardiology",
    Neuro: "Neurology",
    Trauma: "Trauma",
    Ortho: "Orthopaedics",
    Surgery: "General Surgery",
    Medicine: "General Medicine",
    Allied_Medical: "Allied Medical",
    Allied_Surgical: "Allied Surgical"
  });
  const [disciplines, setDisciplines] = useState({
    doctor: "Physician / Registrar",
    nurse: "Staff Nurse / Charge Nurse",
    physiotherapist: "Physiotherapist",
    allied: "Allied Health Professional"
  });

  // Instructor Selections
  const [selectedLevel, setSelectedLevel] = useState("beginner");
  const [selectedLocation, setSelectedLocation] = useState("ER");
  const [selectedSpeciality, setSelectedSpeciality] = useState("ER");
  const [selectedDisciplines, setSelectedDisciplines] = useState(["doctor"]);
  const [useOwnScenario, setUseOwnScenario] = useState(false);
  const [customText, setCustomText] = useState("");
  const [teamName, setTeamName] = useState("");
  const [rhythms, setRhythms] = useState({});
  const [selectedRhythm, setSelectedRhythm] = useState('');
  const [programmes,setProgrammes]=useState({});
  const [optionsLoading,setOptionsLoading]=useState(true);
  const [optionsError,setOptionsError]=useState('');
  const [optionsRetry,setOptionsRetry]=useState(0);
  const [programme,setProgramme]=useState('ACLS');
  const [subtopic,setSubtopic]=useState('Adult cardiac arrest — ward-based case');
  const [clinicalSeverity,setClinicalSeverity]=useState('arrest');
  const wardArrest = subtopic === 'Adult cardiac arrest — ward-based case';
  const [tachySeverity, setTachySeverity] = useState('stable');
  const megacode = subtopic === 'Adult megacode — configurable ward-based case';
  const [megaStages,setMegaStages] = useState(['tachy_stable','tachy_unstable','brady_unstable','arrest','rosc','post_arrest']);
  const megaLabels = {tachy_stable:'Tachycardia — maintained perfusion',tachy_unstable:'Tachycardia — unstable',brady_stable:'Bradycardia — maintained perfusion',brady_unstable:'Bradycardia — unstable',arrest:'Cardiac arrest',rosc:'Confirmed ROSC',post_arrest:'Post-arrest care'};
  const packReady=(programmes[programme]?.generatable_topics || programmes[programme]?.launchable_topics)?.includes(subtopic) === true;
  const launchReady=programmes[programme]?.launchable_topics?.includes(subtopic) === true;
  const [paediatricProfile,setPaediatricProfile]=useState('child');
  const [neonatalProfile,setNeonatalProfile]=useState('term');
  const [neonatalCourse,setNeonatalCourse]=useState('vigorous');
  const [neonatalSetting,setNeonatalSetting]=useState('delivery_room');
  const [neonatalVentCourse,setNeonatalVentCourse]=useState('apnoea');
  const [neonatalVentProblem,setNeonatalVentProblem]=useState('mask_leak');
  const [neonatalAdvancedContext,setNeonatalAdvancedContext]=useState('persistent_bradycardia');
  const [neonatalAdvancedEntry,setNeonatalAdvancedEntry]=useState('escalation');
  const [neonatalPostFocus,setNeonatalPostFocus]=useState('assessment');
  const [obstetricCause,setObstetricCause]=useState('tone');
  const [obstetricSeverity,setObstetricSeverity]=useState('maintained');
  const [obstetricSetting,setObstetricSetting]=useState('delivery_suite');
  const [obstetricHtContext,setObstetricHtContext]=useState('antenatal');
  const [obstetricHtEntry,setObstetricHtEntry]=useState('warning_signs');
  const [obstetricHtSetting,setObstetricHtSetting]=useState('maternity');
  const [maternalContext,setMaternalContext]=useState('antenatal');
  const [maternalEntry,setMaternalEntry]=useState('deteriorating');
  const [maternalCause,setMaternalCause]=useState('undifferentiated');
  const [maternalSetting,setMaternalSetting]=useState('maternity');
  const [obstetricEmergencyKind,setObstetricEmergencyKind]=useState('sepsis');
  const [neonatalStages,setNeonatalStages]=useState(['neonatal_poor_transition','neo_vent_ineffective','neo_adv_escalation','neo_adv_ongoing','neo_adv_hr_response','neo_post_assessment','neo_post_handover']);
  const neonatalStageLabels={neonatal_vigorous:'2 min — vigorous transition',neonatal_poor_transition:'2 min — poor transition',neo_vent_apnoea:'2 min — apnoea',neo_vent_ineffective:'3 min — ineffective ventilation',neo_vent_effective:'5 min — effective assisted ventilation',neo_adv_escalation:'5 min — advanced escalation after effective ventilation',neo_adv_ongoing:'5 min — ongoing resuscitation',neo_adv_refractory:'10 min — persistent poor response',neo_adv_hr_response:'10 min — heart-rate recovery',neo_adv_stabilisation:'10 min — recovery with support',neo_vent_spontaneous:'10 min — spontaneous breathing',neo_post_assessment:'10 min — post-resuscitation assessment',neo_post_respiratory:'10 min — respiratory compromise',neo_post_perfusion:'10 min — poor perfusion',neo_post_temperature:'10 min — low temperature',neo_post_neurometabolic:'10 min — neurological/glucose assessment',neo_post_deterioration:'15 min — recurrent deterioration',neo_post_response:'20 min — stabilisation',neo_post_handover:'20 min — monitored handover'};
  const [respiratorySeverity,setRespiratorySeverity]=useState('distress');
  const [shockSeverity,setShockSeverity]=useState('compensated');
  const [shockCause,setShockCause]=useState('hypovolaemic');
  const [paediatricBradySeverity,setPaediatricBradySeverity]=useState('compromise');
  const [paediatricTachySeverity,setPaediatricTachySeverity]=useState('maintained');
  const [paediatricTachyPattern,setPaediatricTachyPattern]=useState('sinus');
  const [paediatricArrestContext,setPaediatricArrestContext]=useState('respiratory');
  const [paediatricArrestRhythm,setPaediatricArrestRhythm]=useState('');
  const [paediatricPostFocus,setPaediatricPostFocus]=useState('assessment');
  const [traumaMechanism,setTraumaMechanism]=useState('external');
  const [traumaSeverity,setTraumaSeverity]=useState('compensated');
  const [traumaInjury,setTraumaInjury]=useState('airway');
  const [traumaChestSeverity,setTraumaChestSeverity]=useState('initial');
  const [headInjuryCourse,setHeadInjuryCourse]=useState('observation');
  const [multisystemFocus,setMultisystemFocus]=useState('initial');
  const [transferProfile,setTransferProfile]=useState('bleeding');
  const [transferPhase,setTransferPhase]=useState('preparation');
  const paediatricMegacode = subtopic === 'Paediatric megacode — configurable combined case';
  const [paediatricMegaStages,setPaediatricMegaStages]=useState(['respiratory_distress','sinus_tachy','shock_compensated','respiratory_failure','shock_hypotensive','brady_compromise','brady_persistent','arrest_pea','rosc','post_oxygenation','post_ventilation','post_perfusion','stabilisation']);
  const paediatricMegaLabels = {respiratory_distress:'Respiratory distress',respiratory_failure:'Respiratory failure',shock_compensated:'Compensated shock',shock_hypotensive:'Hypotensive shock',sinus_tachy:'Sinus tachycardia',svt:'SVT — optional variant',vt_pulse:'VT with a pulse — optional variant',brady_compromise:'Bradycardia with compromise',brady_persistent:'Persistent bradycardia after ventilation',arrest_pea:'Cardiac arrest — PEA',arrest_asystole:'Cardiac arrest — asystole',arrest_vf:'Cardiac arrest — VF',arrest_pvt:'Cardiac arrest — pulseless VT',rosc:'Confirmed ROSC',post_oxygenation:'Post-resuscitation hypoxaemia',post_ventilation:'Post-resuscitation hypoventilation',post_perfusion:'Post-resuscitation hypotension',stabilisation:'Stabilisation and reassessment'};
  const [outline,setOutline]=useState(null);
  const [outlineError,setOutlineError]=useState('');
  const showOutline=async()=>{
    setOutlineError('');
    try {
      const token=sessionStorage.getItem('token') || localStorage.getItem('token');
      const response=await fetch(`${API}/api/curriculum/draft`,{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${token}`},body:JSON.stringify({programme,subtopic})});
      const result=await response.json();if(!response.ok)throw new Error(result.detail || 'Cannot load outline');setOutline(result);
    } catch(error){setOutlineError(error.message);}
  };
  useEffect(()=>{setOutline(null);setOutlineError('');setSelectedRhythm('');},[programme,subtopic]);

  // UI / Logic State
  const [spec, setSpec] = useState(null);
  const [loading, setLoading] = useState(false);
  const [narrating, setNarrating] = useState(false);
  const [showChecklist, setShowChecklist] = useState(false);
  const [launching, setLaunching] = useState(false);
  const [launchError, setLaunchError] = useState('');
  useEffect(() => { setSpec(null); }, [selectedLevel, selectedLocation, selectedSpeciality, selectedDisciplines, clinicalSeverity, tachySeverity, useOwnScenario, customText]);

  // Load configuration options
  useEffect(() => {
    let cancelled=false;
    setOptionsLoading(true);setOptionsError('');
    const token = sessionStorage.getItem("token") || localStorage.getItem("token");
    const headers = token ? { Authorization: `Bearer ${token}` } : {};

    fetch(`${API}/api/scenario/list`, { headers })
      .then((res) => {
        if (!res.ok) throw new Error(res.status===401?'Your sign-in has expired. Please sign in again.':'Could not load programmes. Check that the backend is running, then retry.');
        return res.json();
      })
      .then((data) => {
        if(cancelled)return;
        if(!data.programmes || !Object.keys(data.programmes).length) throw new Error('No programmes were returned. Please retry.');
        if (data.levels) setLevels(data.levels);
        if (data.programmes) setProgrammes(data.programmes);
        if (data.rhythms) setRhythms(data.rhythms);
        if (data.locations) setLocations(data.locations);
        if (data.specialities) setSpecialities(data.specialities);
        if (data.disciplines) setDisciplines(data.disciplines);
      })
      .catch((err) => {
        if(!cancelled)setOptionsError(err.message==='Failed to fetch'?'Cannot reach the backend. Check that it is running, then retry.':err.message);
      }).finally(()=>{if(!cancelled)setOptionsLoading(false);});
    return ()=>{cancelled=true;};
  }, [navigate,optionsRetry]);

  const handleGenerate = async () => {
    if (!packReady) return;
    setLoading(true);
    setSpec(null);
    const token = sessionStorage.getItem("token") || localStorage.getItem("token");
    const headers = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    try {
      let resSpec;
      if (useOwnScenario) {
        // Parse custom instructor text first
        const res = await fetch(`${API}/api/scenario/instructor`, {
          method: "POST",
          headers,
          credentials: "include",
          body: JSON.stringify({ text: customText, level:selectedLevel, discipline:selectedDisciplines, programme, subtopic })
        });
        if (!res.ok) throw new Error("Failed to parse custom scenario");
        const parsedData = await res.json();
        resSpec = parsedData.spec;
      } else {
        // Standard generator
        const res = await fetch(`${API}/api/scenario/generate`, {
          method: "POST",
          headers,
          credentials: "include",
          body: JSON.stringify({
            level: selectedLevel,
            programme, subtopic,
            paediatric_profile: paediatricProfile, respiratory_severity: respiratorySeverity,
            neonatal_profile:neonatalProfile, neonatal_course:neonatalCourse, neonatal_setting:neonatalSetting,
            neonatal_ventilation_course:neonatalVentCourse, neonatal_ventilation_problem:neonatalVentProblem,
            neonatal_advanced_context:neonatalAdvancedContext, neonatal_advanced_entry:neonatalAdvancedEntry,
            neonatal_post_focus:neonatalPostFocus,
            neonatal_sequence:neonatalStages,
            obstetric_cause:obstetricCause, obstetric_severity:obstetricSeverity, obstetric_setting:obstetricSetting,
            obstetric_ht_context:obstetricHtContext, obstetric_ht_entry:obstetricHtEntry, obstetric_ht_setting:obstetricHtSetting,
            maternal_context:maternalContext,maternal_entry:maternalEntry,maternal_cause:maternalCause,maternal_setting:maternalSetting,obstetric_emergency_kind:obstetricEmergencyKind,
            shock_severity: shockSeverity, shock_cause: shockCause,
            paediatric_brady_severity: paediatricBradySeverity,
            paediatric_tachy_severity: paediatricTachySeverity, paediatric_tachy_pattern: paediatricTachyPattern,
            paediatric_arrest_context: paediatricArrestContext, paediatric_arrest_rhythm: paediatricArrestRhythm,
            paediatric_post_resuscitation_focus: paediatricPostFocus,
            trauma_mechanism: traumaMechanism, trauma_severity: traumaSeverity,
            trauma_injury: traumaInjury, trauma_chest_severity: traumaChestSeverity,
            head_injury_course: headInjuryCourse,
            multisystem_focus: multisystemFocus,
            transfer_profile: transferProfile, transfer_phase: transferPhase,
            paediatric_megacode_sequence: paediatricMegaStages,
            megacode_sequence: megaStages,
            clinical_severity: ['Tachycardia','Bradycardia'].includes(subtopic) ? tachySeverity : clinicalSeverity,
            rhythm: selectedRhythm || null,
            location: selectedLocation,
            discipline: selectedDisciplines,
            speciality: selectedSpeciality
          })
        });
        if (!res.ok) {
          const errorData = await res.json();
          throw new Error(typeof errorData.detail === 'string' ? errorData.detail : 'Failed to generate scenario');
        }
        const genData = await res.json();
        resSpec = genData.spec;
      }

      resSpec.curriculum={programme,subtopic,reference:programmes[programme].reference,version:'framework-1',status:'prototype — faculty review required'};
      setSpec(resSpec);
    } catch (err) {
      console.error(err);
      alert(err.message || "Error generating scenario. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleLaunch = async () => {
    if (!spec || !launchReady || launching) return;
    setLaunching(true);
    setLaunchError('');
    try {
      const token = sessionStorage.getItem('token') || localStorage.getItem('token');
      // Direct testing launch never attaches an old prebrief or its recordings.
      const { prebrief: _previousPrebrief, ...launchSpec } = spec;
      const response = await fetch(`${API}/api/scenario/launch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ spec: launchSpec, team_name: teamName || 'Resus Team' }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Scenario launch failed');
      sessionStorage.setItem('session_code', data.session_code);
      sessionStorage.setItem('team_name', teamName || 'Resus Team');
      navigate('/instructor');
    } catch (error) {
      setLaunchError(error.message);
    } finally {
      setLaunching(false);
    }
  };

  const handlePrebrief = () => {
    if (!spec || !launchReady || launching) return;
    sessionStorage.setItem('prebrief_draft', JSON.stringify({ spec, team_name: teamName || 'Resus Team' }));
    navigate('/prebrief');
  };

  const handleNarrate = () => {
    if (!spec || narrating) return;
    setNarrating(true);
    const token = sessionStorage.getItem("token") || localStorage.getItem("token");
    const headers = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    fetch(`${API}/api/scenario/narrate`, {
      method: "POST",
      headers,
      credentials: "include",
      body: JSON.stringify({ spec })
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.text) {
          window.speechSynthesis.cancel();
          const utterance = new SpeechSynthesisUtterance(data.text);
          utterance.onend = () => setNarrating(false);
          utterance.onerror = () => setNarrating(false);
          window.speechSynthesis.speak(utterance);
        } else {
          setNarrating(false);
        }
      })
      .catch((err) => {
        console.error(err);
        setNarrating(false);
      });
  };

  const handleToggleDiscipline = (discKey) => {
    setSpec(null);
    setSelectedDisciplines((prev) =>
      prev.includes(discKey)
        ? prev.filter((d) => d !== discKey)
        : [...prev, discKey]
    );
  };

  const handleLogout = () => {
    sessionStorage.clear();
    navigate("/");
  };

  return (
    <div className="medsim-dashboard-page" style={{ backgroundColor: "#F8FAFC" }}>
      {/* Navbar */}
      <Navbar
        searchQuery=""
        setSearchQuery={() => { }}
        showNotifications={showNotifications}
        setShowNotifications={setShowNotifications}
        showProfileMenu={showProfileMenu}
        setShowProfileMenu={setShowProfileMenu}
        handleStartSimulation={() => navigate("/initializing")}
        handleLogout={handleLogout}
        onOpenSettings={() => navigate("/settings")}
      />

      <div style={{ display: "flex", flex: 1, overflow: "hidden", position: "relative" }}>
        {/* Sidebar */}
        <Sidebar
          sidebarExpanded={sidebarExpanded}
          setSidebarExpanded={setSidebarExpanded}
          activeTab="simulation"
          setActiveTab={() => { }}
          handleStartSimulation={() => navigate("/initializing")}
          onOpenModal={(modalType) => setActiveModal(modalType)}
        />

        {/* Scrollable Main Content */}
        <main className="medsim-main-content" style={{ display: "grid", gridTemplateColumns: "380px 1fr", gap: "24px", padding: "32px 40px", overflowY: "auto" }}>

          {/* Left Configuration Panel */}
          <div style={{
            backgroundColor: "#FFFFFF",
            border: "1px solid #E2E8F0",
            borderRadius: "16px",
            padding: "24px",
            display: "flex",
            flexDirection: "column",
            gap: "20px",
            boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.05)",
            height: "fit-content"
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", paddingBottom: "12px", borderBottom: "1px solid #F1F5F9" }}>
              <div style={{
                width: "36px", height: "36px", borderRadius: "10px",
                backgroundColor: "#F0FDFA", border: "1px solid #CCFBF1",
                display: "flex", alignItems: "center", justifyContent: "center",
                color: "#0F766E"
              }}>
                <Sparkles size={18} />
              </div>
              <div>
                <h2 style={{ fontSize: "16px", fontWeight: 700, color: "#0F172A", margin: 0 }}>Scenario Studio</h2>
                <p style={{ fontSize: "11px", color: "#64748B", margin: 0 }}>Design your simulation parameters</p>
              </div>
            </div>

            {/* Difficulty Level */}
            <div className="scenario-selectors" style={{display:'grid',gap:8}}>
              <label htmlFor="programme">Life-support programme</label>
              <select id="programme" disabled={optionsLoading||!!optionsError} value={Object.keys(programmes).length?programme:''} onChange={e=>{setProgramme(e.target.value);setSubtopic(programmes[e.target.value].topics[0]);setSpec(null);}}>
                {!Object.keys(programmes).length&&<option value="">{optionsLoading?'Loading programmes…':'Programmes unavailable'}</option>}
                {Object.keys(programmes).map(p=><option key={p} value={p}>{programmes[p].label || p}</option>)}
              </select>
              <label htmlFor="subtopic">Subtopic</label>
              <select id="subtopic" aria-describedby="selected-subtopic" disabled={optionsLoading||!!optionsError} value={programmes[programme]?.topics?.length?subtopic:''} onChange={e=>{setSubtopic(e.target.value);setSpec(null);}}>
                {!programmes[programme]?.topics?.length&&<option value="">{optionsLoading?'Loading subtopics…':'Subtopics unavailable'}</option>}
                {programmes[programme]?.topics.map(t=><option key={t}>{t}</option>)}
              </select>
              {!optionsLoading&&!optionsError&&<p id="selected-subtopic" className="scenario-selection-summary"><strong>Selected:</strong> {programmes[programme]?.label || programme}<br/>{subtopic}</p>}
              {optionsError&&<div role="alert" className="scenario-options-error">{optionsError} <button type="button" onClick={()=>setOptionsRetry(value=>value+1)}>Retry loading</button></div>}
              <p style={{fontSize:12}}>{programmes[programme]?.reference}</p>
              <p style={{fontSize:12}}>Independently authored research modules. No affiliation, endorsement or course certification is implied.</p>
              <button type="button" onClick={showOutline}>Review module design outline</button>
              {outlineError && <p role="alert">{outlineError}</p>}
              {outline && <section style={{padding:12,background:'#f1f5f9',fontSize:12}}>
                <h3>{outline.label}: {outline.subtopic}</h3><p>{outline.status}</p>
                <h4>Patient information needed</h4><ul>{outline.patient_requirements.map(x=><li key={x}>{x}</li>)}</ul>
                <h4>Assessment domains</h4>{Object.entries(outline.assessment_domains).map(([phase,items])=><div key={phase}><strong>{phase.replaceAll('_',' ')}</strong><ul>{Object.values(items).map(x=><li key={x}>{x}</li>)}</ul></div>)}
                <h4>Difficulty design</h4>{Object.entries(outline.difficulty_design).map(([level,text])=><p key={level}><strong>{level}:</strong> {text}</p>)}
                <h4>Still required</h4><ul>{outline.pending.map(x=><li key={x}>{x}</li>)}</ul>
              </section>}
              <p role="status" style={{fontSize:12,color:packReady?'#0f766e':'#92400e'}}>{packReady?(launchReady?'Research prototype — faculty review required; not a certified course.':'Case preview available; launch disabled pending paediatric monitor and clinical validation.'):'Draft curriculum: generation and launch are unavailable until clinical content and assessment rules are implemented and reviewed.'}</p>
            </div>
            {programme==='NALS'&&packReady&&<div>
              <h3>Newborn — {subtopic}</h3>
              <label>Gestation / birth weight<select aria-label="Neonatal profile" value={neonatalProfile} onChange={e=>{setNeonatalProfile(e.target.value);setSpec(null);}}><option value="term">Term — 39 weeks, 3.2 kg</option><option value="late_preterm">Late preterm — 35 weeks, 2.3 kg</option></select></label>
              <label>Birth setting<select aria-label="Birth setting" value={neonatalSetting} onChange={e=>{setNeonatalSetting(e.target.value);setSpec(null);}}><option value="delivery_room">Delivery room</option><option value="theatre">Obstetric theatre</option><option value="emergency">Emergency department birth</option></select></label>
              {subtopic==='Neonatal combined case — configurable progression'?<>
                <h4>Planned stages — instructor-controlled</h4>
                {neonatalStages.map((stage,index)=><div key={index} style={{display:'flex',gap:6,flexWrap:'wrap',marginBottom:8}}>
                  <label>Stage {index+1}<select aria-label={`Neonatal stage ${index+1}`} value={stage} onChange={e=>{setNeonatalStages(neonatalStages.map((v,i)=>i===index?e.target.value:v));setSpec(null);}}>{Object.entries(neonatalStageLabels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
                  <button type="button" disabled={index===0} onClick={()=>{const stages=[...neonatalStages];[stages[index-1],stages[index]]=[stages[index],stages[index-1]];setNeonatalStages(stages);setSpec(null);}}>Move up</button>
                  <button type="button" disabled={neonatalStages.length<=2} onClick={()=>{setNeonatalStages(neonatalStages.filter((_,i)=>i!==index));setSpec(null);}}>Remove</button>
                </div>)}
                <button type="button" disabled={neonatalStages.length>=16} onClick={()=>{setNeonatalStages([...neonatalStages,'neo_post_handover']);setSpec(null);}}>Add stage</button>
                <label>Ventilation problem<select aria-label="Combined neonatal ventilation problem" value={neonatalVentProblem} onChange={e=>{setNeonatalVentProblem(e.target.value);setSpec(null);}}><option value="mask_leak">Mask leak</option><option value="airway_position">Airway position</option><option value="equipment">Equipment problem</option></select></label>
                <label>Advanced context<select aria-label="Combined neonatal advanced context" value={neonatalAdvancedContext} onChange={e=>{setNeonatalAdvancedContext(e.target.value);setSpec(null);}}><option value="persistent_bradycardia">Persistent severe bradycardia</option><option value="blood_loss">Suspected blood loss</option><option value="air_leak">Suspected air leak</option></select></label>
                <p>Choose 2–16 stages. Birth age cannot run backwards. Include a recovery/response stage before post-resuscitation assessment and assessment before handover. Stages never advance automatically.</p>
              </>:subtopic==='Post-resuscitation stabilisation'?<>
                <label>Stabilisation focus<select aria-label="Neonatal stabilisation focus" value={neonatalPostFocus} onChange={e=>{setNeonatalPostFocus(e.target.value);setSpec(null);}}><option value="assessment">Initial post-resuscitation assessment</option><option value="respiratory">Ongoing respiratory compromise</option><option value="perfusion">Persistent poor perfusion</option><option value="temperature">Low temperature</option><option value="neurometabolic">Neurological / glucose assessment</option></select></label>
                <p>Faculty selects recurrent deterioration, stabilisation or monitored handover. Glucose and neurological findings are entered and revealed through Patient assessment, not inferred from monitor values. No automated cooling or drug response.</p>
              </>:subtopic==='Advanced neonatal resuscitation'?<>
                <label>Clinical context<select aria-label="Advanced neonatal context" value={neonatalAdvancedContext} onChange={e=>{setNeonatalAdvancedContext(e.target.value);setSpec(null);}}><option value="persistent_bradycardia">Persistent severe bradycardia</option><option value="blood_loss">Suspected blood loss</option><option value="air_leak">Suspected air leak</option></select></label>
                <label>Entry stage<select aria-label="Advanced neonatal entry" value={neonatalAdvancedEntry} onChange={e=>{setNeonatalAdvancedEntry(e.target.value);setSpec(null);}}><option value="escalation">HR below 60 after effective ventilation</option><option value="ongoing_resuscitation">Ongoing coordinated resuscitation</option></select></label>
                <p>All cases are critical; difficulty changes coaching, not severity. Intrinsic HR is not compression rate. Drug/procedure responses and progression require faculty confirmation; no dose calculator or compression waveform is simulated.</p>
              </>:subtopic==='Ventilation support'?<>
                <label>Initial ventilation state<select aria-label="Initial neonatal ventilation" value={neonatalVentCourse} onChange={e=>{setNeonatalVentCourse(e.target.value);setSpec(null);}}><option value="apnoea">Apnoea — ventilation required</option><option value="ineffective">Attempted ventilation ineffective</option></select></label>
                <label>Faculty teaching problem<select aria-label="Neonatal ventilation problem" value={neonatalVentProblem} onChange={e=>{setNeonatalVentProblem(e.target.value);setSpec(null);}}><option value="mask_leak">Mask leak</option><option value="airway_position">Airway position / patency</option><option value="equipment">Device / circuit problem</option></select></label>
                <p>Effective assisted ventilation, recovery and persistent severe bradycardia are faculty-selected branches. Effective ventilation rate is not attempted bag cadence. No device or pressure/volume simulation.</p>
              </>:<label>Initial transition<select aria-label="Initial neonatal transition" value={neonatalCourse} onChange={e=>{setNeonatalCourse(e.target.value);setSpec(null);}}><option value="vigorous">Vigorous — regular breathing and good tone</option><option value="poor_transition">Poor transition — ineffective breathing and reduced tone</option></select></label>}
              <p>Case age is specified by the selected state, not a recommendation to delay support. Faculty selects later stages; session time is not age since birth. Birth setting overrides the general ward label. All neonatal modules are independent teaching pilots requiring faculty review.</p>
            </div>}
            {programme==='ALSO'&&['Maternal collapse','Other obstetric emergencies'].includes(subtopic)&&packReady&&<div>
              <h3>{subtopic}</h3>
              {subtopic==='Other obstetric emergencies'&&<label>Emergency<select aria-label="Obstetric emergency" value={obstetricEmergencyKind} onChange={e=>{setObstetricEmergencyKind(e.target.value);setSpec(null);}}>
                <option value="sepsis">Maternal sepsis</option><option value="cord_prolapse">Umbilical cord prolapse</option><option value="shoulder_dystocia">Shoulder dystocia</option>
              </select></label>}
              {(subtopic==='Maternal collapse'||obstetricEmergencyKind==='sepsis')&&<label>Context<select aria-label="Maternal context" value={maternalContext} onChange={e=>{setMaternalContext(e.target.value);setSpec(null);}}>
                <option value="antenatal">Antenatal — 34 weeks</option><option value="postpartum">24 hours postpartum</option>
              </select></label>}
              {subtopic==='Maternal collapse'&&<>
                <label>Initial severity<select aria-label="Maternal collapse entry" value={maternalEntry} onChange={e=>{setMaternalEntry(e.target.value);setSpec(null);}}><option value="deteriorating">Severe deterioration — pulse present</option><option value="arrest">Cardiac arrest — initially PEA</option></select></label>
                <label>Faculty cause hypothesis<select aria-label="Maternal collapse cause" value={maternalCause} onChange={e=>{setMaternalCause(e.target.value);setSpec(null);}}><option value="undifferentiated">Undifferentiated</option><option value="haemorrhage">Suspected haemorrhage</option><option value="embolism">Suspected embolic cause</option><option value="anaesthetic">Possible anaesthetic complication</option></select></label>
              </>}
              <label>Care setting<select aria-label="Maternal emergency setting" value={maternalSetting} onChange={e=>{setMaternalSetting(e.target.value);setSpec(null);}}><option value="maternity">Maternity / delivery suite</option><option value="emergency">Emergency department</option><option value="theatre">Obstetric theatre</option><option value="critical_care">Critical care</option></select></label>
              <p>Independent faculty-reviewed teaching pilot. Delivery emergencies use an intrapartum 39-week case. Fetal findings and procedures are faculty-described; no CTG or delivery-mechanics simulator. Maternal readings cannot establish fetal wellbeing. Progression and ROSC require instructor confirmation.</p>
            </div>}
            {programme==='ALSO'&&subtopic==='Hypertensive emergencies'&&packReady&&<div>
              <h3>Maternal hypertensive emergencies</h3>
              <label>Clinical context<select aria-label="Maternal hypertension context" value={obstetricHtContext} onChange={e=>{setObstetricHtContext(e.target.value);setSpec(null);}}><option value="antenatal">Antenatal — 34 weeks pregnant</option><option value="postpartum">Postpartum — 24 hours after birth</option></select></label>
              <label>Presentation<select aria-label="Maternal hypertension presentation" value={obstetricHtEntry} onChange={e=>{setObstetricHtEntry(e.target.value);setSpec(null);}}><option value="severe_hypertension">Severe hypertension</option><option value="warning_signs">Hypertension with concerning symptoms</option><option value="eclampsia">Convulsion — suspected eclampsia</option></select></label>
              <label>Care setting<select aria-label="Maternal hypertension setting" value={obstetricHtSetting} onChange={e=>{setObstetricHtSetting(e.target.value);setSpec(null);}}><option value="maternity">Maternity assessment / delivery unit</option><option value="emergency">Emergency department</option><option value="critical_care">Obstetric critical care</option></select></label>
              <p>Faculty-selected convulsion, respiratory deterioration and recovery branches. No automatic drug effect, seizure animation or fetal monitor. Maternal assessment and clinical review are required.</p>
            </div>}
            {programme==='ALSO'&&subtopic==='Obstetric haemorrhage'&&packReady&&<div>
              <h3>Postpartum haemorrhage — independent teaching pilot</h3>
              <label>Maternal care setting<select aria-label="Obstetric setting" value={obstetricSetting} onChange={e=>{setObstetricSetting(e.target.value);setSpec(null);}}><option value="delivery_suite">Delivery suite</option><option value="postnatal_ward">Postnatal ward</option><option value="theatre">Obstetric theatre — after caesarean</option><option value="emergency">Emergency department transfer</option></select></label>
              <label>Suspected cause<select aria-label="Postpartum bleeding cause" value={obstetricCause} onChange={e=>{setObstetricCause(e.target.value);setSpec(null);}}><option value="tone">Tone — suspected atony</option><option value="trauma">Trauma — genital tract injury</option><option value="tissue">Tissue — placental concern</option><option value="thrombin">Thrombin — coagulation concern</option></select></label>
              <label>Initial clinical severity<select aria-label="Postpartum haemorrhage severity" value={obstetricSeverity} onChange={e=>{setObstetricSeverity(e.target.value);setSpec(null);}}><option value="maintained">Bleeding with maintained blood pressure</option><option value="hypotensive">Hypotension and poor perfusion</option><option value="critical">Critical ongoing haemorrhage — pulse present</option></select></label>
              <p>Fictional 28-year-old, 70 kg patient, 30 minutes postpartum. Severity is independent of difficulty. Faculty confirms cause and response; no automatic drug/transfusion effects or licensed course content. Obstetric setting overrides the general ward label.</p>
            </div>}
            {programme === 'TLS' ? <div>
              <h3>Adult trauma — {subtopic} pilot</h3>
              <p>Fictional 35-year-old, 70 kg adult. Unavailable trauma topics remain draft.</p>
              {subtopic === 'Transfer and reassessment' ? <>
                <label htmlFor="transfer-profile">Transfer case</label>
                <select id="transfer-profile" value={transferProfile} onChange={e=>{setTransferProfile(e.target.value);setSpec(null);}}>
                  <option value="bleeding">Pelvic injury — ongoing bleeding risk</option><option value="head_injury">Head injury — persistent neurological impairment</option>
                </select>
                <label htmlFor="transfer-phase">Starting phase</label>
                <select id="transfer-phase" value={transferPhase} onChange={e=>{setTransferPhase(e.target.value);setSpec(null);}}>
                  <option value="preparation">Preparation and risk review</option><option value="deterioration">Deterioration during preparation</option>
                </select>
                <p>Faculty supplies destination, escort and transport resources. This teaching case does not provide automatic transfer clearance or contact a receiving facility.</p>
              </> : subtopic === 'Multisystem trauma' ? <>
                <label htmlFor="multisystem-focus">Starting phase — head, right chest and pelvic injuries</label>
                <select id="multisystem-focus" value={multisystemFocus} onChange={e=>{setMultisystemFocus(e.target.value);setSpec(null);}}>
                  <option value="initial">Initial assessment of multiple injuries</option>
                  <option value="respiratory">Chest compromise with shock</option>
                  <option value="circulatory">Persistent shock after chest support</option>
                  <option value="neurological">Neurological deterioration after physiological support</option>
                </select>
                <p>One patient, sequential instructor-selected phases. Later starts assume the prior support described in the case; normalised vital signs do not establish neurological recovery.</p>
              </> : subtopic === 'Head injury' ? <>
                <label htmlFor="head-injury-course">Initial head-injury presentation</label>
                <select id="head-injury-course" value={headInjuryCourse} onChange={e=>{setHeadInjuryCourse(e.target.value);setSpec(null);}}>
                  <option value="observation">Confusion after injury — initial assessment</option>
                  <option value="neurological_deterioration">Neurological deterioration with maintained vital signs</option>
                  <option value="secondary_insult">Reduced consciousness with hypoxaemia and hypotension</option>
                </select>
                <p>Instructor supplies serial GCS components and pupil findings. Normal monitor values do not exclude intracranial injury or prove neurological recovery.</p>
              </> : subtopic === 'Airway and chest injury' ? <>
                <label htmlFor="trauma-injury">Airway/chest case</label>
                <select id="trauma-injury" value={traumaInjury} onChange={e=>{setTraumaInjury(e.target.value);setSpec(null);}}>
                  <option value="airway">Facial trauma — threatened airway</option><option value="tension">Suspected tension pneumothorax</option><option value="haemothorax">Suspected major haemothorax</option>
                </select>
                <label htmlFor="trauma-chest-severity">Starting state</label>
                <select id="trauma-chest-severity" value={traumaChestSeverity} onChange={e=>{setTraumaChestSeverity(e.target.value);setSpec(null);}}>
                  <option value="initial">Initial compromise — urgent assessment</option><option value="deteriorating">Worsening respiratory/circulatory compromise</option>
                </select>
                <p>Both starting states require urgent assessment. Chest examination findings are disclosed by the instructor, not encoded by the waveform.</p>
              </> : <>
              <label htmlFor="trauma-mechanism">Injury context</label>
              <select id="trauma-mechanism" value={traumaMechanism} onChange={e=>{setTraumaMechanism(e.target.value);setSpec(null);}}>
                <option value="external">Limb injury — external bleeding</option><option value="pelvic">Road collision — suspected pelvic bleeding</option><option value="abdominal">Blunt injury — suspected abdominal bleeding</option>
              </select>
              <label htmlFor="trauma-severity">Initial clinical severity</label>
              <select id="trauma-severity" value={traumaSeverity} onChange={e=>{setTraumaSeverity(e.target.value);setSpec(null);}}>
                <option value="compensated">Abnormal perfusion with maintained blood pressure</option><option value="hypotensive">Hypotension and poor perfusion</option>
              </select>
              </>}
              <p>Assess external life-threatening bleeding and ABCDE, reassess, then complete the secondary survey when appropriate. Instructor controls findings and progression; presets do not demonstrate treatment delivery.</p>
            </div> : programme === 'PALS' ? <div>
              <h3>Paediatric {subtopic} teaching pilot</h3>
              <label htmlFor="paediatric-profile">Patient profile</label>
              <select id="paediatric-profile" value={paediatricProfile} onChange={e=>{setPaediatricProfile(e.target.value);setSpec(null);}}>
                <option value="infant">Infant — 6 months, 7.5 kg</option><option value="child">Child — 5 years, 18 kg</option>
              </select>
              {paediatricMegacode ? <>
                <h4>Combined case sequence</h4>
                <label htmlFor="paediatric-mega-cause">Underlying shock context</label>
                <select id="paediatric-mega-cause" value={shockCause} onChange={e=>{setShockCause(e.target.value);setSpec(null);}}>
                  <option value="hypovolaemic">Fluid loss / hypovolaemia</option><option value="septic">Suspected infection / sepsis</option><option value="cardiogenic">Cardiogenic</option><option value="haemorrhagic">Haemorrhagic</option>
                </select>
                <p>Choose 2–16 stages. After arrest, add confirmed ROSC before any pulse-present stage. These are instructor-selected teaching transitions, not an automatic disease trajectory.</p>
                {paediatricMegaStages.map((stage,index)=><div key={index} style={{display:'flex',gap:6,marginBottom:6,flexWrap:'wrap'}}>
                  <label htmlFor={`paediatric-mega-${index}`}>Stage {index+1}</label>
                  <select id={`paediatric-mega-${index}`} value={stage} onChange={e=>{setPaediatricMegaStages(paediatricMegaStages.map((v,i)=>i===index?e.target.value:v));setSpec(null);}}>
                    {Object.entries(paediatricMegaLabels).map(([key,label])=><option key={key} value={key}>{label}</option>)}
                  </select>
                  <button type="button" disabled={index===0} onClick={()=>{const next=[...paediatricMegaStages];[next[index-1],next[index]]=[next[index],next[index-1]];setPaediatricMegaStages(next);setSpec(null);}}>Move up</button>
                  <button type="button" disabled={paediatricMegaStages.length<=2} onClick={()=>{setPaediatricMegaStages(paediatricMegaStages.filter((_,i)=>i!==index));setSpec(null);}}>Remove</button>
                </div>)}
                <button type="button" disabled={paediatricMegaStages.length>=16} onClick={()=>{setPaediatricMegaStages([...paediatricMegaStages,'stabilisation']);setSpec(null);}}>Add stage</button>
              </> : subtopic === 'Post-resuscitation care' ? <>
                <label htmlFor="paediatric-post-focus">Initial post-resuscitation problem — pulse present</label>
                <select id="paediatric-post-focus" value={paediatricPostFocus} onChange={e=>{setPaediatricPostFocus(e.target.value);setSpec(null);}}>
                  <option value="assessment">Initial assessment after return of circulation</option>
                  <option value="oxygenation">Persistent hypoxaemia</option>
                  <option value="ventilation">Inadequate ventilation</option>
                  <option value="perfusion">Hypotension and poor perfusion</option>
                </select>
                <p>Instructor-selected reassessment stages; improved vital signs do not establish neurological recovery.</p>
              </> : subtopic === 'Cardiac arrest' ? <>
                <label htmlFor="paediatric-arrest-context">Clinical context — all cardiac arrest is critical</label>
                <select id="paediatric-arrest-context" value={paediatricArrestContext} onChange={e=>{setPaediatricArrestContext(e.target.value);setSpec(null);}}>
                  <option value="respiratory">Respiratory deterioration</option><option value="shock">Shock-related deterioration</option><option value="sudden">Sudden witnessed collapse</option>
                </select>
                <label htmlFor="paediatric-arrest-rhythm">Optional initial rhythm override (faculty)</label>
                <select id="paediatric-arrest-rhythm" value={paediatricArrestRhythm} onChange={e=>{setPaediatricArrestRhythm(e.target.value);setSpec(null);}}>
                  <option value="">Use case default</option><option value="PEA">PEA</option><option value="ASYSTOLE">Asystole</option><option value="VF">VF</option><option value="PVT">Pulseless VT</option>
                </select>
                <p>Rhythm remains changeable during the session. An organised rhythm alone does not confirm ROSC.</p>
              </> : subtopic === 'Tachyarrhythmia' ? <>
                <label htmlFor="paediatric-tachy-pattern">Faculty teaching variant</label>
                <select id="paediatric-tachy-pattern" value={paediatricTachyPattern} onChange={e=>{setPaediatricTachyPattern(e.target.value);setSpec(null);}}>
                  <option value="sinus">Illness-associated sinus tachycardia</option><option value="narrow">Sudden-onset narrow-complex pattern</option><option value="wide">Wide-complex pattern with pulse</option>
                </select>
                <label htmlFor="paediatric-tachy-severity">Initial perfusion state</label>
                <select id="paediatric-tachy-severity" value={paediatricTachySeverity} onChange={e=>{setPaediatricTachySeverity(e.target.value);setSpec(null);}}>
                  <option value="maintained">Maintained perfusion</option><option value="compromise">Cardiopulmonary compromise</option>
                </select>
                <p>Rate alone is not diagnostic. ECG morphology is generic; precise paediatric interval interpretation is not validated.</p>
              </> : subtopic === 'Bradycardia' ? <>
                <label htmlFor="paediatric-brady-severity">Initial perfusion state</label>
                <select id="paediatric-brady-severity" value={paediatricBradySeverity} onChange={e=>{setPaediatricBradySeverity(e.target.value);setSpec(null);}}>
                  <option value="maintained">Slow pulse with maintained perfusion</option>
                  <option value="compromise">Bradycardia with respiratory and circulatory compromise</option>
                </select>
              </> : subtopic === 'Shock' ? <>
                <label htmlFor="shock-cause">Faculty case mechanism</label>
                <select id="shock-cause" value={shockCause} onChange={e=>{setShockCause(e.target.value);setSpec(null);}}>
                  {['hypovolaemic','septic','cardiogenic','haemorrhagic'].map(x=><option key={x} value={x}>{x}</option>)}
                </select>
                <label htmlFor="shock-severity">Initial severity</label>
                <select id="shock-severity" value={shockSeverity} onChange={e=>{setShockSeverity(e.target.value);setSpec(null);}}>
                  <option value="compensated">Compensated shock — maintained BP</option><option value="hypotensive">Hypotensive shock</option>
                </select>
              </> : <><label htmlFor="respiratory-severity">Respiratory severity</label>
              <select id="respiratory-severity" value={respiratorySeverity} onChange={e=>{setRespiratorySeverity(e.target.value);setSpec(null);}}>
                <option value="distress">Respiratory distress</option><option value="failure">Respiratory failure</option>
              </select></>}
              <p>Profile-specific monitor values and teaching alarm limits. Regenerate older drafts before launching. Generic ECG morphology; faculty clinical review remains required.</p>
            </div> : megacode ? <div>
              <h3>Instructor-defined megacode sequence</h3>
              <p style={{fontSize:12}}>Choose 2–10 stages in order. Include explicit ROSC after arrest before any pulse-present stage. These are manual teaching presets, not automatic treatment responses.</p>
              {megaStages.map((stage,index)=><div key={index} style={{display:'flex',gap:6,marginBottom:6}}>
                <label htmlFor={`mega-${index}`}>{index+1}.</label>
                <select id={`mega-${index}`} value={stage} onChange={e=>{setMegaStages(megaStages.map((v,i)=>i===index?e.target.value:v));setSpec(null);}}>
                  {Object.entries(megaLabels).map(([key,label])=><option key={key} value={key}>{label}</option>)}
                </select>
                <button type="button" disabled={megaStages.length<=2} onClick={()=>{setMegaStages(megaStages.filter((_,i)=>i!==index));setSpec(null);}}>Remove</button>
              </div>)}
              <button type="button" disabled={megaStages.length>=10} onClick={()=>{setMegaStages([...megaStages,'arrest']);setSpec(null);}}>Add stage</button>
            </div> : ['Tachycardia','Bradycardia'].includes(subtopic) ? <div>
              <label htmlFor="tachy-severity">Initial clinical stability (pulse present)</label>
              <select id="tachy-severity" value={tachySeverity} onChange={e=>setTachySeverity(e.target.value)}>
                <option value="stable">Maintained perfusion — assess and investigate</option>
                <option value="unstable">Circulatory instability — urgent assessment</option>
              </select>
              <p style={{fontSize:12}}>{subtopic === 'Bradycardia' ? 'Assess whether the slow rate is causing poor perfusion, review reversible causes and escalate appropriately. A low rate alone does not establish instability.' : 'The ward determines the clinical context. Distinguish a primary arrhythmia from sinus tachycardia caused by another illness.'} The instructor can change rhythm and pulse during the session.</p>
            </div> : wardArrest ? <div>
              <label htmlFor="clinical-course">Clinical course (all arrest is critical)</label>
              <select id="clinical-course" value={clinicalSeverity} onChange={e=>setClinicalSeverity(e.target.value)}>
                <option value="arrest">Cardiac arrest → post-arrest reassessment</option>
                <option value="arrest_with_post_rosc_instability">Cardiac arrest → persistent post-ROSC instability</option>
              </select>
              <p style={{fontSize:12}}>The ward determines the initial case. The instructor can change any rhythm during resuscitation; an organised rhythm alone does not establish ROSC. Difficulty controls teaching support, not arrest severity.</p>
            </div> : <div>
              <label htmlFor="scenario-rhythm" style={{ display:'block', fontWeight:600 }}>Target rhythm / ECG pattern</label>
              <select id="scenario-rhythm" value={selectedRhythm} disabled={useOwnScenario || loading || subtopic !== 'Adult arrest and peri-arrest (existing prototype)'}
                onChange={e => { setSelectedRhythm(e.target.value); setSpec(null); }}
                style={{ width:'100%', padding:10, border:'1px solid #CBD5E1', borderRadius:8 }}>
                <option value="">Any rhythm — library selection</option>
                {Object.entries(rhythms).map(([key,label]) => <option key={key} value={key}>{label}</option>)}
              </select>
              <p style={{ fontSize:12, color:'#64748B' }}>Explicit rhythm drafts retain your ward and personnel. Difficulty changes teaching support; instructor clinical review is required. Custom text uses its own rhythm request.</p>
            </div>}
            <div>
              <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px" }}>Teaching Difficulty</label>
              <div style={{ display: "flex", gap: "10px" }}>
                {levels.map((lvl) => {
                  const active = selectedLevel === lvl;
                  const labelMap = { beginner: "Beg", intermediate: "Int", advanced: "Adv" };
                  const colorMap = { beginner: "#0F766E", intermediate: "#D97706", advanced: "#DC2626" };
                  return (
                    <button
                      key={lvl}
                      onClick={() => {setSelectedLevel(lvl);setSpec(null);}}
                      style={{
                        flex: 1,
                        padding: "10px 6px",
                        borderRadius: "10px",
                        border: active ? `2px solid ${colorMap[lvl]}` : "1px solid #E2E8F0",
                        background: active ? `${colorMap[lvl]}0A` : "#FFFFFF",
                        color: active ? colorMap[lvl] : "#64748B",
                        fontWeight: 600,
                        fontSize: "12px",
                        cursor: "pointer",
                        textTransform: "capitalize",
                        transition: "all 0.2s"
                      }}
                    >
                      {labelMap[lvl] || lvl}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Department Location */}
            <div>
              <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px" }}>Location / Department</label>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                {Object.entries(locations).map(([key, loc]) => {
                  const active = selectedLocation === key;
                  return (
                    <button
                      key={key}
                      onClick={() => setSelectedLocation(key)}
                      style={{
                        padding: "10px 8px",
                        borderRadius: "10px",
                        border: active ? "2px solid #0F766E" : "1px solid #E2E8F0",
                        background: active ? "#F0FDFA" : "#FFFFFF",
                        color: active ? "#0F766E" : "#64748B",
                        fontSize: "12px",
                        fontWeight: 500,
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                        transition: "all 0.2s",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis"
                      }}
                    >
                      <span>{loc.icon || "🏥"}</span>
                      <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{loc.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Speciality Dropdown */}
            <div>
              <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px" }}>Speciality</label>
              <div style={{ position: "relative" }}>
                <select
                  value={selectedSpeciality}
                  onChange={(e) => setSelectedSpeciality(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "10px 14px",
                    borderRadius: "10px",
                    border: "1px solid #E2E8F0",
                    background: "#FFFFFF",
                    color: "#0F172A",
                    fontSize: "13px",
                    outline: "none",
                    cursor: "pointer",
                    appearance: "none"
                  }}
                >
                  {Object.entries(specialities).map(([key, label]) => (
                    <option key={key} value={key} style={{ color: "#0F172A" }}>
                      {label}
                    </option>
                  ))}
                </select>
                <ChevronDown size={16} color="#64748B" style={{ position: "absolute", right: "12px", top: "13px", pointerEvents: "none" }} />
              </div>
            </div>

            {/* Disciplines Selection */}
            <div>
              <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px" }}>Speciality Disciplines</label>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {Object.entries(disciplines).map(([key, label]) => {
                  const active = selectedDisciplines.includes(key);
                  return (
                    <div
                      key={key}
                      onClick={() => handleToggleDiscipline(key)}
                      style={{
                        padding: "8px 12px",
                        borderRadius: "10px",
                        border: "1px solid #E2E8F0",
                        background: active ? "#F0FDFA" : "#FFFFFF",
                        color: active ? "#0F766E" : "#64748B",
                        fontSize: "12px",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        transition: "all 0.2s"
                      }}
                    >
                      <span style={{ fontWeight: active ? 600 : 500 }}>{label}</span>
                      <input
                        type="checkbox"
                        checked={active}
                        readOnly
                        style={{ accentColor: "#0F766E", width: "14px", height: "14px", cursor: "pointer" }}
                      />
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Use own scenario Toggle */}
            <div style={{ borderTop: "1px solid #F1F5F9", paddingTop: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContext: "space-between", justifyContent: "space-between", marginBottom: "8px" }}>
                <span style={{ fontSize: "12px", fontWeight: 600, color: "#64748B" }}>Use My Own Scenario</span>
                <label className="switch" style={{ position: "relative", display: "inline-block", width: "36px", height: "20px" }}>
                  <input
                    type="checkbox"
                    checked={useOwnScenario}
                    onChange={(e) => setUseOwnScenario(e.target.checked)}
                    style={{ opacity: 0, width: 0, height: 0 }}
                  />
                  <span style={{
                    position: "absolute",
                    cursor: "pointer",
                    top: 0, left: 0, right: 0, bottom: 0,
                    backgroundColor: useOwnScenario ? "#0F766E" : "#CBD5E1",
                    transition: ".3s",
                    borderRadius: "20px"
                  }}>
                    <span style={{
                      position: "absolute",
                      content: "",
                      height: "14px", width: "14px",
                      left: useOwnScenario ? "18px" : "3px",
                      bottom: "3px",
                      backgroundColor: "white",
                      transition: ".3s",
                      borderRadius: "50%"
                    }} />
                  </span>
                </label>
              </div>

              {useOwnScenario && (
                <textarea
                  placeholder="Describe your custom clinical scenario. AI will parse rhythm, checklist and demographics..."
                  value={customText}
                  onChange={(e) => setCustomText(e.target.value)}
                  style={{
                    width: "100%",
                    height: "80px",
                    padding: "10px",
                    borderRadius: "10px",
                    border: "1px solid #E2E8F0",
                    background: "#F8FAFC",
                    color: "#0F172A",
                    fontSize: "12px",
                    outline: "none",
                    resize: "none"
                  }}
                />
              )}
            </div>

            {/* Team details */}
            <div style={{ borderTop: "1px solid #F1F5F9", paddingTop: "16px" }}>
              <label style={{ display: "block", fontSize: "11px", fontWeight: 600, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px" }}>Team Name</label>
              <input
                type="text"
                placeholder="e.g. ER Resus Team"
                value={teamName}
                onChange={(e) => setTeamName(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  borderRadius: "10px",
                  border: "1px solid #E2E8F0",
                  background: "#F8FAFC",
                  color: "#0F172A",
                  fontSize: "13px",
                  outline: "none"
                }}
              />
            </div>

            {/* Generate Action Button */}
            <button
              onClick={handleGenerate}
              disabled={!packReady || loading || (useOwnScenario && !customText.trim())}
              style={{
                width: "100%",
                padding: "12px",
                borderRadius: "12px",
                border: "none",
                background: "linear-gradient(135deg, #0F766E, #0D9488)",
                color: "#FFFFFF",
                fontWeight: 700,
                fontSize: "13px",
                cursor: "pointer",
                boxShadow: "0 2px 6px rgba(15, 118, 110, 0.2)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
                transition: "all 0.2s"
              }}
            >
              {loading ? "Generating..." : "Generate Scenario"}
            </button>
          </div>

          {/* Right Preview Panel */}
          <div style={{
            backgroundColor: "#FFFFFF",
            border: "1px solid #E2E8F0",
            borderRadius: "16px",
            padding: "32px",
            boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.05)",
            display: "flex",
            flexDirection: "column",
            justifyContent: spec ? "flex-start" : "center",
            alignItems: spec ? "stretch" : "center",
            minHeight: "560px"
          }}>
            {!spec ? (
              <div style={{ textAlign: "center", maxWidth: "440px" }}>
                <div style={{
                  width: "72px",
                  height: "72px",
                  borderRadius: "50%",
                  background: "#F0FDFA",
                  border: "1px solid #CCFBF1",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  margin: "0 auto 20px"
                }}>
                  <Activity size={32} color="#0F766E" />
                </div>
                <h3 style={{ fontSize: "20px", fontWeight: 700, color: "#0F172A", marginBottom: "8px" }}>Scenario Studio</h3>
                <p style={{ fontSize: "13px", color: "#64748B", lineHeight: 1.6 }}>
                  Configure your scenario parameters on the left and click **Generate Scenario** to begin your simulation training.
                </p>
              </div>
            ) : (
              // Generated Scenario Specification Layout
              <div style={{ animation: "reveal 0.4s ease-out" }}>
                {/* Header Info */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "20px" }}>
                  <div>
                    <span style={{
                      fontSize: "10px",
                      fontWeight: 700,
                      color: "#0F766E",
                      background: "#F0FDFA",
                      border: "1px solid #CCFBF1",
                      padding: "4px 8px",
                      borderRadius: "6px",
                      textTransform: "uppercase",
                      letterSpacing: "0.5px"
                    }}>{spec.location_label || spec.location}</span>
                    <h2 style={{ fontSize: "24px", fontWeight: 800, color: "#0F172A", marginTop: "10px", marginBottom: "4px" }}>
                      {spec.title}
                    </h2>
                    <p style={{ fontSize: "13px", color: "#64748B", margin: 0, fontStyle: "italic" }}>
                      {spec.patient?.presentation}
                    </p>
                  </div>
                  <span style={{
                    fontSize: "10px",
                    fontWeight: 700,
                    color: spec.level === "advanced" ? "#DC2626" : spec.level === "intermediate" ? "#D97706" : "#0F766E",
                    background: spec.level === "advanced" ? "#FEE2E2" : spec.level === "intermediate" ? "#FEF3C7" : "#F0FDFA",
                    border: spec.level === "advanced" ? "1px solid #FCA5A5" : spec.level === "intermediate" ? "1px solid #FCD34D" : "1px solid #CCFBF1",
                    padding: "6px 12px",
                    borderRadius: "20px",
                    textTransform: "uppercase",
                    letterSpacing: "0.5px"
                  }}>{spec.level}</span>
                </div>

                {/* Patient Demographics Card */}
                <div style={{
                  background: "#F8FAFC",
                  border: "1px solid #E2E8F0",
                  borderRadius: "14px",
                  padding: "16px 20px",
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr 1fr",
                  gap: "16px",
                  marginBottom: "24px"
                }}>
                  <div>
                    <span style={{ display: "block", fontSize: "11px", color: "#64748B", marginBottom: "4px" }}>Age</span>
                    <span style={{ fontSize: "18px", fontWeight: 700, color: "#0F172A" }}>{spec.patient?.age} Years</span>
                  </div>
                  <div>
                    <span style={{ display: "block", fontSize: "11px", color: "#64748B", marginBottom: "4px" }}>Sex</span>
                    <span style={{ fontSize: "18px", fontWeight: 700, color: "#0F172A" }}>{spec.patient?.sex}</span>
                  </div>
                  <div>
                    <span style={{ display: "block", fontSize: "11px", color: "#64748B", marginBottom: "4px" }}>Weight</span>
                    <span style={{ fontSize: "18px", fontWeight: 700, color: "#0F172A" }}>{spec.patient?.weight_kg} kg</span>
                  </div>
                </div>

                {/* Clinical History */}
                <div style={{ marginBottom: "24px" }}>
                  <h4 style={{ fontSize: "11px", fontWeight: 600, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px" }}>Patient History</h4>
                  <p style={{ fontSize: "13px", color: "#334155", lineHeight: 1.5, background: "#F8FAFC", padding: "12px 16px", borderRadius: "10px", borderLeft: "3px solid #0F766E", margin: 0 }}>
                    {spec.patient?.history}
                  </p>
                </div>

                {/* Complications & Hints */}
                <TeachingPlan plan={spec.teaching_plan} />
                {((spec.complications && spec.complications.length > 0) || (spec.hints && spec.hints.length > 0)) && (
                  <div style={{ display: "grid", gridTemplateColumns: spec.complications?.length && spec.hints?.length ? "1fr 1fr" : "1fr", gap: "20px", marginBottom: "24px" }}>
                    {spec.complications?.length > 0 && (
                      <div>
                        <h4 style={{ fontSize: "11px", fontWeight: 600, color: "#DC2626", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px", display: "flex", alignItems: "center", gap: "6px" }}>
                          <AlertTriangle size={14} /> Complications
                        </h4>
                        <ul style={{ paddingLeft: "16px", margin: 0, color: "#475569", fontSize: "12px", lineHeight: 1.5 }}>
                          {spec.complications.map((comp, idx) => <li key={idx} style={{ marginBottom: "4px" }}>{comp}</li>)}
                        </ul>
                      </div>
                    )}
                    {spec.hints?.length > 0 && (
                      <div>
                        <h4 style={{ fontSize: "11px", fontWeight: 600, color: "#16A34A", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px" }}>Helpful Hints</h4>
                        <ul style={{ paddingLeft: "16px", margin: 0, color: "#475569", fontSize: "12px", lineHeight: 1.5 }}>
                          {spec.hints.map((hint, idx) => <li key={idx} style={{ marginBottom: "4px" }}>{hint}</li>)}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                {/* Resources Profile */}
                <div style={{ marginBottom: "24px" }}>
                  <h4 style={{ fontSize: "11px", fontWeight: 600, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "8px" }}>Resources Available</h4>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                    {Object.entries(spec.resources || {}).map(([key, val]) => {
                      if (typeof val !== "boolean") return null;
                      const labelMap = {
                        crash_cart: "Crash Cart",
                        defibrillator: "Defibrillator",
                        ventilator: "Ventilator",
                        advanced_airway: "Advanced Airway",
                        iv_access_ready: "IV Access"
                      };
                      return (
                        <span key={key} style={{
                          fontSize: "11px",
                          fontWeight: 500,
                          color: val ? "#16A34A" : "#DC2626",
                          background: val ? "#F0FDF4" : "#FEE2E2",
                          border: val ? "1px solid #BBF7D0" : "1px solid #FCA5A5",
                          padding: "6px 12px",
                          borderRadius: "8px",
                          display: "flex",
                          alignItems: "center",
                          gap: "6px"
                        }}>
                          {val ? "✓" : "✗"} {labelMap[key] || key}
                        </span>
                      );
                    })}
                  </div>
                </div>

                {/* Gamification Panel */}
                <div style={{
                  background: "linear-gradient(135deg, #F0FDFA, #FFFFFF)",
                  border: "1px solid #CCFBF1",
                  borderRadius: "14px",
                  padding: "18px 20px",
                  marginBottom: "24px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "12px"
                }}>
                  <div style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between"
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                      <Users size={20} color="#0F766E" />
                      <div>
                        <span style={{ display: "block", fontSize: "10px", color: "#64748B", textTransform: "uppercase", letterSpacing: "0.5px" }}>Target Team Size</span>
                        <span style={{ fontSize: "14px", fontWeight: 700, color: "#0F172A" }}>{spec.team_size ? `${spec.team_size} Members` : 'Confirm team headcount'}</span>
                      </div>
                    </div>

                    <div style={{ textAlign: "right" }}>
                      <span style={{ display: "block", fontSize: "10px", color: "#64748B", textTransform: "uppercase", letterSpacing: "0.5px" }}>Scenario Base Reward</span>
                      <span style={{ fontSize: "16px", fontWeight: 800, color: "#0F766E" }}>
                        +{spec.xp_reward || (spec.level === "advanced" ? 700 : spec.level === "intermediate" ? 400 : 200)} Base XP
                      </span>
                    </div>
                  </div>

                  <div style={{ fontSize: "11px", color: "#64748B", fontStyle: "italic", borderTop: "1px dashed #CCFBF1", paddingTop: "8px" }}>
                    * Actual XP earned is determined post-simulation based on clinical accuracy, speed, and protocol deviations.
                  </div>

                  {/* Possible Achievement Opportunities */}
                  <div style={{ paddingTop: "4px" }}>
                    <span style={{ display: "block", fontSize: "10px", fontWeight: 700, color: "#0F766E", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "6px" }}>
                      Achievement Opportunities
                    </span>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                      {spec.level === "advanced" && (
                        <span style={{ fontSize: "11px", backgroundColor: "#FEF2F2", color: "#991B1B", border: "1px solid #FCA5A5", padding: "2px 8px", borderRadius: "10px", fontWeight: 600 }}>
                          🔥 Advanced Operator
                        </span>
                      )}
                      <span style={{ fontSize: "11px", backgroundColor: "#FEF3C7", color: "#92400E", border: "1px solid #FCD34D", padding: "2px 8px", borderRadius: "10px", fontWeight: 600 }}>
                        ⭐ Perfect Performance (≥95%)
                      </span>
                      <span style={{ fontSize: "11px", backgroundColor: "#F0FDFA", color: "#0F766E", border: "1px solid #99F6E4", padding: "2px 8px", borderRadius: "10px", fontWeight: 600 }}>
                        ⚡ Rapid Responder
                      </span>
                      <span style={{ fontSize: "11px", backgroundColor: "#ECFDF5", color: "#047857", border: "1px solid #A7F3D0", padding: "2px 8px", borderRadius: "10px", fontWeight: 600 }}>
                        ✅ Zero Deviations
                      </span>
                    </div>
                  </div>
                </div>

                {/* Expected Action Checklist Accordion */}
                <div style={{ marginBottom: "28px", border: "1px solid #E2E8F0", borderRadius: "10px" }}>
                  <button
                    onClick={() => setShowChecklist(!showChecklist)}
                    style={{
                      width: "100%",
                      padding: "12px 16px",
                      background: "#F8FAFC",
                      border: "none",
                      color: "#0F172A",
                      fontSize: "13px",
                      fontWeight: 600,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      borderRadius: showChecklist ? "10px 10px 0 0" : "10px"
                    }}
                  >
                    <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <ClipboardList size={16} color="#0F766E" />
                      Expected Action Checklist
                    </span>
                    <span>{showChecklist ? "▲" : "▼"}</span>
                  </button>

                  {showChecklist && (
                    <div style={{ padding: "12px 16px", background: "#FFFFFF", borderTop: "1px solid #E2E8F0" }}>
                      {spec.checklist?.map((item, idx) => (
                        <div key={idx} style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          padding: "8px 0",
                          borderBottom: idx < spec.checklist.length - 1 ? "1px solid #F1F5F9" : "none",
                          fontSize: "12px",
                          color: "#334155"
                        }}>
                          <span style={{ display: "flex", alignItems: "center", gap: "6px", color: item.critical ? "#DC2626" : "#334155", fontWeight: item.critical ? 600 : 400 }}>
                            {item.critical ? "★" : "○"} {item.action}
                          </span>
                          <span style={{ fontSize: "11px", background: "#F1F5F9", padding: "2px 6px", borderRadius: "4px", color: "#64748B" }}>
                            {item.window_sec > 0 ? `< ${item.window_sec}s` : 'Instructor-reviewed timing'}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Simulation Action Buttons */}
                <p style={{ color: '#475569', fontSize: '13px' }}>Prebriefing is optional during development. Launch directly for testing, or choose team prebriefing.</p>
                {launchError && <p role="alert" style={{ color: '#B91C1C' }}>{launchError}</p>}
                <div style={{ display: "flex", gap: "16px", flexWrap: 'wrap' }}>
                  <button
                    onClick={handleLaunch}
                    disabled={launching || !launchReady}
                    style={{
                      flex: 1,
                      padding: "14px",
                      borderRadius: "12px",
                      border: "none",
                      background: "linear-gradient(135deg, #16A34A, #15803D)",
                      color: "#ffffff",
                      fontWeight: 700,
                      fontSize: "14px",
                      cursor: "pointer",
                      boxShadow: "0 2px 6px rgba(22, 163, 74, 0.2)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: "8px"
                    }}
                  >
                    <Play size={16} fill="currentColor" /> {launching ? 'Launching…' : 'Launch Scenario'}
                  </button>

                  <button onClick={handlePrebrief} disabled={launching || !launchReady}
                    style={{ padding: '14px 20px', borderRadius: '12px', border: '1px solid #CBD5E1', background: '#fff', color: '#0F766E', fontWeight: 600 }}>
                    Team Prebriefing (optional)
                  </button>

                  <button
                    onClick={handleNarrate}
                    disabled={narrating}
                    style={{
                      padding: "14px 20px",
                      borderRadius: "12px",
                      border: "1px solid #E2E8F0",
                      background: narrating ? "#F1F5F9" : "#FFFFFF",
                      color: "#0F766E",
                      fontWeight: 600,
                      fontSize: "13px",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: "8px"
                    }}
                  >
                    <Volume2 size={16} /> {narrating ? "Narrating..." : "Narrate Intro"}
                  </button>

                  <button
                    onClick={handleGenerate}
                    style={{
                      padding: "14px 20px",
                      borderRadius: "12px",
                      border: "1px solid #E2E8F0",
                      background: "#FFFFFF",
                      color: "#64748B",
                      fontWeight: 600,
                      fontSize: "13px",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: "8px"
                    }}
                  >
                    <RotateCcw size={16} /> Regenerate
                  </button>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>

      {/* Global settings or other modals */}
      <DashboardModals
        activeModal={activeModal}
        onClose={() => setActiveModal(null)}
        handleStartSimulation={() => navigate("/initializing")}
        initialSessions={[]}
      />
    </div>
  );
}
