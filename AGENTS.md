# AGENTS.md

Working agreement for AI agents contributing to llmPEG (package name: `llmpeg`).

## What this project is

llmPEG — the *LLM Photo Expert Group*, punning on JPEG's Joint Photographic Experts Group. The
package, CLI, and artifact extension are all `llmpeg` (`.llmpeg.json`); the project was originally
called PromptPress, and early commits still carry that name.

A satirical meme — "compress your photos into an AI prompt and delete the originals" — built as a
real, measured prototype. A vision model encodes an image into a compact versioned JSON artifact;
an image generator later renders a **new** image from that text alone. The generator never sees the
source.

The project is **totally lossy** and says so everywhere. That honesty is the product, not a
disclaimer bolted on afterwards. See `vision.md` for the contract and `plan.md` for the delivery
plan.

## The one rule that matters

**Never overstate what the code does.** Every number in this repository must be traceable to a
file, a measurement, or a checked-in report. If you cannot point at the evidence, do not write the
claim.

Concretely:

- Do not invent compression ratios, quality scores, or test counts. Measure them and quote the
  measurement.
- Do not describe the reconstruct step as "decompression". There is no decompressor. `reconstruct`
  renders a text prompt; a separate generator invents a new image from it.
- When a result fails, say it failed. The flagship demo in `examples/` scores
  `"status": "fail"` on critical-text recall and that stays visible in the README.
- Never let the encoder silently drop content to make a ratio look better. Over-budget output must
  fail closed. This is enforced in `artifact.py`, not just documented.

## Media rule

Every benchmark, survey, and demo image added to this repository must be **freely licensed**
(CC0, public domain, or an explicit free licence). Before adding one, record its author, licence,
and source URL in the relevant manifest `credit` block — read from the source record, never
guessed. An image whose provenance you cannot verify does not go in.

The single existing exception is `media/newsArticle.jpg`, the third-party satirical image that
motivated the project. It is reproduced for commentary, is labelled as not free-licensed in the
README, and is not part of the benchmark set. Do not add a second exception.

## Repository layout

| Path | What lives there |
| --- | --- |
| `src/llmpeg/artifact.py` | Versioned artifact model, canonical JSON, profile byte budgets |
| `src/llmpeg/encoder.py` | Image → artifact encoding |
| `src/llmpeg/providers.py` | Ollama vision client and provider protocols |
| `src/llmpeg/evaluation.py` | Deterministic visual proxy metrics |
| `src/llmpeg/survey.py` | HTML survey report generation (embedded CSS/JS, `E501` exempt) |
| `src/llmpeg/cli.py` | `llmpeg` console entry point |
| `examples/` | The flagship news-article demo: artifact, prompt, reconstruction, evaluation |
| `survey/` | Reproduction surveys, sources, prompts, artifacts, results |
| `docs/architecture.md` | C4 diagrams, system context down to components |

## Commands

```bash
uv sync --extra dev
uv run llmpeg --help
```

Gates — all five must pass before a commit, and `.github/workflows/ci.yml` runs them on
Python 3.14 for every push and pull request:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest --cov=llmpeg --cov-report=term-missing --cov-fail-under=90
uv run python -m build
```

Current baseline: **46 tests, 93.5% branch coverage**. Update this line when it changes — a stale
self-measurement is the most embarrassing possible bug in a project about honest measurement.

## Testing

The suite is fully offline and injects fake providers via `tests/conftest.py`. Live Ollama calls
and image generation are manual demo steps, never test dependencies. Do not add a test that needs
the network, credentials, or a running model.

## Encoding behavior

- Default model `qwen3-vl:32b-ctx49k` over Ollama `/api/chat`, `OLLAMA_VISION_HOST`.
- Deterministic settings: temperature `0`, seed `42`, `/no_think`.
- Source images are never modified or deleted.
- Output files are never overwritten without `--overwrite`.
- Encoding uploads the full image to the configured endpoint. Treat that as a privacy boundary and
  keep it visible to the user.

## Commit messages

**Conventional Commits are required.** Format:

```
type(scope): imperative subject
```

- Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`.
- Subject in lowercase, imperative mood ("add", not "added" or "adds"), no trailing period,
  ideally under 72 characters.
- Use the body to explain **why** when the reason is not obvious from the diff.
- Keep commits atomic — one logical change each. The existing history is deliberately readable as
  a build story; preserve that.

Established scopes: `codec` (encoder/artifact/providers), `survey`, `architecture`, `docs`.

> Note: the first eight commits use `promptpress` as a scope for what later commits call `codec`.
> That was the project's original name, kept verbatim in history. Prefer `codec` going forward;
> the old commits are left as-is rather than rewritten for cosmetics.

## Git etiquette

- **Never push.** Not to `origin`, not to any branch, under any circumstance, unless the user
  explicitly asks in that message. The user handles all pushes, including force pushes.
- Commit locally and report what you committed.
- Do not create branches, tags, or remotes unless asked.
- Do not rewrite published history unless the user asks for it.

## Known issues

- The expanded scene benchmark is measured at `n=6`, not the planned `n=10`. Four cases
  (`kitchen-table`, `living-room`, `mountain-hikers`, `street-bicycles`) are encoded and have
  rendered prompts but no reconstruction, because generation is a manual adapter step.
- Those same four sources have no recorded Commons URL. They must be traced before publication —
  see the media rule above.
- Two measured cases (`train-platform`, `workspace-books`) have no OCR transcript, so they report
  `incomplete` rather than pass or fail.
