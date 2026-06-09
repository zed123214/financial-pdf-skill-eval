import ast
import re
from pathlib import Path

import pandas as pd
from huggingface_hub import hf_hub_download

RAW = Path("datasets/officeqa/raw")
CSV_PATH = RAW / "officeqa_pro.csv"
MAX_UNIQUE_PDFS = 5

df = pd.read_csv(CSV_PATH)

def parse_source_files(value):
    text = str(value).strip()
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            parts = parsed
        else:
            parts = [parsed]
    except Exception:
        parts = re.split(r"(?:\\r\\n|\\n|\\r|\r\n|\n|\r|,|;)+", text)

    cleaned = []
    for part in parts:
        item = str(part).strip().strip('"').strip("'")
        if item:
            cleaned.append(item)
    return cleaned

wanted = []
seen = set()

for _, row in df.iterrows():
    for src in parse_source_files(row["source_files"]):
        stem = Path(src).stem
        pdf_name = f"{stem}.pdf"
        if pdf_name not in seen:
            seen.add(pdf_name)
            wanted.append(pdf_name)
        if len(wanted) >= MAX_UNIQUE_PDFS:
            break
    if len(wanted) >= MAX_UNIQUE_PDFS:
        break

print(f"Will download {len(wanted)} unique PDFs:")
for name in wanted:
    print(" -", name)

for name in wanted:
    repo_file = f"treasury_bulletin_pdfs/{name}"
    path = hf_hub_download(
        repo_id="databricks/officeqa",
        repo_type="dataset",
        filename=repo_file,
        local_dir=RAW,
    )
    print("downloaded:", path)
