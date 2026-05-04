import streamlit as st
import pandas as pd

st.title("Zeitreihenanalyse Demo")

file = st.file_uploader("CSV hochladen", type=["csv"])

if file is not None:
    df = pd.read_csv(file)

    st.subheader("Daten")
    st.write(df.head())

    st.subheader("Einfache Statistik")
    st.write(df.describe())

    st.subheader("Plot")
    st.line_chart(df)