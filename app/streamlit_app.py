"""The app's entry point: `streamlit run app/streamlit_app.py`.

Hosted mode (the default): the public pages only, read as public_app. The
local pages, the role switcher and the timeline are not even imported.
Local mode (APP_MODE=local): a role switcher, and the local pages too.
"""

import sys
from pathlib import Path

# Streamlit puts this file's folder on the path; the project root is one up.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from app.db import HOSTED, LOCAL_ROLES, PUBLIC_ROLE, mode
from app.public_views import PAGES as PUBLIC_PAGES

st.set_page_config(page_title="Synthetic EHR", layout="wide")
st.title("Synthetic EHR + Privacy-by-Design")

if mode() == HOSTED:
    st.sidebar.caption("Public view: suppressed aggregates only.")
    page = st.sidebar.radio("Page", list(PUBLIC_PAGES))
    PUBLIC_PAGES[page](PUBLIC_ROLE)
else:
    from app.local_views import PAGES as LOCAL_PAGES

    role = st.sidebar.selectbox("Role", LOCAL_ROLES)
    st.sidebar.caption(
        "Every page asks the database as this role; it decides what you see."
    )
    pages = {**LOCAL_PAGES, **PUBLIC_PAGES}
    page = st.sidebar.radio("Page", list(pages))
    pages[page](role)
