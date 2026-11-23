# Design tokens

The UI uses the Pipenzo "Flow look" tokens: black page, Flow-style alpha layers, one accent (Pipenzo yellow `#FECE02`), red only for danger. Dark is the primary design; the light block is the matching light theme. The operating system colour scheme (`prefers-color-scheme`) picks one.

## Source

`sheet_history/static/tokens.css` is a byte-for-byte copy of `extension/sidepanel/tokens.css` in `jortega0033/clip-to-reel-studio` at commit `a13378ce73e5b27213c9a200fc960ec93afef054` (2026-11-21). Its header comment holds the contrast numbers and a yellow rule that is narrower than the rules below (it lists yellow on the primary button, the current-step node and a few small marks, and does not list the current selection). The copy must stay identical to the source, so the comment is not edited here. Where the comment and this document differ, this document takes precedence.

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
- Yellow only on the primary action, the current-step marker and the current selection (UI rule 8 in `docs/ui-quality.md`; owner decision of 2026-11-23, see `docs/owner-decisions.md`).
- A current selection is a solid `--primary` fill with `--on-primary` text, not only a yellow border: a yellow border has about 1.5:1 against white on the light theme. It also carries a second sign that is not colour (weight, an icon or text) and the existing aria attribute (`aria-current` or `aria-selected`). Never a tint with a border of the same hue, and never a thick one-sided border.
- `--focus` is a focus indicator and is exempt from the accent limit, including where it is yellow in the dark theme. A ticket that says the focus style stays unchanged means the focus rule on `main` after the token pull request.
- Contrast and the no-colour-alone check cover both themes: the light block and the dark block of `tokens.css`.
- Text never sits on a bare alpha layer; use the opaque tokens.
- Page order: `tokens.css` loads before `app.css`.

## Light and dark

`tokens.css` defines the light theme in `:root` and the dark theme inside the `prefers-color-scheme: dark` media query. There is no theme switch in the page.

## Current state of the page

The page does not follow the selection rule yet. The selected project in the project list (`#project-list button[aria-current="true"]` in `app.css`) is still marked with a neutral colour (`--bg-sunken` and a bolder weight). The page follows in ticket work; this document does not claim it is done.
