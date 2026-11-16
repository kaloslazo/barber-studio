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

  return { say, stop, bind, supported, get on() { return on && supported; } };
})();
