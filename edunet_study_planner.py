import streamlit as st
import pandas as pd
import numpy as np
import os
import re
from datetime import datetime, date
import altair as alt


from edunet_auth import register_user, login_user
from email_utils import send_task_email


# --- Hide the deploy button and toolbar ---
st.markdown(
    """
    <style>
    [data-testid="stToolbar"] {
        visibility: hidden !important;
    }
    footer {
        visibility: hidden !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# --- Page config & branding ---
st.set_page_config(page_title="EDUNET Smart Study Planner", layout="wide", initial_sidebar_state="expanded")
st.title("🎓 EDUNET Smart Study Planner & Procrastination Nudge")
st.caption("AI-powered academic planner — EDUNET")


# --- Constants ---
STOPWORDS = set(["the","is","in","at","to","and","a","of","on","for","with","that","this","as","it","by","from","an","be","are","or","was"])
PROCRASTINATION_KEYWORDS = ["start","research","plan","think about","figure out","conceptualize"]
ALL_EFFORTS = ['Low','Medium','High']
ALL_TYPES = ['Reading','Assignment','Revision','Project','Other']
ALL_USER_PRIORITIES = ['Low','Medium','High']
ALL_AI_PRIORITIES = ['Low','Medium','High']


# --- Session user management ---
if "user_email" not in st.session_state:
    st.session_state.user_email = None


def sanitize_email_for_filename(email: str) -> str:
    """Make a safe filename from an email address."""
    return re.sub(r"[^0-9A-Za-z\-_.]", "_", email.lower())


def get_tasks_filename_for_user(email: str) -> str:
    san = sanitize_email_for_filename(email)
    return f"tasks_{san}.csv"


def load_tasks_for_user(email: str) -> pd.DataFrame:
    filename = get_tasks_filename_for_user(email)
    cols = ['Task Name','Course','Due Date','Effort','Type','User Priority','AI Priority','Status','Keywords','Days Until Due','Actual_AI_Priority','Actual_Effort_Rating','Completed Date']
    if os.path.exists(filename):
        df = pd.read_csv(filename)
        # Ensure columns exist
        for c in cols:
            if c not in df.columns:
                df[c] = None
        # Normalize date columns
        try:
            if 'Due Date' in df.columns:
                df['Due Date'] = pd.to_datetime(df['Due Date']).dt.date
        except Exception:
            pass
        try:
            if 'Completed Date' in df.columns:
                df['Completed Date'] = pd.to_datetime(df['Completed Date']).dt.date
        except Exception:
            pass
        return df[cols]
    else:
        return pd.DataFrame(columns=cols)


def save_tasks_for_user(email: str, df: pd.DataFrame):
    filename = get_tasks_filename_for_user(email)
    df.to_csv(filename, index=False)


# --- Simple helpers ---
def hashable_lower(s: str):
    return str(s).strip().lower()


def extract_keywords_simple(text: str):
    if not isinstance(text, str):
        return ""
    text = text.lower()
    words = re.findall(r'\b[a-z]{2,}\b', text)
    filtered = [w for w in words if w.isalnum() and w not in STOPWORDS]
    return ", ".join(filtered)


def calculate_days_until_due(due_date):
    if pd.isna(due_date) or due_date is None:
        return None
    if isinstance(due_date, str):
        try:
            due_date = datetime.fromisoformat(due_date)
        except Exception:
            return None
    if isinstance(due_date, pd.Timestamp):
        due_date = due_date.to_pydatetime()
    if isinstance(due_date, date) and not isinstance(due_date, datetime):
        due_date = datetime.combine(due_date, datetime.min.time())
    delta = due_date - datetime.now()
    return max(0, delta.days)


def check_for_procrastination(task_name: str) -> bool:
    if not isinstance(task_name, str):
        return False
    s = task_name.lower()
    for kw in PROCRASTINATION_KEYWORDS:
        if re.search(r'\b' + re.escape(kw) + r'\b', s):
            return True
    return False


# --- Authentication UI ---
if st.session_state.user_email is None:
    st.sidebar.header("🔐 Sign in to EDUNET")
    tab1, tab2 = st.sidebar.tabs(["Login", "Register"])


    with tab1:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login", key="login_btn"):
            if login_user(email, password):
                st.session_state.user_email = email.strip().lower()
                st.success(f"Logged in as {st.session_state.user_email}")
                st.rerun()
            else:
                st.error("Invalid credentials. Try again.")


    with tab2:
        new_email = st.text_input("New Email", key="reg_email")
        new_pass = st.text_input("New Password", type="password", key="reg_pass")
        if st.button("Register", key="reg_btn"):
            ok, msg = register_user(new_email, new_pass)
            if ok:
                st.success(msg + " You may now login.")
            else:
                st.error(msg)


    st.stop()  # stop here until logged in


# --- Main app (user is logged in) ---
user_email = st.session_state.user_email
st.sidebar.success(f"Signed in as {user_email}")
st.sidebar.button("Logout", on_click=lambda: (st.session_state.clear(), st.rerun()))


# Load user tasks
df_tasks = load_tasks_for_user(user_email)


# Ensure days and keywords
if not df_tasks.empty:
    if 'Days Until Due' not in df_tasks.columns or df_tasks['Days Until Due'].isnull().all():
        df_tasks['Days Until Due'] = df_tasks['Due Date'].apply(calculate_days_until_due)
    if 'Keywords' not in df_tasks.columns or df_tasks['Keywords'].isnull().all():
        df_tasks['Keywords'] = df_tasks['Task Name'].apply(extract_keywords_simple)
else:
    # ensure columns exist
    for c in ['Days Until Due', 'Keywords', 'Actual_AI_Priority', 'Actual_Effort_Rating', 'Completed Date']:
        if c not in df_tasks.columns:
            df_tasks[c] = None


# --- Sidebar: Add Task ---
with st.sidebar.expander("✨ Add New Study Task", expanded=False):
    with st.form("task_form"):
        task_name = st.text_input("Task Name", help="e.g., Read Chapter 5")
        course = st.text_input("Course/Subject", help="e.g., Computer Science")
        due_date = st.date_input("Due Date", min_value=datetime.now().date())
        effort = st.selectbox("Estimated Effort", ALL_EFFORTS)
        task_type = st.selectbox("Task Type", ALL_TYPES)
        user_priority = st.selectbox("Your Priority", ALL_USER_PRIORITIES)
        add_submitted = st.form_submit_button("Add Task")
        if add_submitted:
            if task_name and course and due_date:
                days_until = calculate_days_until_due(due_date)
                keywords = extract_keywords_simple(task_name)
                new_task = {
                    'Task Name': task_name,
                    'Course': course,
                    'Due Date': due_date,
                    'Effort': effort,
                    'Type': task_type,
                    'User Priority': user_priority,
                    'AI Priority': user_priority,
                    'Status': 'Pending',
                    'Keywords': keywords,
                    'Days Until Due': days_until,
                    'Actual_AI_Priority': None,
                    'Actual_Effort_Rating': None,
                    'Completed Date': None
                }
                df_tasks = pd.concat([df_tasks, pd.DataFrame([new_task])], ignore_index=True)
                save_tasks_for_user(user_email, df_tasks)
                st.success("Task added successfully!")
                st.rerun()
            else:
                st.error("Please fill in all task details.")


# --- Top: Tasks table & actions ---
st.subheader("📋 My Study Tasks")
if df_tasks.empty:
    st.info("You have no tasks. Add some from the sidebar.")
else:
    # display table
    display_cols = [c for c in ['Task Name','Course','Due Date','Effort','Type','User Priority','AI Priority','Status'] if c in df_tasks.columns]
    st.dataframe(df_tasks[display_cols].sort_values(by=['Status','Due Date']), use_container_width=True, height=300)


# Action center
st.markdown("---")
st.subheader("Action Center")
col1, col2 = st.columns(2)


with col1:
    st.markdown("#### ✅ Mark Task as Complete")
    pending = df_tasks[df_tasks['Status'] == 'Pending'] if not df_tasks.empty else pd.DataFrame()
    if not pending.empty:
        choice = st.selectbox("Which task did you finish?", pending['Task Name'].tolist(), key="complete_select")
        with st.form("complete_form"):
            actual_priority = st.selectbox("Actual importance/priority", ALL_AI_PRIORITIES)
            actual_effort = st.selectbox("Actual effort compared to estimate", ['Shorter','As Estimated','Longer'])
            submitted = st.form_submit_button("Submit Feedback & Complete")
            if submitted:
                idx = df_tasks[df_tasks['Task Name'] == choice].index[0]
                df_tasks.loc[idx, 'Status'] = 'Completed'
                df_tasks.loc[idx, 'Actual_AI_Priority'] = actual_priority
                df_tasks.loc[idx, 'Actual_Effort_Rating'] = actual_effort
                df_tasks.loc[idx, 'Completed Date'] = datetime.now().date()
                save_tasks_for_user(user_email, df_tasks)
                st.success(f"Marked '{choice}' as completed with feedback.")
                st.rerun()
    else:
        st.info("No pending tasks to complete.")


with col2:
    st.markdown("#### 🗑 Delete Task")
    if not df_tasks.empty:
        delete_choice = st.selectbox("Select task to delete", df_tasks['Task Name'].tolist(), key="delete_select")
        if st.button("Delete Selected Task"):
            df_tasks = df_tasks[df_tasks['Task Name'] != delete_choice].reset_index(drop=True)
            save_tasks_for_user(user_email, df_tasks)
            st.success(f"Deleted '{delete_choice}'.")
            st.rerun()
    else:
        st.info("No tasks to delete.")


# --- Email section ---
st.markdown("---")
st.subheader("📧 Email Tasks")
st.markdown("Send your current tasks to your registered email address.")
if st.button("Send my tasks to my email"):
    try:
        # send only relevant columns for neatness
        cols = [c for c in ['Task Name','Course','Due Date','Effort','Type','User Priority','AI Priority','Status'] if c in df_tasks.columns]
        df_for_email = df_tasks[cols] if not df_tasks.empty else pd.DataFrame()
        send_task_email(user_email, df_for_email)
        st.success(f"Tasks emailed to {user_email} ✅ (check spam folder if not visible).")
    except Exception as e:
        st.error(f"Failed to send email: {e}")


# --- Dashboard & Charts ---
st.markdown("---")
st.subheader("📊 EDUNET Dashboard & Insights")


def study_time_suggestions(df):
    if df is None or df.empty:
        return None
    effort_map = {'Low': 1.0, 'Medium': 2.5, 'High': 5.0}
    pending = df[df['Status'] == 'Pending']
    if pending.empty:
        return 0.0
    total_hours = pending['Effort'].map(effort_map).sum()
    try:
        nearest_due = min([d for d in pending['Due Date'] if not pd.isna(d)])
        days_remaining = max(1, (nearest_due - date.today()).days)
    except Exception:
        days_remaining = 7
    return round(total_hours / days_remaining, 1)


# metrics
col_a, col_b, col_c = st.columns(3)
col_a.metric("Total Tasks", len(df_tasks))
col_b.metric("Pending", int((df_tasks['Status'] == 'Pending').sum()) if not df_tasks.empty else 0)
col_c.metric("Completed", int((df_tasks['Status'] == 'Completed').sum()) if not df_tasks.empty else 0)


suggested = study_time_suggestions(df_tasks)
if suggested is None:
    st.info("Add tasks to get study time suggestions.")
else:
    st.success(f"Suggested study time: **{suggested} hours/day** until nearest pending deadline.")


if not df_tasks.empty:
    # Pie: distribution by Type
    type_counts = df_tasks['Type'].fillna('Other').value_counts().reset_index()
    type_counts.columns = ['Type','Count']


    # Bar: tasks per course
    course_counts = df_tasks['Course'].fillna('Unknown').value_counts().reset_index()
    course_counts.columns = ['Course','Count']
    course_counts = course_counts.head(20)


    # Line: completed over time
    comp = df_tasks[df_tasks['Status'] == 'Completed'].copy()
    if not comp.empty and 'Completed Date' in comp.columns:
        comp['Completed Date'] = pd.to_datetime(comp['Completed Date'])
        timeline = comp.groupby(comp['Completed Date'].dt.date).size().reset_index(name='Completed')
        timeline.columns = ['Date','Completed']
    else:
        timeline = pd.DataFrame(columns=['Date','Completed'])


    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 📖 Task Distribution by Type")
        pie = alt.Chart(type_counts).mark_arc().encode(theta='Count', color='Type', tooltip=['Type','Count'])
        st.altair_chart(pie, use_container_width=True)
        st.markdown("### 📈 Completed Tasks Over Time")
        if not timeline.empty:
            line = alt.Chart(timeline).mark_line(point=True).encode(x='Date:T', y='Completed:Q', tooltip=['Date','Completed'])
            st.altair_chart(line, use_container_width=True)
        else:
            st.info("No completed tasks yet to show on timeline.")
    with c2:
        st.markdown("### 📚 Tasks per Course")
        bar = alt.Chart(course_counts).mark_bar().encode(x=alt.X('Course:N', sort='-y'), y='Count:Q', tooltip=['Course','Count'], color='Course')
        st.altair_chart(bar, use_container_width=True)


st.markdown("---")
st.caption("Built with ❤ and AI — EDUNET")
