import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from sift.store import delete_assessment, init_db, load_assessments, update_rating

st.set_page_config(page_title="💘 Sifter", layout="wide")
st.title("💘 Sifter")

init_db()
assessments = load_assessments()

if not assessments:
    st.info("No assessments yet. Run the pipeline first.")
    st.stop()

SOURCE_DISPLAY = {
    "stepstone": "StepStone",
    "linkedin": "LinkedIn",
    "manual-test": "Manual",
}
SUGGESTION_ICON = {"apply": "🟢", "consider": "🟡", "skip": "🔴"}
FIT_ICON = {"high": "🟢", "medium": "🟡", "low": "🔴"}
GAP_ICON = {"high": "🔴", "medium": "🟡", "low": "🟢"}
RATING_ICON = {"new": "🆕", "liked": "👍", "disliked": "👎"}

SUGGESTION_LABELS = {
    f"{SUGGESTION_ICON[v]} {v.title()}": v for v in ["apply", "consider", "skip"]
}
FIT_LABELS = {f"{FIT_ICON[v]} {v}": v for v in ["high", "medium", "low"]}
GAP_LABELS = {f"{GAP_ICON[v]} {v}": v for v in ["high", "medium", "low"]}
RATING_LABELS = {
    f"{RATING_ICON[v]} {v.title()}": v for v in ["new", "liked", "disliked"]
}

raw_df = pd.DataFrame([a.model_dump() for a in assessments])
raw_df["scraped_at"] = pd.to_datetime(raw_df["scraped_at"]).dt.strftime("%Y-%m-%d")

df = raw_df.copy()
df["suggestion"] = df["suggestion"].map(lambda v: f"{SUGGESTION_ICON[v]} {v.title()}")
_DOT = {"high": "🟢", "medium": "🟡", "low": "🔴"}
_DOT_INV = {"low": "🟢", "medium": "🟡", "high": "🔴"}
df["domain_fit"] = raw_df["domain_fit"].map(_DOT)
df["role_fit"] = raw_df["role_fit"].map(_DOT)
df["gap_risk"] = raw_df["gap_risk"].map(_DOT_INV)
df["source"] = df["source"].map(lambda v: SOURCE_DISPLAY.get(v, v.title()))
df["rating"] = raw_df["rating"].map(lambda v: RATING_ICON.get(v, "🆕"))

# --- Sidebar filters ---
st.sidebar.header("Filters")

# Predefined pills for ratings, suggestions, fits, and gap risk
rating_labels = st.sidebar.pills(
    "Rating",
    options=list(RATING_LABELS),
    default=[k for k, v in RATING_LABELS.items() if v in ("new", "liked")],
    selection_mode="multi",
) or list(RATING_LABELS)
suggestion_labels = st.sidebar.pills(
    "Suggestion",
    options=list(SUGGESTION_LABELS),
    default=list(SUGGESTION_LABELS),
    selection_mode="multi",
)
domain_fit_labels = st.sidebar.pills(
    "Domain Fit",
    options=list(FIT_LABELS),
    default=list(FIT_LABELS),
    selection_mode="multi",
)
role_fit_labels = st.sidebar.pills(
    "Role Fit",
    options=list(FIT_LABELS),
    default=list(FIT_LABELS),
    selection_mode="multi",
)
gap_risk_labels = st.sidebar.pills(
    "Gap Risk",
    options=list(GAP_LABELS),
    default=list(GAP_LABELS),
    selection_mode="multi",
)

# Search box for employer, title, or reasoning text
search = st.sidebar.text_input(
    "Search", placeholder="Employer, job title, listing, ..."
)

# Multi-select filters for employer and job title, populated from the dataset
employers = sorted([e for e in raw_df["employer"].unique() if e])
selected_employers = (
    (
        st.sidebar.multiselect(
            "Employer",
            options=employers,
            default=None,
            placeholder="Filter by employer",
        )
        or []
    )
    if employers
    else []
)

job_titles = sorted([t for t in raw_df["job_title"].unique() if t])
selected_titles = (
    (
        st.sidebar.multiselect(
            "Job Title",
            options=job_titles,
            default=None,
            placeholder="Filter by job title",
        )
        or []
    )
    if job_titles
    else []
)

# --- Apply filters ---
suggestions = [SUGGESTION_LABELS[l] for l in suggestion_labels]
domain_fits = [FIT_LABELS[l] for l in domain_fit_labels]
role_fits = [FIT_LABELS[l] for l in role_fit_labels]
ratings = [RATING_LABELS[l] for l in rating_labels]

mask = (
    raw_df["suggestion"].isin(suggestions)
    & raw_df["domain_fit"].isin(domain_fits)
    & raw_df["role_fit"].isin(role_fits)
    & raw_df["rating"].isin(ratings)
)
if selected_employers:
    mask &= raw_df["employer"].isin(selected_employers)
if selected_titles:
    mask &= raw_df["job_title"].isin(selected_titles)
