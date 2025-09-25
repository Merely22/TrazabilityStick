import streamlit as st
import pandas as pd
import numpy as np 
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime
import io
import plotly.express as px
import plotly.graph_objects as go 
#========================================================================================
st.set_page_config(page_title="Dashboard Trazability STICK", layout="wide")
st.title("📊 Trazability STICK ")

# Autenticación con Google Sheets
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = service_account.Credentials.from_service_account_info(
    st.secrets, scopes=SCOPES)
service = build("sheets", "v4", credentials=credentials)

# ID de la hoja y nombre de la hoja
SPREADSHEET_ID = "1j8ZSrj2nRZgBp5F6c03dxN7GLqCki2M8vWEX8kICB8M"
SHEET_NAME = "STICKB1" # changed pending

@st.cache_data(ttl=60) # actualiza cada 60 segundos
def load_data(): 
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A2:AD500" # changed pending
    ).execute()

    values = result.get("values", [])
    if not values:
        st.warning("No se encontraron datos en la hoja de cálculo.")
        return pd.DataFrame()
    
    headers = values[0]
    data = values[1:]
    #return pd.DataFrame(data, columns=headers)
    # Rellenar filas cortas con valores vacíos para que coincidan con headers
    fixed_data = [row + [""] * (len(headers) - len(row)) for row in data]

    return pd.DataFrame(fixed_data, columns=headers)
#========================================================================================
# Cargar datos
df = load_data()

# --- PASO 1: Renombrar las columnas para que sean más fáciles de usar ---
df.rename(columns={
    '#': 'ID',
    'MAC': 'MAC',
    'BATCH': 'BATCH',
    'LAB TESTING DATE': 'Date_Test_Lab',
    'Testing_Date01': 'Date_NMEA_QC1',
    'Testing_Date02': 'Date_NMEA_QC2',
    'Production Date': 'Date_Prod',
    'Shippent Date': 'Date_Shipp',
    'Observations': 'Observations' # add observations column
}, inplace=True)

# --- PASO 2: Eliminar filas donde la MAC es nula
df.dropna(subset=['MAC'], inplace=True)
df = df[df['MAC'].str.strip() != '']
df['MAC'] = df['MAC'].astype(str).str.strip()

# --- PASO 3: Convertir las columnas de fecha a formato de fecha ---
date_columns = ['Date_Test_Lab', 'Date_NMEA_QC1', 'Date_NMEA_QC2', 'Date_Prod', 'Date_Shipp']
for col in date_columns:
    df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)

#  build a dictionary with observations
observaciones = [
    "no recibe mensajes",
    "no envia mensajes",
    "no recibe correcciones",
    "datos faltantes",
    "bluetooth",
    "pierde conexión",
    "no converge",
    "se apagó",
    "no enciende",
    "cortes",
    "conector",
    "cabezal",
    "ublox",
    "bug microcontrolador",
    "error satélites",
    "led"
]

# build a df and clean column observations 
df['Observations_lower'] = df['Observations'].str.lower().fillna('')

# build a function 
def find_word(texto):
    for palabra in observaciones:
        if palabra in texto:
            return palabra.capitalize() 
    return np.nan # Devolvemos NaN si no se encuentra ninguna

# build the column 'Estado_Observacion' applied the fuction
df['Estado_Observacion'] = df['Observations_lower'].apply(find_word)

# --- PASO 4: Asignamos la etapa de forma secuencial. La última condición que se cumpla será la etapa final.
df['Etapa_Actual'] = '0. Pendiente' # Valor por defecto
df.loc[df['Date_Test_Lab'].notna(), 'Etapa_Actual'] = 'Pruebas de Laboratorio'
df.loc[df['Date_NMEA_QC1'].notna(), 'Etapa_Actual'] = 'NMEA QC 01'
df.loc[df['Date_NMEA_QC2'].notna(), 'Etapa_Actual'] = 'NMEA QC 02'
df.loc[df['Date_Prod'].notna(), 'Etapa_Actual'] = 'Produccion Finalizada'
df.loc[df['Date_Shipp'].notna(), 'Etapa_Actual'] = 'Equipos Enviados'

