# Industrial Graphite design system

Industrial Graphite is a restrained dark interface system for Ari: near-black
graphite surfaces, hairline dividers, one oxidized-vermilion signal, Inter for
UI and display text, and IBM Plex Mono for code and metadata.

## Tokens

The source of truth is `frontend/app/tokens.css`, imported before the global
and interface stylesheets.

| Role | Tokens |
| --- | --- |
| Surfaces | `--surface-0` `#0B0B0D` canvas; `--surface-1` `#141416` panels; `--surface-2` `#1B1B1E` hover/secondary; `--surface-3` `#222225` selected/raised; `--code-bg` `#0F0F11` |
| Lines | `--line-1` `#232326` separators; `--line-2` `#36363A` control borders; `--line-3` `#4A4A4F` strong control borders |
| Ink | `--ink-1` `#F2F0EB` primary; `--ink-2` `#C9C7C2` secondary; `--ink-3` `#9A9A9F` muted; `--ink-4` `#808085` faint |
| Signal | `--signal` `#E5582F` primary vermilion; `--signal-deep` `#B8411F`; `--signal-soft` `#2A1510`; `--on-signal` `#0B0B0D` |
| Semantic | `--ok` `#3FA36B`, `--warn` `#D9A03F`, `--bad` `#E5484D`, `--info` `#9AA4B2` for actual status meaning only |
| Shape and elevation | `--radius-1` 2px, `--radius-2` 4px, `--radius-3` 6px; `--shadow-inset` for panels; `--shadow-pop` for menus/dialogs |
| Motion | `--dur-1` 120ms, `--dur-2` 200ms, `--dur-3` 360ms, `--dur-scene` 900ms; `--ease-out` and `--ease-inout` |
| Type | `--font-ui` Inter; `--font-code` IBM Plex Mono; `--text-*` scale from 11px to the responsive display size |

Tailwind utility names map to these variables in `globals.css` so existing
components can adopt the palette without changing their structure.

## Usage

- Use signal as the single brand accent for primary actions, focus, and
  navigation state. Do not use it as decoration on every panel.
- Semantic colors describe actual success, warning, failure, or informational
  state. Neutral content uses the ink and line tokens.
- Use `--radius-1` for rectangular status chips and tags, `--radius-2` for
  controls, and `--radius-3` for panels. Avatars remain round.
- Use the inset shadow only for restrained surface definition. Reserve the pop
  shadow for menus and dialogs.
- Use the shared 120/200/360 ms motion durations and the shared easing tokens.
  Respect `prefers-reduced-motion`; the global reduced-motion rule reduces
  transitions and animations to near-zero duration.
- Keep console surfaces flat. Do not add ambient orbs, grain, radial glows, or
  pointer-following panel effects.
- Keep paper sections on their neutral paper tokens so dark text remains
  readable; do not mix paper colors into graphite console surfaces.

## Assessment state vocabulary

Use these labels consistently in assessment and finding interfaces:

`FLAGGED` / `VALIDATED` / `INCONCLUSIVE` / `FAILED` / `FIX PROPOSED` / `VERIFIED`

These are display vocabulary only; they do not define or change backend state
transitions.
