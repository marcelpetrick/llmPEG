"""Generate a static, interactive quality-survey report."""

from __future__ import annotations

import html
import json
import statistics
from pathlib import Path
from typing import Any

from promptpress.artifact import Artifact, ArtifactError


def render_survey(manifest_path: Path) -> str:
    """Render a manifest and its local results as one portable HTML document."""
    manifest = _read_object(manifest_path)
    root = manifest_path.parent
    title = _string(manifest, "title")
    profile = _string(manifest, "profile")
    cases_value = manifest.get("cases")
    if not isinstance(cases_value, list) or not cases_value:
        raise ArtifactError("survey cases must be a non-empty array")

    cases: list[dict[str, Any]] = []
    for value in cases_value:
        if not isinstance(value, dict):
            raise ArtifactError("each survey case must be an object")
        case = dict(value)
        case_id = _string(case, "id")
        result = _read_object(root / _string(case, "result"))
        artifact_path = root / _string(case, "artifact")
        artifact = Artifact.read(artifact_path)
        prompt = (root / _string(case, "prompt")).read_text(encoding="utf-8")
        metrics = result.get("metrics")
        if not isinstance(metrics, dict):
            raise ArtifactError(f"survey result metrics missing for {case_id}")
        case["metrics"] = metrics
        case["status"] = _string(result, "status")
        case["artifact_bytes"] = len(artifact.to_bytes())
        case["source_bytes"] = artifact.source.byte_size
        case["ratio"] = artifact.source.byte_size / len(artifact.to_bytes())
        case["prompt_text"] = prompt
        baseline_result_path = case.get("baseline_result")
        if baseline_result_path is not None:
            if not isinstance(baseline_result_path, str) or not baseline_result_path:
                raise ArtifactError(f"survey baseline_result invalid for {case_id}")
            baseline_result = _read_object(root / baseline_result_path)
            baseline_metrics = baseline_result.get("metrics")
            if not isinstance(baseline_metrics, dict):
                raise ArtifactError(f"survey baseline metrics missing for {case_id}")
            case["baseline_metrics"] = baseline_metrics
        cases.append(case)

    visual_mean = statistics.fmean(_number(case["metrics"], "visual_proxy_score") for case in cases)
    layout_mean = statistics.fmean(_number(case["metrics"], "layout_score") for case in cases)
    palette_mean = statistics.fmean(_number(case["metrics"], "palette_distance") for case in cases)
    dhash_mean = statistics.fmean(_number(case["metrics"], "dhash_similarity") for case in cases)
    pass_count = sum(case["status"] == "pass" for case in cases)
    quality = "high" if visual_mean >= 0.75 else "moderate" if visual_mean >= 0.60 else "low"
    compared = [case for case in cases if "baseline_metrics" in case]
    comparison = ""
    if compared:
        baseline_mean = statistics.fmean(
            _number(case["baseline_metrics"], "visual_proxy_score") for case in compared
        )
        delta = visual_mean - baseline_mean
        comparison = (
            '<p class="comparison"><strong>Baseline → refined:</strong> mean visual proxy '
            f"{baseline_mean:.3f} → {visual_mean:.3f} ({delta:+.3f}). "
            "Use the three-way comparisons below to judge identity directly.</p>"
        )

    cards = "\n".join(_render_case(case) for case in cases)
    survey_ids = json.dumps([case["id"] for case in cases]).replace("</", "<\\/")
    return _page(
        title=title,
        date=_string(manifest, "date"),
        profile=profile,
        count=len(cases),
        pass_count=pass_count,
        quality=quality,
        visual_mean=visual_mean,
        layout_mean=layout_mean,
        palette_mean=palette_mean,
        dhash_mean=dhash_mean,
        comparison=comparison,
        cards=cards,
        survey_ids=survey_ids,
    )


