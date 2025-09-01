"""
Unit tests for extraction fixes: statistics, UMLS, captions, authors.
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from scripts.statistics_gated import extract_statistics, has_statistical_context, is_excluded_pattern
from scripts.umls_filters import filter_umls_links, BLACKLIST_TERMS
from scripts.caption_linker import link_captions, find_caption_for_asset
from scripts.authors_fallback import extract_authors_from_frontmatter, is_valid_author_name

class TestStatistics:
    """Test context-gated statistics extraction."""
    
    def test_blocks_grant_ids(self):
        """Grant IDs should not be extracted as statistics."""
        text = "This work was supported by NIH grant 1U54HL119810-03."
        stats = extract_statistics(text)
        assert len(stats) == 0, "Grant ID should not be extracted"
    
    def test_blocks_citation_tuples(self):
        """Citation tuples like (3,4) should not be extracted."""
        text = "Previous studies (3,4) have shown similar results."
        stats = extract_statistics(text)
        assert len(stats) == 0, "Citation tuple should not be extracted"
    
    def test_blocks_doi(self):
        """DOIs should not be extracted as statistics."""
        text = "doi: 10.1016/j.cell.2023.01.001"
        stats = extract_statistics(text)
        assert len(stats) == 0, "DOI should not be extracted"
    
    def test_extracts_real_p_value(self):
        """Real p-values with context should be extracted."""
        text = "The difference was statistically significant (p<0.001)."
        stats = extract_statistics(text)
        assert len(stats) == 1
        assert stats[0]['type'] == 'p_value'
        assert stats[0]['value'] == 0.001
    
    def test_extracts_confidence_interval(self):
        """Confidence intervals with context should be extracted."""
        text = "The hazard ratio was 0.75 (95% CI: 0.60-0.92, p=0.006)."
        stats = extract_statistics(text)
        # Should find CI and p-value
        assert len(stats) >= 1
        ci_stats = [s for s in stats if s['type'] == 'ci']
        assert len(ci_stats) == 1
        assert ci_stats[0]['value'] == [0.60, 0.92]
    
    def test_extracts_mean_sd(self):
        """Mean ± SD with context should be extracted."""
        text = "The mean age was 65.3 ± 8.2 years in the treatment group."
        stats = extract_statistics(text)
        assert len(stats) == 1
        assert stats[0]['type'] == 'mean_sd'
        assert stats[0]['value']['mean'] == 65.3
        assert stats[0]['value']['sd'] == 8.2
    
    def test_requires_statistical_context(self):
        """Numbers without statistical context should not be extracted."""
        text = "The study included 150 patients from 2020-2023."
        stats = extract_statistics(text)
        assert len(stats) == 0, "Numbers without statistical context should not be extracted"

class TestUMLSFiltering:
    """Test UMLS link filtering."""
    
    def test_filters_blacklisted_terms(self):
        """Blacklisted terms should be filtered out."""
        links = [
            {'text': 'history of three', 'cui': 'C123', 'score': 0.9, 'semtypes': ['T033']},
            {'text': 'diabetes', 'cui': 'C456', 'score': 0.85, 'semtypes': ['T047']}
        ]
        filtered = filter_umls_links(links)
        assert len(filtered) == 1
        assert filtered[0]['text'] == 'diabetes'
    
    def test_filters_low_score(self):
        """Links below minimum score should be filtered."""
        links = [
            {'text': 'hypertension', 'cui': 'C123', 'score': 0.6, 'semtypes': ['T047']},
            {'text': 'diabetes', 'cui': 'C456', 'score': 0.85, 'semtypes': ['T047']}
        ]
        filtered = filter_umls_links(links, min_score=0.7)
        assert len(filtered) == 1
        assert filtered[0]['text'] == 'diabetes'
    
    def test_filters_short_terms(self):
        """Very short terms should be filtered."""
        links = [
            {'text': 'a', 'cui': 'C123', 'score': 0.9, 'semtypes': ['T047']},
            {'text': 'cancer', 'cui': 'C456', 'score': 0.85, 'semtypes': ['T191']}
        ]
        filtered = filter_umls_links(links, min_term_length=3)
        assert len(filtered) == 1
        assert filtered[0]['text'] == 'cancer'
    
    def test_requires_alphabetic(self):
        """Terms without alphabetic characters should be filtered."""
        links = [
            {'text': '123', 'cui': 'C123', 'score': 0.9, 'semtypes': ['T047']},
            {'text': 'covid-19', 'cui': 'C456', 'score': 0.85, 'semtypes': ['T047']}
        ]
        filtered = filter_umls_links(links, require_alphabetic=True)
        assert len(filtered) == 1
        assert filtered[0]['text'] == 'covid-19'
    
    def test_deduplicates_by_cui(self):
        """Should keep only best score per CUI."""
        links = [
            {'text': 'heart attack', 'cui': 'C123', 'score': 0.8, 'semtypes': ['T047']},
            {'text': 'myocardial infarction', 'cui': 'C123', 'score': 0.95, 'semtypes': ['T047']},
            {'text': 'diabetes', 'cui': 'C456', 'score': 0.85, 'semtypes': ['T047']}
        ]
        filtered = filter_umls_links(links)
        assert len(filtered) == 2
        # Should keep the higher scoring match for C123
        c123_matches = [l for l in filtered if l['cui'] == 'C123']
        assert len(c123_matches) == 1
        assert c123_matches[0]['text'] == 'myocardial infarction'

class TestCaptionLinking:
    """Test caption and footnote linking."""
    
    def test_links_table_caption(self):
        """Should link caption to table."""
        doc = {
            'structure': {
                'tables': [{'id': 'table1', 'page': 5}],
                'sections': [{
                    'paragraphs': [
                        {'text': 'Table 1: Patient demographics and baseline characteristics'}
                    ]
                }]
            }
        }
        doc = link_captions(doc)
        assert 'assets' in doc
        assert 'tables' in doc['assets']
        assert len(doc['assets']['tables']) == 1
        assert len(doc['assets']['tables'][0]['captions']) > 0
        assert 'Patient demographics' in doc['assets']['tables'][0]['captions'][0]
    
    def test_links_figure_caption(self):
        """Should link caption to figure."""
        doc = {
            'structure': {
                'figures': [{'id': 'fig1', 'page': 3}],
                'sections': [{
                    'paragraphs': [
                        {'text': 'Figure 1: Study flow diagram showing patient enrollment'}
                    ]
                }]
            }
        }
        doc = link_captions(doc)
        assert 'assets' in doc
        assert 'figures' in doc['assets']
        assert len(doc['assets']['figures']) == 1
        assert len(doc['assets']['figures'][0]['captions']) > 0
        assert 'Study flow diagram' in doc['assets']['figures'][0]['captions'][0]
    
    def test_finds_footnotes(self):
        """Should find and link footnotes."""
        doc = {
            'structure': {
                'tables': [{'id': 'table1', 'page': 5}],
                'sections': [{
                    'paragraphs': [
                        {'text': 'Table 1: Results summary', 'page': 5},
                        {'text': '* p<0.05 compared to control', 'page': 5}
                    ]
                }]
            }
        }
        doc = link_captions(doc)
        assert len(doc['assets']['tables'][0]['footnotes']) > 0
        assert 'p<0.05' in doc['assets']['tables'][0]['footnotes'][0]

class TestAuthorExtraction:
    """Test author fallback extraction."""
    
    def test_extracts_authors_from_frontmatter(self):
        """Should extract authors from document front matter."""
        doc = {
            'structure': {
                'sections': [{
                    'title': '',
                    'paragraphs': [
                        {'text': 'John A. Smith1, Jane Doe2, Robert Johnson Jr.3'}
                    ]
                }]
            }
        }
        authors = extract_authors_from_frontmatter(doc)
        assert len(authors) >= 2
        assert 'John A. Smith' in authors or 'John Smith' in authors
        assert 'Jane Doe' in authors
    
    def test_validates_author_names(self):
        """Should validate author names correctly."""
        assert is_valid_author_name("John Smith")
        assert is_valid_author_name("Jane A. Doe")
        assert is_valid_author_name("Robert Johnson Jr.")
        
        assert not is_valid_author_name("123")
        assert not is_valid_author_name("University")
        assert not is_valid_author_name("Department of Medicine")
        assert not is_valid_author_name("")
        assert not is_valid_author_name("A")
    
    def test_cleans_author_names(self):
        """Should clean author names properly."""
        from scripts.authors_fallback import clean_author_name
        
        assert clean_author_name("John Smith1,2") == "John Smith"
        assert clean_author_name("Jane Doe*") == "Jane Doe"
        assert clean_author_name("Robert Johnson (Harvard)") == "Robert Johnson"
        assert clean_author_name("Alice  Brown") == "Alice Brown"

class TestIntegration:
    """Light integration tests."""
    
    def test_all_modules_importable(self):
        """All fix modules should be importable."""
        import scripts.statistics_gated
        import scripts.umls_filters
        import scripts.caption_linker
        import scripts.authors_fallback
        import scripts.http_retry
        assert True  # If we get here, imports worked
    
    def test_stats_context_detection(self):
        """Statistical context detection should work."""
        assert has_statistical_context("The p-value was 0.05")
        assert has_statistical_context("95% confidence interval")
        assert not has_statistical_context("The year was 2023")
    
    def test_excluded_pattern_detection(self):
        """Excluded pattern detection should work."""
        assert is_excluded_pattern("R01HL123456")
        assert is_excluded_pattern("10.1016/j.cell.2023")
        assert is_excluded_pattern("(3,4,5)")
        assert not is_excluded_pattern("p=0.001")