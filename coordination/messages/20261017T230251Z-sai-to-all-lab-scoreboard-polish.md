# Sai → all: Defense Lab "Who defends best?" redesign

- New headline row with three big numbers for the trained AI defender (attacks that reached their goal, uptime, steps to contain), each compared against a baseline. All values come from the bundle via `scoreboard()`.
- The metric cards are cleaner: one aligned row per defender (name, bar, value). The 95% range is a shaded band on the bar, with the numbers in small grey text after the value; "Best" is a soft pill.
- The trade-off note is now a quiet line with an info icon; the defender legend is a two-column list.
- e2e `honesty.spec.ts` now expects `7.1% 95% range 4.1–11.2%` (the range label is screen-reader text) and a `Best` pill instead of `★ best`.
- No data, contract or backend changes. Owner: Sai (frontend).
