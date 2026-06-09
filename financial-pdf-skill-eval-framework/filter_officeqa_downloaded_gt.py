import json
import re
from pathlib import Path

import pandas as pd

RAW = Path("datasets/officeqa/raw")
PDF_DIR = RAW / "treasury_bulletin_pdfs"
CSV_PATH = RAW / "officeqa_pro.csv"
OUT_DIR = Path("evaluation/ground_truth")
OUT_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(CSV_PATH)

downloaded_stems = {p.stem for p in PDF_DIR.glob("*.pdf")}
print("Downloaded PDFs:")
for s in sorted(downloaded_stems):
    print(" -", s)

def split_source_files(value):
    text = str(value)
    parts = re.split(r"(?:\\r\\n|\\n|\\r|\r\n|\n|\r|,|;)+", text)
    return [p.strip() for p in parts if p.strip()]

selected = []

for _, row in df.iterrows():
    source_files = split_source_files(row["source_files"])
    source_stems = {Path(x).stem for x in source_files}

    matched = sorted(source_stems & downloaded_stems)
    if not matched:
        continue

    selected.append({
        "uid": str(row["uid"]),
        "question": str(row["question"]),
        "answer": str(row["answer"]),
        "source_docs": str(row.get("source_docs", "")),
        "source_files": source_files,
        "matched_downloaded_pdfs": [f"{x}.pdf" for x in matched],
        "difficulty": str(row.get("difficulty", ""))
    })

print()
print("Matched QA rows:", len(selected))
for item in selected[:20]:
    print(item["uid"], "->", item["matched_downloaded_pdfs"], "answer:", item["answer"])

out = {
    "case_id": "officeqa_downloaded_5pdfs_qa",
    "source": "public_dataset_officeqa",
    "task_type": "document_qa",
    "note": "OfficeQA question-answer GT for downloaded Treasury Bulletin PDFs. This is QA GT, not financial metric GT.",
    "questions": selected
}

out_path = OUT_DIR / "officeqa_downloaded_5pdfs_qa_gt.json"
out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print()
print("Wrote:", out_path)