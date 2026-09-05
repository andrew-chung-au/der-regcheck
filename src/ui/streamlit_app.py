from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st
import yaml

# Ensure repo root is on sys.path so "from src.*" works with:
#   streamlit run src/ui/streamlit_app.py
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database.db_connection import get_connection
from src.generation.answer_generator import AnswerGenerator, GeneratedAnswer
from src.observability.query_cache import (
    compute_config_hash,
    get_cached_answer,
    get_cached_answer_by_id,
    list_recent_queries,
    save_answer_to_cache,
)


FEEDBACK_PATH = ROOT / "data" / "feedback" / "feedback.jsonl"
TIER2_QUESTIONS_PATH = ROOT / "data" / "evaluation" / "tier2_questions.yaml"
TIER2_SCORES_PATH = ROOT / "data" / "evaluation" / "tier2_manual_scores.jsonl"

FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
TIER2_SCORES_PATH.parent.mkdir(parents=True, exist_ok=True)

PROMPT_VERSION = "v3_few_shot_grounded_rag"
TOP_K = 10
RETRIEVAL_CONFIG_ID = "original_query_vector_rerank_equal"


STATUS_LABEL_MAP = {
    "answered": "Answered",
    "partial": "Partial",
    "needs_clarification": "Needs clarification",
    "insufficient_evidence": "Insufficient evidence",
    "high_stakes_boundary": "High-stakes boundary",
}

STATUS_STYLES = {
    "Answered": ("✅", "success"),
    "Partial": ("🟡", "warning"),
    "Needs clarification": ("❓", "info"),
    "Insufficient evidence": ("⚠️", "warning"),
    "High-stakes boundary": ("🛑", "error"),
}


def ui_status_from_answer_status(answer_status: str) -> str:
    """Map an internal status value to a reviewer-facing label."""
    return STATUS_LABEL_MAP.get(answer_status, "Answered")


def render_status_badge(answer_status: str) -> None:
    """Render a status badge for the selected answer."""
    ui_status = ui_status_from_answer_status(answer_status)
    icon, message_type = STATUS_STYLES.get(ui_status, ("ℹ️", "info"))
    message = f"{icon} **Answer status: {ui_status}**"

    if message_type == "success":
        st.success(message)
    elif message_type == "warning":
        st.warning(message)
    elif message_type == "error":
        st.error(message)
    else:
        st.info(message)


def safe_value(value: Any, fallback: str = "Not available in source metadata") -> Any:
    """Return a UI-safe fallback for missing metadata."""
    if value in (None, "", [], {}):
        return fallback
    return value


def load_tier2_questions() -> list[dict[str, Any]]:
    """Load curated Tier 2 manual RAG-quality evaluation questions."""
    if not TIER2_QUESTIONS_PATH.exists():
        return []

    with TIER2_QUESTIONS_PATH.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    questions = data.get("questions", [])
    return questions if isinstance(questions, list) else []


def build_tier2_display_label(
    question: dict[str, Any],
    max_length: int = 105,
) -> str:
    """
    Build a readable Tier 2 label for the Ask and Review selectors.

    Example:
    T2-003 — For a DER project in SCE territory, what interconnection review...
    """
    question_id = str(question.get("id", "tier2_unknown"))
    friendly_id = question_id.replace("tier2_", "T2-").upper()

    question_text = str(question.get("question", "")).replace("\n", " ").strip()
    if len(question_text) > max_length:
        question_text = f"{question_text[:max_length].rstrip()}..."

    return f"{friendly_id} — {question_text}"


