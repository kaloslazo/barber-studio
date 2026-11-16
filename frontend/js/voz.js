const freshVoice = (() => {
  const KEY = "fresh-voz";
  const state = { last: "", at: 0, voice: null };
  const supported = "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;

  function stored() {
    try {
      return localStorage.getItem(KEY) !== "off";
    } catch (error) {
      return true;
    }
  }

  let on = stored();

  function pick() {
    if (!supported) return null;
    const spanish = speechSynthesis.getVoices().filter((voice) => (voice.lang || "").toLowerCase().startsWith("es"));
    const rank = (voice) => (/419|mx|us|pe|co|ar|cl/i.test(voice.lang) ? 0 : 1) + (voice.localService ? 0 : 0.5);
    return spanish.sort((a, b) => rank(a) - rank(b))[0] || null;
  }

  if (supported) {
    state.voice = pick();
    speechSynthesis.addEventListener("voiceschanged", () => {
      state.voice = pick();
    });
  }

  function say(text, { now = false, gap = 2800 } = {}) {
    if (!supported || !on || !text) return;
    const time = performance.now();
    if (!now) {
      if (speechSynthesis.speaking) return;
      if (time - state.at < gap) return;
      if (text === state.last && time - state.at < 7000) return;
    }
    speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    if (state.voice) utterance.voice = state.voice;
    utterance.lang = state.voice ? state.voice.lang : "es-419";
    utterance.rate = 1.05;
    state.last = text;
    state.at = time;
    speechSynthesis.speak(utterance);
  }

  let audio = null;

  function tone(frequency, start, length, volume, type = "sine") {
    const oscillator = audio.createOscillator();
    const gain = audio.createGain();
    oscillator.type = type;
    oscillator.frequency.setValueAtTime(frequency, start);
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(volume, start + 0.008);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + length);
    oscillator.connect(gain).connect(audio.destination);
    oscillator.start(start);
    oscillator.stop(start + length + 0.02);
  }

  function sound(kind, value = 0) {
    if (!on) return;
    const Context = window.AudioContext || window.webkitAudioContext;
    if (!Context) return;
    try {
      audio = audio || new Context();
      if (audio.state === "suspended") audio.resume();
      const now = audio.currentTime;
      if (kind === "tick") tone(520 + 640 * Math.min(1, Math.max(0, value)), now, 0.06, 0.05, "triangle");
      if (kind === "shot") tone(880, now, 0.05, 0.04, "triangle");
      if (kind === "chime") {
        tone(660, now, 0.35, 0.08);
        tone(990, now + 0.12, 0.5, 0.07);
      }
      if (kind === "error") {
        tone(220, now, 0.22, 0.07, "triangle");
        tone(165, now + 0.16, 0.3, 0.07, "triangle");
      }
    } catch (error) {
      audio = null;
    }
  }

  function stop() {
    if (supported) speechSynthesis.cancel();
  }

  function setOn(value) {
    on = Boolean(value);
    if (!on) stop();
    try {
      localStorage.setItem(KEY, on ? "on" : "off");
    } catch (error) {
      return;
    }
  }

  function bind(checkbox) {
    if (!checkbox) return;
    checkbox.checked = on && supported;
    checkbox.disabled = !supported;
    checkbox.addEventListener("change", () => {
      setOn(checkbox.checked);
      document.querySelectorAll("[data-voice-toggle]").forEach((other) => {
        if (other !== checkbox) other.checked = checkbox.checked;
      });
      if (checkbox.checked) say("Listo, te voy guiando con la voz", { now: true });
    });
  }

  return { say, stop, bind, sound, supported, get on() { return on && supported; } };
})();
