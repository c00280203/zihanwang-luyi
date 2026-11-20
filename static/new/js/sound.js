/* Lightweight sound effects generated with the Web Audio API. */
(function () {
  let ctx = null;

  function enabled() {
    return localStorage.getItem("kh_sound") !== "off";
  }

  function audio() {
    if (!ctx) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return null;
      ctx = new Ctx();
    }
    return ctx;
  }

  function tone(freq, start, duration, type, volume) {
    const ac = audio();
    if (!ac) return;
    const osc = ac.createOscillator();
    const gain = ac.createGain();
    osc.type = type || "sine";
    osc.frequency.setValueAtTime(freq, ac.currentTime + start);
    gain.gain.setValueAtTime(0.0001, ac.currentTime + start);
    gain.gain.exponentialRampToValueAtTime(volume || 0.06, ac.currentTime + start + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, ac.currentTime + start + duration);
    osc.connect(gain).connect(ac.destination);
    osc.start(ac.currentTime + start);
    osc.stop(ac.currentTime + start + duration + 0.02);
  }

  const sounds = {
    click: function () { tone(520, 0, 0.09, "sine", 0.05); },
    success: function () {
      tone(523, 0, 0.12, "sine", 0.05);
      tone(659, 0.09, 0.12, "sine", 0.05);
      tone(784, 0.18, 0.16, "sine", 0.05);
    },
    error: function () { tone(180, 0, 0.2, "sawtooth", 0.04); },
    pop: function () { tone(720, 0, 0.07, "triangle", 0.05); }
  };

  function play(name) {
    if (!enabled() || !sounds[name]) return;
    try { sounds[name](); } catch (e) { /* audio not available */ }
  }

  window.Sound = { play: play };
})();
