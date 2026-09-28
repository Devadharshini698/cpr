import { useEffect } from "react";
import audioEngine from "../engine/audioEngine";
import useMonitorStore from "../store/monitorStore";

const CRITICAL_ALARMS = ["APNEA", "DESAT"];

/** Drives the Web Audio alarm engine off real alarm state from the monitor store. */
export default function useAlarmAudio() {
  const alarms = useMonitorStore((s) => s.alarms) || [];

  useEffect(() => {
    audioEngine.init();
    const resumeOnGesture = () => audioEngine.resume();
    window.addEventListener("click", resumeOnGesture, { once: true });
    return () => window.removeEventListener("click", resumeOnGesture);
  }, []);

  useEffect(() => {
    const critical = alarms.some((a) => CRITICAL_ALARMS.includes(a));
    const warning = alarms.length > 0 && !critical;
    audioEngine.setCritical(critical);
    audioEngine.setWarning(warning);
  }, [alarms]);

  useEffect(() => {
    return () => {
      audioEngine.setCritical(false);
      audioEngine.setWarning(false);
    };
  }, []);
}
