"""Thin Streamlit demo — all logic lives in fooding.demo_helpers (tested)."""

try:
    import streamlit as st
except ImportError:  # pragma: no cover
    raise SystemExit("pip install streamlit  # demo only") from None

from fooding.demo_helpers import (
    DEFAULT_QUESTIONS,
    answer_question,
    price_showcase,
    substitution_showcase,
    trial_showcase,
)

st.title("Glinthaven Foods — R&D agent (synthetic demo)")
st.caption("All data is fictional and seeded. No real brands.")

q = st.selectbox("Ask a question", DEFAULT_QUESTIONS)
if st.button("Run"):
    out = answer_question(q)
    st.json(out)

st.subheader("Substitution engine")
for opt in substitution_showcase():
    st.write(opt["breakdown"])

st.subheader("Trial tracker")
st.json(trial_showcase())

st.subheader("Price signal")
st.json(price_showcase())
