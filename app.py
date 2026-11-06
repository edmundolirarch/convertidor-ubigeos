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
    df['Ubigeo'] = df['Ubigeo'].astype(str).str.zfill(6)
    df['Concat'] = df['Departamento'] + " | " + df['Provincia'] + " | " + df['Distrito']
    return df

df_master = load_master()
master_choices = df_master['Concat'].tolist()
ubigeo_dict = dict(zip(df_master['Concat'], df_master['Ubigeo']))

# Función inicial de procesamiento
def iniciar_procesamiento(df_input):
    data = {}
    progress_bar = st.progress(0)
    total = len(df_input)
    
    for idx, row in df_input.iterrows():
        dep = str(row.iloc[0]).strip().upper() if pd.notna(row.iloc[0]) else ""
        prov = str(row.iloc[1]).strip().upper() if pd.notna(row.iloc[1]) else ""
        dist = str(row.iloc[2]).strip().upper() if pd.notna(row.iloc[2]) else ""
        busqueda = f"{dep} | {prov} | {dist}"
        
        match = process.extractOne(busqueda, master_choices, scorer=fuzz.WRatio)
        
        if match and match[1] == 100:
            data[idx] = {
                'Original': busqueda, 'Dep_Orig': dep, 'Prov_Orig': prov, 'Dist_Orig': dist,
                'Estado': 'Aprobado', 'Ubigeo_Oficial': ubigeo_dict[match[0]],
                'Nombre_Oficial': match[0], 'Similitud': 100,
                'Sugerencias': [], 'Opciones_Crudas': [], 'Edit_Mode': False, 'Seleccionado': False
            }
        else:
            opciones = process.extract(busqueda, master_choices, scorer=fuzz.WRatio, limit=5)
            sugerencias = [f"{op[0]} (Similitud: {op[1]:.0f}%)" for op in opciones]
            data[idx] = {
                'Original': busqueda, 'Dep_Orig': dep, 'Prov_Orig': prov, 'Dist_Orig': dist,
                'Estado': 'Pendiente', 'Ubigeo_Oficial': '',
                'Nombre_Oficial': '', 'Similitud': '',
                'Sugerencias': sugerencias, 'Opciones_Crudas': [op[0] for op in opciones],
                'Edit_Mode': False, 
                'Seleccionado': True # Preseleccionado por defecto
            }
        progress_bar.progress((idx + 1) / total)
        
    progress_bar.empty()
    st.session_state['data'] = data
    st.session_state['procesado'] = True

# Pestañas de la interfaz
tab1, tab2 = st.tabs(["🔄 Convertidor Masivo", "🔍 Consulta Inversa"])

