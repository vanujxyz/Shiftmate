/**
 * Who is signed in on this tablet, and the operator's display preferences (F-START-02).
 * Kept in localStorage so a reload keeps the operator signed in; the edge stays the authority:
 * if its snapshot says someone else (or nobody) is signed in, the shell sends the cab back to /start.
 * Storage can be missing (private window, blocked site data), so every access is guarded and the
 * app works without it.
 */
import type { Language } from "@shiftmate/contracts";
import type { Theme } from "@shiftmate/ui";
import { create } from "zustand";

export type SignedIn = { operatorId: string; machineId: string; name: string };

type Saved = { language: Language; theme: Theme; readAloud: boolean; signedIn: SignedIn | null };

const KEY = "shiftmate.cab.session";

const DEFAULTS: Saved = { language: "en", theme: "day", readAloud: true, signedIn: null };

function load(): Saved {
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? { ...DEFAULTS, ...(JSON.parse(raw) as Partial<Saved>) } : DEFAULTS;
  } catch {
    return DEFAULTS;
  }
}

function save(s: Saved): void {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(s));
  } catch {
    /* storage unavailable: preferences last for this page only */
  }
}

type SessionStore = Saved & {
  setLanguage: (language: Language) => void;
  setTheme: (theme: Theme) => void;
  setReadAloud: (on: boolean) => void;
  signIn: (s: SignedIn) => void;
  signOut: () => void;
};

export const useSession = create<SessionStore>((set, get) => {
  const update = (patch: Partial<Saved>) => {
    set(patch);
    const { language, theme, readAloud, signedIn } = { ...get(), ...patch };
    save({ language, theme, readAloud, signedIn });
  };
  return {
    ...load(),
    setLanguage: (language) => update({ language }),
    setTheme: (theme) => update({ theme }),
    setReadAloud: (readAloud) => update({ readAloud }),
    signIn: (signedIn) => update({ signedIn }),
    signOut: () => update({ signedIn: null }),
  };
});
