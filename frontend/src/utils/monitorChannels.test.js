import { test } from 'node:test';
import assert from 'node:assert/strict';
import { channelEnabled, channelConfigured } from './monitorChannels.js';
import { studentVisible } from './studentDisplay.js';

test('legacy defaults and separate ABP/PAP overrides', () => {
  assert.equal(channelEnabled({show_ibp:false},'abp'),false);
  const state = {show_ibp:false,waveform_channels:{abp:true,pap:false}};
  assert.equal(channelEnabled(state,'abp'),true);
  assert.equal(channelEnabled(state,'pap'),false);
  assert.equal(channelConfigured({},'abp'),true);
  assert.equal(channelConfigured({show_ibp:false},'pap'),false);
  assert.equal(channelConfigured({show_ibp:false,configured_channels:{abp:true}},'abp'),true);
});
test('enabling an unconfigured channel neither fabricates availability nor reveals it', () => {
  const state = {waveform_channels:{pap:true},configured_channels:{pap:false},student_display:{pap_wave:false}};
  assert.equal(channelEnabled(state,'pap'),true);
  assert.equal(channelConfigured(state,'pap'),false);
  assert.equal(studentVisible(state,true,'pap_wave'),false);
  assert.equal(channelConfigured({etCO2:0,configured_channels:{co2:true}},'co2'),true);
});
