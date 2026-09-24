/**
 * Speech recognition in the operator's language (TRD §11.2 Speech: en-IN, hi-IN, ta-IN), with
 * live partial words so the transcript sheet can show what is being heard. Uses the browser's
 * Web Speech API (Chrome); where it is missing the push-to-talk shows the calm error and every
 * voice action still has its big button. Injectable for tests.
 */
export const SPEECH_LANG: Record<string, string> = { en: "en-IN", hi: "hi-IN", ta: "ta-IN" };

type ResultEvent = {
  resultIndex: number;
  results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }>;
};

/** The small part of the Web Speech API used here. */
export type SpeechLike = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  onresult: ((e: ResultEvent) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};

export type SpeechCtor = new () => SpeechLike;

export function speechSupport(): SpeechCtor | null {
  const w = window as unknown as { SpeechRecognition?: SpeechCtor; webkitSpeechRecognition?: SpeechCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export type Heard = { final: string; pending: string };

export type Listener = {
  stop: () => void;
  abort: () => void;
};

/**
 * Start listening. `onHeard` gets the words so far (final + still-changing); `onDone` gets the
 * final transcript when recognition ends (empty if nothing was understood); `onError` gets the
 * browser's error code ("no-speech", "not-allowed", "network", …).
 */
export function listen(
  Ctor: SpeechCtor,
  language: string,
  onHeard: (h: Heard) => void,
  onDone: (text: string) => void,
  onError: (code: string) => void,
): Listener {
  const r = new Ctor();
  r.lang = SPEECH_LANG[language] ?? "en-IN";
  r.interimResults = true;
  r.continuous = true;
  r.maxAlternatives = 1;
  let final = "";
  let failed = false;
  r.onresult = (e) => {
    let pending = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const res = e.results[i]!;
      if (res.isFinal) final = `${final} ${res[0].transcript}`.trim();
      else pending = `${pending} ${res[0].transcript}`.trim();
    }
    onHeard({ final, pending });
  };
  r.onerror = (e) => {
    failed = true;
    onError(e.error);
  };
  r.onend = () => {
    if (!failed) onDone(final.trim());
  };
  r.start();
  return { stop: () => r.stop(), abort: () => r.abort() };
}
