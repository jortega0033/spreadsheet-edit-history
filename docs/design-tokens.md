# Design tokens

The UI uses the Pipenzo "Flow look" tokens: black page, Flow-style alpha layers, one accent (Pipenzo yellow `#FECE02`), red only for danger. Dark is the primary design; the light block is the matching light theme. The operating system colour scheme (`prefers-color-scheme`) picks one.

## Source

`sheet_history/static/tokens.css` is a byte-for-byte copy of `extension/sidepanel/tokens.css` in `jortega0033/clip-to-reel-studio` at commit `a13378ce73e5b27213c9a200fc960ec93afef054` (2026-11-21). Its header comment holds the contrast numbers and the usage rules.

## Resync

Copy the file over `sheet_history/static/tokens.css`. Nothing else. Do not edit the copy.

## Token names by role

- Surfaces: `--bg`, `--bg-raised`, `--surface`, `--bg-sunken`
- Text: `--fg`, `--muted`, `--faint`
- Lines: `--border`, `--hairline`, `--control-border`, `--input-border`
- Dark block (the top bar): `--ink`, `--on-ink`, `--on-ink-muted`, `--ink-border`
- Accent: `--primary`, `--primary-press`, `--on-primary`, `--primary-edge`
- Status: `--ok`, `--ok-bg`, `--warn-fg`, `--warn-bg`, `--danger`, `--danger-bg`, `--success`, `--info`
- Focus: `--focus`
- Alpha layers: `--glass*`, `--scrim`, `--state-hover`, `--state-selected`, `--btn-secondary*`
- Shadows, type, space, radius, motion: `--shadow-*`, `--font*`, `--space-*`, `--radius-*`, `--dur-*`, `--ease-*`

## Rules

- New UI uses these tokens. No new colour literals.
- Yellow only on the primary action and the current-step marker.
- Text never sits on a bare alpha layer; use the opaque tokens.
- Page order: `tokens.css` loads before `app.css`.

## Light and dark

`tokens.css` defines the light theme in `:root` and the dark theme inside the `prefers-color-scheme: dark` media query. There is no theme switch in the page.
