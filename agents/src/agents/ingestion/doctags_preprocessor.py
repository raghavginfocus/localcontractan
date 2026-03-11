"""
DocTags Preprocessor - Walks Docling's DocTags tree to produce structured
sections.

Docling gives us rich layout info (sections, headers, tables, formatting) but
the pipeline was previously flattening it to markdown. This module preserves
that structure so downstream LLM agents get pre-segmented, context-rich input.

Flow: DocTags JSON dict → List[DocumentSection]
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

import structlog

logger = structlog.get_logger(__name__)


class TableCell(BaseModel):
    """A single cell in a table extracted by Docling."""

    row: int = 0
    col: int = 0
    row_span: int = 1
    col_span: int = 1
    text: str = ""


class DocumentTable(BaseModel):
    """A table extracted from the document by Docling."""

    table_ref: str = ""
    cells: list[TableCell] = Field(default_factory=list)
    num_rows: int = 0
    num_cols: int = 0

    def to_markdown(self) -> str:
        """Render table as markdown for LLM consumption."""
        if not self.cells:
            return ""

        grid: dict[tuple[int, int], str] = {}
        max_row = max_col = 0
        for cell in self.cells:
            grid[(cell.row, cell.col)] = cell.text
            max_row = max(max_row, cell.row)
            max_col = max(max_col, cell.col)

        lines: list[str] = []
        for r in range(max_row + 1):
            row_vals = [grid.get((r, c), "") for c in range(max_col + 1)]
            row_str = "| " + " | ".join(
                v.replace("|", "\\|") for v in row_vals
            ) + " |"
            lines.append(row_str)
            if r == 0:
                sep = (
                    "| " + " | ".join("---" for _ in range(max_col + 1)) + " |"
                )
                lines.append(sep)
        return "\n".join(lines)


class DocumentSection(BaseModel):
    """
    A logical section extracted from DocTags structure.

    Represents a chunk of the document with its structural context intact:
    section title, paragraphs, tables, formatting hints, and provenance.
    """

    section_id: str = ""
    title: str = ""
    level: int = 0
    paragraphs: list[str] = Field(default_factory=list)
    tables: list[DocumentTable] = Field(default_factory=list)
    formatting_hints: list[str] = Field(default_factory=list)
    page_range: str = ""
    parent_section_id: str = ""
    child_section_ids: list[str] = Field(default_factory=list)

    @property
    def has_table(self) -> bool:
        return len(self.tables) > 0

    @property
    def full_text(self) -> str:
        """All paragraph text joined."""
        return "\n".join(self.paragraphs)

    @property
    def char_count(self) -> int:
        return sum(len(p) for p in self.paragraphs)

    def to_llm_text(self) -> str:
        """
        Format this section for LLM consumption.

        Includes title, paragraph text, tables, and formatting hints
        in a structured but readable format.
        """
        parts: list[str] = []

        if self.title:
            header = f"=== Section: \"{self.title}\" ==="
        else:
            header = f"=== Section {self.section_id} ==="
        if self.page_range:
            header += f"  (pages {self.page_range})"
        parts.append(header)

        for para in self.paragraphs:
            parts.append(para)

        for table in self.tables:
            md = table.to_markdown()
            if md:
                parts.append(f"\n[Table]\n{md}\n")

        if self.formatting_hints:
            hints_str = "; ".join(self.formatting_hints[:10])
            parts.append(f"[Formatting: {hints_str}]")

        return "\n".join(parts)


def _resolve_ref(ref: str) -> tuple[str, int] | None:
    """
    Resolve a DocTags JSON pointer like '#/texts/5' to ('texts', 5).

    Returns None for unresolvable refs (e.g. '#/body').
    """
    match = re.match(r"^#/(\w+)/(\d+)$", ref)
    if match:
        return match.group(1), int(match.group(2))
    return None


def _extract_page_range(text_elements: list[dict]) -> str:
    """Extract page range from provenance data of text elements."""
    pages: set[int] = set()
    for elem in text_elements:
        for prov in elem.get("prov", []):
            page = prov.get("page_no") or prov.get("page")
            if isinstance(page, int):
                pages.add(page)
    if not pages:
        return ""
    sorted_pages = sorted(pages)
    if len(sorted_pages) == 1:
        return str(sorted_pages[0])
    return f"{sorted_pages[0]}-{sorted_pages[-1]}"


def _extract_formatting_hints(text_elements: list[dict]) -> list[str]:
    """Extract formatting-based hints from text elements."""
    hints: list[str] = []
    for elem in text_elements:
        fmt = elem.get("formatting", {})
        text_snippet = (elem.get("text") or "")[:60]
        if not text_snippet.strip():
            continue

        if fmt.get("bold"):
            hints.append(f"bold: \"{text_snippet}\"")
        if fmt.get("underline"):
            hints.append(f"underline: \"{text_snippet}\"")
    return hints


def _parse_table(table_dict: dict) -> DocumentTable:
    """Convert a DocTags table dict to a DocumentTable."""
    cells: list[TableCell] = []
    table_data = table_dict.get("data", {})
    raw_cells = table_data.get("table_cells", [])

    for raw in raw_cells:
        cells.append(TableCell(
            row=raw.get("start_row_offset_idx", raw.get("row", 0)),
            col=raw.get("start_col_offset_idx", raw.get("col", 0)),
            row_span=raw.get("row_span", 1),
            col_span=raw.get("col_span", 1),
            text=(raw.get("text") or "").strip(),
        ))

    num_rows = table_data.get("num_rows", 0)
    num_cols = table_data.get("num_cols", 0)
    if cells and not num_rows:
        num_rows = max(c.row for c in cells) + 1
    if cells and not num_cols:
        num_cols = max(c.col for c in cells) + 1

    return DocumentTable(
        table_ref=table_dict.get("self_ref", ""),
        cells=cells,
        num_rows=num_rows,
        num_cols=num_cols,
    )


def preprocess_doctags(doctags: dict[str, Any]) -> list[DocumentSection]:
    """
    Walk a Docling DocTags JSON dict and produce structured sections.

    Strategy:
    1. Build a map from self_ref → element for texts, groups, tables
    2. Walk groups to find sections (groups with section_header children)
    3. Associate texts and tables with their parent group/section
    4. Texts not belonging to any group go into a catch-all section

    Args:
        doctags: The DocTags JSON dict from Docling's export_to_dict().

    Returns:
        List of DocumentSection objects preserving document structure.
    """
    texts: list[dict] = doctags.get("texts", [])
    groups: list[dict] = doctags.get("groups", [])
    tables: list[dict] = doctags.get("tables", [])

    if not texts and not tables:
        logger.warning("doctags_empty", msg="No texts or tables in DocTags")
        return []

    # Index elements by self_ref
    text_by_ref: dict[str, dict] = {}
    for t in texts:
        ref = t.get("self_ref", "")
        if ref:
            text_by_ref[ref] = t

    table_by_ref: dict[str, dict] = {}
    for tb in tables:
        ref = tb.get("self_ref", "")
        if ref:
            table_by_ref[ref] = tb

    group_by_ref: dict[str, dict] = {}
    for g in groups:
        ref = g.get("self_ref", "")
        if ref:
            group_by_ref[ref] = g

    # Map parent_ref → list of child text/table elements
    parent_to_texts: dict[str, list[dict]] = {}
    for t in texts:
        parent = t.get("parent", {})
        parent_ref = parent.get("$ref", "") if isinstance(parent, dict) else ""
        parent_to_texts.setdefault(parent_ref, []).append(t)

    parent_to_tables: dict[str, list[dict]] = {}
    for tb in tables:
        parent = tb.get("parent", {})
        parent_ref = parent.get("$ref", "") if isinstance(parent, dict) else ""
        parent_to_tables.setdefault(parent_ref, []).append(tb)

    # Build sections from groups
    sections: list[DocumentSection] = []
    used_text_refs: set[str] = set()
    used_table_refs: set[str] = set()

    for i, group in enumerate(groups):
        group_ref = group.get("self_ref", f"#/groups/{i}")
        group_label = group.get("label", "")
        group_name = group.get("name", "")

        # Collect texts belonging to this group (direct children)
        group_texts = parent_to_texts.get(group_ref, [])
        group_tables_list = parent_to_tables.get(group_ref, [])

        if not group_texts and not group_tables_list:
            continue

        # Find section title from section_header children
        title = ""
        paragraphs: list[str] = []
        for t in group_texts:
            used_text_refs.add(t.get("self_ref", ""))
            label = t.get("label", "")
            text_content = (t.get("text") or "").strip()
            if not text_content:
                continue
            if label == "section_header":
                title = text_content
            else:
                paragraphs.append(text_content)

        # If no explicit section_header, use group name as title
        if not title and group_name and group_label == "section":
            title = group_name

        # Parse tables
        doc_tables: list[DocumentTable] = []
        for tb in group_tables_list:
            used_table_refs.add(tb.get("self_ref", ""))
            doc_tables.append(_parse_table(tb))

        formatting = _extract_formatting_hints(group_texts)
        pages = _extract_page_range(group_texts)

        # Determine parent section
        group_parent = group.get("parent", {})
        parent_ref = (
            group_parent.get("$ref", "")
            if isinstance(group_parent, dict)
            else ""
        )

        sections.append(DocumentSection(
            section_id=f"sec_{i}",
            title=title,
            level=1 if group_label == "section" else 0,
            paragraphs=paragraphs,
            tables=doc_tables,
            formatting_hints=formatting,
            page_range=pages,
            parent_section_id=(
                parent_ref if parent_ref != "#/body" else ""
            ),
        ))

    # Collect orphan texts (not belonging to any group)
    orphan_texts: list[dict] = []
    for t in texts:
        if t.get("self_ref", "") not in used_text_refs:
            orphan_texts.append(t)

    orphan_tables: list[dict] = []
    for tb in tables:
        if tb.get("self_ref", "") not in used_table_refs:
            orphan_tables.append(tb)

    if orphan_texts or orphan_tables:
        orphan_paragraphs = []
        for t in orphan_texts:
            text_content = (t.get("text") or "").strip()
            if text_content:
                orphan_paragraphs.append(text_content)

        orphan_doc_tables = [_parse_table(tb) for tb in orphan_tables]
        orphan_formatting = _extract_formatting_hints(orphan_texts)
        orphan_pages = _extract_page_range(orphan_texts)

        if orphan_paragraphs or orphan_doc_tables:
            sections.insert(0, DocumentSection(
                section_id="sec_root",
                title="",
                level=0,
                paragraphs=orphan_paragraphs,
                tables=orphan_doc_tables,
                formatting_hints=orphan_formatting,
                page_range=orphan_pages,
            ))

    # Set child refs
    section_map = {s.section_id: s for s in sections}
    for s in sections:
        if s.parent_section_id:
            resolved = _resolve_ref(s.parent_section_id)
            if resolved:
                parent_sid = f"sec_{resolved[1]}"
                if parent_sid in section_map:
                    s.parent_section_id = parent_sid
                    parent_sec = section_map[parent_sid]
                    parent_sec.child_section_ids.append(s.section_id)

    total_chars = sum(s.char_count for s in sections)
    total_tables = sum(len(s.tables) for s in sections)
    logger.info(
        "doctags_preprocessed",
        sections=len(sections),
        total_chars=total_chars,
        total_tables=total_tables,
    )

    return sections


def sections_to_llm_text(sections: list[DocumentSection]) -> str:
    """
    Convert sections list to a single structured text for LLM consumption.

    Each section gets a header with its title, followed by paragraphs and
    tables. This replaces the flat export_to_markdown() output.
    """
    return "\n\n".join(
        s.to_llm_text() for s in sections if s.paragraphs or s.tables
    )


def extract_structural_hints(
    sections: list[DocumentSection],
) -> dict[str, Any]:
    """
    Extract high-level structural hints for entity extraction.

    Returns a dict with:
    - section_titles: list of section headings found
    - bold_terms: list of bold-formatted text (often party names, defined
      terms)
    - table_summaries: brief description of each table
    - total_sections: count
    """
    titles = [s.title for s in sections if s.title]
    bold_terms: list[str] = []
    for s in sections:
        for hint in s.formatting_hints:
            if hint.startswith("bold:"):
                term = hint.removeprefix("bold:").strip().strip('"')
                if term and len(term) > 2:
                    bold_terms.append(term)

    table_summaries: list[str] = []
    for s in sections:
        for table in s.tables:
            ctx = f"in section \"{s.title}\"" if s.title else ""
            desc = (
                f"Table {ctx}: {table.num_rows} rows x {table.num_cols} cols"
            )
            table_summaries.append(desc)

    return {
        "section_titles": titles,
        "bold_terms": list(dict.fromkeys(bold_terms)),
        "table_summaries": table_summaries,
        "total_sections": len(sections),
    }
