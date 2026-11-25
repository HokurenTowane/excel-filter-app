import streamlit as st
import pandas as pd

st.set_page_config(page_title="Excel Filter Tool", layout="wide")
st.title("Excel Data Filter Tool")
st.write("Upload your Excel file to filter the data.")

uploaded_file = st.file_uploader("Choose an Excel file", type=["xlsx", "xls"])

if uploaded_file is not None:
    @st.cache_data
    def load_data(file):
        return pd.read_excel(file)

    df = load_data(uploaded_file)

    st.success(f"File loaded! {len(df)} rows and {len(df.columns)} columns.")

    with st.expander("Preview Original Data"):
        st.dataframe(df.head())

    st.subheader("Filter Settings")
    column_to_filter = st.selectbox("Select the column you want to filter:", df.columns)
    unique_values = df[column_to_filter].unique()
    selected_values = st.multiselect(
        f"Select values for '{column_to_filter}':",
        options=unique_values,
        default=unique_values[:5] if len(unique_values) > 5 else unique_values
    )

    if selected_values:
        filtered_df = df[df[column_to_filter].isin(selected_values)]
    else:
        filtered_df = df

    st.subheader("Filtered Results")
    st.write(f"Showing {len(filtered_df)} rows after filtering.")
    st.dataframe(filtered_df)

    csv = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Filtered Data as CSV",
        data=csv,
        file_name='filtered_data.csv',
        mime='text/csv',
    )