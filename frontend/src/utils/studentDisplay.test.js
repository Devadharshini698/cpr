import test from 'node:test';
import assert from 'node:assert/strict';
import {DEFAULT_STUDENT_DISPLAY, studentVisible, displayedAlarms} from './studentDisplay.js';
test('students default to concealed; instructor remains complete',()=>{
  assert.equal(studentVisible({},true,'pap'),false);
  const state={student_display:{pap:false,pap_wave:false}};
  assert.equal(studentVisible(state,true,'pap'),false);
  assert.equal(studentVisible(state,false,'pap'),true);
  assert.equal(studentVisible(state,true,'abp'),false);
});
test('waveforms and numbers are independently selectable',()=>{
  const state={student_display:{...DEFAULT_STUDENT_DISPLAY, abp_wave:false, abp:true}};
  assert.equal(studentVisible(state,true,'abp_wave'),false);
  assert.equal(studentVisible(state,true,'abp'),true);
});
test('hidden measurements do not leak through alarm banner or sound',()=>{
  const state={alarms:['PAP_sys HIGH','HR LOW','DESAT'],student_display:{pap:false,spo2:false,hr:true,alarms:true}};
  assert.deepEqual(displayedAlarms(state,true),['HR LOW']);
  assert.equal(displayedAlarms(state,false).length,3);
  state.student_display.alarms=false;
  assert.deepEqual(displayedAlarms(state,true),[]);
});
