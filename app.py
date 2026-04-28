import pandas as pd
import streamlit as st
import plotly.express as px
from sqlalchemy import create_engine
engine = create_engine(
    st.secrets["DB_URL"],
    pool_pre_ping=True,   # helps with dropped connections
)
#engine = create_engine("postgresql://postgres:jayanti@localhost:5432/gtu_patents")
uploaded_files = None
try:
    with engine.connect() as conn:
        pass
except Exception as e:
    st.error("❌ Database connection failed")
    st.write(e)
    st.stop()

# -------------------------------
# PROCESS FUNCTION
# -------------------------------
def process_file(file):
    import pandas as pd

    df = pd.read_excel(file)

    # Clean columns
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )

    # -------------------------------
    # HANDLE FILED FILE
    # -------------------------------
    if "year_filed" in df.columns:
        df["year"] = df["year_filed"]

    # -------------------------------
    # HANDLE GRANTED FILE
    # -------------------------------
    elif "ipr_status_year" in df.columns:
        df["year"] = df["ipr_status_year"]

    elif "unnamed:_0" in df.columns:
        df["year"] = df["unnamed:_0"]

    # -------------------------------
    # FALLBACK → extract from date
    # -------------------------------
    else:
        for col in df.columns:
            if "date" in col:
                df["year"] = pd.to_datetime(df[col], errors="coerce").dt.year

    # -------------------------------
    # FORCE NUMERIC
    # -------------------------------
    # df["year"] = pd.to_numeric(df["year"], errors="coerce")
    # -------------------------------
    # SAFE YEAR EXTRACTION
    # -------------------------------
    if "year" in df.columns:
        # Try numeric first
        df["year"] = pd.to_numeric(df["year"], errors="coerce")

    # If still many nulls → extract from date
        if df["year"].isna().sum() > len(df) * 0.5:
            for col in df.columns:
                if "date" in col:
                    df["year"] = pd.to_datetime(df[col], errors="coerce").dt.year
                    break

    # -------------------------------
    # STATUS
    # -------------------------------
    filename = file.name.lower()
    df["status"] = "Granted" if "grant" in filename else "Filed"

    # -------------------------------
    # FINAL CLEAN
    # -------------------------------
    #df = df.dropna(subset=["year"])
    df = df.dropna(how="all")
    return df



# -------------------------------
# USER DATABASE (EDIT THIS)
# -------------------------------
users = {
    "admin": {"password": "admin123", "role": "admin"},
    "gtu_user": {"password": "gtu123", "role": "viewer"}
}

def login():
    st.title("🔐 Login - GTU Patent Dashboard")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username in users and users[username]["password"] == password:
            st.session_state["logged_in"] = True
            st.session_state["user"] = username
            st.session_state["role"] = users[username]["role"]
            st.success("Login successful")
            st.rerun()
        else:
            st.error("Invalid username or password")

# Initialize session
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

# If not logged in → show login page
if not st.session_state["logged_in"]:
    login()
    st.stop()

col1, col2 = st.columns([6,1])

with col2:
    if st.button("Logout"):
        st.session_state["logged_in"] = False
        st.rerun()
       
col1, col2, col3 = st.columns([1, 6, 1])

with col1:
    st.image("gtu-logo.png", width=80)

with col2:
    st.markdown("""
        <h1 style='text-align: center; color: #1f4e79;'>
            📊 GTU Patent Analytics Dashboard
        </h1>
        <p style='text-align: center; font-size:18px;'>
            Gujarat Technological University
        </p>
    """, unsafe_allow_html=True)

with col3:
    st.image("IPFC.png", width=80)
# -------------------------------
# PAGE CONFIG
# -------------------------------
st.set_page_config(
    page_title="GTU Patent Dashboard",
    layout="wide"
)

# -------------------------------
# HEADER
# -------------------------------
#st.title("📊 GTU Patent Analytics Dashboard")
#st.caption("Gujarat Technological University")

# -------------------------------
# FILE UPLOAD
# -------------------------------
#import streamlit as st

#uploaded_files = st.file_uploader("Granted_Patent",type=["xlsx"],accept_multiple_files=True)

if st.session_state["role"] == "admin":
    uploaded_files = st.file_uploader(
        "Granted_Patent",
        type=["xlsx"],
        accept_multiple_files=True
    )

