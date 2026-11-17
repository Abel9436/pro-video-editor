# What platforms measure

Read only for retention-style projects (shorts, reels, TikTok, YouTube long-form growth edits).

**Virality is a probability the edit can raise, never a guarantee.** Say so to the user. The descriptions below are third-party summaries from late 2026: treat them as starting points and re-check each platform's current creator guidance.

| Platform | First signal | Then | Edit implication |
|---|---|---|---|
| YouTube Shorts | Watch vs swipe away, decided in the opening seconds; each Short is tested on a small audience first | Retention, replays, engagement | Hook in the first second; a misleading hook that causes early swipes hurts distribution |
| TikTok | Completion rate and watch time | Rewatches, shares, saves, comments (shares and saves count more than likes) | Short as the story allows; loop endings; practical value worth saving |
| Instagram Reels | Retention and shares (similar to TikTok; verify current guidance) | Saves, sends via DM | Works muted: on-screen text in the first second |
| YouTube long-form | Click-through rate (title + thumbnail) | Average view duration, average percentage viewed | The first minute loses the most viewers and gets the most care; the opening confirms what the title and thumbnail promised |

## The shared rule
**Remove every reason to leave; add reasons to rewatch and share.**

## How the skill measures this
- virality_score.py: hook layers in the first second, first payoff time, dead air, longest stretch without a visual change, caption coverage, loop similarity; Claude's judged fields (emotion, STEPPS, promise kept) with one-line reasons. Pass at 70/100 (STARTING DEFAULT weights: hook 25, retention 25, payoff 15, captions 10, loop 10, judged 15).
- retention_sim.py: a predicted risk curve, second by second, with the reason for each dip. It is structural risk, not a forecast. Calibrate it per channel with `profile.py analytics`.