with tab1:
    st.markdown("### Ingreso de Datos")
    metodo = st.radio("Selecciona el método de carga:", ["Cargar archivo Excel (.xlsx)", "Copiar y Pegar desde Excel"])
    
    df_input = None
    
    if metodo == "Cargar archivo Excel (.xlsx)":
        uploaded_file = st.file_uploader("Sube tu archivo (Debe contener 3 columnas: Depto, Prov, Dist)", type=["xlsx"])
        if uploaded_file is not None:
            df_input = pd.read_excel(uploaded_file)
            
    else:
        st.info("Paso 1: Copia las 3 columnas de tu Excel (sin encabezados) y pégalas aquí:")
        txt_input = st.text_area("Datos copiados:", height=150, label_visibility="collapsed")
        
        # Paso 2: Botón de carga intermedio
        if st.button("📥 Cargar texto pegado", type="primary"):
            if txt_input.strip():
                try:
                    df_temp = pd.read_csv(io.StringIO(txt_input), sep='\t', header=None)
                    if len(df_temp.columns) >= 3:
                        df_temp = df_temp.iloc[:, :3]
                        df_temp.columns = ['Departamento', 'Provincia', 'Distrito']
                        st.session_state['df_preview'] = df_temp
                    else:
                        st.error("Error: Los datos pegados no tienen 3 columnas. Verifica el copiado.")
                except Exception as e:
                    st.error("Error al leer el texto.")
            else:
                st.warning("El recuadro está vacío.")

        # Paso 3: Vista previa
        if 'df_preview' in st.session_state:
            st.markdown("**Vista previa de datos cargados:**")
            st.dataframe(st.session_state['df_preview'], height=200, use_container_width=True)
            df_input = st.session_state['df_preview']

    # Procesar
    if df_input is not None and not df_input.empty:
        st.markdown("---")
        if st.button("🚀 Procesar Ubigeos"):
            iniciar_procesamiento(df_input)

    # Mostrar Resultados interactivos
    if 'procesado' in st.session_state and st.session_state['procesado']:
        datos = st.session_state['data']
        pendientes_count = sum(1 for v in datos.values() if v['Estado'] == 'Pendiente')
        aprobados_count = len(datos) - pendientes_count

        # Función de Aprobación en Lote
        def aprobar_lote():
            modificados = False
            for i, d in st.session_state['data'].items():
                if d['Estado'] == 'Pendiente' and st.session_state.get(f"chk_{i}", False):
                    sel_text = st.session_state[f"sel_{i}"]
                    idx_sel = d['Sugerencias'].index(sel_text)
                    nombre_oficial = d['Opciones_Crudas'][idx_sel]
                    
                    st.session_state['data'][i]['Estado'] = 'Aprobado'
                    st.session_state['data'][i]['Nombre_Oficial'] = nombre_oficial
                    st.session_state['data'][i]['Ubigeo_Oficial'] = ubigeo_dict[nombre_oficial]
                    modificados = True
            if modificados:
                st.rerun()

        # PANEL LATERAL FLOTANTE PARA APROBACIÓN
        if pendientes_count > 0:
            with st.sidebar:
                st.markdown("### ⚙️ Acciones en Lote")
                st.info(f"Tienes **{pendientes_count}** registros pendientes en revisión.")
                if st.button("✅ Aprobar Seleccionados (Lote)", type="primary", use_container_width=True):
                    aprobar_lote()
                st.divider()
                st.markdown("💡 *Este panel siempre estará visible mientras bajas por la lista.*")

        st.divider()
        st.markdown("### Resultados de la Validación")
        
        tab_exactos, tab_pendientes = st.tabs([
            f"✅ Aprobados ({aprobados_count})", 
            f"⚠️ Pendientes de Revisión ({pendientes_count})"
        ])
        
        with tab_pendientes:
            if pendientes_count == 0:
                st.success("¡Excelente! No hay registros pendientes.")
            else:
                # Botones de Selección Masiva (Arriba)
                col_sel1, col_sel2, col_sel3 = st.columns([2, 2, 4])
                with col_sel1:
                    if st.button("☑️ Marcar Todos"):
                        for i, d in st.session_state['data'].items():
                            if d['Estado'] == 'Pendiente':
                                st.session_state['data'][i]['Seleccionado'] = True
                                st.session_state[f"chk_{i}"] = True
                        st.rerun()
                with col_sel2:
                    if st.button("☐ Desmarcar Todos"):
                        for i, d in st.session_state['data'].items():
                            if d['Estado'] == 'Pendiente':
                                st.session_state['data'][i]['Seleccionado'] = False
                                st.session_state[f"chk_{i}"] = False
                        st.rerun()
                with col_sel3:
                    if st.button("✅ Aprobar Seleccionados", type="primary"):
                        aprobar_lote()

                st.info("Revisa las sugerencias, mantén marcados los correctos y aprueba por lote usando el botón de arriba o el menú lateral.")
                
                # Lista de Pendientes
                for idx, item in datos.items():
                    if item['Estado'] == 'Pendiente':
                        with st.container(border=True):
                            if not item['Edit_Mode']:
                                col_chk, col_info, col_btn = st.columns([0.5, 5, 1.5])
                                with col_chk:
                                    st.write("") 
                                    chk = st.checkbox("Sel", value=item['Seleccionado'], key=f"chk_{idx}", label_visibility="collapsed")
                                    st.session_state['data'][idx]['Seleccionado'] = chk
                                with col_info:
                                    st.markdown(f"**Fila {idx + 1}:** `{item['Original']}`")
                                    sel = st.selectbox("Sugerencias:", item['Sugerencias'], key=f"sel_{idx}", label_visibility="collapsed")
                                with col_btn:
                                    st.write("")
                                    if st.button("✏️ Edición Manual", key=f"btn_edit_{idx}", use_container_width=True):
                                        st.session_state['data'][idx]['Edit_Mode'] = True
                                        st.rerun()
                            else:
                                st.markdown(f"#### ✏️ Editando Fila {idx + 1}: `{item['Original']}`")
                                c1, c2, c3 = st.columns(3)
                                with c1:
                                    new_dep = st.text_input("Departamento", item['Dep_Orig'], key=f"nd_{idx}")
                                with c2:
                                    new_prov = st.text_input("Provincia", item['Prov_Orig'], key=f"np_{idx}")
                                with c3:
                                    new_dist = st.text_input("Distrito", item['Dist_Orig'], key=f"ndi_{idx}")
                                    
                                cb1, cb2 = st.columns([2, 2])
                                with cb1:
                                    if st.button("🔍 Buscar nuevas coincidencias", type="primary", key=f"btn_busc_{idx}"):
                                        busqueda_nueva = f"{new_dep.strip().upper()} | {new_prov.strip().upper()} | {new_dist.strip().upper()}"
                                        opciones = process.extract(busqueda_nueva, master_choices, scorer=fuzz.WRatio, limit=5)
                                        st.session_state['data'][idx]['Sugerencias'] = [f"{op[0]} (Similitud: {op[1]:.0f}%)" for op in opciones]
                                        st.session_state['data'][idx]['Opciones_Crudas'] = [op[0] for op in opciones]
                                        st.session_state['data'][idx]['Edit_Mode'] = False
                                        # DESMARCAR al hacer búsqueda manual para obligar confirmación visual
                                        st.session_state['data'][idx]['Seleccionado'] = False
                                        st.session_state[f"chk_{idx}"] = False
                                        st.rerun()
                                with cb2:
                                    if st.button("❌ Cancelar", key=f"btn_canc_{idx}"):
                                        st.session_state['data'][idx]['Edit_Mode'] = False
                                        st.rerun()

        # Generar DataFrame final manteniendo el ORDEN EXACTO ORIGINAL
        final_data = []
        for i in range(len(datos)):
            item = datos[i]
            final_data.append({
                'Fila_Original': i + 1,
                'Departamento_Orig': item['Dep_Orig'],
                'Provincia_Orig': item['Prov_Orig'],
                'Distrito_Orig': item['Dist_Orig'],
                'Ubigeo_Oficial': item['Ubigeo_Oficial'],
                'Nombre_Oficial': item['Nombre_Oficial'],
                'Estado': item['Estado']
            })
        df_export = pd.DataFrame(final_data)

        with tab_exactos:
            st.dataframe(df_export[df_export['Estado'] == 'Aprobado'], use_container_width=True, hide_index=True)

        # Botón de Descarga Global
        st.divider()
        if pendientes_count > 0:
            st.warning(f"⚠️ Aún tienes {pendientes_count} registro(s) sin aprobar. Puedes descargar el Excel ahora, pero esos registros tendrán el Ubigeo en blanco.")
        else:
            st.success("✅ Todos los registros han sido aprobados. El Excel mantendrá el mismo orden de las filas originales.")
            
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Ubigeos_Validados')
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
