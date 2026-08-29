"""
dashboard.py

Full multi-page job platform dashboard: login/signup, personalized
dashboard, resume upload + AI recommendations, job search, applications
tracking, and analytics.
"""

import streamlit as st
from auth.auth_utils import signup_user, login_user
from embedding.embedding_utils import embed_text
from resume.resume_agent import process_resume

st.set_page_config(page_title="JobConnect", layout="wide", page_icon="💼")

st.markdown("""
<style>
    [data-testid="stMetric"] {
        background-color: rgba(28, 131, 225, 0.1);
        border: 1px solid rgba(28, 131, 225, 0.2);
        padding: 15px;
        border-radius: 10px;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px;
    }
    .stButton button {
        border-radius: 8px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_postgres():
    from database.postgres_client import PostgresClient
    return PostgresClient()


@st.cache_resource
def get_qdrant():
    from database.qdrant_client import QdrantClient
    return QdrantClient()


if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None


def show_login_signup():
    st.title("👋 Welcome to JobConnect")
    tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log In")
            if submitted:
                result = login_user(username, password)
                if result["success"]:
                    st.session_state.logged_in = True
                    st.session_state.user = result["user"]
                    st.rerun()
                else:
                    st.error(result["error"])

    with tab_signup:
        with st.form("signup_form"):
            new_username = st.text_input("Choose a username")
            new_email = st.text_input("Email")
            new_password = st.text_input("Choose a password", type="password")
            full_name = st.text_input("Full name")
            location = st.text_input("Location (city, country)")
            submitted = st.form_submit_button("Sign Up")
            if submitted:
                if not new_username or not new_password or not new_email:
                    st.error("Username, email, and password are required.")
                else:
                    result = signup_user(new_username, new_email, new_password, full_name, location)
                    if result["success"]:
                        st.success("Account created! Please log in.")
                    else:
                        st.error(result["error"])


def page_dashboard(user):
    p = get_postgres()
    applications = p.get_applications(user["id"])
    resume = p.get_resume(user["id"])

    st.title(f"Welcome back, {user['full_name'] or user['username']}! 👋")
    st.caption("Ready for your next career move?")

    col1, col2, col3 = st.columns(3)
    col1.metric("Applied Jobs", len(applications))
    col2.metric("Resume Status", "✅ Uploaded" if resume else "❌ Not uploaded")
    col3.metric("Location", user["location"] or "Not set")

    st.divider()

    if applications:
        st.subheader("Recent Applications")
        for job_url, status, applied_at, title, company in applications[:5]:
            st.write(f"**{title}** @ {company} — *{status}* ({applied_at.strftime('%b %d, %Y')})")
    else:
        st.info("You haven't applied to any jobs yet. Head to Job Search to get started!")


def page_upload_resume(user):
    st.title("📄 Upload Your Resume")
    st.caption("Upload your resume to get personalized job recommendations")

    p = get_postgres()
    existing = p.get_resume(user["id"])

    if existing:
        st.success(f"Current resume on file: **{existing[1]}** (uploaded {existing[2].strftime('%b %d, %Y')})")

    uploaded_file = st.file_uploader("Choose a PDF or DOCX file", type=["pdf", "docx"])

    if uploaded_file and st.button("Upload & Process"):
        with st.spinner("Extracting and analyzing your resume..."):
            result = process_resume(uploaded_file, user["id"])
        if result["success"]:
            st.success(f"Resume processed! Extracted {result['text_length']} characters.")
            st.balloons()
        else:
            st.error(result["error"])

    st.divider()
    st.subheader("🎯 Recommended Jobs For You")

    resume_row = p.get_resume(user["id"])
    if not resume_row:
        st.info("Upload a resume above to see personalized recommendations.")
        return

    resume_text = resume_row[0]
    qdrant = get_qdrant()
    vector = embed_text(resume_text[:2000])
    results = qdrant.recommend_jobs(vector, limit=10)

    for r in results:
        title = r.payload.get("title")
        company = r.payload.get("company")
        url = r.payload.get("url")
        if not title:
            continue
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**{title}**")
                st.caption(company or "N/A")
                st.markdown(f"[View posting]({url})")
            with col2:
                if st.button("Apply", key=f"rec_apply_{url}"):
                    p.add_application(user["id"], url)
                    st.success("Applied!")
                    st.rerun()


def page_job_search(user):
    p = get_postgres()
    qdrant = get_qdrant()

    st.title("🔍 Job Search")
    st.caption("Search across live job postings, matched by role similarity")

    query = st.text_input("Search for a job (e.g. 'Data Analyst', 'Senior Software Engineer')", "")
    num_results = st.slider("Number of results", 5, 50, 15)

    if query:
        with st.spinner("Searching..."):
            vector = embed_text(query)
            results = qdrant.search(vector, limit=num_results)

            for r in results:
                title = r.payload.get("title")
                company = r.payload.get("company")
                url = r.payload.get("url")
                if not title:
                    continue
                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.markdown(f"**{title}**")
                        st.caption(company or "N/A")
                        st.markdown(f"[View posting]({url})")
                    with col2:
                        st.metric("Match", f"{r.score:.0%}")
                    with col3:
                        if st.button("Apply", key=f"search_apply_{url}"):
                            p.add_application(user["id"], url)
                            st.success("Applied!")
                            st.rerun()
    else:
        st.info("Enter a search term above to find matching jobs.")


def page_my_applications(user):
    p = get_postgres()

    st.title("📋 My Applications")

    applications = p.get_applications(user["id"])

    if not applications:
        st.info("You haven't applied to any jobs yet.")
        return

    for job_url, status, applied_at, title, company in applications:
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**{title or 'Unknown'}** @ {company or 'N/A'}")
                st.caption(f"Applied on {applied_at.strftime('%b %d, %Y')}")
                st.markdown(f"[View posting]({job_url})")
            with col2:
                st.success(status.title())


def page_analytics(user):
    import pandas as pd
    import plotly.express as px

    st.title("📊 Analytics")
    p = get_postgres()

    tab1, tab2 = st.tabs(["👤 Your Activity", "🌐 Job Market Insights"])

    with tab1:
        applications = p.get_applications(user["id"])
        resume = p.get_resume(user["id"])

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Applications", len(applications))
        col2.metric("Resume Status", "Uploaded ✅" if resume else "Not uploaded ❌")

        if applications:
            df = pd.DataFrame(applications, columns=["job_url", "status", "applied_at", "title", "company"])
            df["applied_at"] = pd.to_datetime(df["applied_at"])

            col3.metric("Most Recent", df["applied_at"].max().strftime("%b %d, %Y"))

            st.subheader("Applications Over Time")
            timeline = df.groupby(df["applied_at"].dt.date).size().reset_index(name="count")
            fig = px.line(timeline, x="applied_at", y="count", markers=True)
            fig.update_layout(height=300, xaxis_title="Date", yaxis_title="Applications")
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("Status Breakdown")
            status_counts = df["status"].value_counts().reset_index()
            status_counts.columns = ["status", "count"]
            fig2 = px.pie(status_counts, names="status", values="count", hole=0.4)
            fig2.update_layout(height=300)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Apply to jobs to see your activity here.")

    with tab2:
        with p.conn.cursor() as cur:
            cur.execute("""
                SELECT job_url, title, company, source, segment_id, segment_label, is_validated
                FROM job_segments
            """)
            rows = cur.fetchall()
        df = pd.DataFrame(rows, columns=["job_url", "title", "company", "source", "segment_id", "segment_label", "is_validated"])

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Jobs", len(df))
        col2.metric("Categories", df[df["segment_id"] != -1]["segment_label"].nunique())
        col3.metric("Validated", f"{df['is_validated'].mean():.0%}")
        col4.metric("Sources", df["source"].nunique())

        st.subheader("Top Job Categories")
        cluster_sizes = (
            df[df["segment_id"] != -1]
            .groupby("segment_label")
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
            .head(15)
        )
        fig3 = px.bar(cluster_sizes, x="count", y="segment_label", orientation="h",
                       color="count", color_continuous_scale="Blues")
        fig3.update_layout(height=500, yaxis_title="", xaxis_title="Number of Jobs",
                            yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig3, use_container_width=True)

        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Jobs by Source")
            source_counts = df["source"].value_counts().reset_index()
            source_counts.columns = ["source", "count"]
            fig4 = px.pie(source_counts, names="source", values="count", hole=0.4)
            st.plotly_chart(fig4, use_container_width=True)
        with col_b:
            st.subheader("Data Quality")
            validity_counts = df["is_validated"].value_counts().reset_index()
            validity_counts.columns = ["valid", "count"]
            validity_counts["valid"] = validity_counts["valid"].map({True: "Validated", False: "Flagged"})
            fig5 = px.pie(validity_counts, names="valid", values="count", hole=0.4,
                          color="valid", color_discrete_map={"Validated": "#2ecc71", "Flagged": "#e74c3c"})
            st.plotly_chart(fig5, use_container_width=True)


def show_main_app():
    user = st.session_state.user

    st.sidebar.title(f"👤 {user['full_name'] or user['username']}")
    st.sidebar.caption(user['email'])
    page = st.sidebar.radio(
        "Navigate",
        ["Dashboard", "Upload Resume", "Job Search", "My Applications", "Analytics"],
    )

    if st.sidebar.button("Log Out"):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.rerun()

    if page == "Dashboard":
        page_dashboard(user)
    elif page == "Upload Resume":
        page_upload_resume(user)
    elif page == "Job Search":
        page_job_search(user)
    elif page == "My Applications":
        page_my_applications(user)
    elif page == "Analytics":
        page_analytics(user)


if st.session_state.logged_in:
    show_main_app()
else:
    show_login_signup()