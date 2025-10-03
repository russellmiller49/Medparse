"""Utilities for exporting graph-friendly payloads from merged documents."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from scripts.umls_filters import cluster_umls_links


def _make_id(prefix: str, value: str) -> str:
    safe = (value or "").strip() or "unknown"
    safe = safe.replace(" ", "_")
    return f"{prefix}:{safe}"


def _ensure_concepts(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    if doc.get("umls_concepts"):
        return doc["umls_concepts"]
    links = doc.get("umls_links") or []
    concepts = cluster_umls_links(links)
    doc["umls_concepts"] = concepts
    return concepts


def build_graph_payload(doc: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Build a node/edge payload suitable for graph ingestion."""

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    metadata = doc.get("metadata", {})
    doc_identifier = (
        metadata.get("doi")
        or metadata.get("pmid")
        or metadata.get("title")
        or metadata.get("doc_id")
        or metadata.get("pdf_name")
        or "document"
    )
    document_id = _make_id("document", str(doc_identifier))

    nodes.append(
        {
            "id": document_id,
            "type": "Document",
            "data": {
                "title": metadata.get("title"),
                "doi": metadata.get("doi"),
                "pmid": metadata.get("pmid"),
                "year": metadata.get("year"),
            },
        }
    )

    sections = doc.get("structure", {}).get("sections", [])
    section_nodes: Dict[int, str] = {}
    for idx, section in enumerate(sections):
        section_id = _make_id("section", str(idx))
        section_nodes[idx] = section_id
        nodes.append(
            {
                "id": section_id,
                "type": "Section",
                "data": {
                    "index": idx,
                    "title": section.get("title"),
                    "category": section.get("category"),
                },
            }
        )
        edges.append(
            {
                "source": document_id,
                "target": section_id,
                "type": "HAS_SECTION",
                "data": {"order": idx},
            }
        )

    recommendations = doc.get("recommendations", [])
    recommendation_nodes: Dict[str, str] = {}
    for rec in recommendations:
        rec_id = rec.get("id") or rec.get("number")
        if not rec_id:
            continue
        node_id = _make_id("recommendation", str(rec_id))
        recommendation_nodes[rec_id] = node_id
        nodes.append(
            {
                "id": node_id,
                "type": "Recommendation",
                "data": {
                    "id": rec_id,
                    "number": rec.get("number"),
                    "grade": rec.get("grade"),
                    "text": rec.get("text"),
                },
            }
        )
        edges.append(
            {
                "source": document_id,
                "target": node_id,
                "type": "HAS_RECOMMENDATION",
                "data": {},
            }
        )

        section_refs = rec.get("sections") or []
        for ref in section_refs:
            section_index = ref.get("index")
            if section_index is None:
                continue
            section_node = section_nodes.get(int(section_index))
            if section_node:
                edges.append(
                    {
                        "source": node_id,
                        "target": section_node,
                        "type": "LOCATED_IN",
                        "data": {},
                    }
                )

    figures = doc.get("figures", [])
    figure_nodes: Dict[str, str] = {}
    for fig in figures:
        fig_local_id = fig.get("local_id") or fig.get("id")
        if not fig_local_id:
            continue
        node_id = _make_id("figure", fig_local_id)
        figure_nodes[fig_local_id] = node_id
        nodes.append(
            {
                "id": node_id,
                "type": "Figure",
                "data": {
                    "id": fig_local_id,
                    "caption": fig.get("caption"),
                    "page": fig.get("page"),
                },
            }
        )
        edges.append(
            {
                "source": document_id,
                "target": node_id,
                "type": "HAS_FIGURE",
                "data": {},
            }
        )

    tables = doc.get("tables", [])
    table_nodes: Dict[str, str] = {}
    for table in tables:
        table_local_id = table.get("local_id") or table.get("id")
        if not table_local_id:
            continue
        node_id = _make_id("table", table_local_id)
        table_nodes[table_local_id] = node_id
        nodes.append(
            {
                "id": node_id,
                "type": "Table",
                "data": {
                    "id": table_local_id,
                    "caption": table.get("caption"),
                    "page": table.get("page"),
                },
            }
        )
        edges.append(
            {
                "source": document_id,
                "target": node_id,
                "type": "HAS_TABLE",
                "data": {},
            }
        )

    stats = doc.get("statistics", [])
    statistic_nodes: Dict[str, str] = {}
    for stat in stats:
        stat_id = stat.get("id") or f"stat_{len(statistic_nodes) + 1:04d}"
        node_id = _make_id("statistic", stat_id)
        statistic_nodes[stat_id] = node_id
        nodes.append(
            {
                "id": node_id,
                "type": "Statistic",
                "data": {k: stat.get(k) for k in stat.keys() if k != "id"},
            }
        )
        edges.append(
            {
                "source": document_id,
                "target": node_id,
                "type": "HAS_STATISTIC",
                "data": {},
            }
        )
        section_index = stat.get("section_index")
        if section_index is not None and section_index in section_nodes:
            edges.append(
                {
                    "source": section_nodes[section_index],
                    "target": node_id,
                    "type": "CONTAINS_STATISTIC",
                    "data": {
                        "source": stat.get("source"),
                    },
                }
            )
        table_id = stat.get("table_id")
        if table_id and table_id in table_nodes:
            edges.append(
                {
                    "source": table_nodes[table_id],
                    "target": node_id,
                    "type": "REPORTS_STATISTIC",
                    "data": {},
                }
            )
        figure_id = stat.get("figure_id")
        if figure_id and figure_id in figure_nodes:
            edges.append(
                {
                    "source": figure_nodes[figure_id],
                    "target": node_id,
                    "type": "REPORTS_STATISTIC",
                    "data": {},
                }
            )

    references = doc.get("references_enriched") or []
    reference_nodes: Dict[str, str] = {}
    for idx, ref in enumerate(references):
        key = ref.get("pmid") or ref.get("doi") or ref.get("title") or str(idx)
        node_id = _make_id("reference", str(key))
        reference_nodes[str(key)] = node_id
        nodes.append(
            {
                "id": node_id,
                "type": "Reference",
                "data": {k: ref.get(k) for k in ("title", "journal", "year", "doi", "pmid")},
            }
        )
        edges.append(
            {
                "source": document_id,
                "target": node_id,
                "type": "HAS_REFERENCE",
                "data": {},
            }
        )

    concepts = _ensure_concepts(doc)
    concept_nodes: Dict[str, str] = {}
    for concept in concepts:
        cui = concept.get("cui")
        if not cui:
            continue
        node_id = _make_id("concept", cui)
        concept_nodes[cui] = node_id
        nodes.append(
            {
                "id": node_id,
                "type": "Concept",
                "data": {
                    k: concept.get(k)
                    for k in (
                        "cui",
                        "preferred_term",
                        "tui",
                        "synonyms",
                        "max_confidence",
                        "mean_confidence",
                        "mention_count",
                        "negated_mentions",
                        "has_negated_mentions",
                        "all_mentions_negated",
                        "sources",
                    )
                },
            }
        )
        edges.append(
            {
                "source": document_id,
                "target": node_id,
                "type": "HAS_CONCEPT",
                "data": {"mention_count": concept.get("mention_count")},
            }
        )

    section_concept_counts: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for concept in concepts:
        cui = concept.get("cui")
        node_id = concept_nodes.get(cui)
        if not node_id:
            continue
        for mention in concept.get("mentions", []):
            section_index = mention.get("section_index")
            if section_index is None:
                continue
            section_concept_counts[int(section_index)][node_id] += 1

    for section_idx, concept_map in section_concept_counts.items():
        section_node = section_nodes.get(section_idx)
        if not section_node:
            continue
        for concept_node, count in concept_map.items():
            edges.append(
                {
                    "source": section_node,
                    "target": concept_node,
                    "type": "MENTIONS_CONCEPT",
                    "data": {"count": count},
                }
            )

    for rec in recommendations:
        rec_id = rec.get("id") or rec.get("number")
        rec_node = recommendation_nodes.get(rec_id)
        if not rec_node:
            continue
        rec_text = (rec.get("text") or "").lower()
        section_indices = {
            ref.get("index") for ref in (rec.get("sections") or []) if ref.get("index") is not None
        }
        for concept in concepts:
            cui = concept.get("cui")
            concept_node = concept_nodes.get(cui)
            if not concept_node:
                continue
            linked = False
            for mention in concept.get("mentions", []):
                section_index = mention.get("section_index")
                if section_index in section_indices:
                    mention_text = (mention.get("text") or "").lower()
                    if mention_text and mention_text in rec_text:
                        linked = True
                        break
            if linked:
                edges.append(
                    {
                        "source": rec_node,
                        "target": concept_node,
                        "type": "REFERS_TO",
                        "data": {},
                    }
                )

        for stat in stats:
            stat_id = stat.get("id")
            stat_node = statistic_nodes.get(stat_id)
            if not stat_node:
                continue
            if stat.get("section_index") in section_indices:
                edges.append(
                    {
                        "source": rec_node,
                        "target": stat_node,
                        "type": "SUPPORTED_BY",
                        "data": {"source": stat.get("source")},
                    }
                )

    return {"nodes": nodes, "edges": edges}


__all__ = ["build_graph_payload"]
