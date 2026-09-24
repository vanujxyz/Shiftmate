/**
 * Alert tones and spoken alerts in the browser (DESIGN §8).
 *
 * Tones sit at 1–3 kHz, where hearing is sharpest and cab noise is thinnest, and are told apart by
 * pitch pattern, not volume:
 *   critical (P1): three rising pulses 1400 → 1800 → 2400 Hz, 120 ms each, 60 ms apart
 *   urgent (P2):   two level pulses at 1600 Hz, 150 ms each, 100 ms apart
 *   confirm:       a falling pair 2400 → 1400 Hz, 150 ms each (after a P1 is acknowledged)
 *   listen_tick:   one short 880 Hz tick when push-to-talk starts listening
 *   error_tick:    a low double tick (440 Hz) when speech was not understood
 * Speech uses the operator's language (en-IN, hi-IN, ta-IN); if the tablet has no voice for it,
 * the English line is spoken instead and the words stay on screen.
 */
type Pulse = { hz: number; ms: number; gapMs: number };

const PATTERNS: Record<"critical_tone" | "urgent_tone" | "ack_confirm" | "listen_tick" | "error_tick", Pulse[]> = {
  critical_tone: [
    { hz: 1400, ms: 120, gapMs: 60 },
    { hz: 1800, ms: 120, gapMs: 60 },
    { hz: 2400, ms: 120, gapMs: 0 },
  ],
  urgent_tone: [
    { hz: 1600, ms: 150, gapMs: 100 },
    { hz: 1600, ms: 150, gapMs: 0 },
  ],
  ack_confirm: [
    { hz: 2400, ms: 150, gapMs: 0 },
    { hz: 1400, ms: 150, gapMs: 0 },
  ],
  listen_tick: [{ hz: 880, ms: 60, gapMs: 0 }],
  error_tick: [
    { hz: 440, ms: 70, gapMs: 70 },
    { hz: 440, ms: 70, gapMs: 0 },
  ],
};

let lastSpoken: { text: string; language: string; english: string } | null = null;

/** The last line said aloud, for "repeat" (F-ASK-04). */
export function repeatLast(): boolean {
  if (!lastSpoken) return false;
  speak(lastSpoken.text, lastSpoken.language, lastSpoken.english);
  return true;
}

const SPEECH_LANG: Record<string, string> = { en: "en-IN", hi: "hi-IN", ta: "ta-IN" };

let context: AudioContext | null = null;

export function playTone(name: keyof typeof PATTERNS): void {
  const Ctx = window.AudioContext;
  if (!Ctx) return;
  context ??= new Ctx();
  const ctx = context;
  let at = ctx.currentTime + 0.01;
  for (const p of PATTERNS[name]) {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "square"; // square-ish with odd harmonics, so it cuts through engine noise
    osc.frequency.value = p.hz;
    gain.gain.setValueAtTime(0.25, at);
    gain.gain.setValueAtTime(0, at + p.ms / 1000);
    osc.connect(gain).connect(ctx.destination);
    osc.start(at);
    osc.stop(at + p.ms / 1000);
    at += (p.ms + p.gapMs) / 1000;
  }
}

/** Speak `text` in `language`; fall back to `english` if there is no voice for the language. */
export function speak(text: string, language: string, english: string): void {
  lastSpoken = { text, language, english };
  const synth = window.speechSynthesis;
  if (!synth) return;
  const want = SPEECH_LANG[language] ?? "en-IN";
  const voices = synth.getVoices();
  const voice =
    voices.find((v) => v.lang === want) ?? voices.find((v) => v.lang.startsWith(want.slice(0, 2)));
  const utterance = new SpeechSynthesisUtterance(voice || language === "en" ? text : english);
  utterance.lang = voice ? voice.lang : "en-IN";
  if (voice) utterance.voice = voice;
  utterance.rate = 0.95; // slightly slower than conversation (DESIGN §8 pace)
  synth.cancel(); // a new alert line cuts off whatever was being said
  synth.speak(utterance);
}
