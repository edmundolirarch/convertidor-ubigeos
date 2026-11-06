import streamlit as st
import pandas as pd
import io
from rapidfuzz import process, fuzz

# Configuración de página
st.set_page_config(page_title="Convertidor de Ubigeos", layout="wide")
st.title("📍 Convertidor y Validador de Ubigeos")

# 1. Cargar Data Maestra
@st.cache_data
def load_master():
    df = pd.read_excel('Ubigeos.xlsx')
    # Asegurar que el Ubigeo tenga 6 dígitos
    df['Ubigeo'] = df['Ubigeo'].astype(str).str.zfill(6)
    # Crear columna concatenada para búsqueda
    df['Concat'] = df['Departamento'] + " | " + df['Provincia'] + " | " + df['Distrito']
    return df

df_master = load_master()
master_choices = df_master['Concat'].tolist()
ubigeo_dict = dict(zip(df_master['Concat'], df_master['Ubigeo']))

# Función para procesar y buscar similitudes
def procesar_datos(df_input):
    resultados_exactos = []
    resultados_pendientes = []
    
    # Progreso visual
    progress_bar = st.progress(0)
    total = len(df_input)
    
    for idx, row in df_input.iterrows():
        # Limpiar y concatenar entrada
        dep = str(row.iloc[0]).strip().upper()
        prov = str(row.iloc[1]).strip().upper()
        dist = str(row.iloc[2]).strip().upper()
        busqueda = f"{dep} | {prov} | {dist}"
        
        # Buscar en RapidFuzz (maneja abreviaturas y errores tipográficos)
        match = process.extractOne(busqueda, master_choices, scorer=fuzz.WRatio)
        
        if match and match[1] == 100:
            resultados_exactos.append({
                'Departamento_Orig': dep, 'Provincia_Orig': prov, 'Distrito_Orig': dist,
                'Ubigeo_Oficial': ubigeo_dict[match[0]],
                'Nombre_Oficial': match[0],
                'Similitud': match[1]
            })
        else:
            # Obtener top 5 opciones
            opciones = process.extract(busqueda, master_choices, scorer=fuzz.WRatio, limit=5)
            sugerencias = [f"{op[0]} (Similitud: {op[1]:.0f}%)" for op in opciones]
            
            resultados_pendientes.append({
                'ID': idx,
                'Original': busqueda,
                'Sugerencias': sugerencias,
                'Opciones_Crudas': [op[0] for op in opciones]
            })
            
        progress_bar.progress((idx + 1) / total)
        
    return pd.DataFrame(resultados_exactos), resultados_pendientes

# Pestañas de la interfaz
tab1, tab2 = st.tabs(["🔄 Convertidor Masivo", "🔍 Consulta Inversa (Código a Texto)"])

with tab1:
    st.markdown("### Ingreso de Datos")
    metodo = st.radio("Selecciona el método de carga:", ["Cargar archivo Excel (.xlsx)", "Copiar y Pegar desde Excel"])
    
    df_input = None
    
    if metodo == "Cargar archivo Excel (.xlsx)":
        uploaded_file = st.file_uploader("Sube tu archivo (Debe contener 3 columnas: Depto, Prov, Dist)", type=["xlsx"])
        if uploaded_file is not None:
            df_input = pd.read_excel(uploaded_file)
            
    else:
        st.info("Copia las celdas de tu Excel (sin los encabezados) y pégalas en el recuadro de abajo.")
        txt_input = st.text_area("Pega aquí los datos:", height=150)
        if txt_input:
            df_input = pd.read_csv(io.StringIO(txt_input), sep='\t', header=None)
            df_input.columns = ['Departamento', 'Provincia', 'Distrito']

    if df_input is not None and not df_input.empty:
        if st.button("Procesar Ubigeos", type="primary"):
            df_exactos, pendientes = procesar_datos(df_input)
            
            st.session_state['df_exactos'] = df_exactos
            st.session_state['pendientes'] = pendientes
            
    # Mostrar resultados si existen en sesión
    if 'df_exactos' in st.session_state:
        st.divider()
        st.markdown("### Resultados de la Validación")
        
        tab_exactos, tab_pendientes = st.tabs([
            f"✅ Aprobados Automáticos ({len(st.session_state['df_exactos'])})", 
            f"⚠️ Pendientes de Revisión ({len(st.session_state['pendientes'])})"
        ])
        
        with tab_exactos:
            st.dataframe(st.session_state['df_exactos'], use_container_width=True)
            
        with tab_pendientes:
            pendientes = st.session_state['pendientes']
            if not pendientes:
                st.success("¡Excelente! Todos los registros coincidieron al 100%.")
                df_final = st.session_state['df_exactos']
            else:
                st.warning("Selecciona la opción correcta para los registros con errores tipográficos o abreviaturas.")
                
                with st.form("form_revision"):
                    selecciones = []
                    for item in pendientes:
                        st.markdown(f"**Original ingresado:** `{item['Original']}`")
                        seleccion = st.selectbox(
                            "Selecciona la coincidencia correcta:",
                            options=item['Sugerencias'],
                            key=f"sel_{item['ID']}"
                        )
                        # Extraer el nombre original limpio de la selección
                        idx_seleccionado = item['Sugerencias'].index(seleccion)
                        selecciones.append(item['Opciones_Crudas'][idx_seleccionado])
                        st.markdown("---")
                        
                    submit_revision = st.form_submit_button("Aprobar Selecciones y Consolidar")
                    
                    if submit_revision:
                        # Crear dataframe de los corregidos
                        corregidos_list = []
                        for i, item in enumerate(pendientes):
                            nombre_oficial = selecciones[i]
                            partes = item['Original'].split(" | ")
                            corregidos_list.append({
                                'Departamento_Orig': partes[0] if len(partes)>0 else "", 
                                'Provincia_Orig': partes[1] if len(partes)>1 else "", 
                                'Distrito_Orig': partes[2] if len(partes)>2 else "",
                                'Ubigeo_Oficial': ubigeo_dict[nombre_oficial],
                                'Nombre_Oficial': nombre_oficial,
                                'Similitud': 'Aprobado Manual'
                            })
                        df_corregidos = pd.DataFrame(corregidos_list)
                        df_final = pd.concat([st.session_state['df_exactos'], df_corregidos], ignore_index=True)
                        st.session_state['df_final'] = df_final
                        st.success("Revisiones aprobadas. Ya puedes descargar el archivo consolidado.")

        # Botón de descarga consolidada
        if 'df_final' in st.session_state:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                st.session_state['df_final'].to_excel(writer, index=False, sheet_name='Ubigeos_Validados')
            datos_excel = output.getvalue()
            
            st.download_button(
                label="📥 Descargar Excel Consolidado",
                data=datos_excel,
                file_name="Ubigeos_Validados.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

with tab2:
    st.markdown("### Consulta Inversa de Ubigeo")
    codigo_input = st.text_input("Ingresa el código de 6 dígitos (Ej: 010101):", max_chars=6)
    
    if codigo_input:
        if len(codigo_input) == 6 and codigo_input.isdigit():
            resultado = df_master[df_master['Ubigeo'] == codigo_input]
            if not resultado.empty:
                st.success("Ubigeo encontrado:")
                st.dataframe(resultado[['Ubigeo', 'Departamento', 'Provincia', 'Distrito']], hide_index=True)
            else:
                st.error("El código ingresado no existe en la base de datos.")
        else:
            st.warning("El ubigeo debe contener exactamente 6 números.")