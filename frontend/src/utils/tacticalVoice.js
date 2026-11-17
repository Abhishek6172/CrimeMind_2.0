/**
 * Tactical AI Voice Synthesizer (Native Web Speech API)
 * Generates calm, synthetic, militaristic cybernetic voice announcements (JARVIS style).
 */

let voiceEnabled = true;

try {
  const saved = localStorage.getItem("cm_voice_enabled");
  if (saved !== null) {
    voiceEnabled = saved === "true";
  }
} catch {}

export const tacticalVoice = {
  isEnabled: () => voiceEnabled,

  setEnabled: (enabled) => {
    voiceEnabled = !!enabled;
    try {
      localStorage.setItem("cm_voice_enabled", String(voiceEnabled));
    } catch {}
    return voiceEnabled;
  },

  toggle: () => {
    voiceEnabled = !voiceEnabled;
    try {
      localStorage.setItem("cm_voice_enabled", String(voiceEnabled));
    } catch {}
    if (voiceEnabled) {
      tacticalVoice.speak("Tactical voice HUD online.");
    }
    return voiceEnabled;
  },

  speak: (text, priority = false) => {
    if (!voiceEnabled && !priority) return;
    if (typeof window === "undefined" || !window.speechSynthesis) return;

    try {
      // Cancel previous utterances if high priority
      if (priority) {
        window.speechSynthesis.cancel();
      }

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.05;
      utterance.pitch = 0.92;
      utterance.volume = 0.75;

      // Select an English voice if available
      const voices = window.speechSynthesis.getVoices();
      const preferred = voices.find(
        (v) =>
          (v.name.includes("Google") || v.name.includes("Natural") || v.name.includes("David") || v.name.includes("Samantha")) &&
          v.lang.startsWith("en")
      ) || voices.find((v) => v.lang.startsWith("en")) || voices[0];

      if (preferred) {
        utterance.voice = preferred;
      }

      window.speechSynthesis.speak(utterance);
    } catch {
      // Ignore voice policy errors
    }
  },

  // Tactical Announcement Presets
  announceCaseLoaded: (caseRef, title) => {
    tacticalVoice.speak(`Case ${caseRef.replace("-", " ")} loaded. Active investigation docket initialized.`);
  },

  announceInferenceStarted: (modelName = "YOLOv11") => {
    tacticalVoice.speak(`${modelName} neural surveillance pipeline dispatched.`);
  },

  announceInferenceCompleted: (tracksCount = 0) => {
    tacticalVoice.speak(`Surveillance inference complete. ${tracksCount} persistent tracks authenticated.`);
  },

  announceContradiction: (subjectName) => {
    tacticalVoice.speak(`Warning. Evidence contradiction flagged in statement of ${subjectName}.`, true);
  },

  announceOptics: (mode) => {
    tacticalVoice.speak(`Optics calibrated to ${mode.toUpperCase()} mode.`);
  },

  announceEmpReboot: () => {
    tacticalVoice.speak(`Electromagnetic pulse diagnostic initiated. System rebooting.`, true);
  },
};
