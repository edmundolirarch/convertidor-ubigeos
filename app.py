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
# Diccionario inverso para búsquedas rápidas por código
master_inv_dict = df_master.set_index('Ubigeo')[['Departamento', 'Provincia', 'Distrito']].to_dict('index')

# Función inicial de procesamiento (Pestaña 1)
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
tab1, tab2 = st.tabs(["🔄 Convertidor de Texto a Código", "🔍 Consulta Inversa (Código a Texto)"])

# ==========================================
# PESTAÑA 1: CONVERTIDOR (INDIVIDUAL Y MASIVO)
# ==========================================
with tab1:
    st.markdown("### 🔍 Consulta Individual")
    col_ind_1, col_ind_2, col_ind_3 = st.columns(3)
    with col_ind_1: dep_ind = st.text_input("Departamento", key="ind_dep_t1")
    with col_ind_2: prov_ind = st.text_input("Provincia", key="ind_prov_t1")
    with col_ind_3: dist_ind = st.text_input("Distrito", key="ind_dist_t1")
    
    if st.button("🔎 Buscar Ubigeo", type="primary", key="btn_ind_t1"):
        if dep_ind or prov_ind or dist_ind:
            busqueda_ind = f"{dep_ind.strip().upper()} | {prov_ind.strip().upper()} | {dist_ind.strip().upper()}"
            match = process.extractOne(busqueda_ind, master_choices, scorer=fuzz.WRatio)
            
            if match:
                oficial = match[0]
                similitud = match[1]
                ubigeo = ubigeo_dict[oficial]
                
                if similitud == 100:
                    st.success(f"✅ Coincidencia exacta ({similitud:.0f}%)")
                elif similitud >= 80:
                    st.warning(f"⚠️ Coincidencia aproximada ({similitud:.0f}%)")
                else:
                    st.error(f"⚠️ Coincidencia baja ({similitud:.0f}%). Revisa la ortografía.")
                
                c_res1, c_res2 = st.columns([1, 4])
                with c_res1:
                    st.markdown("**Ubigeo (Clic para copiar):**")
                    st.code(ubigeo, language="text")
                with c_res2:
                    st.info(f"**Resultado Oficial:** {oficial}")
        else:
            st.warning("Ingresa al menos un dato para realizar la búsqueda.")

    st.divider()

    st.markdown("### 🗂️ Convertidor Masivo por Lotes")
    metodo = st.radio("Selecciona el método de carga masiva:", ["Cargar archivo Excel (.xlsx)", "Copiar y Pegar desde Excel"], key="radio_t1")
    
    df_input = None
    
    if metodo == "Cargar archivo Excel (.xlsx)":
        uploaded_file = st.file_uploader("Sube tu archivo (Debe contener 3 columnas: Depto, Prov, Dist)", type=["xlsx"], key="up_t1")
        if uploaded_file is not None:
            df_input = pd.read_excel(uploaded_file, header=None) # Forzar lectura sin asumir encabezados
            
    else:
        st.info("Paso 1: Copia las 3 columnas de tu Excel (sin encabezados) y pégalas aquí:")
        txt_input = st.text_area("Datos copiados:", height=150, label_visibility="collapsed", key="txt_t1")
        
        if st.button("📥 Cargar texto pegado", type="primary", key="btn_carg_t1"):
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

        if 'df_preview' in st.session_state:
            st.markdown("**Vista previa de datos cargados:**")
            st.dataframe(st.session_state['df_preview'], height=200, use_container_width=True)
            df_input = st.session_state['df_preview']

    # Procesar Pestaña 1
    if df_input is not None and not df_input.empty:
        st.markdown("---")
        if st.button("🚀 Procesar Ubigeos Masivos", key="btn_proc_t1"):
            iniciar_procesamiento(df_input)

    # Mostrar Resultados Pestaña 1
    if 'procesado' in st.session_state and st.session_state['procesado']:
        datos = st.session_state['data']
        pendientes_count = sum(1 for v in datos.values() if v['Estado'] == 'Pendiente')
        aprobados_count = len(datos) - pendientes_count

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

        # PANEL LATERAL
        if pendientes_count > 0:
            with st.sidebar:
                st.markdown("### ⚙️ Acciones en Lote")
                st.info(f"Tienes **{pendientes_count}** registros pendientes en revisión.")
                if st.button("✅ Aprobar Seleccionados", type="primary", use_container_width=True):
                    aprobar_lote()
                st.divider()
                st.markdown("💡 *Este panel te acompaña mientras revisas la lista.*")

        st.divider()
        st.markdown("### Resultados de la Validación Masiva")
        
        tab_exactos, tab_pendientes = st.tabs([f"✅ Aprobados ({aprobados_count})", f"⚠️ Pendientes de Revisión ({pendientes_count})"])
        
        with tab_pendientes:
            if pendientes_count == 0:
                st.success("¡Excelente! No hay registros pendientes.")
            else:
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
                    if st.button("✅ Aprobar Seleccionados", type="primary", key="btn_apr_top"):
                        aprobar_lote()

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
                                    if st.button("🔍 Buscar coincidencias", type="primary", key=f"btn_busc_{idx}"):
                                        busqueda_nueva = f"{new_dep.strip().upper()} | {new_prov.strip().upper()} | {new_dist.strip().upper()}"
                                        opciones = process.extract(busqueda_nueva, master_choices, scorer=fuzz.WRatio, limit=5)
                                        st.session_state['data'][idx]['Sugerencias'] = [f"{op[0]} (Similitud: {op[1]:.0f}%)" for op in opciones]
                                        st.session_state['data'][idx]['Opciones_Crudas'] = [op[0] for op in opciones]
                                        st.session_state['data'][idx]['Edit_Mode'] = False
                                        st.session_state['data'][idx]['Seleccionado'] = False
                                        st.session_state[f"chk_{idx}"] = False
                                        st.rerun()
                                with cb2:
                                    if st.button("❌ Cancelar", key=f"btn_canc_{idx}"):
                                        st.session_state['data'][idx]['Edit_Mode'] = False
                                        st.rerun()

        final_data = []
        for i in range(len(datos)):
            item = datos[i]
            final_data.append({
                'Fila_Original': i + 1, 'Departamento_Orig': item['Dep_Orig'], 'Provincia_Orig': item['Prov_Orig'],
                'Distrito_Orig': item['Dist_Orig'], 'Ubigeo_Oficial': item['Ubigeo_Oficial'],
                'Nombre_Oficial': item['Nombre_Oficial'], 'Estado': item['Estado']
            })
        df_export = pd.DataFrame(final_data)

        with tab_exactos:
            st.dataframe(df_export[df_export['Estado'] == 'Aprobado'], use_container_width=True, hide_index=True)

        st.divider()
        if pendientes_count > 0:
            st.warning(f"⚠️ Aún tienes {pendientes_count} registro(s) sin aprobar. Puedes descargar el Excel ahora, pero esos registros tendrán el Ubigeo en blanco.")
            
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Ubigeos_Validados')
        datos_excel = output.getvalue()
        
        st.download_button(
            label="📥 Descargar Excel Consolidado", data=datos_excel,
            file_name="Ubigeos_Validados.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary", key="btn_down_t1"
        )


