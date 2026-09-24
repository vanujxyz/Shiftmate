# Milestone 16: Training hub

## What was built
- **Learn** (`/learn`, cab `screens/learn/`):
  - suggested lessons first, each with a plain reason such as "Suggested because: people close to the machine";
  - then every lesson with New or Done, its length and its format, each with an illustration;
  - My progress and Book an instructor are one tap away;
  - the Learn tab stays marked on lesson, booking and progress pages.
- **Lesson player** (D-095):
  - narrated cards are read aloud in the operator's language and move on by themselves, with Pause, Read again and Next;
  - then the quiz, where the right answer is marked and its reason spoken;
  - finishing saves the share of right answers, the time taken and the language to `/lessons/{id}/complete`.
- **Hazard drill** (D-096):
  - 7 scenes of 4 s each (5 hazards and 2 safe scenes);
  - tap STOP, or say "stop" in en/hi/ta;
  - each decision gets a verdict with the scene described;
  - results are shown as facts ("4 of 7 right decisions", "Average time to stop: 1.6 s") and saved to `/drills/results`.
- **Instructor booking:** 20 sessions at the site's Cat dealer training centre, each with its topic and seats left. Pick one, then Book this session. Full sessions and ones already booked say so.
- **Progress** (new `GET /training/progress`, D-094):
  - lessons finished out of 12;
  - days in a row;
  - drills over time;
  - the habits each finished lesson targets (times seen the week before vs this week);
  - booked sessions.
- **Pause-only offers** (D-097): a lesson offered by the gateway shows as a quiet card in Paused mode, with Start lesson and Not now. Going back to work removes it.
- **My Day:** an idea with a lesson now has "Open the lesson".
- **Illustrations** (D-098): 53 pictures drawn in the ui package from plan-view parts, all tested against the config.
- 75 new strings in en, hi and ta (`scripts/i18n/m16_learn.yaml`).

## Checked live (gateway and cab running, 1280 × 800)
- Learn listed 3 suggestions for Ravi (from proximity events) and all 12 lessons.
- "Keep the swing zone clear": cards, then the quiz (a wrong answer marked), finish, then "Saved to your progress".
- Booking: booked Friday 09:00, and the slot then showed "Booked" with 5 seats left.
- The drill ran all 7 scenes, and the result (4 of 7, 1.6 s) was saved.
- Progress showed 1 of 12, 1 day, the drill and the habit trend.
- The same pages in Tamil have no horizontal overflow.
- Fixed while checking:
  - drill and lesson times were shown in UTC and are now in site time;
  - a wrong STOP on a safe scene read "Missed" and now reads "Stopped, not needed".

## How to test
```
uv run --directory backend shiftmate edge
pnpm --filter cab dev
```
Load Ravi's shift, sign in with PIN 1001, then open Learn.
```
pnpm test:all
pnpm lint:all
pnpm e2e
```

## Tests run
- **Backend:** 258 pass, 2 of them new: the progress endpoint (privacy, facts, site time) and the streak and habit helpers.
- **Frontend:** 227 pass, 9 of them new:
  - Learn (8): suggestions and catalogue; cards → quiz → save; drill scoring with fake timers; booking; progress; offers and work clearing them; My Day → lesson; reason and stop words;
  - illustration coverage (1).
- **e2e:** 3 pass. Lint and typecheck are clean.
