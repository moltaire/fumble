import re
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st
import tomlkit

_REPO_ROOT = Path(__file__).parent.parent
_RESOURCES = _REPO_ROOT / "resources"

_PROFILE_PATH = _RESOURCES / "profile.md"
_PROFILE_EXAMPLE = _RESOURCES / "profile.example.md"
_CRITERIA_PATH = _RESOURCES / "search-criteria.md"
_CRITERIA_EXAMPLE = _RESOURCES / "search-criteria.example.md"
_SOURCES_PATH = _RESOURCES / "sources.toml"

# Domains used by generic email-sending platforms — too broad on their own,
# so we include a path segment to make the pattern more specific.
_GENERIC_DOMAINS = {
    "ct.sendgrid.net",
    "sendgrid.net",
    "links.brevo.net",
    "brevo.net",
    "list-manage.com",
    "mailchimp.com",
    "mailtrack.io",
}

# Known job board presets — everything except the IMAP folder, which is personal.
_PRESETS: dict[str, dict] = {
    "LinkedIn": {
        "name": "linkedin",
        "display": "LinkedIn",
        "url_pattern": r"linkedin\.com/comm/jobs/view",
        "dedup_pattern": r"/jobs/view/(\d+)",
        "scraper": "browser",
    },
    "StepStone": {
        "name": "stepstone",
        "display": "StepStone",
        "url_pattern": r"click\.stepstone\.de",
    },
    "GoodJobs": {
        "name": "goodjobs",
        "display": "GoodJobs",
        "url_pattern": r"brevo\.net/tr/cl|list-manage\.com/track/click",
    },
    "Climatebase": {
        "name": "climatebase",
        "display": "Climatebase",
        "url_pattern": r"ct\.sendgrid\.net/ls/click",
    },
    "Academics": {
        "name": "academics",
        "display": "Academics",
        "url_pattern": r"academics\.de/lnk",
    },
    "Google Jobs": {
        "name": "google",
        "display": "Google",
        "url_pattern": r"google\.com/about/careers/applications/jobs/results/",
    },
}