else:
    st.info("Viewer mode: Upload disabled")
# -------------------------------
# LOAD FROM DATABASE
# -------------------------------
df = pd.DataFrame()

try:
    df = pd.read_sql("SELECT * FROM gtu_patents", engine)
except:
    pass

# -------------------------------
# PROCESS UPLOAD
# -------------------------------
dataframes = []

if uploaded_files:
    for file in uploaded_files:
        try:
            df_temp = process_file(file)

            if df_temp is not None and not df_temp.empty:
                dataframes.append(df_temp)
                st.success(f"✅ Processed: {file.name}")
            else:
                st.warning(f"⚠️ No usable data in: {file.name}")

        except Exception as e:
            st.error(f"❌ Failed: {file.name}")
            st.write(e)

# -------------------------------
# UPDATE DB IF NEW DATA
# -------------------------------
if dataframes:
    df = pd.concat(dataframes, ignore_index=True)
    df = df.drop_duplicates()

    try:
        df.to_sql("gtu_patents", engine, if_exists="replace", index=False)
        st.success("✅ Database updated successfully")
    except Exception as e:
        st.warning("⚠️ Could not write to database")
        st.write(e)

# -------------------------------
# FALLBACK (VIEWER MODE)
# -------------------------------
elif df.empty:
    st.warning("⚠️ No data available")
    st.stop()

# -------------------------------
# FINAL CLEANING (IMPORTANT)
# -------------------------------
df = df.rename(columns={
    "type_of_ipr_(design/patent/trademark/_gi/_copyright)": "ipr_type"
})

if "ipr_type" not in df.columns:
    for col in df.columns:
        if "type" in col:
            df["ipr_type"] = df[col]
            break

if "ipr_type" not in df.columns:
    df["ipr_type"] = "Unknown"

df["ipr_type"] = df["ipr_type"].astype(str).str.strip().str.title()
df["status"] = df["status"].astype(str).str.title()


# SIDEBAR FILTERS
# -------------------------------
st.sidebar.header("Filters")

if "year" in df.columns:
    df["year"] = pd.to_numeric(df["year"], errors="coerce")

    # Drop missing years (recommended)
    df = df.dropna(subset=["year"])

# Convert safely
    df["year"] = df["year"].astype(int)

    years = sorted(df["year"].dropna().unique())

    selected_years = st.sidebar.multiselect(
    "Select Year",
    years,
    default=years
    )
    

    df = df[df["year"].isin(selected_years)]
# -------------------------------
# CLEAN DATA (IMPORTANT)
# -------------------------------
df["status"] = df["status"].astype(str).str.strip().str.title()
df["ipr_type"] = df["ipr_type"].astype(str).str.strip().str.title()

# -------------------------------
# CLEAN DATA (IMPORTANT)
# -------------------------------
df["status"] = df["status"].astype(str).str.strip().str.title()
df["ipr_type"] = df["ipr_type"].astype(str).str.strip().str.title()

# Normalize IPR types (very important for GTU data)
df["ipr_type"] = (
    df["ipr_type"]
    .str.lower()
    .str.replace("copy r", "copyright")
    .str.replace("trademark.*", "trademark", regex=True)
    .str.replace("patent.*", "patent", regex=True)
    .str.strip()
    .str.title()
)

# -------------------------------
# OVERALL KPIs
# -------------------------------
filed_patent = df[(df["status"]=="Filed") & (df["ipr_type"]=="Patent")].shape[0]
granted_patent = df[(df["status"]=="Granted") & (df["ipr_type"]=="Patent")].shape[0]

grant_rate = (granted_patent / filed_patent * 100) if filed_patent > 0 else 0

# -------------------------------
# TRADEMARK
# -------------------------------
filed_tm = df[(df["status"]=="Filed") & (df["ipr_type"]=="Trademark")].shape[0]
granted_tm = df[(df["status"]=="Granted") & (df["ipr_type"]=="Trademark")].shape[0]

# -------------------------------
# COPYRIGHT
# -------------------------------
filed_cr = df[(df["status"]=="Filed") & (df["ipr_type"]=="Copyright")].shape[0]
granted_cr = df[(df["status"]=="Granted") & (df["ipr_type"]=="Copyright")].shape[0]

