"""Local mode only: pages that show per-patient data, for the role chosen in
the role switcher. Never imported in hosted mode (app/streamlit_app.py).

Every page asks the database as the chosen role, so what appears is what
that role may read: a clinician sees only its own patients (row-level
security), a researcher only pseudonyms, the public role nothing here.
"""

import streamlit as st

from app.db import Refused, query
from app.public_views import show_refused

CONDITIONS = [
    "hypertension",
    "hyperlipidaemia",
    "type2_diabetes",
    "ckd",
    "atrial_fibrillation",
    "heart_failure",
]


def cohort_builder_page(role: str) -> None:
    st.header("Cohort builder")
    st.caption("From the pseudonymized marts: no names or record numbers.")
    chosen = st.multiselect("Patients who have (by the end of the history)", CONDITIONS)
    sex = st.radio("Sex", ["both", "F", "M"], horizontal=True)
    where = [
        f"has_{c}" for c in chosen
    ]  # names from the fixed list above, never typed in
    params: tuple = ()
    if sex != "both":
        where.append("sex = %s")
        params = (sex,)
    clause = ("where " + " and ".join(where)) if where else ""
    try:
        data = query(
            role,
            f"select age_band_at_start as age_band, count(*) as patients "
            f"from marts.dim_patient {clause} group by 1 order by 1",
            params,
        )
    except Refused as error:
        return show_refused(error, role)
    st.metric("Patients in the cohort", int(data["patients"].sum()) if len(data) else 0)
    st.bar_chart(data, x="age_band", y="patients")


def timeline_page(role: str) -> None:
    st.header("Patient timeline")
    st.caption(
        "Identifiable: only clinicians (for the patients they treat) and the data steward."
    )
    try:
        patients = query(
            role,
            "select mrn, given_name || ' ' || family_name as name, patient_id "
            "from ehr_identity.patient_identity order by mrn limit 500",
        )
    except Refused as error:
        return show_refused(error, role)
    if patients.empty:
        st.info("No patients visible to this role.")
        return
    label = st.selectbox("Patient", patients["mrn"] + "  " + patients["name"])
    patient_id = int(
        patients.loc[
            (patients["mrn"] + "  " + patients["name"]) == label, "patient_id"
        ].iloc[0]
    )
    events = query(
        role,
        """
        select onset_date::timestamp as at, 'diagnosis' as kind, icd10_code as what
        from ehr.condition where patient_id = %s
        union all
        select e.start_time, e.encounter_type || ' visit', d.name
        from ehr.encounter as e inner join ehr.department as d using (department_id)
        where e.patient_id = %s
        union all
        select start_date::timestamp, 'medicine order', atc_code
        from ehr.medication_order where patient_id = %s
        order by 1
        """,
        (patient_id, patient_id, patient_id),
    )
    st.dataframe(events, width="stretch", hide_index=True)
    potassium = query(
        role,
        """
        select o.ordered_at as at, r.value as potassium
        from ehr.lab_order as o inner join ehr.lab_result as r using (lab_order_id)
        where o.patient_id = %s and o.loinc_code = '2823-3'
        order by 1
        """,
        (patient_id,),
    )
    if not potassium.empty:
        st.subheader("Potassium (mmol/L)")
        st.line_chart(potassium, x="at", y="potassium")


def drug_lab_events_page(role: str) -> None:
    st.header("Drug–lab events")
    st.caption(
        "From the pseudonymized marts: each result taken while on a linked medicine."
    )
    try:
        data = query(
            role,
            "select rule, count(*) as results, count(*) filter (where rule_triggered) as events "
            "from marts.fact_drug_lab_event group by rule order by rule",
        )
    except Refused as error:
        return show_refused(error, role)
    st.dataframe(data, width="stretch", hide_index=True)


PAGES = {
    "Cohort builder": cohort_builder_page,
    "Patient timeline": timeline_page,
    "Drug–lab events": drug_lab_events_page,
}
