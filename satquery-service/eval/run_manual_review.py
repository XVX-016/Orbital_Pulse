#!/usr/bin/env python3
"""
Live controller caller for manual review.

Calls route_and_execute() directly (same code path as POST /api/analyze)
for 10 selected real-benchmark items, using the available proxy images where
the original dataset images are absent.

Outputs a Markdown table to satquery-service/eval/manual_review.md.

Run from repo root:
    python satquery-service/eval/run_manual_review.py
"""

import os, sys, json, time

SERVICE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, SERVICE_DIR)

DATA_DIR = os.path.join(os.path.dirname(__file__), "benchmark_data")

# ── Available proxy images ────────────────────────────────────────────────────
AIRPORT   = os.path.join(DATA_DIR, "airport.jpg")   # roads, tarmac, structures
AGRI      = os.path.join(DATA_DIR, "agri.jpg")      # fields, farmland, rural
COASTAL   = os.path.join(DATA_DIR, "coastal.jpg")   # water, forest, hills
PORT      = os.path.join(DATA_DIR, "port.jpg")      # docks, urban waterfront

# ── 10 selected items (5 VRSBench + 5 RSVQA-LR) ─────────────────────────────
# Image proxy rationale noted per item.
ITEMS = [
    # ── VRSBench (vehicle/object-level VQA over aerial imagery) ──────────────
    {
        "id":          "vrs_real_0",
        "benchmark":   "VRSBench-Real",
        "task_type":   "object color",
        "question":    "What color are the large vehicles seen in the image?",
        "gt":          "Yellow",
        "proxy_img":   AIRPORT,
        "proxy_note":  "Airport tarmac with ground-service vehicles (closest available)",
    },
    {
        "id":          "vrs_real_1",
        "benchmark":   "VRSBench-Real",
        "task_type":   "object quantity",
        "question":    "How many small vehicles are visible in the image?",
        "gt":          "2",
        "proxy_img":   AIRPORT,
        "proxy_note":  "Airport tarmac (vehicles visible)",
    },
    {
        "id":          "vrs_real_2",
        "benchmark":   "VRSBench-Real",
        "task_type":   "object existence",
        "question":    "Is there a vehicle located at the top-most position in the provided image?",
        "gt":          "Yes",
        "proxy_img":   AIRPORT,
        "proxy_note":  "Airport tarmac (vehicles visible)",
    },
    {
        "id":          "vrs_real_5",
        "benchmark":   "VRSBench-Real",
        "task_type":   "object position",
        "question":    "What is the position of the large vehicle in the image?",
        "gt":          "middle-left",
        "proxy_img":   AIRPORT,
        "proxy_note":  "Airport tarmac (spatial reasoning test)",
    },
    {
        "id":          "vrs_real_12",
        "benchmark":   "VRSBench-Real",
        "task_type":   "object existence",
        "question":    "Are there any large vehicles that are positioned away from the main cluster?",
        "gt":          "yes",
        "proxy_img":   AIRPORT,
        "proxy_note":  "Airport tarmac (cluster vs isolated vehicles)",
    },
    # ── RSVQA-LR (scene-level classification over 10m satellite tile) ─────────
    {
        "id":          "rsvqa_lr_real_23208",
        "benchmark":   "RSVQA-LR-Real",
        "task_type":   "rural_urban",
        "question":    "Is it a rural or an urban area?",
        "gt":          "urban",
        "proxy_img":   AIRPORT,
        "proxy_note":  "Airport/city scene (clearly urban)",
    },
    {
        "id":          "rsvqa_lr_real_23209",
        "benchmark":   "RSVQA-LR-Real",
        "task_type":   "presence",
        "question":    "Is there a grass area?",
        "gt":          "yes",
        "proxy_img":   AGRI,
        "proxy_note":  "Agricultural field (green vegetation/grass present)",
    },
    {
        "id":          "rsvqa_lr_real_23211",
        "benchmark":   "RSVQA-LR-Real",
        "task_type":   "presence",
        "question":    "Is there a road?",
        "gt":          "yes",
        "proxy_img":   AIRPORT,
        "proxy_note":  "Airport scene with roads/taxiways",
    },
    {
        "id":          "rsvqa_lr_real_23213",
        "benchmark":   "RSVQA-LR-Real",
        "task_type":   "comp",
        "question":    "Are there less buildings than farmlands?",
        "gt":          "no",
        "proxy_img":   AIRPORT,
        "proxy_note":  "Urban/airport scene (buildings >> farmland)",
    },
    {
        "id":          "rsvqa_lr_real_23216",
        "benchmark":   "RSVQA-LR-Real",
        "task_type":   "presence",
        "question":    "Is a forest present in the image?",
        "gt":          "yes",
        "proxy_img":   COASTAL,
        "proxy_note":  "Coastal/forested scene (forest visible)",
    },
]


