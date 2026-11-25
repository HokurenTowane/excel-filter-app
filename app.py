import streamlit as st
import pandas as pd

st.set_page_config(page_title="Advanced Excel Filter Tool", layout="wide")
st.title("🧬 Advanced Excel Data Filter Tool")
st.write("Upload your Excel file to filter, search, and sort the data.")

uploaded_file = st.file_uploader("Choose an Excel file", type=["xlsx", "xls"])

if uploaded_file is not None:
    @st.cache_data
    def load_data(file):
        return pd.read_excel(file)

    df = load_data(uploaded_file)
    filtered_df = df.copy() # We will apply filters to this copy

    st.success(f"File loaded! {len(df)} rows and {len(df.columns)} columns.")

    # --- SIDEBAR FOR FILTERS ---
    st.sidebar.header("Filter Settings")
    
    # 1. Text Search (filters across ALL columns for a specific word)
    search_query = st.sidebar.text_input("🔍 Search for a specific value (e.g., a Gene ID):")
    if search_query:
        # This looks for the search term in any column, ignoring case
        mask = filtered_df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)
        filtered_df = filtered_df[mask]

    st.sidebar.markdown("---")
    st.sidebar.subheader("Category Filters")

    # 2. Multi-Column Dropdown Filters
    # We let the user pick up to 3 columns to filter by
    columns_to_filter = st.sidebar.multiselect("Select columns to filter by:", df.columns)
    
    for col in columns_to_filter:
        unique_values = df[col].dropna().unique()
        # If there are too many unique values, show a text input instead of a massive dropdown
        if len(unique_values) > 50:
            specific_val = st.sidebar.text_input(f"Type exact value for {col}:")
            if specific_val:
                filtered_df = filtered_df[filtered_df[col].astype(str).str.contains(specific_val, case=False, na=False)]
        else:
            selected_values = st.sidebar.multiselect(f"Select values for {col}:", options=unique_values)
            if selected_values:
                filtered_df = filtered_df[filtered_df[col].isin(selected_values)]

    st.sidebar.markdown("---")
    st.sidebar.subheader("Range Filter (Numbers)")

    # 3. Numeric Range Slider
    # Find all columns that contain numbers
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    if numeric_cols:
        range_col = st.sidebar.selectbox("Select a numeric column to filter by range:", numeric_cols)
        if range_col:
            min_val = float(df[range_col].min())
            max_val = float(df[range_col].max())
            # Create the slider
            selected_range = st.sidebar.slider(
                f"Select range for {range_col}:",
                min_value=min_val,
                max_value=max_val,
                value=(min_val, max_val)
            )
            # Apply the range filter
            filtered_df = filtered_df[(filtered_df[range_col] >= selected_range[0]) & (filtered_df[range_col] <= selected_range[1])]

    # --- MAIN PAGE RESULTS ---
    st.subheader("Filtered Results")
    st.write(f"Showing **{len(filtered_df)}** rows based on your filters.")
    
    # Let them sort the final table by clicking the column headers
    st.dataframe(filtered_df, use_container_width=True)

    # Download Button
    csv = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Filtered Data as CSV",
        data=csv,
        file_name='filtered_data.csv',
        mime='text/csv',
    )

    with st.expander("Preview Original Unfiltered Data"):
        st.dataframe(df.head())
