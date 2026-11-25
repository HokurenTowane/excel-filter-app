"""
Secure Excel Filter
===================
A Streamlit app that puts a login wall in front of an Excel filter/search/sort tool.

Tested with streamlit 1.67.0 and streamlit-authenticator 0.4.2.

The script is re-executed top-to-bottom on every interaction (that is how Streamlit
works), so everything below is written to be safe to run a thousand times:
no global side effects, no unconditional reruns, and config.yaml is re-read each run.
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

# --------------------------------------------------------------------------- #
# 1. CONSTANTS
# --------------------------------------------------------------------------- #
APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.yaml"
UPLOADER_KEY = "excel_uploader"          # session-state key used to reset the uploader
SUPPORTED_TYPES = ["xlsx", "xlsm", "xls"]  # .xls legacy needs the xlrd package

# streamlit-authenticator enforces this on register_user(); show it up front so a
# rejected password is never a surprise. (8-20 chars: upper, lower, digit, special.)
PASSWORD_RULES = (
    "**Password rules** — 8 to 20 characters, with at least one uppercase letter, "
    "one lowercase letter, one digit and one special character "
    "(for example `@ $ ! % * ? &`)."
)

# Custom labels for the sign-up form (all keys are optional; these are just nicer).
REGISTER_LABELS = {
    "Form name": "Create an account",
    "First name": "First name",
    "Last name": "Last name",
    "Email": "Email",
    "Username": "Username",
    "Password": "Password",
    "Repeat password": "Repeat password",
    "Password hint": "Password hint (optional)",
    "Register": "Register",
}


# --------------------------------------------------------------------------- #
# 2. CONFIG HELPERS
# --------------------------------------------------------------------------- #
def load_config() -> dict:
    """Read config.yaml from disk. Called on every run, so edits show up immediately."""
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return yaml.load(handle, Loader=SafeLoader)


def save_config(config: dict) -> None:
    """Write config.yaml atomically: a crash mid-write can never truncate the file."""
    temp_path = CONFIG_PATH.with_name(CONFIG_PATH.name + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        yaml.dump(
            config,
            handle,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
    temp_path.replace(CONFIG_PATH)  # atomic replace (works on Windows and Linux)


# --------------------------------------------------------------------------- #
# 3. EXCEL HELPERS
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner="Reading the workbook…")
def load_excel(payload: bytes) -> pd.DataFrame:
    """Parse an uploaded workbook. Cached on the file's bytes, not on the widget."""
    return pd.read_excel(io.BytesIO(payload))


def clear_upload() -> None:
    """Button callback: runs BEFORE the next render, so the uploader is really reset."""
    st.session_state.pop(UPLOADER_KEY, None)
    load_excel.clear()


# --------------------------------------------------------------------------- #
# 4. AUTHENTICATION
# --------------------------------------------------------------------------- #
def render_registration(config: dict, authenticator) -> None:
    """The sign-up form, shown to anyone who is not logged in."""
    with st.expander("Don't have an account? Register here"):
        st.markdown(PASSWORD_RULES)
        try:
            # 0.4.x returns a 3-tuple (email, username, name) on success and
            # (None, None, None) when the form was only displayed. Test the EMAIL:
            # testing the tuple itself would always be truthy and re-render forever.
            email, username, _name = authenticator.register_user(
                location="main",
                captcha=False,  # 0.4.x defaults to True and demands an unreadable captcha
                fields=REGISTER_LABELS,
            )
        except Exception as exc:  # bad/duplicate username, weak password, ...
            st.error(exc)
            return

        if not email:  # form shown but not submitted -> nothing to do
            return

        try:
            save_config(config)
        except OSError as exc:
            st.warning(
                f"Account **{username}** works for now, but config.yaml could not be "
                f"saved ({exc}), so it may disappear when the app restarts."
            )
        else:
            st.success(f"Account **{username}** created — log in above.")


st.set_page_config(page_title="Secure Excel Filter", page_icon="🧬", layout="wide")

# --- load config + build the authenticator ---------------------------------- #
try:
    config = load_config()
    authenticator = stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
    )
except Exception as exc:  # missing / truncated / malformed config.yaml
    st.error(f"config.yaml could not be loaded: {exc}")
    st.stop()

# --- login form ------------------------------------------------------------- #
try:
    authenticator.login(location="main")
except Exception as exc:  # e.g. a stale cookie for a user that no longer exists
    st.error(exc)

name = st.session_state.get("name")
username = st.session_state.get("username")
authentication_status = st.session_state.get("authentication_status")