# --- PASO 5: Calcular la duración en días entre cada etapa ---
df['Dias_Lab_a_NMEA1'] = (df['Date_NMEA_QC1'] - df['Date_Test_Lab']).dt.days
df['Dias_NMEA1_a_NMEA2'] = (df['Date_NMEA_QC2'] - df['Date_NMEA_QC1']).dt.days
df['Dias_NMEA2_a_FinProd'] = (df['Date_Prod'] - df['Date_NMEA_QC2']).dt.days
df['Dias_Prod_Shipp'] = (df['Date_Shipp'] - df['Date_Prod']).dt.days
df['Dias_Totales'] = (df['Date_Shipp'] - df['Date_Test_Lab']).dt.days

# build a df with the main observation
df_obs = df.dropna(subset=['Estado_Observacion'])
#========================================================================================

# --- KPIs / Resumen General ---
# Contar equipos en cada etapa 
total_equipos = len(df)
en_etapa1 = len(df[df['Etapa_Actual'] == 'Pruebas de Laboratorio'])
en_etapa2 = len(df[df['Etapa_Actual'] == 'NMEA QC 01'])
en_etapa3 = len(df[df['Etapa_Actual'] == 'NMEA QC 02'])
en_etapa4 = len(df[df['Etapa_Actual'] == 'Produccion Finalizada'])
en_etapa5 = len(df[df['Etapa_Actual'] == 'Equipos Enviados'])

st.header ('Resumen de Equipos por Etapa')
col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Total de Equipos", f"{total_equipos}",f"{total_equipos*100/total_equipos:.1f}%")
col2.metric("En Lab Test", f"{en_etapa1}", f"{(en_etapa1*100)/total_equipos:.1f}%")
col3.metric("En NMEA QC 1", f"{en_etapa2}", f"{(en_etapa2*100)/total_equipos:.1f}%")
col4.metric("En NMEA QC 2", f"{en_etapa3}", f"{(en_etapa3*100)/total_equipos:.1f}%")
col5.metric("Produccion finalizada", f"{en_etapa4}", f"{(en_etapa4*100)/total_equipos:.1f}%")
col6.metric("Enviados", f"{en_etapa5}", f"{(en_etapa5*100)/total_equipos:.1f}%")

st.divider()

# --- Add table with observations ---  
col_obs1, col_obs2 = st.columns(2)
with col_obs1:
    st.subheader ('Equipos en estado de Observación')
    count_obs = df_obs['Estado_Observacion'].value_counts().reset_index()     # observation counts
    st.write("Total de equipos observados:", len(df_obs))
    count_obs.columns = ['Tipo de Problema', 'Cantidad']
    fig_obs = px.bar(
        count_obs,
        x='Cantidad',
        y='Tipo de Problema',
        orientation='h',
        text='Cantidad'
    )
    fig_obs.update_layout(yaxis={'categoryorder':'total ascending'})
    st.plotly_chart(fig_obs, use_container_width=True)

with col_obs2:
    st.subheader("Estado actual de equipos Observados")
    st.dataframe(
        df_obs[['MAC','Estado_Observacion', 'Etapa_Actual']],
        use_container_width=True
    )

st.divider()

# --- Análisis de Tiempos ---
#st.header("⏱️ Análisis de Tiempos de Producción")
col1_tiempo, col2_tiempo = st.columns(2)

