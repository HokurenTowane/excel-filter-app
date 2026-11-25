import streamlit as st
import pandas as pd
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import io

st.set_page_config(page_title="Secure Excel Filter", layout="wide")

# --- 1. LOAD THE LOGIN CONFIG ---
with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

# Load the authenticator (New version syntax)
authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

# --- 2. THE LOGIN WALL ---
try:
    authenticator.login(location='main')
except Exception as e:
    if "User not authorized" in str(e):
        # Clears the broken cookie if it happens
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    else:
        st.error(e)

name = st.session_state.get('name')
authentication_status = st.session_state.get('authentication_status')

if authentication_status == False:
    st.error('Username/password is incorrect')
    
elif authentication_status == None:
    st.warning('Please enter your username and password')
    
    # Registration form (New version syntax)
    with st.expander("Don't have an account? Register here"):
        try:
            if authenticator.register_user(location='main'):
                st.success('User registered successfully!')
                with open('config.yaml', 'w') as file:
                    yaml.dump(config, file, default_flow_style=False)
                st.rerun()
        except Exception as e:
            st.error(e)

# --- 3. THE ACTUAL APP (Only shows if logged in) ---
elif authentication_status == True:
    
    st.sidebar.write(f'Welcome *{name}*')
    authenticator.logout('Logout', 'sidebar')
    
    st.title("🧬 Advanced Excel Data Filter Tool")
    st.write("Upload your Excel file to filter, search, and sort the data.")

    uploaded_file = st.file_uploader("Choose an Excel file", type=["xlsx", "xls"])

    if uploaded_file is not None:
        @st.cache_data
        def load_data(file):
            return pd.read_excel(file)

        df = load_data(uploaded_file)
        filtered_df = df.copy()

        st.success(f"File loaded! {len(df)} rows and {len(df.columns)} columns.")

        # --- SIDEBAR FOR FILTERS ---
        st.sidebar.header("Filter Settings")
        
        search_query = st.sidebar.text_input("🔍 Search for a specific value:")
        if search_query:
            mask = filtered_df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)
            filtered_df = filtered_df[mask]

        st.sidebar.markdown("---")
        st.sidebar.subheader("Category Filters")

        columns_to_filter = st.sidebar.multiselect("Select columns to filter by:", df.columns)
        
        # NEW: The ATCG Fix!
        for col in columns_to_filter:
            if pd.api.types.is_numeric_dtype(df[col]):
                min_val = float(df[col].min())
                max_val = float(df[col].max())
                selected_range = st.sidebar.slider(
                    f"Range for {col}:",
                    min_value=min_val,
                    max_value=max_val,
                    value=(min_val, max_val)
                )
                filtered_df = filtered_df[(filtered_df[col] >= selected_range[0]) & (filtered_df[col] <= selected_range[1])]
            else:
                unique_values = df[col].dropna().unique()
                selected_values = st.sidebar.multiselect(f"Select values for {col}:", options=unique_values)
                if selected_values:
                    filtered_df = filtered_df[filtered_df[col].isin(selected_values)]

        # --- MAIN PAGE RESULTS ---
        st.subheader("Filtered Results")
        
        if st.button("🔄 Clear Data & Upload New File"):
            st.rerun()

        st.write(f"Showing **{len(filtered_df)}** rows based on your filters.")
        st.dataframe(filtered_df, use_container_width=True)

        # --- DOWNLOAD OPTIONS (CSV & Excel) ---
        st.write("### Download Options")
        download_format = st.radio("Choose format:", ["CSV", "Excel (.xlsx)"], horizontal=True)
        
        if download_format == "CSV":
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download as CSV",
                data=csv,
                file_name='filtered_data.csv',
                mime='text/csv',
            )
        else:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                filtered_df.to_excel(writer, index=False, sheet_name='Filtered_Data')
            
            st.download_button(
                label="📥 Download as Excel",
                data=buffer.getvalue(),
                file_name='filtered_data.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
