# AGENTS.md

Guidance for AI coding assistants (ChatGPT Codex, Claude Code, ...) working in this repo.
Product Development project of team 6 (University of Antwerp): software, hardware and UI for a Petoi Bittle robot dog.

Most team members are new to Git and use GitHub Desktop. Keep explanations simple, and answer in the language the user writes in (often Dutch).

## Golden rules (from [HOW-TO-GIT.md](HOW-TO-GIT.md))

1. **Never work on `main`.** Use a branch named `<role>/<task>` with lowercase letters and hyphens only,
   e.g. `sw/walking-script`, `hw/servo-calibration`, `ui/start-screen`, `docs/report-week-3`. No `+`, spaces or underscores.
2. **Stay in the user's own folder:** `hardware/`, `software/`, `ui/` or `docs/`.
   Before you edit or add files in another role's folder, stop and tell the user to ask that role first.
3. **Small Pull Requests.** One feature or fix per PR. If a task grows into several features, suggest splitting it.
4. **No secrets.** Never commit passwords, Wi-Fi credentials, API keys or personal data.
   Put them in a gitignored file (e.g. `wifi_secrets.h`) and commit an `*.example` version with placeholders.
5. **No large or generated files.** Never save screenshots, renders, videos, zips or other output into the repo.
   Put scratch files and screenshots in a temp folder outside the repo, never in a new folder inside the repo (like the old `Claude outputs/`).
   Images that belong in a report go in `docs/`; small CAD exports (a few MB) are fine.

## Git

- Don't commit, push or open PRs unless the user asks. Michael (git manager) reviews and merges every PR.
- When opening a PR, fill in the template in `.github/pull_request_template.md` (description, part, checklist).
- On a merge conflict or anything unexpected: stop and tell the user to ask Michael. Don't force-push or rewrite history.

## Project layout

| Folder | What | Owner |
|---|---|---|
| `hardware/` | Firmware/Arduino sketches (one sub-folder each), wiring, CAD exports | Hardware pair |
| `software/` | Code that controls the Bittle; see `software/INSTRUCTIES.md` | Software pair |
| `software/bittle-studio/` | 3D simulator + web UI; read `docs/developer-guide.md` before changing it | Software pair |
| `software/two-player-controller/` | Server + phone page to drive the dog with two phones | Software pair |
| `ui/` | Interface code and design exports | UI pair |
| `docs/` | Reports, meeting notes, research | Everyone |

## Testing

- Bittle Studio: run `software/bittle-studio/dev-tools/run-tests.cmd` (Windows) or `run-tests.sh` (Mac/Linux)
  before pushing, and add or update tests in `app/tests/` for new behaviour.
- When you change Bittle Studio, also update `software/bittle-studio/docs/developer-guide.md` if the change affects it.
- Logic that exists in more than one place (firmware, Python, JavaScript) must stay in sync. Change every copy, or better, keep one source.