if search:
    sl = search.lower()
    mask &= (
        raw_df["employer"].str.lower().str.contains(sl, na=False)
        | raw_df["job_title"].str.lower().str.contains(sl, na=False)
        | raw_df["reasoning"].str.lower().str.contains(sl, na=False)
        | raw_df["listing_text"].str.lower().str.contains(sl, na=False)
    )

filtered = df[mask].reset_index(drop=True)
filtered_raw = raw_df[mask].reset_index(drop=True)

st.caption(f"{len(filtered)} of {len(df)} assessments shown")

# --- Table ---
TABLE_COLS = [
    "rating",
    "suggestion",
    "employer",
    "job_title",
    "domain_fit",
    "role_fit",
    "gap_risk",
    "scraped_at",
    "url",
]

selected_url = st.session_state.get("selected_url")

# Auto-select first visible row if nothing is selected
if not selected_url and not filtered_raw.empty:
    selected_url = filtered_raw.iloc[0]["url"]
    st.session_state["selected_url"] = selected_url

_ROW_H = 35
_HEADER_H = 38
table_height = min(len(filtered) * _ROW_H + _HEADER_H, 280 if selected_url else 560)

selection = st.dataframe(
    filtered[TABLE_COLS],
    column_config={
        "rating": st.column_config.TextColumn("Rating"),
        "suggestion": st.column_config.TextColumn(
            "Suggestion",
            help="LLM recommendation: apply, consider, or skip. Advisory only.",
        ),
        "employer": st.column_config.TextColumn("Employer"),
        "job_title": st.column_config.TextColumn("Job Title"),
        "domain_fit": st.column_config.TextColumn(
            "Domain",
            help="Domain fit: 🟢 high · 🟡 medium · 🔴 low",
        ),
        "role_fit": st.column_config.TextColumn(
            "Role",
            help="Role fit: 🟢 high · 🟡 medium · 🔴 low",
        ),
        "gap_risk": st.column_config.TextColumn(
            "Gap",
            help="Gap risk (inverted): 🟢 low risk · 🟡 medium · 🔴 high risk",
        ),
        "scraped_at": st.column_config.TextColumn("Date"),
        "url": st.column_config.LinkColumn(
            "Link",
            display_text="https?://(?:[a-zA-Z0-9-]+\\.)*([a-zA-Z0-9-]+\\.[a-zA-Z]{2,})",
        ),
    },
    width="stretch",
    hide_index=True,
    height=table_height,
    selection_mode="single-row",
    on_select="rerun",
)

# When a table row is clicked, update selected_url.
selected_rows = selection.selection.rows
if selected_rows and not st.session_state.pop("_from_nav", False):
    clicked_url = filtered_raw.iloc[selected_rows[0]]["url"]
    if clicked_url != selected_url:
        st.session_state["selected_url"] = clicked_url
        selected_url = clicked_url

# Show queued toast (set before a st.rerun() call)
if "_toast" in st.session_state:
    st.toast(st.session_state.pop("_toast"))