def _suggest_pattern(url: str) -> str:
    """Derive a reasonable url_pattern regex from a raw tracking URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith("www."):
            domain = domain[4:]
        pattern = re.escape(domain)
        path_parts = [p for p in parsed.path.split("/") if p]
        if path_parts:
            # Always include first path segment — makes the pattern more specific
            # and handles generic tracker domains that share a domain across clients.
            pattern += "/" + re.escape(path_parts[0])
        return pattern
    except Exception:
        return ""


def _load_text(path: Path, fallback: Path) -> str:
    if path.exists():
        return path.read_text()
    if fallback.exists():
        return fallback.read_text()
    return ""


def _load_sources() -> list[dict]:
    if not _SOURCES_PATH.exists():
        return []
    with open(_SOURCES_PATH) as f:
        data = tomlkit.load(f)
    return list(data.get("sources", []))


def _save_sources(sources: list[dict]) -> None:
    doc = tomlkit.document()
    aot = tomlkit.aot()
    for source in sources:
        t = tomlkit.table()
        for k, v in source.items():
            t.add(k, v)
        aot.append(t)
    doc.add("sources", aot)
    _SOURCES_PATH.write_text(tomlkit.dumps(doc))


@st.dialog("Source")
def _source_dialog(existing: dict | None = None) -> None:
    is_edit = existing is not None

    # Reset all dialog state when switching between sources (or add vs edit),
    # identified by source name or "__new__" for the add form.
    _ctx = existing["name"] if is_edit else "__new__"
    if st.session_state.get("_dlg_ctx") != _ctx:
        st.session_state["_dlg_ctx"] = _ctx
        st.session_state["_dlg_preset"] = "Custom"
        st.session_state["_dlg_name"] = existing["name"] if is_edit else ""
        st.session_state["_dlg_display"] = existing.get("display", "") if is_edit else ""
        st.session_state["_dlg_folder"] = existing["folder"] if is_edit else ""
        st.session_state["_dlg_url_pattern"] = existing["url_pattern"] if is_edit else ""
        st.session_state["_dlg_dedup_pattern"] = existing.get("dedup_pattern", "") if is_edit else ""
        st.session_state["_dlg_scraper"] = existing.get("scraper", "auto") if is_edit else "auto"

    st.subheader("Edit source" if is_edit else "Add source")

    # --- Preset picker (add mode only) ---
    if not is_edit:
        preset_options = ["Custom"] + list(_PRESETS)
        selected_preset = st.selectbox(
            "Start from a known job board",
            options=preset_options,
            key="_dlg_preset",
            help="Fills in the URL pattern and other settings automatically. You only need to add your IMAP folder.",
        )
        # When the user picks a preset, populate all other fields from it.
        if selected_preset != "Custom":
            data = _PRESETS[selected_preset]
            st.session_state["_dlg_name"] = data.get("name", "")
            st.session_state["_dlg_display"] = data.get("display", "")
            st.session_state["_dlg_url_pattern"] = data.get("url_pattern", "")
            st.session_state["_dlg_dedup_pattern"] = data.get("dedup_pattern", "")
            st.session_state["_dlg_scraper"] = data.get("scraper", "auto")

    name = st.text_input(
        "Name *",
        key="_dlg_name",
        help="Internal identifier used in logs and the database, e.g. `linkedin`",
    )
    display = st.text_input(
        "Display name",
        key="_dlg_display",
        help="Human-readable label shown in the dashboard. Defaults to title-cased name.",
    )
    folder = st.text_input(
        "IMAP folder *",
        key="_dlg_folder",
        help="Full path in your mailbox, e.g. `Job Search/LinkedIn Job Alerts`",
    )

    st.divider()

    # --- URL pattern with live tester ---
    test_url = st.text_input(
        "Paste a raw link from your email to test",
        placeholder="https://click.example.com/track?id=...",
        help=(
            "Right-click a job link in your email client → Copy Link Address. "
            "This is the tracking URL, not the final job page URL."
        ),
    )

    if test_url:
        suggested = _suggest_pattern(test_url)
        if suggested:
            c_sug, c_use = st.columns([5, 1])
            with c_sug:
                st.caption(f"💡 Suggested pattern: `{suggested}`")
            with c_use:
                if st.button("Use", key="_dlg_use_suggestion"):
                    st.session_state["_dlg_url_pattern"] = suggested

    url_pattern = st.text_input(
        "URL pattern *",
        key="_dlg_url_pattern",
        help=(
            "Regex matched against every link in the email. "
            "Only links that match are scraped as job listings."
        ),
    )

    if test_url and url_pattern:
        try:
            if re.search(url_pattern, test_url):
                st.success("✅ Pattern matches")
            else:
                st.warning("❌ No match — try adjusting the pattern or use the suggestion above")
        except re.error as exc:
            st.error(f"Invalid regex: {exc}")

    # --- Advanced ---
    with st.expander("Advanced"):
        dedup_pattern = st.text_input(
            "Dedup pattern",
            key="_dlg_dedup_pattern",
            help=(
                r"Only needed when the same job appears in multiple emails with different "
                r"tracking tokens. Provide a regex with one capture group that extracts a stable "
                r"job ID — e.g. `/jobs/view/(\d+)` for LinkedIn. Jobs with the same captured ID "
                r"are only processed once."
            ),
        )
        scraper = st.selectbox(
            "Scraper",
            options=["auto", "browser"],
            key="_dlg_scraper",
            help=(
                "`auto` tries a fast HTTP request first and falls back to a headless browser "
                "if needed. Use `browser` to always use Playwright — required for sites that "
                "need you to be logged in (e.g. LinkedIn)."
            ),
        )

    st.divider()

    if st.button("Save", type="primary", use_container_width=True):
        errors = []
        if not name.strip():
            errors.append("Name is required.")
        if not folder.strip():
            errors.append("IMAP folder is required.")
        if not url_pattern.strip():
            errors.append("URL pattern is required.")
        if errors:
            for msg in errors:
                st.error(msg)
            return

        new_source: dict = {"folder": folder.strip(), "name": name.strip()}
        if display.strip():
            new_source["display"] = display.strip()
        new_source["url_pattern"] = url_pattern.strip()
        if dedup_pattern.strip():
            new_source["dedup_pattern"] = dedup_pattern.strip()
        if scraper != "auto":
            new_source["scraper"] = scraper

        sources = _load_sources()
        if is_edit:
            sources = [new_source if s["name"] == existing["name"] else s for s in sources]
        else:
            sources.append(new_source)
        _save_sources(sources)
        st.rerun()


def _render_sources_tab() -> None:
    sources = _load_sources()

    if not sources:
        st.info("No sources configured yet. Add one below to get started.")
    else:
        for source in sources:
            with st.container(border=True):
                c_info, c_edit, c_del = st.columns([5, 1, 1])
                with c_info:
                    label = source.get("display") or source["name"].title()
                    st.markdown(f"**{label}** &nbsp; `{source['name']}`")
                    st.caption(f"📁 {source['folder']}")
                    st.caption(f"🔗 `{source['url_pattern']}`")
                    extras = []
                    if source.get("dedup_pattern"):
                        extras.append(f"dedup: `{source['dedup_pattern']}`")
                    if source.get("scraper") == "browser":
                        extras.append("browser scraper")
                    if extras:
                        st.caption("  ·  ".join(extras))
                with c_edit:
                    if st.button(
                        ":material/edit:",
                        key=f"edit_{source['name']}",
                        use_container_width=True,
                        help="Edit",
                    ):
                        _source_dialog(existing=dict(source))
                with c_del:
                    confirm_key = f"_confirm_del_{source['name']}"
                    if st.session_state.get(confirm_key):
                        if st.button(
                            ":material/check:",
                            key=f"confirm_{source['name']}",
                            use_container_width=True,
                            help="Confirm delete",
                            type="primary",
                        ):
                            _save_sources([s for s in sources if s["name"] != source["name"]])
                            st.session_state.pop(confirm_key, None)
                            st.rerun()
                    else:
                        if st.button(
                            ":material/delete:",
                            key=f"del_{source['name']}",
                            use_container_width=True,
                            help="Delete",
                        ):
                            st.session_state[confirm_key] = True
                            st.rerun()

    st.divider()
    if st.button("+ Add source", type="primary"):
        _source_dialog()


def render() -> None:
    c_head, c_back = st.columns([6, 1])
    with c_head:
        st.header("⚙️ Settings")
    with c_back:
        st.write("")  # nudge button down to align with header
        if st.button("← Back", use_container_width=True):
            st.session_state["show_settings"] = False
            st.rerun()

    tab_profile, tab_criteria, tab_sources = st.tabs(
        ["👤 Profile", "🔍 Search Criteria", "📧 Sources"]
    )

    with tab_profile:
        st.caption(
            "Describes your background, skills, and experience. "
            "Used by the LLM to assess role and domain fit."
        )
        profile_text = _load_text(_PROFILE_PATH, _PROFILE_EXAMPLE)
        new_profile = st.text_area(
            "profile.md",
            value=profile_text,
            height=500,
            label_visibility="collapsed",
        )
        if st.button("Save", type="primary", key="save_profile"):
            _PROFILE_PATH.write_text(new_profile)
            st.success("Saved.")

    with tab_criteria:
        st.caption(
            "Defines the roles, domains, and conditions you're targeting. "
            "Used for spam filtering and fit assessment."
        )
        criteria_text = _load_text(_CRITERIA_PATH, _CRITERIA_EXAMPLE)
        new_criteria = st.text_area(
            "search-criteria.md",
            value=criteria_text,
            height=500,
            label_visibility="collapsed",
        )
        if st.button("Save", type="primary", key="save_criteria"):
            _CRITERIA_PATH.write_text(new_criteria)
            st.success("Saved.")

    with tab_sources:
        st.caption(
            "Email folders to scan for job listings and the URL patterns used to extract job links."
        )
        _render_sources_tab()