# ==========================================
# PESTAÑA 2: CONSULTA INVERSA (MASIVA E INDIVIDUAL)
# ==========================================
with tab2:
    st.markdown("### 🔍 Consulta Individual")
    codigo_input = st.text_input("Ingresa un solo código de 6 dígitos (Ej: 010101):", max_chars=6)
    
    if codigo_input:
        if len(codigo_input) == 6 and codigo_input.isdigit():
            if codigo_input in master_inv_dict:
                st.success("Ubigeo encontrado:")
                row_ind = master_inv_dict[codigo_input]
                df_ind = pd.DataFrame([{"Ubigeo": codigo_input, "Departamento": row_ind['Departamento'], 
                                        "Provincia": row_ind['Provincia'], "Distrito": row_ind['Distrito']}])
                st.dataframe(df_ind, hide_index=True, use_container_width=True)
            else:
                st.error("El código ingresado no existe en la base de datos.")
        else:
            st.warning("El ubigeo debe contener exactamente 6 números.")

    st.divider()
    
    st.markdown("### 🗂️ Consulta Masiva por Lotes")
    metodo_inv = st.radio("Selecciona el método de carga (Debe ser 1 sola columna con los códigos numéricos):", 
                          ["Cargar archivo Excel (.xlsx)", "Copiar y Pegar desde Excel"], key="radio_inv")

    df_input_inv = None

    if metodo_inv == "Cargar archivo Excel (.xlsx)":
        uploaded_file_inv = st.file_uploader("Sube tu archivo con códigos de Ubigeo", type=["xlsx"], key="up_inv")
        if uploaded_file_inv is not None:
            df_input_inv = pd.read_excel(uploaded_file_inv, header=None)
            
    else:
        st.info("Paso 1: Copia la columna de códigos de tu Excel (sin encabezados) y pégala aquí:")
        txt_input_inv = st.text_area("Códigos copiados:", height=150, label_visibility="collapsed", key="txt_inv")
        
        if st.button("📥 Cargar códigos pegados", type="primary", key="btn_carg_inv"):
            if txt_input_inv.strip():
                try:
                    df_temp_inv = pd.read_csv(io.StringIO(txt_input_inv), sep='\t', header=None, dtype=str)
                    st.session_state['df_preview_inv'] = df_temp_inv.iloc[:, :1] # Tomar solo la primera columna
                except Exception as e:
                    st.error("Error al leer el texto.")
            else:
                st.warning("El recuadro está vacío.")

        if 'df_preview_inv' in st.session_state:
            st.markdown("**Vista previa de códigos cargados:**")
            st.dataframe(st.session_state['df_preview_inv'], height=150, use_container_width=True)
            df_input_inv = st.session_state['df_preview_inv']

    # Procesamiento Masivo Inverso
    if df_input_inv is not None and not df_input_inv.empty:
        st.markdown("---")
        if st.button("🚀 Procesar Códigos Masivos", key="btn_proc_inv"):
            raw_codes = df_input_inv.iloc[:, 0].astype(str)
            # Limpiar: quitar ".0" si Excel lo pasó como flotante, borrar espacios y rellenar 6 ceros
            clean_codes = raw_codes.str.replace(r'\.0$', '', regex=True).str.strip().str.zfill(6)
            
            resultados_inv = []
            errores_inv = 0
            
            for i, code in enumerate(clean_codes):
                if code in master_inv_dict:
                    row_data = master_inv_dict[code]
                    resultados_inv.append({
                        "Fila": i + 1,
                        "Ubigeo_Ingresado": raw_codes.iloc[i],
                        "Ubigeo_Seis_Digitos": code,
                        "Departamento": row_data['Departamento'],
                        "Provincia": row_data['Provincia'],
                        "Distrito": row_data['Distrito']
                    })
                else:
                    errores_inv += 1
                    resultados_inv.append({
                        "Fila": i + 1,
                        "Ubigeo_Ingresado": raw_codes.iloc[i],
                        "Ubigeo_Seis_Digitos": code,
                        "Departamento": "NO ENCONTRADO",
                        "Provincia": "NO ENCONTRADO",
                        "Distrito": "NO ENCONTRADO"
                    })
                    
            st.session_state['resultados_inv'] = pd.DataFrame(resultados_inv)
            st.session_state['errores_inv'] = errores_inv

    # Mostrar Resultados Inversos Masivos
    if 'resultados_inv' in st.session_state:
        st.divider()
        st.markdown("### Resultados de la Consulta Masiva")
        
        df_res = st.session_state['resultados_inv']
        errores = st.session_state['errores_inv']
        
        if errores > 0:
            st.error(f"⚠️ Atención: Se encontraron {errores} código(s) que no existen en el catálogo oficial. Aparecerán marcados como 'NO ENCONTRADO'.")
        else:
            st.success("✅ Todos los códigos fueron encontrados correctamente. El Excel mantendrá el mismo orden de las filas originales.")
            
        st.dataframe(df_res, hide_index=True, use_container_width=True)
        
        output_inv = io.BytesIO()
        with pd.ExcelWriter(output_inv, engine='openpyxl') as writer:
            df_res.to_excel(writer, index=False, sheet_name='Consulta_Inversa_Masiva')
        datos_excel_inv = output_inv.getvalue()
        
        st.download_button(
            label="📥 Descargar Resultados Masivos (Excel)",
            data=datos_excel_inv,
            file_name="Consulta_Inversa_Masiva.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            key="btn_down_inv"
        )