# --- Detail panel ---
if selected_url:
    matches = raw_df[raw_df["url"] == selected_url]
    if matches.empty:
        st.session_state.pop("selected_url", None)
    else:
        row = matches.iloc[0]
        st.divider()

        # Prev / Next + quick-rate navigation row
        _pos = filtered_raw.index[filtered_raw["url"] == selected_url]
        _pos = int(_pos[0]) if len(_pos) else 0
        _total = len(filtered_raw)
        _next_url = filtered_raw.iloc[_pos + 1]["url"] if _pos < _total - 1 else None

        _, _nav = st.columns([2, 1], gap="large")
        with _nav:
            _pc, _mc, _nc, _gap, _bc, _hc = st.columns([1, 1.5, 1, 0.3, 1, 1])
            with _pc:
                if st.button("‹", disabled=_pos == 0, use_container_width=True):
                    st.session_state["selected_url"] = filtered_raw.iloc[_pos - 1][
                        "url"
                    ]
                    st.session_state["_from_nav"] = True
                    st.rerun()
            with _mc:
                st.markdown(
                    f"<p style='text-align:center;padding-top:4px;font-size:0.85rem'>{_pos + 1} / {_total}</p>",
                    unsafe_allow_html=True,
                )
            with _nc:
                if st.button(
                    "›", disabled=_pos >= _total - 1, use_container_width=True
                ):
                    st.session_state["selected_url"] = filtered_raw.iloc[_pos + 1][
                        "url"
                    ]
                    st.session_state["_from_nav"] = True
                    st.rerun()
            _current_rating = row["rating"]
            with _bc:
                if st.button(
                    "👍",
                    type="primary" if _current_rating == "liked" else "secondary",
                    use_container_width=True,
                    help="Like (b)",
                ):
                    new_r = "new" if _current_rating == "liked" else "liked"
                    update_rating(selected_url, new_r)
                    st.session_state["_toast"] = (
                        "Liked 👍" if new_r == "liked" else "Removed 👍"
                    )
                    if _next_url and new_r == "liked":
                        st.session_state["selected_url"] = _next_url
                        st.session_state["_from_nav"] = True
                    st.rerun()
            with _hc:
                if st.button(
                    "👎",
                    type="primary" if _current_rating == "disliked" else "secondary",
                    use_container_width=True,
                    help="Dislike (x)",
                ):
                    new_r = "new" if _current_rating == "disliked" else "disliked"
                    update_rating(selected_url, new_r)
                    st.session_state["_toast"] = (
                        "Hidden 👎" if new_r == "disliked" else "Removed 👎"
                    )
                    if _next_url and new_r == "disliked":
                        st.session_state["selected_url"] = _next_url
                        st.session_state["_from_nav"] = True
                    st.rerun()

        col1, col2 = st.columns([2, 1], gap="large")

        with col1:
            st.markdown(f"### {row['job_title']}")
            st.markdown(f"#### {row['employer']}")

            if row.get("job_summary"):
                st.caption(row["job_summary"])
            with st.container(border=True):
                if row.get("listing_text"):
                    st.markdown(row["listing_text"])
                else:
                    st.caption("No listing text available.")

        with col2:
            st.markdown(
                "### {} Suggestion: {}".format(
                    SUGGESTION_ICON.get(row["suggestion"], ""),
                    row["suggestion"].title(),
                )
            )
            st.caption(row["reasoning"])

            st.markdown("#### Fit analysis")
            st.markdown(
                f"**{FIT_ICON.get(row['domain_fit'], '')} Domain fit: {row['domain_fit'].title()}**"
            )
            if row.get("domain_fit_reason"):
                st.caption(row["domain_fit_reason"])
            st.markdown(
                f"**{FIT_ICON.get(row['role_fit'], '')} Role fit: {row['role_fit'].title()}**"
            )
            if row.get("role_fit_reason"):
                st.caption(row["role_fit_reason"])
            st.markdown(
                f"**{GAP_ICON.get(row['gap_risk'], '')} Gap risk: {row['gap_risk'].title()}**"
            )
            if row.get("gap_risk_reason"):
                st.caption(row["gap_risk_reason"])

            with st.expander("Show details", expanded=False):
                fit_areas = row.get("fit_areas") or []
                gaps = row.get("gaps") or []
                SEVERITY_ICON = {"minor": "🟡", "manageable": "🟠", "severe": "🔴"}
                if fit_areas:
                    st.markdown("**Concrete Overlap**")
                    for area in fit_areas:
                        st.caption(f"- {area}")
                if gaps:
                    st.markdown("**Concrete Gaps**")
                    for gap in gaps:
                        icon = SEVERITY_ICON.get(gap.get("severity", ""), "")
                        st.caption(f"- {icon} {gap['description']}")

            st.divider()
            source_col, date_col = st.columns(2)
            with source_col:
                st.write(
                    f"**Source:** {SOURCE_DISPLAY.get(row['source'], row['source'].title())}"
                )
            with date_col:
                st.write(f"**Date:** {row['scraped_at']}")
            url = row["url"]
            if url:
                st.link_button(
                    "Open original listing",
                    url,
                    icon=":material/open_in_new:",
                    type="secondary",
                    width="stretch",
                )

            st.divider()
            if st.button(
                "Delete listing from database",
                key="delete_btn",
                width="stretch",
                type="secondary",
            ):
                st.session_state["confirm_delete"] = selected_url
            if st.session_state.get("confirm_delete") == selected_url:
                st.warning("This will permanently delete this entry.")
                if st.button(
                    "Confirm delete", key="confirm_btn", width="stretch", type="primary"
                ):
                    delete_assessment(selected_url)
                    st.session_state.pop("confirm_delete", None)
                    st.session_state.pop("selected_url", None)
                    st.rerun()

# Keyboard navigation: arrow keys and k/l move through listings; b/x for like/dislike.
# Injected into the parent frame; deduplication guard prevents stacking listeners on reruns.
components.html(
    """
    <script>
    (function () {
        var win = window.parent;
        if (win._sift_nav_bound) return;
        win._sift_nav_bound = true;
        win.document.addEventListener('keydown', function (e) {
            var active = win.document.activeElement;
            if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA' || active.isContentEditable)) return;
            var label = null;
            if (e.key === 'ArrowLeft'  || e.key === 'k') label = '\u2039';
            if (e.key === 'ArrowRight' || e.key === 'l') label = '\u203a';
            if (e.key === 'b') label = '👍';
            if (e.key === 'x') label = '👎';
            if (!label) return;
            var buttons = win.document.querySelectorAll('button');
            for (var i = 0; i < buttons.length; i++) {
                if (buttons[i].innerText.trim() === label && !buttons[i].disabled) {
                    buttons[i].click();
                    return;
                }
            }
        });
    })();
    </script>
    """,
    height=0,
)