with col1_tiempo:
    st.subheader("Tiempos Promedio entre Etapas")
    avg_dias_1_2 = df['Dias_Lab_a_NMEA1'].mean()
    avg_dias_2_3 = df['Dias_NMEA1_a_NMEA2'].mean()
    avg_dias_3_4 = df['Dias_NMEA2_a_FinProd'].mean()
    avg_dias_4_5 = df['Dias_Prod_Shipp'].mean()
    avg_dias_total = df['Dias_Totales'].mean()

    # Mostramos los promedios 
    if pd.notna(avg_dias_1_2):
        st.info(f"**Promedio Lab → NMEA 1:** {avg_dias_1_2:.1f} días")
    if pd.notna(avg_dias_2_3):
        st.info(f"**Promedio NMEA 1 → NMEA 2:** {avg_dias_2_3:.1f} días")
    if pd.notna(avg_dias_3_4):
        st.info(f"**Promedio NMEA 2 → Produccion Final:** {avg_dias_3_4:.1f} días")
    if pd.notna(avg_dias_4_5):
        st.info(f"**Produccion Final → Envio:** {avg_dias_4_5:.1f} días")
    if pd.notna(avg_dias_total):
        st.success(f"**Promedio Total Proceso:** {avg_dias_total:.1f} días")
        
with col2_tiempo:
    st.subheader("Visualización del Flujo de Proceso")
    etapas_labels = [
                '1. Pruebas de Laboratorio', '2. NMEA QC 01', '3. NMEA QC 02',
                '4. Produccion Finalizada', '5. Equipos Enviados'
            ]
    etapas_valores = [
        len(df[df['Date_Test_Lab'].notna()]),
        len(df[df['Date_NMEA_QC1'].notna()]),
        len(df[df['Date_NMEA_QC2'].notna()]),
        len(df[df['Date_Prod'].notna()]),
        len(df[df['Date_Shipp'].notna()])
    ]
    
    fig_funnel = go.Figure(go.Funnel(
        y = [label.split('. ')[1] for label in etapas_labels], # Nombres más limpios
        x = etapas_valores,
        textinfo = "value+percent initial"
    ))
    fig_funnel.update_layout(margin=dict(t=30, b=10, l=10, r=10))
    st.plotly_chart(fig_funnel, use_container_width=True)


st.divider()

# --- Detalle por Etapa ---
st.header("📋 Estado de los Equipos por Etapa")

# Crear pestañas para cada etapa
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    f"Lab Test ({en_etapa1})", 
    f"NMEA QC 01 ({en_etapa2})", 
    f"NMEA QC 02 ({en_etapa3})",
    f" Producciòn Final ({en_etapa4})",
    f" Equipos Enviados ({en_etapa5})"
])

with tab1:

    st.subheader("Equipos en Pruebas de Laboratorio")
    df_filtrado = df[df['Etapa_Actual'] == 'Pruebas de Laboratorio']
    st.dataframe(df_filtrado[['ID', 'MAC', 'BATCH', 'Date_Test_Lab']])

with tab2:
    st.subheader("Equipos en Evaluación NMEA QC 01")
    df_filtrado = df[df['Etapa_Actual'] == 'NMEA QC 01']
    st.dataframe(df_filtrado[['ID', 'MAC', 'BATCH', 'Date_NMEA_QC1', 'Dias_Lab_a_NMEA1']])

with tab3:
    st.subheader("Equipos en Evaluación NMEA QC 02")
    df_filtrado = df[df['Etapa_Actual'] == 'NMEA QC 02']
    st.dataframe(df_filtrado[['ID', 'MAC', 'BATCH', 'Date_NMEA_QC2', 'Dias_NMEA1_a_NMEA2']])

with tab4:
    st.subheader("Equipos en Producciòn Finalizada")
    df_filtrado = df[df['Etapa_Actual'] == 'Produccion Finalizada']
    st.dataframe(df_filtrado[['ID', 'MAC', 'BATCH', 'Date_Prod', 'Dias_Totales']])

with tab5:
    st.subheader("Equipos Enviados")
    df_filtrado = df[df['Etapa_Actual'] == 'Equipos Enviados']
    st.dataframe(df_filtrado[['ID', 'MAC', 'BATCH', 'Date_Prod', 'Dias_Totales']])

# --- Tabla de Datos Completa ---
with st.expander("Ver tabla de datos completa y procesada"):
    st.write("Esta tabla contiene todos los datos cargados y las columnas calculadas (etapas y duraciones).")
    st.dataframe(df)

