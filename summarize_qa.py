import json
from pathlib import Path
import pandas as pd

qa_files = Path("out/qa").glob("*.qa.json")
data = []
for f in qa_files:
    with open(f) as fp:
        qa = json.load(fp)
        data.append(qa)

if data:
    df = pd.DataFrame(data)
    print("\n=== QA Summary by Linker ===")
    print(df.groupby('linker')[['n_umls_links', 'n_local_links', 'completeness_score']].mean())
    print("\n=== Papers with Issues ===")
    invalid = df[~df['is_valid']]
    if not invalid.empty:
        print(invalid[['pdf', 'linker', 'completeness_score']])
    else:
        print("All papers passed validation!")
    
    print("\n=== Overall Statistics ===")
    print(f"Total papers processed: {len(df['pdf'].unique())}")
    print(f"Average completeness score: {df['completeness_score'].mean():.1f}")
    print(f"Total UMLS concepts: {df['n_umls_links'].sum()}")
    print(f"Total local concepts: {df['n_local_links'].sum()}")
else:
    print("No QA files found. Process some PDFs first!")