# --- gate: logged out users see the form and stop here ---------------------- #
if not authentication_status:
    if authentication_status is False:
        st.error("Username/password is incorrect.")
    else:
        st.info("Please log in, or create an account below.")
    render_registration(config, authenticator)
    st.stop()  # keeps the app body below flat (no giant if/else nest)

# --------------------------------------------------------------------------- #
# 5. THE APP (only reached while logged in)
# --------------------------------------------------------------------------- #
st.sidebar.write(f"Welcome *{name or username}*")
authenticator.logout("Logout", "sidebar")

st.title("🧬 Advanced Excel Data Filter Tool")
st.write("Upload an Excel file to search, filter and sort it, then download the result.")

uploaded_file = st.file_uploader(
    "Choose an Excel file", type=SUPPORTED_TYPES, key=UPLOADER_KEY
)

if uploaded_file is None:
    st.stop()

try:
    df = load_excel(uploaded_file.getvalue())
except Exception as exc:
    st.error(f"Could not read **{uploaded_file.name}**: {exc}")
    st.stop()

if df.empty:
    st.warning("That workbook has no rows.")
    st.stop()

st.success(f"Loaded **{uploaded_file.name}** — {len(df):,} rows × {len(df.columns)} columns.")

filtered_df = df.copy()

# --------------------------------------------------------------------------- #
# 6. SIDEBAR: SEARCH, FILTER, SORT
# --------------------------------------------------------------------------- #
st.sidebar.header("Search & Filter")

search_query = st.sidebar.text_input("🔍 Search all columns")
if search_query:
    # regex=False so a search such as "A[1]" is treated as text, not a regex
    hit_rows = (
        filtered_df.astype(str)
        .apply(lambda column: column.str.contains(search_query, case=False, regex=False))
        .any(axis=1)
    )
    filtered_df = filtered_df[hit_rows]

filtered_columns = st.sidebar.multiselect("Narrow down by column", list(df.columns))

for column in filtered_columns:
    series = df[column]
    label = str(column)

    if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
        low, high = series.min(), series.max()
        if pd.isna(low) or pd.isna(high):
            st.sidebar.caption(f"**{label}**: nothing numeric to filter on")
            continue
        low, high = float(low), float(high)
        if low == high:  # a 0-width slider is invalid in Streamlit
            st.sidebar.caption(f"**{label}**: only one value ({low:g})")
            continue

        selected_range = st.sidebar.slider(
            f"Range for {label}",
            min_value=low,
            max_value=high,
            value=(low, high),
        )
        filtered_df = filtered_df[
            filtered_df[column].between(selected_range[0], selected_range[1])
        ]
    else:
        options = sorted(series.dropna().unique(), key=str)
        selected_values = st.sidebar.multiselect(f"Values for {label}", options)
        if selected_values:
            filtered_df = filtered_df[filtered_df[column].isin(selected_values)]

st.sidebar.markdown("---")
st.sidebar.subheader("Sort")

sort_column = st.sidebar.selectbox(
    "Sort by", list(df.columns), index=None, placeholder="— no sorting —"
)
if sort_column is not None:
    descending = (
        st.sidebar.radio("Direction", ["Ascending", "Descending"], horizontal=True)
        == "Descending"
    )
    try:
        filtered_df = filtered_df.sort_values(
            by=sort_column, ascending=not descending, kind="stable", na_position="last"
        )
    except TypeError:
        st.sidebar.warning(f"**{sort_column}** mixes text and numbers, so it can't be sorted.")


# --------------------------------------------------------------------------- #
# 7. RESULTS + DOWNLOADS
# --------------------------------------------------------------------------- #
st.subheader("Results")

st.button(
    "🔄 Clear data & upload a new file",
    on_click=clear_upload,
    help="Forget the current file (and its cached copy) so you can pick another one.",
)

st.write(f"Showing **{len(filtered_df):,}** of **{len(df):,}** rows.")

if filtered_df.empty:
    st.warning("No rows match your search and filters.")
else:
    st.dataframe(filtered_df, use_container_width=True)

st.write("### Download")

download_format = st.radio(
    "Choose format", ["CSV", "Excel (.xlsx)"], horizontal=True, label_visibility="collapsed"
)

if download_format == "CSV":
    # utf-8-sig adds a BOM so Excel shows accented/Chinese text correctly
    csv_bytes = filtered_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "📥 Download as CSV",
        data=csv_bytes,
        file_name="filtered_data.csv",
        mime="text/csv",
    )
else:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        filtered_df.to_excel(writer, index=False, sheet_name="Filtered_Data")
    st.download_button(
        "📥 Download as Excel",
        data=buffer.getvalue(),
        file_name="filtered_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
