import pandas as pd
import streamlit as st

from sift.store import (
    STATUS_PROGRESSION,
    delete_assessment,
    init_db,
    load_assessments,
    update_tags,
)

st.set_page_config(page_title="⏳ Sift", layout="wide")
st.title("⏳ Sift Job Listings")

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
FIT_ICON = {"high": "▲", "medium": "◆", "low": "▽"}
STATUS_ICON = {
    "New": "✨",
    "Researching": "🔵",
    "Applied": "🟢",
    "Rejected": "🔴",
}

SUGGESTION_LABELS = {
    f"{SUGGESTION_ICON[v]} {v.title()}": v for v in ["apply", "consider", "skip"]
}
FIT_LABELS = {f"{FIT_ICON[v]} {v}": v for v in ["high", "medium", "low"]}


def _stars_display(v) -> str:
    if v is None or pd.isna(v):
        return ""
    n = int(v) + 1
    return "★" * n + "☆" * (5 - n)


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
df["status"] = raw_df["status"].map(
    lambda v: f"{STATUS_ICON.get(v, '')} {v}" if v else "✨ New"
)
df["stars"] = raw_df["stars"].apply(_stars_display)

# --- Sidebar filters ---
st.sidebar.header("Filters")

search = st.sidebar.text_input("Search", placeholder="employer, title, reasoning...")

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
status_filter = st.sidebar.pills(
    "Status",
    options=STATUS_PROGRESSION,
    default=STATUS_PROGRESSION,
    selection_mode="multi",
) or list(STATUS_PROGRESSION)

hide_hidden = st.sidebar.checkbox("Hide hidden entries", value=True)

employers = sorted([e for e in raw_df["employer"].unique() if e])
selected_employers = (
    (
        st.sidebar.pills(
            "Employer", options=employers, default=None, selection_mode="multi"
        )
        or []
    )
    if employers
    else []
)

job_titles = sorted([t for t in raw_df["job_title"].unique() if t])
selected_titles = (
    (
        st.sidebar.pills(
            "Job Title", options=job_titles, default=None, selection_mode="multi"
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

mask = (
    raw_df["suggestion"].isin(suggestions)
    & raw_df["domain_fit"].isin(domain_fits)
    & raw_df["role_fit"].isin(role_fits)
    & raw_df["status"].isin(status_filter)
)
if hide_hidden:
    mask &= ~raw_df["hidden"].astype(bool)
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
    )

filtered = df[mask].reset_index(drop=True)
filtered_raw = raw_df[mask].reset_index(drop=True)

st.caption(f"{len(filtered)} of {len(df)} assessments shown")

# --- Table ---
TABLE_COLS = [
    "suggestion",
    "employer",
    "job_title",
    "domain_fit",
    "role_fit",
    "gap_risk",
    "status",
    "stars",
    "scraped_at",
    "url",
]

selected_url = st.session_state.get("selected_url")
table_height = 280 if selected_url else 560

selection = st.dataframe(
    filtered[TABLE_COLS],
    column_config={
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
        "status": st.column_config.TextColumn("Status"),
        "stars": st.column_config.TextColumn("Stars"),
        "source": st.column_config.TextColumn("Source"),
        "scraped_at": st.column_config.TextColumn("Date"),
        "url": st.column_config.LinkColumn(
            "Link",
            display_text="https?://(?:[a-zA-Z0-9-]+\\.)*([a-zA-Z0-9-]+\\.[a-zA-Z]{2,})",
        ),
    },
    use_container_width=True,
    hide_index=True,
    height=table_height,
    selection_mode="single-row",
    on_select="rerun",
)

# When a table row is clicked, update selected_url and clear widget state for
# that URL so segmented_control/toggle/feedback initialise from DB values.
selected_rows = selection.selection.rows
if selected_rows:
    clicked_url = filtered_raw.iloc[selected_rows[0]]["url"]
    if clicked_url != selected_url:
        for key in (
            f"status_{clicked_url}",
            f"hidden_{clicked_url}",
            f"stars_{clicked_url}",
        ):
            st.session_state.pop(key, None)
        st.session_state["selected_url"] = clicked_url
        selected_url = clicked_url

# --- Detail panel ---
if selected_url:
    matches = raw_df[raw_df["url"] == selected_url]
    if matches.empty:
        st.session_state.pop("selected_url", None)
    else:
        row = matches.iloc[0]
        st.divider()

        st.markdown(f"### {row['job_title']}")
        st.markdown(f"#### {row['employer']}")

        col1, col2 = st.columns([2, 1])

        with col1:
            if row.get("job_summary"):
                st.caption(row["job_summary"])
            with st.expander("Original Job Listing", expanded=True):
                if row.get("listing_text"):
                    st.markdown(row["listing_text"])
                else:
                    st.caption("No listing text available.")

            st.subheader("AI Assessment")
            st.markdown(row["reasoning"])
            summary = row.get("summary") or []
            if summary:
                st.markdown("\n".join(f"- {b}" for b in summary))

        with col2:
            current_status = row["status"]
            current_hidden = row["hidden"]
            current_stars = row["stars"]

            # st.feedback has no default param — initialise from DB via session state
            star_key = f"stars_{selected_url}"
            if star_key not in st.session_state and current_stars is not None:
                st.session_state[star_key] = current_stars

            new_status = st.segmented_control(
                "Status",
                options=STATUS_PROGRESSION,
                default=current_status,
                key=f"status_{selected_url}",
                width="content",
            )

            st.caption("Rating")
            new_stars = st.feedback("stars", key=star_key)

            # Auto-save status and stars on change
            if (
                new_status is not None and new_status != current_status
            ) or new_stars != current_stars:
                update_tags(
                    selected_url,
                    new_status or current_status,
                    current_hidden,
                    new_stars,
                )

            st.divider()
            url = row["url"]
            short_url = (url[:60] + "…") if len(url) > 60 else url
            st.write(
                f"**Source:** {SOURCE_DISPLAY.get(row['source'], row['source'].title())}"
            )
            st.write(f"**Language:** {row['language']}")
            st.write(f"**Date:** {row['scraped_at']}")
            st.write(f"**Link:** [{short_url}]({url})")

            st.divider()
            st.caption(
                "Hide or delete entries. "
                "Hidden entries can be shown via a toggle in the sidebar. "
                "Deleted entries are removed for good."
            )
            hide_col, delete_col = st.columns(2)
            with hide_col:
                hide_label = "Unhide" if current_hidden else "Hide"
                if st.button(hide_label, key="hide_btn", use_container_width=True):
                    update_tags(
                        selected_url, current_status, not current_hidden, current_stars
                    )
                    st.rerun()
            with delete_col:
                if st.button("🗑 Delete", key="delete_btn", use_container_width=True):
                    st.session_state["confirm_delete"] = selected_url
            if st.session_state.get("confirm_delete") == selected_url:
                st.warning("This will permanently delete this entry.")
                if st.button("Confirm delete", key="confirm_btn"):
                    delete_assessment(selected_url)
                    st.session_state.pop("confirm_delete", None)
                    st.session_state.pop("selected_url", None)
                    st.rerun()