def build_evidence_cards_data_from_cached(
    cached: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Convert cached evidence snapshots to reviewer-facing evidence-card data.

    Raw reranker scores are not shown because they are not currently captured
    consistently by the retrieval runtime. Final retrieval rank is preserved.
    """
    evidence_snapshot = cached.get("evidence_snapshot") or []
    evidence: list[dict[str, Any]] = []

    for fallback_rank, item in enumerate(evidence_snapshot, start=1):
        citation = item.get("citation") or {}
        source_policy = item.get("source_policy") or {}
        heading_path = " > ".join(item.get("heading_path") or [])

        authority_tier = str(source_policy.get("authority_tier", "unknown"))
        currency_status = str(source_policy.get("currency_status", "unknown"))

        source_class = (
            f"{authority_tier.replace('_', ' ').title()} "
            f"({currency_status.replace('_', ' ')})"
        )

        page_or_section_parts: list[str] = []

        if heading_path:
            page_or_section_parts.append(heading_path)

        pdf_page = citation.get("pdf_page_start")
        if pdf_page is not None:
            page_or_section_parts.append(f"PDF page {pdf_page}")

        section_ids = citation.get("section_ids")
        if section_ids:
            section_text = ".".join(str(value) for value in section_ids)
            page_or_section_parts.append(f"Section {section_text}")

        retrieval_rank = item.get("retrieval_rank", fallback_rank)

        evidence.append(
            {
                "citation_id": f"S{retrieval_rank}",
                "source_title": item.get("source_id", "Unknown source"),
                "source_class": source_class,
                "page_or_section": (
                    " | ".join(page_or_section_parts)
                    if page_or_section_parts
                    else None
                ),
                "excerpt": item.get("evidence_text", ""),
                "retrieval_rank": retrieval_rank,
            }
        )

    return evidence


def render_evidence_cards(evidence_items: list[dict[str, Any]]) -> None:
    """Render expandable evidence cards for the selected query."""
    if not evidence_items:
        st.info("No retrieved evidence is available for this cached response.")
        return

    st.subheader("Retrieved evidence")

    for item in evidence_items:
        citation_id = safe_value(item.get("citation_id"), "Unlabelled source")
        title = safe_value(item.get("source_title"), "Untitled source")

        with st.expander(f"{citation_id} — {title}", expanded=False):
            st.markdown(
                f"**Source class:** {safe_value(item.get('source_class'))}"
            )
            st.markdown(
                f"**Page / section:** {safe_value(item.get('page_or_section'))}"
            )
            st.markdown(
                f"**Final retrieval rank:** "
                f"{safe_value(item.get('retrieval_rank'))}"
            )
            st.markdown("**Supporting excerpt:**")
            st.write(safe_value(item.get("excerpt")))


def render_cached_answer(
    cached: dict[str, Any],
    show_question: bool = True,
) -> str:
    """Render one cached answer consistently in Ask and Review."""
    if show_question:
        st.subheader("Selected question")
        st.markdown(f"**{cached['question_text']}**")

    render_status_badge(str(cached["answer_status"]))

    st.subheader("Answer")
    answer_text = str(cached.get("direct_answer", ""))
    st.markdown(answer_text)

    uncertainty = cached.get("uncertainty_statement")
    if uncertainty:
        st.caption(str(uncertainty))

    if cached.get("answer_status") == "high_stakes_boundary":
        st.warning(
            "This question touches high-stakes regulatory, engineering, or "
            "compliance territory. Treat this as evidence-oriented research "
            "support only; do not rely on it for filings, approvals, engineering "
            "decisions, or compliance determinations."
        )

    clarifying_question = cached.get("clarifying_question")
    if clarifying_question:
        st.info(f"**Clarifying question:** {clarifying_question}")

    evidence_gaps = cached.get("evidence_gaps") or []
    if evidence_gaps:
        st.info(
            "**Evidence gaps:**\n"
            + "\n".join(f"- {gap}" for gap in evidence_gaps)
        )

    next_steps = cached.get("research_next_steps") or []
    if next_steps:
        st.info(
            "**Suggested next steps:**\n"
            + "\n".join(f"- {step}" for step in next_steps)
        )

    return answer_text


def append_feedback(
    cache_id: str,
    rating: str,
    comment: str,
) -> None:
    """
    Store an independent feedback event linked to a cached response.

    Multiple feedback events may be stored for the same cache entry.
    """
    cleaned_comment = comment.strip() or None

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO answer_feedback (cache_id, rating, comment)
                VALUES (%s, %s, %s)
                """,
                (cache_id, rating, cleaned_comment),
            )
        conn.commit()

    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "cache_id": str(cache_id),
        "rating": rating,
        "comment": cleaned_comment,
    }

    with FEEDBACK_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def append_manual_score(
    *,
    cache_id: str,
    question_id: str | None,
    is_tier2: bool,
    groundedness: int,
    relevance: int,
    completeness: int,
    citation_quality: int,
    appropriate_uncertainty: int,
    notes: str,
) -> None:
    """
    Store an independent manual-review event linked to a cached answer.

    This supports multiple reviewer scores for the same generated response.
    """
    cleaned_notes = notes.strip() or None

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO manual_scores (
                    cache_id,
                    question_id,
                    is_tier2,
                    groundedness,
                    relevance,
                    completeness,
                    citation_quality,
                    appropriate_uncertainty,
                    notes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    cache_id,
                    question_id,
                    is_tier2,
                    groundedness,
                    relevance,
                    completeness,
                    citation_quality,
                    appropriate_uncertainty,
                    cleaned_notes,
                ),
            )
        conn.commit()

    record = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "cache_id": str(cache_id),
        "question_id": question_id,
        "is_tier2": is_tier2,
        "groundedness": groundedness,
        "relevance": relevance,
        "completeness": completeness,
        "citation_quality": citation_quality,
        "appropriate_uncertainty": appropriate_uncertainty,
        "notes": cleaned_notes,
    }

    with TIER2_SCORES_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_or_load_query(
    *,
    question_text: str,
    config_hash: str,
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    """
    Load a cached answer for an identical configuration, or generate one.

    Returns:
        cached_answer: Complete persisted cache row, or None on failure.
        cache_status: "hit", "miss", or None.
        error_message: User-displayable error text, or None.

    Stored latency represents a cache-miss full RAG generation request.
    Cache hits are database lookups and do not overwrite original latency.
    """
    cleaned_question = question_text.strip()

    if not cleaned_question:
        return None, None, "Question must not be empty."

    cached = get_cached_answer(cleaned_question, config_hash)
    if cached is not None:
        full_cached = get_cached_answer_by_id(cached["cache_id"])
        return full_cached, "hit", None

    try:
        start = time.perf_counter()

        generated_answer: GeneratedAnswer = st.session_state[
            "answer_generator"
        ].answer(
            question=cleaned_question,
            top_k=TOP_K,
        )

        latency_ms = int((time.perf_counter() - start) * 1000)

        cache_id = save_answer_to_cache(
            question_text=cleaned_question,
            config_hash=config_hash,
            gen_answer=generated_answer,
            latency_ms=latency_ms,
        )

        full_cached = get_cached_answer_by_id(cache_id)
        return full_cached, "miss", None

    except Exception as error:
        return None, None, f"{type(error).__name__}: {error}"


def render_bar_chart_or_empty(
    *,
    title: str,
    description: str,
    dataframe: pd.DataFrame,
    x: str,
    y: str,
    x_label: str,
    y_label: str,
    empty_message: str,
    horizontal: bool = False,
    height: int = 360,
) -> None:
    """
    Render an explicitly configured Altair bar chart or safe empty state.

    Altair is used instead of Streamlit's simple bar chart helper so the app
    can control category label orientation, chart dimensions, and axis layout.
    """
    st.subheader(title)
    st.caption(description)

    if dataframe.empty:
        st.info(empty_message)
        return

    if horizontal:
        chart = (
            alt.Chart(dataframe)
            .mark_bar()
            .encode(
                x=alt.X(
                    f"{x}:Q",
                    title=x_label,
                    axis=alt.Axis(
                        orient="bottom",
                        labelAngle=0,
                        grid=True,
                        tickCount=6,
                        titlePadding=14,
                    ),
                ),
                y=alt.Y(
                    f"{y}:N",
                    title=y_label,
                    sort="-x",
                    axis=alt.Axis(
                        labelAngle=0,
                        labelLimit=360,
                        labelPadding=8,
                        titlePadding=14,
                    ),
                ),
                tooltip=[
                    alt.Tooltip(f"{y}:N", title=y_label),
                    alt.Tooltip(f"{x}:Q", title=x_label, format=".2f"),
                ],
            )
            .properties(height=height)
            .configure_view(strokeWidth=0)
        )
    else:
        chart = (
            alt.Chart(dataframe)
            .mark_bar()
            .encode(
                x=alt.X(
                    f"{x}:N",
                    title=x_label,
                    axis=alt.Axis(
                        labelAngle=0,
                        labelLimit=160,
                        labelPadding=8,
                        titlePadding=14,
                    ),
                ),
                y=alt.Y(
                    f"{y}:Q",
                    title=y_label,
                    axis=alt.Axis(
                        grid=True,
                        titlePadding=14,
                    ),
                ),
                tooltip=[
                    alt.Tooltip(f"{x}:N", title=x_label),
                    alt.Tooltip(f"{y}:Q", title=y_label, format=".2f"),
                ],
            )
            .properties(height=height)
            .configure_view(strokeWidth=0)
        )

    st.altair_chart(chart, width="stretch")


def render_line_chart_or_empty(
    *,
    title: str,
    description: str,
    dataframe: pd.DataFrame,
    x: str,
    y: str,
    x_label: str,
    y_label: str,
    empty_message: str,
    minimum_rows: int = 2,
    height: int = 360,
) -> None:
    """Render a responsive Altair line chart or a safe empty state."""
    st.subheader(title)
    st.caption(description)

    if len(dataframe) < minimum_rows:
        st.info(empty_message)
        return

    chart = (
        alt.Chart(dataframe)
        .mark_line(point=True)
        .encode(
            x=alt.X(
                f"{x}:T",
                title=x_label,
                axis=alt.Axis(
                    labelAngle=0,
                    titlePadding=14,
                ),
            ),
            y=alt.Y(
                f"{y}:Q",
                title=y_label,
                axis=alt.Axis(
                    grid=True,
                    titlePadding=14,
                ),
            ),
            tooltip=[
                alt.Tooltip(f"{x}:T", title=x_label),
                alt.Tooltip(f"{y}:Q", title=y_label, format=".0f"),
            ],
        )
        .properties(height=height)
        .configure_view(strokeWidth=0)
    )

    st.altair_chart(chart, width="stretch")


# ---------- Page configuration ----------


st.set_page_config(
    page_title="DER RegCheck — Prototype",
    page_icon="⚡",
    layout="wide",
)


# ---------- Session state ----------


if "answer_generator" not in st.session_state:
    st.session_state["answer_generator"] = AnswerGenerator(
        prompt_version=PROMPT_VERSION,
    )

if "selected_cache_id" not in st.session_state:
    st.session_state["selected_cache_id"] = None

if "last_cache_status" not in st.session_state:
    st.session_state["last_cache_status"] = None

if "ask_question" not in st.session_state:
    st.session_state["ask_question"] = ""

if "review_question_id" not in st.session_state:
    st.session_state["review_question_id"] = None

if "review_is_tier2" not in st.session_state:
    st.session_state["review_is_tier2"] = False


CONFIG_HASH = compute_config_hash(
    prompt_version=PROMPT_VERSION,
    top_k=TOP_K,
    retrieval_config_id=RETRIEVAL_CONFIG_ID,
)

tier2_questions = load_tier2_questions()

tier2_by_id = {
    str(question.get("id")): question
    for question in tier2_questions
    if question.get("id")
}

UI_EXAMPLE_IDS = [
    "tier2_001",
    "tier2_003",
    "tier2_005",
    "tier2_009",
    "tier2_010",
]

ask_examples = [
    tier2_by_id[question_id]
    for question_id in UI_EXAMPLE_IDS
    if question_id in tier2_by_id
]


# ---------- Sidebar: recent-query navigation ----------


with st.sidebar:
    st.title("DER RegCheck")
    st.caption("Evidence-first DER interconnection research prototype")

    st.markdown("### Recent queries")

    try:
        recent_queries = list_recent_queries(limit=20)
    except Exception as error:
        recent_queries = []
        st.error(
            f"Could not load recent queries: {type(error).__name__}: {error}"
        )

    if not recent_queries:
        st.info("No cached queries yet. Use the Ask or Review tab to create one.")
    else:
        recent_query_by_label: dict[str, str] = {}

        for query in recent_queries:
            cache_id = str(query["cache_id"])
            question_text = str(query["question_text"]).replace("\n", " ").strip()

            short_question = (
                f"{question_text[:62].rstrip()}..."
                if len(question_text) > 62
                else question_text
            )

            status = ui_status_from_answer_status(str(query["answer_status"]))
            label = f"{status} — {short_question}"
            recent_query_by_label[label] = cache_id

        recent_labels = list(recent_query_by_label.keys())
        current_cache_id = str(st.session_state["selected_cache_id"] or "")

        selected_label_index = 0
        for index, label in enumerate(recent_labels):
            if recent_query_by_label[label] == current_cache_id:
                selected_label_index = index
                break

        selected_recent_label = st.selectbox(
            "Select a query",
            options=recent_labels,
            index=selected_label_index,
            key="recent_query_select",
        )

        if selected_recent_label:
            st.session_state["selected_cache_id"] = recent_query_by_label[
                selected_recent_label
            ]

    st.caption(
        "Questions are cached by question text and runtime configuration. "
        "Feedback and manual-review scores are separate records linked to the "
        "selected cached response."
    )


# ---------- Tabs ----------


tab_about, tab_ask, tab_evidence, tab_review, tab_monitoring = st.tabs(
    ["About", "Ask", "Evidence", "Review", "Monitoring"]
)


# ---------- About ----------


with tab_about:
    st.header("About DER RegCheck")

    st.markdown(
        "DER RegCheck is an evidence-first retrieval-augmented generation "
        "prototype for Distributed Energy Resource interconnection and "
        "market-entry research in California. The initial corpus focuses on "
        "CPUC Rule 21 and Southern California Edison materials."
    )

    st.warning(
        "**Important:** DER RegCheck is research support only. It is not legal, "
        "engineering, regulatory, or compliance advice. Verify requirements "
        "against current authoritative source documents and consult qualified "
        "professionals for project decisions, filings, approvals, and compliance."
    )

    st.markdown(
        f"""
**Runtime configuration**

- Prompt: `{PROMPT_VERSION}`
- Retrieval: original query → pgvector vector retrieval → cross-encoder reranking
- Returned evidence: top `{TOP_K}` chunks
- Cache identity: question text + prompt/retrieval configuration
- Feedback and reviewer scores: separate persistent events linked to cached responses
"""
    )

    st.markdown(
        """
**How to use the app**

1. Use **Ask** to submit a DER research question or load an example.
2. Review the answer status, response, evidence gaps, and suggested next steps.
3. Open **Evidence** to inspect expandable source excerpts and retrieval provenance.
4. Use **Review** to score Tier 2 or normal cached responses.
5. Use **Monitoring** to inspect answer behavior, feedback, quality, and latency.
"""
    )

    st.markdown(
        """
**Project links**

- [Repository README](https://github.com/andrew-chung-au/der-regcheck)
- [Runbook](https://github.com/andrew-chung-au/der-regcheck/blob/main/docs/runbook.md)
- [Evaluation notes](https://github.com/andrew-chung-au/der-regcheck/blob/main/docs/evaluation-notes.md)
"""
    )


# ---------- Ask ----------


with tab_ask:
    st.header("Ask a DER research question")

    example_label_to_question = {
        build_tier2_display_label(question): str(question["question"])
        for question in ask_examples
    }

    if example_label_to_question:
        selected_example_label = st.selectbox(
            "Load an example question",
            options=["Select an example..."] + list(example_label_to_question.keys()),
            key="ask_example_select",
        )

        if selected_example_label != "Select an example...":
            selected_example_question = example_label_to_question[
                selected_example_label
            ]

            if st.session_state["ask_question"] != selected_example_question:
                st.session_state["ask_question"] = selected_example_question
    else:
        st.caption(
            "Example questions are unavailable until "
            "`data/evaluation/tier2_questions.yaml` is created."
        )

    user_question = st.text_area(
        "Question",
        placeholder=(
            "Example: What interconnection review pathways could apply to a "
            "50 kW rooftop solar system in SCE territory?"
        ),
        height=110,
        key="ask_question",
    )

    if st.button(
        "Ask",
        disabled=not user_question.strip(),
        key="ask_button",
        type="primary",
    ):
        with st.spinner("Loading cached response or generating a grounded answer..."):
            cached_answer, cache_status, error_message = run_or_load_query(
                question_text=user_question,
                config_hash=CONFIG_HASH,
            )

        if error_message:
            st.error(f"Could not answer the question: {error_message}")
        elif cached_answer:
            st.session_state["selected_cache_id"] = cached_answer["cache_id"]
            st.session_state["last_cache_status"] = cache_status
            st.session_state["review_question_id"] = None
            st.session_state["review_is_tier2"] = False

            if cache_status == "hit":
                st.success(
                    "✅ Cache hit — loaded a previous response for this configuration."
                )
            elif cache_status == "miss":
                st.info("⚡ Cache miss — generated and stored a new response.")

    selected_cache_id = st.session_state.get("selected_cache_id")

    if selected_cache_id:
        cached_answer = get_cached_answer_by_id(selected_cache_id)

        if cached_answer:
            render_cached_answer(cached_answer)

            st.subheader("Feedback")
            st.caption(
                "Feedback is optional. The question and response are already "
                "stored in the query cache. Each submission creates a separate "
                "feedback event linked to this response."
            )

            feedback_rating = st.radio(
                "Was this response useful?",
                options=["👍 Helpful", "👎 Not helpful"],
                index=None,
                horizontal=True,
                key=f"feedback_rating_{selected_cache_id}",
            )

            feedback_comment = st.text_area(
                "Optional comment",
                placeholder="What was useful, missing, or unclear?",
                key=f"feedback_comment_{selected_cache_id}",
            )

            if st.button(
                "Submit feedback",
                disabled=feedback_rating is None,
                key=f"submit_feedback_{selected_cache_id}",
            ):
                rating_value = (
                    "helpful"
                    if feedback_rating == "👍 Helpful"
                    else "not_helpful"
                )

                try:
                    append_feedback(
                        cache_id=str(selected_cache_id),
                        rating=rating_value,
                        comment=feedback_comment,
                    )
                    st.success("Feedback saved.")
                except Exception as error:
                    st.error(
                        f"Could not save feedback: {type(error).__name__}: {error}"
                    )
        else:
            st.error("The selected cached response could not be found.")
    else:
        st.info("Submit a question or select a previous question from the sidebar.")


# ---------- Evidence ----------


with tab_evidence:
    st.header("Evidence")

    selected_cache_id = st.session_state.get("selected_cache_id")

    if selected_cache_id:
        cached_answer = get_cached_answer_by_id(selected_cache_id)

        if cached_answer:
            st.markdown(f"**Selected question:** {cached_answer['question_text']}")
            render_status_badge(str(cached_answer["answer_status"]))

            evidence_items = build_evidence_cards_data_from_cached(cached_answer)
            render_evidence_cards(evidence_items)
        else:
            st.error("The selected cached response could not be found.")
    else:
        st.info(
            "No query is selected. Submit a question in Ask or choose a cached "
            "question from the sidebar."
        )


# ---------- Review ----------


with tab_review:
    st.header("Manual review")

    st.markdown(
        "Use this tab to evaluate a selected cached answer. Tier 2 questions "
        "support realistic end-to-end RAG-quality evaluation; custom and recent "
        "queries support review of ordinary user interactions."
    )

    st.caption(
        "Each review is an independent record in PostgreSQL and "
        "`data/evaluation/tier2_manual_scores.jsonl`. Multiple reviewers, or "
        "multiple review rounds, can score the same cached response."
    )

    review_source = st.radio(
        "Review source",
        options=["Selected recent query", "Tier 2 question", "Custom question"],
        horizontal=True,
        key="review_source",
    )

    if review_source == "Selected recent query":
        selected_cache_id = st.session_state.get("selected_cache_id")

        if selected_cache_id:
            selected_cached = get_cached_answer_by_id(selected_cache_id)

            if selected_cached:
                st.markdown(
                    f"**Selected question:** {selected_cached['question_text']}"
                )
                st.session_state["review_question_id"] = None
                st.session_state["review_is_tier2"] = False
            else:
                st.error("The selected cached response could not be found.")
        else:
            st.info("Select a recent query from the sidebar or use Ask first.")

    elif review_source == "Tier 2 question":
        if not tier2_questions:
            st.warning(
                "No Tier 2 questions found. Create "
                "`data/evaluation/tier2_questions.yaml` first."
            )
        else:
            tier2_ids = [
                str(question["id"])
                for question in tier2_questions
                if question.get("id")
            ]

            selected_tier2_id = st.selectbox(
                "Select Tier 2 question",
                options=tier2_ids,
                format_func=lambda question_id: build_tier2_display_label(
                    tier2_by_id[question_id]
                ),
                key="review_tier2_select",
            )

            selected_tier2_question = tier2_by_id[selected_tier2_id]
            review_question_text = str(selected_tier2_question["question"])

            st.markdown(f"**Question:** {review_question_text}")

            category = selected_tier2_question.get("category")
            if category:
                st.caption(f"Evaluation category: `{category}`")

            expected_behavior = selected_tier2_question.get("expected_behavior")
            if expected_behavior:
                with st.expander("Reviewer expectations", expanded=False):
                    st.json(expected_behavior)

            if st.button(
                "Load or generate Tier 2 response",
                key="run_tier2_review",
                type="primary",
            ):
                with st.spinner(
                    "Loading cached response or generating a grounded answer..."
                ):
                    cached_answer, cache_status, error_message = run_or_load_query(
                        question_text=review_question_text,
                        config_hash=CONFIG_HASH,
                    )

                if error_message:
                    st.error(f"Could not load Tier 2 response: {error_message}")
                elif cached_answer:
                    st.session_state["selected_cache_id"] = cached_answer["cache_id"]
                    st.session_state["last_cache_status"] = cache_status
                    st.session_state["review_question_id"] = selected_tier2_id
                    st.session_state["review_is_tier2"] = True

                    if cache_status == "hit":
                        st.success(
                            "✅ Cache hit — loaded the Tier 2 response for this configuration."
                        )
                    elif cache_status == "miss":
                        st.info(
                            "⚡ Cache miss — generated and stored a Tier 2 response."
                        )

    else:
        review_question_text = st.text_area(
            "Custom question",
            placeholder=(
                "Enter a DER research question to generate and manually review."
            ),
            height=110,
            key="review_custom_question",
        )

        if st.button(
            "Load or generate custom response",
            disabled=not review_question_text.strip(),
            key="run_custom_review",
            type="primary",
        ):
            with st.spinner(
                "Loading cached response or generating a grounded answer..."
            ):
                cached_answer, cache_status, error_message = run_or_load_query(
                    question_text=review_question_text,
                    config_hash=CONFIG_HASH,
                )

            if error_message:
                st.error(f"Could not load custom response: {error_message}")
            elif cached_answer:
                st.session_state["selected_cache_id"] = cached_answer["cache_id"]
                st.session_state["last_cache_status"] = cache_status
                st.session_state["review_question_id"] = None
                st.session_state["review_is_tier2"] = False

                if cache_status == "hit":
                    st.success(
                        "✅ Cache hit — loaded a previous response for this configuration."
                    )
                elif cache_status == "miss":
                    st.info("⚡ Cache miss — generated and stored a new response.")

    selected_cache_id = st.session_state.get("selected_cache_id")

    if selected_cache_id:
        cached_answer = get_cached_answer_by_id(selected_cache_id)

        if cached_answer:
            st.divider()
            st.subheader("Response under review")
            render_cached_answer(cached_answer, show_question=True)

            st.subheader("Human evaluation")
            st.caption(
                "Score each dimension from 1 (poor) to 5 (excellent). Use the "
                "Evidence tab and Tier 2 expectations, where applicable, to "
                "support your assessment."
            )

            score_col_1, score_col_2 = st.columns(2)

            with score_col_1:
                score_groundedness = st.slider(
                    "Groundedness",
                    min_value=1,
                    max_value=5,
                    value=3,
                    key=f"score_groundedness_{selected_cache_id}",
                    help="Are factual claims supported by the retrieved evidence?",
                )

                score_relevance = st.slider(
                    "Relevance",
                    min_value=1,
                    max_value=5,
                    value=3,
                    key=f"score_relevance_{selected_cache_id}",
                    help="Does the answer address the actual user question?",
                )

                score_completeness = st.slider(
                    "Completeness",
                    min_value=1,
                    max_value=5,
                    value=3,
                    key=f"score_completeness_{selected_cache_id}",
                    help=(
                        "Does the answer cover the material points supported "
                        "by the evidence?"
                    ),
                )

            with score_col_2:
                score_citation_quality = st.slider(
                    "Citation quality",
                    min_value=1,
                    max_value=5,
                    value=3,
                    key=f"score_citation_quality_{selected_cache_id}",
                    help="Are claims traceable to appropriate evidence and sources?",
                )

                score_uncertainty = st.slider(
                    "Appropriate uncertainty",
                    min_value=1,
                    max_value=5,
                    value=3,
                    key=f"score_uncertainty_{selected_cache_id}",
                    help=(
                        "Does the answer state limits, missing facts, and "
                        "decision boundaries appropriately?"
                    ),
                )

            score_notes = st.text_area(
                "Reviewer notes",
                placeholder=(
                    "Record strengths, weaknesses, unsupported statements, "
                    "missing evidence, or suggested improvements."
                ),
                key=f"score_notes_{selected_cache_id}",
            )

            stored_question_id = st.session_state.get("review_question_id")
            stored_is_tier2 = bool(
                st.session_state.get("review_is_tier2", False)
            )

            if st.button(
                "Save manual review",
                key=f"save_score_{selected_cache_id}",
            ):
                try:
                    append_manual_score(
                        cache_id=str(selected_cache_id),
                        question_id=stored_question_id,
                        is_tier2=stored_is_tier2,
                        groundedness=score_groundedness,
                        relevance=score_relevance,
                        completeness=score_completeness,
                        citation_quality=score_citation_quality,
                        appropriate_uncertainty=score_uncertainty,
                        notes=score_notes,
                    )
                    st.success("Manual review saved.")
                except Exception as error:
                    st.error(
                        f"Could not save manual review: "
                        f"{type(error).__name__}: {error}"
                    )
        else:
            st.error("The selected cached response could not be found.")
    else:
        st.info(
            "Choose a recent query, load a Tier 2 question, or enter a custom "
            "question before scoring."
        )


# ---------- Monitoring ----------


with tab_monitoring:
    st.header("Monitoring and observability")

    st.caption(
        "Charts use real runtime records stored in PostgreSQL. A fresh database, "
        "new machine, or new Docker volume begins with no cached queries, "
        "feedback, or manual reviews. Each chart displays a safe empty-state "
        "message until enough relevant data exists."
    )

    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM query_cache")
                total_cached_queries = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM answer_feedback")
                total_feedback = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM manual_scores")
                total_manual_reviews = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(*) FROM manual_scores WHERE is_tier2 = TRUE"
                )
                total_tier2_reviews = cursor.fetchone()[0]

                cursor.execute(
                    """
                    SELECT
                        answer_status,
                        COUNT(*) AS query_count
                    FROM query_cache
                    GROUP BY answer_status
                    ORDER BY query_count DESC, answer_status
                    """
                )
                answer_status_rows = cursor.fetchall()

                cursor.execute(
                    """
                    SELECT
                        rating,
                        COUNT(*) AS feedback_count
                    FROM answer_feedback
                    GROUP BY rating
                    ORDER BY rating
                    """
                )
                feedback_rows = cursor.fetchall()

                cursor.execute(
                    """
                    SELECT
                        AVG(groundedness) AS groundedness,
                        AVG(relevance) AS relevance,
                        AVG(completeness) AS completeness,
                        AVG(citation_quality) AS citation_quality,
                        AVG(appropriate_uncertainty) AS appropriate_uncertainty
                    FROM manual_scores
                    """
                )
                average_scores_row = cursor.fetchone()

                cursor.execute(
                    """
                    SELECT
                        created_at,
                        latency_ms
                    FROM query_cache
                    WHERE latency_ms IS NOT NULL
                    ORDER BY created_at
                    """
                )
                latency_time_rows = cursor.fetchall()

                cursor.execute(
                    """
                    SELECT
                        answer_status,
                        AVG(latency_ms) AS average_latency_ms
                    FROM query_cache
                    WHERE latency_ms IS NOT NULL
                    GROUP BY answer_status
                    ORDER BY average_latency_ms DESC
                    """
                )
                latency_status_rows = cursor.fetchall()

                cursor.execute(
                    """
                    SELECT
                        DATE(created_at) AS query_date,
                        COUNT(*) AS query_count
                    FROM query_cache
                    GROUP BY DATE(created_at)
                    ORDER BY query_date
                    """
                )
                query_volume_rows = cursor.fetchall()

                cursor.execute(
                    """
                    SELECT
                        question_id,
                        COUNT(*) AS review_count
                    FROM manual_scores
                    WHERE is_tier2 = TRUE
                      AND question_id IS NOT NULL
                    GROUP BY question_id
                    ORDER BY question_id
                    """
                )
                tier2_coverage_rows = cursor.fetchall()

    except Exception as error:
        st.error(
            f"Could not load monitoring data: {type(error).__name__}: {error}"
        )

    else:
        (
            metric_queries,
            metric_feedback,
            metric_reviews,
            metric_tier2,
            metric_coverage,
        ) = st.columns(5)

        metric_queries.metric("Cached queries", total_cached_queries)
        metric_feedback.metric("Feedback events", total_feedback)
        metric_reviews.metric("Manual reviews", total_manual_reviews)
        metric_tier2.metric("Tier 2 reviews", total_tier2_reviews)

        tier2_question_count = len(tier2_questions)
        tier2_questions_reviewed = len(
            {row[0] for row in tier2_coverage_rows if row[0]}
        )

        metric_coverage.metric(
            "Tier 2 coverage",
            (
                f"{tier2_questions_reviewed} / {tier2_question_count}"
                if tier2_question_count
                else "N/A"
            ),
        )

        st.divider()

        # Chart 1: Answer status distribution
        status_df = pd.DataFrame(
            answer_status_rows,
            columns=["answer_status", "query_count"],
        )

        if not status_df.empty:
            status_df["answer_status"] = status_df["answer_status"].map(
                ui_status_from_answer_status
            )

        render_bar_chart_or_empty(
            title="1. Answer status distribution",
            description=(
                "Distribution of cached answers by response status. This shows "
                "whether the system answers, requests clarification, identifies "
                "insufficient evidence, or applies a high-stakes boundary."
            ),
            dataframe=status_df,
            x="query_count",
            y="answer_status",
            x_label="Cached responses",
            y_label="Answer status",
            empty_message=(
                "No cached responses yet. Submit a question in Ask or generate "
                "a Tier 2 response in Review."
            ),
            horizontal=True,
            height=350,
        )

        # Chart 2: Feedback distribution
        feedback_df = pd.DataFrame(
            feedback_rows,
            columns=["rating", "feedback_count"],
        )

        if not feedback_df.empty:
            feedback_df["rating"] = feedback_df["rating"].replace(
                {
                    "helpful": "Helpful",
                    "not_helpful": "Not helpful",
                }
            )

        render_bar_chart_or_empty(
            title="2. Feedback distribution",
            description=(
                "Helpful and not-helpful feedback events. Multiple feedback "
                "events may be associated with the same cached response."
            ),
            dataframe=feedback_df,
            x="feedback_count",
            y="rating",
            x_label="Feedback events",
            y_label="Feedback rating",
            empty_message=(
                "No feedback yet. Select or generate an answer in Ask and "
                "submit Helpful or Not helpful feedback."
            ),
            horizontal=True,
            height=280,
        )

        # Chart 3: Average manual-review scores
        score_labels = [
            "Groundedness",
            "Relevance",
            "Completeness",
            "Citation quality",
            "Appropriate uncertainty",
        ]

        score_values = (
            list(average_scores_row)
            if average_scores_row is not None
            else [None, None, None, None, None]
        )

        has_manual_scores = any(value is not None for value in score_values)

        if has_manual_scores:
            manual_scores_df = pd.DataFrame(
                {
                    "dimension": score_labels,
                    "average_score": [
                        round(float(value), 2)
                        for value in score_values
                    ],
                }
            )
        else:
            manual_scores_df = pd.DataFrame(
                columns=["dimension", "average_score"]
            )

        render_bar_chart_or_empty(
            title="3. Average manual-review scores",
            description=(
                "Mean human-review score by quality dimension. Scores range "
                "from 1 (poor) to 5 (excellent)."
            ),
            dataframe=manual_scores_df,
            x="average_score",
            y="dimension",
            x_label="Average score (1–5)",
            y_label="Evaluation dimension",
            empty_message=(
                "No manual reviews yet. Select a cached answer in Review, "
                "complete the scoring form, and save the review."
            ),
            horizontal=True,
            height=360,
        )

        # Chart 4: Generation latency over time
        latency_time_df = pd.DataFrame(
            latency_time_rows,
            columns=["created_at", "latency_ms"],
        )

        if not latency_time_df.empty:
            latency_time_df["created_at"] = pd.to_datetime(
                latency_time_df["created_at"]
            )

        render_line_chart_or_empty(
            title="4. Generation latency over time",
            description=(
                "End-to-end RAG generation latency captured only on cache misses. "
                "Cache hits are database lookups and are intentionally excluded."
            ),
            dataframe=latency_time_df,
            x="created_at",
            y="latency_ms",
            x_label="Response generation time",
            y_label="Generation latency (ms)",
            empty_message=(
                "At least two cache-miss responses are needed to show a "
                "generation-latency trend. Submit two different uncached questions."
            ),
            minimum_rows=2,
            height=360,
        )

        # Chart 5: Average generation latency by answer status
        latency_status_df = pd.DataFrame(
            latency_status_rows,
            columns=["answer_status", "average_latency_ms"],
        )

        if not latency_status_df.empty:
            latency_status_df["answer_status"] = latency_status_df[
                "answer_status"
            ].map(ui_status_from_answer_status)

            latency_status_df["average_latency_ms"] = (
                latency_status_df["average_latency_ms"]
                .astype(float)
                .round(0)
            )

        render_bar_chart_or_empty(
            title="5. Average generation latency by answer status",
            description=(
                "Average cache-miss RAG generation time grouped by answer status. "
                "This helps identify whether response behavior is associated with "
                "runtime cost."
            ),
            dataframe=latency_status_df,
            x="average_latency_ms",
            y="answer_status",
            x_label="Average generation latency (ms)",
            y_label="Answer status",
            empty_message=(
                "No generated responses are available yet. Submit an uncached "
                "question to record a complete generation-latency measurement."
            ),
            horizontal=True,
            height=380,
        )

        # Chart 6: Cached query volume per day
        query_volume_df = pd.DataFrame(
            query_volume_rows,
            columns=["query_date", "query_count"],
        )

        if not query_volume_df.empty:
            query_volume_df["query_date"] = pd.to_datetime(
                query_volume_df["query_date"]
            )

        st.subheader("6. Cached query volume over time")
        st.caption(
            "Number of unique configuration-matched cached responses created "
            "per day. Repeated cache hits do not create additional cache rows."
        )

        if query_volume_df.empty:
            st.info(
                "No cached queries yet. Submit a question in Ask or generate "
                "a Tier 2 response in Review."
            )
        else:
            query_volume_chart = (
                alt.Chart(query_volume_df)
                .mark_bar()
                .encode(
                    x=alt.X(
                        "query_date:T",
                        title="Date",
                        axis=alt.Axis(
                            format="%d %b",
                            labelAngle=0,
                            labelPadding=8,
                            titlePadding=14,
                        ),
                    ),
                    y=alt.Y(
                        "query_count:Q",
                        title="New cached responses",
                        axis=alt.Axis(
                            grid=True,
                            tickMinStep=1,
                            titlePadding=14,
                        ),
                    ),
                    tooltip=[
                        alt.Tooltip(
                            "query_date:T",
                            title="Date",
                            format="%d %b %Y",
                        ),
                        alt.Tooltip(
                            "query_count:Q",
                            title="New cached responses",
                            format=".0f",
                        ),
                    ],
                )
                .properties(height=360)
                .configure_view(strokeWidth=0)
            )

            st.altair_chart(query_volume_chart, width="stretch")

        # Chart 7: Tier 2 manual-review coverage
        tier2_coverage_df = pd.DataFrame(
            tier2_coverage_rows,
            columns=["question_id", "review_count"],
        )

        if not tier2_coverage_df.empty:
            tier2_coverage_df["question_code"] = (
                tier2_coverage_df["question_id"]
                .str.replace("tier2_", "T2-", regex=False)
                .str.upper()
            )

        tier2_chart_height = max(300, len(tier2_coverage_df) * 48)

        render_bar_chart_or_empty(
            title="7. Tier 2 manual-review coverage",
            description=(
                "Number of saved human reviews for each curated Tier 2 realistic "
                "RAG-quality evaluation question. Use the Review tab to inspect "
                "the full question and expected behavior for each code."
            ),
            dataframe=tier2_coverage_df,
            x="review_count",
            y="question_code",
            x_label="Saved manual reviews",
            y_label="Tier 2 question",
            empty_message=(
                "No Tier 2 reviews yet. Select a Tier 2 question in Review and "
                "save a manual evaluation."
            ),
            horizontal=True,
            height=tier2_chart_height,
        )

        st.divider()

        st.caption(
            "Interpretation note: generation latency is recorded only for cache "
            "misses. Cache hits reuse a configuration-matched persisted response "
            "and are not equivalent to a complete embedding, retrieval, reranking, "
            "and LLM-generation run."
        )