def write_survey(manifest_path: Path, output_path: Path, *, overwrite: bool = False) -> None:
    """Write a rendered survey without overwriting by default."""
    if output_path.exists() and not overwrite:
        raise ArtifactError(f"refusing to overwrite existing file: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if overwrite else "x"
    with output_path.open(mode, encoding="utf-8") as stream:
        stream.write(render_survey(manifest_path))


def _render_case(case: dict[str, Any]) -> str:
    metrics = case["metrics"]
    credit = case.get("credit")
    if not isinstance(credit, dict):
        raise ArtifactError(f"survey credit missing for {case.get('id', 'unknown')}")
    case_id = html.escape(_string(case, "id"), quote=True)
    source = html.escape(_string(case, "source"), quote=True)
    reconstruction = html.escape(_string(case, "reconstruction"), quote=True)
    prompt = html.escape(_string(case, "prompt"), quote=True)
    result = html.escape(_string(case, "result"), quote=True)
    figures = (
        f'<figure><div class="image-frame"><img src="{source}" alt="Source: '
        f'{html.escape(_string(case, "name"), quote=True)}"></div><figcaption>Source</figcaption>'
        "</figure>"
    )
    baseline = case.get("baseline_reconstruction")
    if baseline is not None:
        if not isinstance(baseline, str) or not baseline:
            raise ArtifactError(f"survey baseline_reconstruction invalid for {case_id}")
        figures += (
            f'<figure><div class="image-frame"><img src="{html.escape(baseline, quote=True)}" '
            f'alt="Balanced baseline: {html.escape(_string(case, "name"), quote=True)}"></div>'
            "<figcaption>Balanced baseline</figcaption></figure>"
        )
    figures += (
        f'<figure><div class="image-frame"><img src="{reconstruction}" '
        f'alt="Prompt-only reconstruction: {html.escape(_string(case, "name"), quote=True)}">'
        "</div><figcaption>Refined prompt-only reconstruction</figcaption></figure>"
    )
    delta = ""
    if "baseline_metrics" in case:
        before = _number(case["baseline_metrics"], "visual_proxy_score")
        after = _number(metrics, "visual_proxy_score")
        delta = f'<p class="delta"><strong>Visual proxy change:</strong> {before:.3f} → {after:.3f} ({after - before:+.3f})</p>'
    delta_line = f"  {delta}\n" if delta else ""
    status = html.escape(str(case["status"]).lower(), quote=True)
    return f"""
<article class="case" id="{case_id}">
  <div class="case-head">
    <div><span class="eyebrow">CASE {case_id}</span><h2>{html.escape(_string(case, "name"))}</h2></div>
    <span class="status {status}">{html.escape(str(case["status"]).upper())}</span>
  </div>
  <div class="pair">{figures}</div>
  <div class="metrics">
    {_metric("Visual proxy", _number(metrics, "visual_proxy_score"), False)}
    {_metric("Layout", _number(metrics, "layout_score"), False)}
    {_metric("dHash", _number(metrics, "dhash_similarity"), False)}
    {_metric("Palette distance", _number(metrics, "palette_distance"), True)}
  </div>
{delta_line}  <p class="compression"><strong>{case["ratio"]:.1f}:1</strong> artifact ratio · {case["source_bytes"]:,} → {case["artifact_bytes"]:,} bytes</p>
  <details><summary>Prompt and machine-readable result</summary><pre>{html.escape(str(case["prompt_text"]))}</pre><p><a href="{prompt}">Prompt</a> · <a href="{result}">Evaluation JSON</a></p></details>
  <section class="questions" data-case="{case_id}">
    <h3>Your assessment</h3>
    {_rating(case_id, "subject", "Subject and action preserved")}
    {_rating(case_id, "composition", "Composition preserved")}
    {_rating(case_id, "appearance", "Color, lighting, and style preserved")}
    {_rating(case_id, "overall", "Overall semantic similarity")}
    <label class="comment">Optional note<textarea name="{case_id}-comment" rows="2" placeholder="What survived? What changed?"></textarea></label>
  </section>
  <p class="credit">Source: <a href="{html.escape(_string(credit, "source_url"), quote=True)}">{html.escape(_string(credit, "author"))}</a> · <a href="{html.escape(_string(credit, "license_url"), quote=True)}">{html.escape(_string(credit, "license"))}</a> · reconstruction generated from text only</p>
</article>"""


def _metric(label: str, value: float, lower_is_better: bool) -> str:
    width = (1 - value if lower_is_better else value) * 100
    return f"""<div class="metric"><span>{html.escape(label)}</span><strong>{value:.3f}</strong><div class="bar"><i style="width:{width:.1f}%"></i></div></div>"""


def _rating(case_id: str, dimension: str, label: str) -> str:
    name = f"{case_id}-{dimension}"
    buttons = "".join(
        f'<label><input type="radio" name="{name}" value="{score}"><span>{score}</span></label>'
        for score in range(1, 6)
    )
    return f'<fieldset><legend>{html.escape(label)}</legend><div class="scale">{buttons}</div><small>1 = not preserved · 5 = strongly preserved</small></fieldset>'


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ArtifactError(f"cannot read survey data {path}: {error}") from error
    if not isinstance(value, dict):
        raise ArtifactError(f"survey data root must be an object: {path}")
    return value


def _string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ArtifactError(f"survey field {key} must be a non-empty string")
    return value


def _number(data: dict[str, Any], key: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ArtifactError(f"survey metric {key} must be a number")
    return float(value)


def _page(**values: Any) -> str:
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>
:root{{--ink:#17202a;--muted:#667085;--paper:#f6f4ef;--card:#fff;--navy:#102a43;--blue:#2878b5;--mint:#32a071;--line:#ddd8ce}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 ui-sans-serif,system-ui,sans-serif}}header{{background:var(--navy);color:white;padding:64px max(24px,calc((100% - 1180px)/2)) 54px}}header p{{max-width:760px;color:#d9e7f2;font-size:1.08rem}}h1{{font-size:clamp(2.4rem,6vw,5rem);line-height:.98;margin:.2em 0}}main{{max-width:1180px;margin:auto;padding:36px 24px 72px}}.summary{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-top:-65px;margin-bottom:36px}}.summary div{{background:var(--card);padding:18px;border-radius:14px;box-shadow:0 8px 25px #102a4315}}.summary span,.eyebrow{{display:block;color:var(--muted);font-size:.73rem;font-weight:750;letter-spacing:.08em;text-transform:uppercase}}.summary strong{{font-size:1.65rem}}.finding{{border-left:5px solid var(--blue);padding:14px 20px;background:#eaf3f9;border-radius:0 10px 10px 0;margin:0 0 16px}}.comparison{{padding:14px 20px;background:#fff7d6;border-radius:10px;margin:0 0 36px}}.case{{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:24px;margin:24px 0;box-shadow:0 12px 35px #243b5310}}.case-head{{display:flex;justify-content:space-between;gap:20px;align-items:start}}h2{{margin:.15em 0 .7em;font-size:1.7rem}}.status{{background:#dff5e9;color:#17663f;border-radius:999px;padding:6px 12px;font-weight:800;font-size:.78rem}}.status.fail{{background:#fee2e2;color:#991b1b}}.status.incomplete{{background:#fff7d6;color:#854d0e}}.pair{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}}figure{{margin:0}}.image-frame{{background:#e8e6e0;aspect-ratio:4/3;border-radius:12px;overflow:hidden;display:flex;align-items:center;justify-content:center}}img{{width:100%;height:100%;object-fit:contain}}figcaption{{font-weight:750;padding:7px 2px}}.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:18px 0}}.metric{{font-size:.82rem}}.metric strong{{float:right}}.bar{{height:7px;background:#e8e9eb;border-radius:9px;clear:both;overflow:hidden;margin-top:6px}}.bar i{{display:block;height:100%;background:var(--mint)}}.compression,.delta{{color:var(--muted)}}details{{border-top:1px solid var(--line);padding-top:13px}}summary{{cursor:pointer;font-weight:700}}pre{{white-space:pre-wrap;background:#101b26;color:#e7edf2;padding:16px;border-radius:10px;max-height:340px;overflow:auto}}a{{color:#176b9c}}.questions{{margin-top:20px;background:#f8fafb;border-radius:14px;padding:18px}}h3{{margin-top:0}}fieldset{{border:0;padding:0;margin:15px 0}}legend{{font-weight:650}}.scale{{display:flex;gap:7px;margin-top:7px}}.scale input{{position:absolute;opacity:0}}.scale span{{display:grid;place-items:center;width:38px;height:34px;border:1px solid #b9c2ca;border-radius:8px;cursor:pointer;background:white}}.scale input:checked+span{{background:var(--blue);color:white;border-color:var(--blue)}}small{{color:var(--muted)}}.comment{{display:grid;gap:6px;font-weight:650}}textarea{{font:inherit;padding:9px;border:1px solid #b9c2ca;border-radius:8px}}.credit{{font-size:.78rem;color:var(--muted);margin-bottom:0}}.actions{{position:sticky;bottom:12px;display:flex;gap:10px;justify-content:center;margin-top:30px}}button{{border:0;border-radius:999px;padding:12px 20px;font-weight:750;cursor:pointer;background:var(--navy);color:white}}button.secondary{{background:white;color:var(--navy);border:1px solid var(--line)}}footer{{color:var(--muted);font-size:.85rem;margin-top:36px}}@media(max-width:800px){{.summary{{grid-template-columns:repeat(2,1fr);margin-top:-45px}}.pair,.metrics{{grid-template-columns:1fr}}header{{padding-top:42px}}}}
</style></head><body><header><span class="eyebrow">EXPLORATORY BENCHMARK · {date}</span><h1>{title}</h1><p>Can a compact semantic description preserve what matters in a photograph? {count} public-domain cat images were encoded with the same vision model and <code>{profile}</code> profile, then reconstructed by Codex image generation from text alone.</p></header><main>
<section class="summary"><div><span>Cases passed</span><strong>{pass_count}/{count}</strong></div><div><span>Mean visual proxy</span><strong>{visual_mean:.3f}</strong></div><div><span>Mean layout</span><strong>{layout_mean:.3f}</strong></div><div><span>Mean palette distance</span><strong>{palette_mean:.3f}</strong></div><div><span>Mean dHash</span><strong>{dhash_mean:.3f}</strong></div></section>
<p class="finding"><strong>Finding: {quality} semantic quality.</strong> {pass_count}/{count} cases meet the <code>{profile}</code> proxy thresholds; mean dHash is {dhash_mean:.3f}. These structural metrics do not prove identity preservation, so inspect and rate each pair below. With n={count}, this is a product probe—not a population estimate.</p>
{comparison}
{cards}
<div class="actions"><button id="export">Export my ratings</button><button class="secondary" id="reset">Reset</button></div>
<footer><p><strong>Method.</strong> Sources were encoded by Ollama/Qwen3-VL into canonical PromptPress JSON. Each reconstruction used the resulting text prompt only. Metrics are deterministic structural proxies: dHash, RGB histogram, edge density, aspect ratio, and symmetric dominant-palette distance. They are not CLIP scores or human judgments. Ratings stay in this browser until exported.</p></footer></main>
<script>const ids={survey_ids},key="promptpress-cat-survey-v1";function collect(){{const out={{created_at:new Date().toISOString(),ratings:{{}}}};for(const id of ids){{const box=document.querySelector(`[data-case="${{id}}"]`),item={{}};box.querySelectorAll("input:checked").forEach(x=>item[x.name.slice(id.length+1)]=Number(x.value));item.comment=box.querySelector("textarea").value;out.ratings[id]=item}}return out}}function save(){{localStorage.setItem(key,JSON.stringify(collect()))}}document.addEventListener("change",save);document.addEventListener("input",save);try{{const old=JSON.parse(localStorage.getItem(key)||"null");if(old?.ratings)for(const [id,item] of Object.entries(old.ratings)){{for(const [field,value] of Object.entries(item)){{if(field==="comment")document.querySelector(`[name="${{id}}-comment"]`).value=value;else{{const input=document.querySelector(`[name="${{id}}-${{field}}"] [value="${{value}}"]`)||document.querySelector(`input[name="${{id}}-${{field}}"][value="${{value}}"]`);if(input)input.checked=true}}}}}}}}catch(e){{console.warn(e)}}document.getElementById("export").onclick=()=>{{const blob=new Blob([JSON.stringify(collect(),null,2)],{{type:"application/json"}}),a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="promptpress-survey-response.json";a.click();URL.revokeObjectURL(a.href)}};document.getElementById("reset").onclick=()=>{{localStorage.removeItem(key);document.querySelectorAll("input").forEach(x=>x.checked=false);document.querySelectorAll("textarea").forEach(x=>x.value="")}};</script></body></html>
""".format(**values)