# -------------------------------
# DISPLAY KPIs (7 cards)
# -------------------------------

st.subheader("📊 Patent KPIs")
col1, col2, col3 = st.columns(3)
col1.metric("📥 Filed Patent", filed_patent)
col2.metric("✅ Granted Patent", granted_patent)
col3.metric("📊 Grant Rate", f"{grant_rate:.2f}%")

st.subheader("🏷 Trademark KPIs")
col4, col5 = st.columns(2)
col4.metric("🏷 Filed Trademark", filed_tm)
col5.metric("🏷 Granted Trademark", granted_tm)

st.subheader("© Copyright KPIs")
col6, col7 = st.columns(2)
col6.metric("© Filed Copyright", filed_cr)
col7.metric("© Granted Copyright", granted_cr)


# -------------------------------
# CHARTS
# -------------------------------
if "year" in df.columns:
    year_data = df.groupby(["year", "status"]).size().reset_index(name="count")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Filed vs Granted (Year-wise)")
        st.plotly_chart(
            px.bar(year_data, x="year", y="count", color="status"),
            width="stretch"
        )

    with col2:
        st.subheader("Trend Over Time")
        st.plotly_chart(
            px.line(year_data, x="year", y="count", color="status", markers=True),
            width="stretch"
        )

# Department chart
if "department" in df.columns:
    st.subheader("Department-wise Distribution")
    dept_data = df.groupby(["department", "status"]).size().reset_index(name="count")

    st.plotly_chart(
        px.bar(dept_data, x="department", y="count", color="status"),
        width="stretch"
    )

st.divider()
# -------------------------------
# PIE CHART - IPR DISTRIBUTION
# -------------------------------
st.subheader("🥧 IPR Distribution: Filed vs Granted")

import plotly.express as px

if "ipr_type" not in df.columns:
    st.warning("IPR Type data not available")

else:
    col1, col2 = st.columns(2)

    # Filed
    with col1:
        filed_df = df[df["status"] == "Filed"]
        filed_counts = filed_df["ipr_type"].value_counts().reset_index()
        filed_counts.columns = ["IPR Type", "Count"]

        fig1 = px.pie(
            filed_counts,
            names="IPR Type",
            values="Count",
            title="Filed IPR Distribution",
            hole=0.4
        )

        st.plotly_chart(fig1, width="stretch")

    # Granted
    with col2:
        granted_df = df[df["status"] == "Granted"]
        granted_counts = granted_df["ipr_type"].value_counts().reset_index()
        granted_counts.columns = ["IPR Type", "Count"]

        fig2 = px.pie(
            granted_counts,
            names="IPR Type",
            values="Count",
            title="Granted IPR Distribution",
            hole=0.4
        )

        st.plotly_chart(fig2, width="stretch")

#fig1.update_traces(hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}")

#fig2.update_traces(hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}")    

status_data = df["status"].value_counts().reset_index()
status_data.columns = ["Status", "Count"]

fig = px.pie(status_data, names="Status", values="Count", hole=0.4)

st.subheader("📊 Filed vs Granted Distribution")
st.plotly_chart(fig,width="stretch")
selected_status = st.selectbox("Select Status", ["Filed", "Granted"])

filtered = df[df["status"] == selected_status]

counts = filtered["ipr_type"].value_counts().reset_index()
counts.columns = ["IPR Type", "Count"]

fig = px.pie(counts, names="IPR Type", values="Count", hole=0.4)

st.plotly_chart(fig, width="stretch")

pivot = df.groupby(["ipr_type", "status"]).size().reset_index(name="count")

fig = px.bar(
    pivot,
    x="ipr_type",
    y="count",
    color="status",
    barmode="group",
    title="IPR Type Distribution: Filed vs Granted"
)

st.plotly_chart(fig,width="stretch")
# -------------------------------
# DOWNLOAD + TABLE
# -------------------------------
st.subheader("📋 Patent Data")

st.download_button(
    "📥 Download Data",
    df.to_csv(index=False),
    file_name="gtu_patents.csv"
)

st.dataframe(df,width="stretch")
#st.metric("Total Filed", len(filed_df))
#st.metric("Total Granted", len(granted_df))
#st.write(df.columns)
#st.write("Columns:", df.columns.tolist())
#st.write("Preview:", df.head())
