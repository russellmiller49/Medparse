ZOTERO_JSON ?= out/zero/zero_export.json
ZOTERO_CSV  ?= out/zero/zero_export.csv
EMAIL       ?= medparse-bot@example.com
INPUT_DIR   ?= input
BATCH_OUT   ?= out/batch_processed
HARDENED    ?= out/hardened
REPORTS     ?= out/reports

.PHONY: audit merge-zotero-dry merge-zotero

audit:
	python3 scripts/audit_extracted.py $(BATCH_OUT) --out $(REPORTS)

merge-zotero-dry:
	python3 scripts/apply_zotero_metadata.py \
	  --in $(BATCH_OUT) \
	  --zotero-json $(ZOTERO_JSON) \
	  --zotero-csv  $(ZOTERO_CSV) \
	  --out $(HARDENED) \
	  --report $(REPORTS) \
	  --dry-run

merge-zotero:
	python3 scripts/apply_zotero_metadata.py \
	  --in $(BATCH_OUT) \
	  --zotero-json $(ZOTERO_JSON) \
	  --zotero-csv  $(ZOTERO_CSV) \
	  --out $(HARDENED) \
	  --report $(REPORTS)

.PHONY: enrich-online-dry enrich-online

enrich-online-dry:
	python3 scripts/enrich_online.py --in $(HARDENED) --out $(HARDENED) --report $(REPORTS) --dry-run --email $(EMAIL)

enrich-online:
	python3 scripts/enrich_online.py --in $(HARDENED) --out $(HARDENED) --report $(REPORTS) --email $(EMAIL)

.PHONY: harden-offline
harden-offline:
	python3 scripts/harden_extracted.py $(HARDENED) --out $(HARDENED) --front-matter-chars 6000 --save-fixlog

.PHONY: dedupe
dedupe:
	python3 scripts/dedupe_by_doi.py --in $(HARDENED) --report $(REPORTS)/duplicates_by_doi.csv --apply

.PHONY: audit-final
audit-final:
	python3 scripts/audit_extracted.py $(HARDENED) --out out/reports_final

.PHONY: extract-batch
extract-batch:
	python3 batch_process_all.py

.PHONY: pipeline-dry pipeline
pipeline-dry: audit merge-zotero-dry enrich-online-dry
	@echo "Dry-run complete. Inspect $(REPORTS) before running 'make pipeline'"

pipeline: extract-batch audit merge-zotero harden-offline enrich-online dedupe audit-final
	@echo "Pipeline complete. See out/reports_final/quality_summary.json"