def main():
    print("=" * 70)
    print("SatQuery — Live Controller Manual Review Runner")
    print("=" * 70)

    print("\nInitializing GeoChat model engine ...")
    from geochat_engine import init_geochat_model, is_geochat_loaded
    ok = init_geochat_model()
    if not ok:
        print("[WARN] GeoChat engine could not be initialized — running in stub/fallback mode.")
    else:
        print("[OK] GeoChat engine loaded.")

    from controller import route_and_execute
    from PIL import Image

    records = []

    for idx, item in enumerate(ITEMS, 1):
        print(f"\n[{idx}/10] {item['id']}  ({item['task_type']})")
        print(f"  Q  : {item['question']}")
        print(f"  GT : {item['gt']}")
        print(f"  Img: {os.path.basename(item['proxy_img'])}  ({item['proxy_note']})")

        img = Image.open(item["proxy_img"]).convert("RGB")
        t0 = time.time()
        res = route_and_execute(images=[img], query=item["question"])
        elapsed = round(time.time() - t0, 1)

        answer = res.get("answer", "").strip()
        specialist = res.get("execution_trace", {}).get("specialist_used", "?")
        print(f"  A  : {answer}")
        print(f"  Specialist: {specialist}  |  {elapsed}s")

        records.append({**item, "answer": answer, "specialist": specialist, "latency": elapsed})

    # ── Write manual_review.md ────────────────────────────────────────────────
    out_path = os.path.join(os.path.dirname(__file__), "manual_review.md")
    _write_markdown(records, out_path)
    print(f"\n[Done] Report written to: {out_path}")


def _write_markdown(records, path):
    geochat_loaded_note = "GeoChat-7B (4-bit quantized)" if any(
        "vqa" in r["specialist"] or "grounding" in r["specialist"] for r in records
    ) else "GeoChat-7B stub (model not loaded at review time)"

    lines = []
    lines.append("# SatQuery — Manual Eyeball Review Report\n")
    lines.append(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M %Z')}\n")
    lines.append("\n## Methodology\n")
    lines.append(
        "10 items drawn from the real benchmark subsets already downloaded "
        "(`vrsbench_test_real.json`: 5 items; `rsvqa_lr_test_real.json`: 5 items). "
        "Each item was run through the live **`route_and_execute()`** controller pipeline — "
        "the exact code path called by `POST /api/analyze` — using the model "
        f"**{geochat_loaded_note}**.\n\n"
        "The original dataset images (`real_images/`) are absent from this repository "
        "(dataset download not completed). Items were run against the nearest available "
        "proxy image from `eval/benchmark_data/` (noted per row). "
        "This is explicitly declared as a **proxy-image limitation** — scores reflect "
        "model capability on similar imagery, not the exact benchmark tiles.\n\n"
        "**Correctness judgement** is made manually by reading each (ground-truth, "
        "model-answer) pair with no string matching, BLEU, or keyword logic. "
        "Judgement rubric:\n"
        "- **Correct** — answer is semantically equivalent to ground truth\n"
        "- **Partial** — answer contains the right information but also includes "
        "irrelevant content, hedges, or minor factual discrepancy\n"
        "- **Incorrect** — answer is wrong or wholly unrelated to the question\n"
        "- **N/A-Proxy** — answer cannot be fairly judged because the proxy image "
        "differs meaningfully from the original benchmark tile\n\n"
        "> **Disclaimer:** This is an internal sanity check. Results MUST NOT be "
        "cited as official VRSBench or RSVQA-LR scores.\n"
    )

    lines.append("\n## Results\n")

    # Table header
    lines.append(
        "| # | ID | Benchmark | Task Type | Question | Ground Truth | "
        "Model Answer | Proxy Image | Judgement | Notes |\n"
    )
    lines.append(
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
    )

    for idx, r in enumerate(records, 1):
        # Escape pipe chars in free-text fields
        q   = r["question"].replace("|", "\\|")
        gt  = r["gt"].replace("|", "\\|")
        ans = r["answer"].replace("|", "\\|").replace("\n", " ")
        # Truncate very long answers
        if len(ans) > 200:
            ans = ans[:197] + "…"
        proxy = os.path.basename(r["proxy_img"])
        lines.append(
            f"| {idx} | `{r['id']}` | {r['benchmark']} | {r['task_type']} | "
            f"{q} | {gt} | {ans} | {proxy} | **JUDGEMENT** | {r['proxy_note']} |\n"
        )

    lines.append("\n---\n")
    lines.append("*Judgement column to be filled in manually after reviewing each row.*\n")

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


if __name__ == "__main__":
    main()
