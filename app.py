import streamlit as st
import pandas as pd
import json
import requests
from datetime import date, datetime
from google import genai
from google.genai import types
from PIL import Image

# Configuração da página
st.set_page_config(
    page_title="Diário Calórico Pro",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CSS CUSTOMIZADO PARA OTIMIZAÇÃO MOBILE ---
st.markdown("""
<style>
    /* Estilização Geral e Responsividade */
    .stApp {
        background-color: #0e1117;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Redução de margens topo em dispositivos móveis */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 3rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }

    /* Cards Personalizados para Métricas */
    .metric-card {
        background: linear-gradient(135deg, #1e222d 0%, #171922 100%);
        border: 1px solid #2d3243;
        border-radius: 14px;
        padding: 14px 10px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
        margin-bottom: 8px;
    }
    .metric-title {
        font-size: 0.75rem;
        color: #8b949e;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 1.25rem;
        font-weight: 800;
        color: #f0f6fc;
    }
    .metric-sub {
        font-size: 0.7rem;
        font-weight: 600;
        margin-top: 2px;
    }

    /* Estilização das Abas Mobile */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background-color: #161b22;
        padding: 6px;
        border-radius: 12px;
        border: 1px solid #30363d;
    }
    .stTabs [data-baseweb="tab"] {
        height: 42px;
        border-radius: 8px;
        font-size: 0.85rem;
        font-weight: 600;
        color: #8b949e;
        padding: 0 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #238636 !important;
        color: #ffffff !important;
    }

    /* Botões Tocáveis e Arredondados */
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        height: 44px;
        font-weight: 700;
        font-size: 0.95rem;
        border: none;
        transition: all 0.2s ease-in-out;
    }
    .stButton>button:active {
        transform: scale(0.98);
    }

    /* Campos de Entrada Formatações */
    .stTextInput input, .stNumberInput input, .stSelectbox div {
        border-radius: 10px !important;
    }
</style>
""", unsafe_allow_html=True)

# Secrets
api_key = st.secrets.get("GEMINI_API_KEY", None)
url_sheets = st.secrets.get("URL_SHEETS", None)

# --- FUNÇÃO DE NORMALIZAÇÃO DE DATA ---
def normalizar_data(val):
    if not val:
        return None
    val_str = str(val).strip().split("T")[0]
    formatos = ["%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"]
    for fmt in formatos:
        try:
            return datetime.strptime(val_str, fmt).date()
        except ValueError:
            pass
    return None

def formatar_data_br(val):
    dt = normalizar_data(val)
    if dt:
        return dt.strftime("%d/%m/%y")
    return str(val)

def buscar_dados_planilha():
    if not url_sheets:
        return {"perfil": {}, "historico": []}
    try:
        res = requests.get(url_sheets)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return {"perfil": {}, "historico": []}

# Carrega dados remotos
dados_remotos = buscar_dados_planilha()
perfil_remoto = dados_remotos.get("perfil", {})
dados_planilha = dados_remotos.get("historico", [])

# Variáveis de Sessão
if "historico_comida" not in st.session_state:
    st.session_state.historico_comida = []
if "historico_treino" not in st.session_state:
    st.session_state.historico_treino = []
if "temp_comida" not in st.session_state:
    st.session_state.temp_comida = None
if "temp_treino" not in st.session_state:
    st.session_state.temp_treino = None

# CABEÇALHO PRINCIPAL
st.markdown("<h2 style='text-align: center; font-weight: 800; margin-bottom: 5px;'>⚡ Diário Calórico Pro</h2>", unsafe_allow_html=True)

# SELETOR DE DATA DEDICADO
col_dt1, col_dt2 = st.columns([3, 1])
data_selecionada = col_dt1.date_input("📅 Data Ativa", value=date.today(), label_visibility="collapsed")
data_sel_br = data_selecionada.strftime("%d/%m/%y")

if col_dt2.button("🔄", help="Atualizar dados"):
    st.rerun()

# SIDEBAR: PERFIL
st.sidebar.header("📊 Perfil & Parâmetros")
if not api_key:
    api_key = st.sidebar.text_input("Chave da API Google Gemini", type="password")

sexo_def = perfil_remoto.get("Sexo", "Masculino")
idx_sexo = 0 if sexo_def == "Masculino" else 1

sexo = st.sidebar.selectbox("Sexo", ["Masculino", "Feminino"], index=idx_sexo)
idade = st.sidebar.number_input("Idade", value=int(perfil_remoto.get("Idade", 30)), step=1)
peso = st.sidebar.number_input("Peso (kg)", value=float(perfil_remoto.get("Peso", 75.0)), step=0.5)
altura = st.sidebar.number_input("Altura (cm)", value=int(perfil_remoto.get("Altura", 175)), step=1)

if sexo == "Masculino":
    tmb = (10 * peso) + (6.25 * altura) - (5 * idade) + 5
else:
    tmb = (10 * peso) + (6.25 * altura) - (5 * idade) - 161

st.sidebar.subheader("Taxa Basal")
st.sidebar.write(f"**TMB (Repouso):** {int(tmb)} kcal")

meta_base_def = int(perfil_remoto.get("Meta_Base", int(tmb * 1.2)))
meta_base = st.sidebar.number_input("Meta Calórica Base (kcal)", value=meta_base_def, step=50)

if st.sidebar.button("💾 Salvar Parâmetros na Planilha"):
    if url_sheets:
        try:
            payload = {
                "action": "update_profile",
                "perfil": {"Sexo": sexo, "Idade": idade, "Peso": peso, "Altura": altura, "Meta_Base": meta_base}
            }
            res = requests.post(url_sheets, json=payload)
            if res.status_code == 200:
                st.sidebar.success("Parâmetros atualizados!")
                st.rerun()
        except Exception as e:
            st.sidebar.error(f"Erro: {e}")

# CÁLCULOS DO DIA
kcal_comida_planilha_dia = sum(
    int(item.get("Calorias_Kcal", 0)) 
    for item in dados_planilha 
    if normalizar_data(item.get("Data")) == data_selecionada and item.get("Tipo") in ["Alimentação", "Alimentacao"]
)

kcal_treino_planilha_dia = sum(
    int(item.get("Calorias_Kcal", 0)) 
    for item in dados_planilha 
    if normalizar_data(item.get("Data")) == data_selecionada and item.get("Tipo") in ["Treino", "Passos"]
)

consumido_sessao = sum(item["calorias"] for item in st.session_state.historico_comida if item["data_obj"] == data_selecionada)
gasto_treinos_sessao = sum(item["calorias"] for item in st.session_state.historico_treino if item["data_obj"] == data_selecionada)

consumido_total = kcal_comida_planilha_dia + consumido_sessao
gasto_exercicio_total = kcal_treino_planilha_dia + gasto_treinos_sessao

saldo_restante = meta_base - consumido_total
deficit_dia = (meta_base + gasto_exercicio_total) - consumido_total

# DASHBOARD EM CARDS ADAPTÁVEIS PARA MOBILE
st.markdown(f"<p style='text-align:center; color:#8b949e; font-size:0.8rem; margin-top:-5px;'>Data selecionada: <b>{data_sel_br}</b></p>", unsafe_allow_html=True)

# Linha 1: Meta Base & Gastos
r1_c1, r1_c2 = st.columns(2)
with r1_c1:
    st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">🎯 Meta Base</div>
            <div class="metric-value">{meta_base} <span style="font-size:0.8rem;">kcal</span></div>
        </div>
    """, unsafe_allow_html=True)
with r1_c2:
    st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">🏃‍♂️ Atividades</div>
            <div class="metric-value" style="color:#2ba640;">+{gasto_exercicio_total} <span style="font-size:0.8rem;">kcal</span></div>
        </div>
    """, unsafe_allow_html=True)

# Linha 2: Consumido & Falta Consumir
r2_c1, r2_c2 = st.columns(2)
with r2_c1:
    st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">🍽️ Consumido</div>
            <div class="metric-value">{consumido_total} <span style="font-size:0.8rem;">kcal</span></div>
        </div>
    """, unsafe_allow_html=True)
with r2_c2:
    cor_falta = "#e3b341" if saldo_restante >= 0 else "#f85149"
    st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">⏳ Falta Consumir</div>
            <div class="metric-value" style="color:{cor_falta};">{saldo_restante} <span style="font-size:0.8rem;">kcal</span></div>
        </div>
    """, unsafe_allow_html=True)

# Linha 3: Card Destacado para o Déficit do Dia
cor_def = "#238636" if deficit_dia >= 0 else "#da3633"
st.markdown(f"""
    <div class="metric-card" style="border: 1px solid {cor_def}; background: rgba(22, 27, 34, 0.8);">
        <div class="metric-title" style="color:#ffffff;">🔥 Déficit Real Estimado do Dia</div>
        <div class="metric-value" style="color:{cor_def}; font-size:1.4rem;">{deficit_dia} <span style="font-size:0.85rem;">kcal</span></div>
    </div>
""", unsafe_allow_html=True)

# BARRA DE PROGRESSO DINÂMICA
porcentagem = (consumido_total / meta_base * 100) if meta_base > 0 else 0
largura_barra = min(porcentagem, 100)

if porcentagem < 80:
    cor_barra = "#238636"
    mensagem_status = f"🟢 Consumo dentro da meta ({porcentagem:.1f}%)"
elif porcentagem <= 100:
    cor_barra = "#d29922"
    mensagem_status = f"⚠️ Atenção! Quase atingindo a meta ({porcentagem:.1f}%)"
else:
    cor_barra = "#da3633"
    mensagem_status = f"🚨 META BASE EXCEDIDA! ({porcentagem:.1f}%)"

st.markdown(f"""
    <div style="background-color: #21262d; border-radius: 10px; padding: 3px; margin-top: 8px;">
        <div style="background-color: {cor_barra}; width: {largura_barra}%; height: 18px; border-radius: 7px; text-align: center; color: white; font-weight: 700; font-size: 11px; line-height: 18px;">
            {porcentagem:.0f}%
        </div>
    </div>
    <p style="text-align: center; font-weight: 700; font-size:0.85rem; margin-top: 5px; color: {cor_barra};">{mensagem_status}</p>
""", unsafe_allow_html=True)

st.markdown("<hr style='margin: 10px 0; border-color: #30363d;'>", unsafe_allow_html=True)

# ABAS DO NAVEGADOR PRINCIPAL
tab_comida, tab_atividade, tab_consulta = st.tabs([
    "🍽️ Comida", 
    "🏃‍♂️ Exercícios",
    "📊 Histórico"
])

# ---------------------------------------------------------
# ABA 1: REFEIÇÕES
# ---------------------------------------------------------
with tab_comida:
    sub_foto, sub_texto, sub_audio = st.tabs(["📸 Foto", "✍️ Texto", "🎙️ Áudio"])
    
    with sub_foto:
        foto = st.file_uploader("Enviar foto do prato", type=["jpg", "jpeg", "png"], key="upload_foto")
        obs_foto = st.text_input("Observação para a IA (opcional)", placeholder="Ex: Bananada sem açúcar, frango na air fryer")
        
        if foto and api_key:
            image = Image.open(foto)
            st.image(image, caption="Foto enviada", use_container_width=True)
            if st.button("🔍 Analisar Foto com IA"):
                try:
                    client = genai.Client(api_key=api_key)
                    prompt = f"Analise esta foto de comida. Considere a obs: '{obs_foto}'. Estime a refeição e calorias. Responda ESTRITAMENTE em JSON: {{\"alimento\": \"string\", \"calorias\": integer}}"
                    response = client.models.generate_content(model='gemini-3.6-flash', contents=[image, prompt])
                    texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
                    st.session_state.temp_comida = json.loads(texto_limpo)
                    st.success("Análise concluída!")
                except Exception as e:
                    st.error(f"Erro: {e}")

    with sub_texto:
        texto_refeicao = st.text_area("Descreva a refeição", placeholder="Ex: 1 bife de frango grelhado")
        if st.button("🧮 Calcular por Texto") and texto_refeicao and api_key:
            try:
                client = genai.Client(api_key=api_key)
                prompt = f"O usuário comeu: '{texto_refeicao}'. Estime a refeição e calorias. Responda ESTRITAMENTE em JSON: {{\"alimento\": \"string\", \"calorias\": integer}}"
                response = client.models.generate_content(model='gemini-3.6-flash', contents=[prompt])
                texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
                st.session_state.temp_comida = json.loads(texto_limpo)
                st.success("Calculado!")
            except Exception as e:
                st.error(f"Erro: {e}")

    with sub_audio:
        audio_comida = st.audio_input("🎙️ Gravador de Áudio")
        if st.button("🎙️ Analisar Áudio da Comida") and audio_comida and api_key:
            try:
                client = genai.Client(api_key=api_key)
                audio_bytes = audio_comida.read()
                prompt = "Ouça o áudio da refeição e estime o alimento e calorias. Responda ESTRITAMENTE em JSON: {\"alimento\": \"string\", \"calorias\": integer}"
                contents = [prompt, types.Part.from_bytes(data=audio_bytes, mime_type=audio_comida.type)]
                response = client.models.generate_content(model='gemini-3.6-flash', contents=contents)
                texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
                st.session_state.temp_comida = json.loads(texto_limpo)
                st.success("Áudio processado!")
            except Exception as e:
                st.error(f"Erro: {e}")

    if st.session_state.temp_comida:
        st.markdown("---")
        st.markdown("##### ✏️ Confirmar / Retificar Refeição")
        with st.form("form_confirmar_comida"):
            nome_editado = st.text_input("Descrição", value=st.session_state.temp_comida.get("alimento", ""))
            calorias_editadas = st.number_input("Calorias (kcal)", value=int(st.session_state.temp_comida.get("calorias", 0)), step=10)
            if st.form_submit_button("✅ Adicionar à Fila do Dia"):
                st.session_state.historico_comida.append({
                    "data_str": data_sel_br, "data_obj": data_selecionada,
                    "alimento": nome_editado, "calorias": calorias_editadas
                })
                st.session_state.temp_comida = None
                st.success("Adicionado!")
                st.rerun()

# ---------------------------------------------------------
# ABA 2: EXERCÍCIOS & PASSOS
# ---------------------------------------------------------
with tab_atividade:
    st.markdown("##### 🏃‍♂️ Passos do Dia")
    passos = st.number_input("Número de Passos", value=0, step=500, label_visibility="collapsed")
    calorias_passos = int(passos * 0.04 * (peso / 70.0))
    st.caption(f"Gasto dos passos: **~{calorias_passos} kcal**")
    
    if st.button("➕ Adicionar Passos"):
        if calorias_passos > 0:
            st.session_state.historico_treino.append({
                "data_str": data_sel_br, "data_obj": data_selecionada,
                "atividade": f"Caminhada / Passos ({passos} passos)", "calorias": calorias_passos
            })
            st.success("Passos adicionados!")
            st.rerun()
            
    st.markdown("---")
    st.markdown("##### 🏋️‍♂️ Outros Exercícios")
    audio_input = st.audio_input("🎙️ Gravador de Áudio do Treino")
    texto_treino = st.text_input("✍️ Digite o treino", placeholder="Ex: 30 min de bicicleta")
    
    if st.button("🔥 Calcular Gasto do Treino") and api_key:
        try:
            client = genai.Client(api_key=api_key)
            prompt = f"O usuário tem {peso}kg. Analise a atividade e estime o gasto energético. Responda ESTRITAMENTE em JSON: {{\"atividade\": \"string\", \"calorias\": integer}}"
            contents = [prompt]
            if audio_input:
                contents.append(types.Part.from_bytes(data=audio_input.read(), mime_type=audio_input.type))
            elif texto_treino:
                contents.append(f"Texto do treino: {texto_treino}")
            
            response = client.models.generate_content(model='gemini-3.6-flash', contents=contents)
            texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
            st.session_state.temp_treino = json.loads(texto_limpo)
            st.success("Gasto estimado!")
        except Exception as e:
            st.error(f"Erro: {e}")
            
    if st.session_state.temp_treino:
        st.markdown("##### ✏️ Confirmar Treino")
        with st.form("form_confirmar_treino"):
            treino_editado = st.text_input("Atividade", value=st.session_state.temp_treino.get("atividade", ""))
            kcal_editada = st.number_input("Calorias (kcal)", value=int(st.session_state.temp_treino.get("calorias", 0)), step=10)
            if st.form_submit_button("✅ Adicionar à Fila"):
                st.session_state.historico_treino.append({
                    "data_str": data_sel_br, "data_obj": data_selecionada,
                    "atividade": treino_editado, "calorias": kcal_editada
                })
                st.session_state.temp_treino = None
                st.success("Treino adicionado!")
                st.rerun()

# ---------------------------------------------------------
# ABA 3: HISTÓRICO E EXCLUSÃO
# ---------------------------------------------------------
with tab_consulta:
    st.markdown("##### 📈 Histórico na Planilha")
    
    if dados_planilha:
        df_planilha = pd.DataFrame(dados_planilha)
        df_planilha["Data_Formatada"] = df_planilha["Data"].apply(formatar_data_br)
        
        termo_busca = st.text_input("🔍 Pesquisar no Histórico", placeholder="Ex: Frango, Bicicleta, 01/08/26")
        
        df_filtrado = df_planilha.copy()
        if termo_busca:
            mask = (
                df_filtrado["Descricao"].astype(str).str.contains(termo_busca, case=False, na=False) |
                df_filtrado["Tipo"].astype(str).str.contains(termo_busca, case=False, na=False) |
                df_filtrado["Data_Formatada"].astype(str).str.contains(termo_busca, case=False, na=False)
            )
            df_filtrado = df_filtrado[mask]
        
        df_exibir = df_filtrado[["Data_Formatada", "Tipo", "Descricao", "Calorias_Kcal"]].copy()
        df_exibir.columns = ["Data", "Tipo", "Descrição / Item", "kcal"]
        st.dataframe(df_exibir, use_container_width=True)
        
        st.markdown("---")
        st.markdown("##### 🗑️ Apagar Vários Registros")
        
        opcoes_deletar = {
            f"L{item['Linha']}: [{formatar_data_br(item['Data'])}] {item['Descricao']} ({item['Calorias_Kcal']} kcal)": item['Linha']
            for item in df_filtrado.to_dict(orient="records")
        }
        
        itens_selecionados = st.multiselect(
            "Selecione itens para apagar:",
            options=list(opcoes_deletar.keys())
        )
        
        if st.button("❌ Apagar Selecionados"):
            if itens_selecionados:
                linhas_para_apagar = [opcoes_deletar[item] for item in itens_selecionados]
                try:
                    res = requests.post(url_sheets, json={"action": "delete_multiple", "rowIndexes": linhas_para_apagar})
                    if res.status_code == 200:
                        st.success(f"{len(linhas_para_apagar)} item(s) apagado(s)!")
                        st.rerun()
                    else:
                        st.error("Erro ao apagar.")
                except Exception as e:
                    st.error(f"Erro: {e}")
    else:
        st.info("Planilha vazia.")

# ---------------------------------------------------------
# REGISTROS PENDENTES A SALVAR
# ---------------------------------------------------------
st.markdown("<hr style='margin: 15px 0; border-color: #30363d;'>", unsafe_allow_html=True)
st.markdown(f"##### 📋 Fila Pendente para Salvar ({data_sel_br})")

col_t1, col_t2 = st.columns(2)

with col_t1:
    st.caption("**Refeições**")
    if st.session_state.historico_comida:
        df_pend_comida = pd.DataFrame(st.session_state.historico_comida)[["alimento", "calorias"]]
        df_pend_comida.columns = ["Item", "kcal"]
        st.dataframe(df_pend_comida, use_container_width=True)
        if st.button("🗑️ Limpar Comidas"):
            st.session_state.historico_comida = []
            st.rerun()
    else:
        st.caption("Nenhuma comida.")

with col_t2:
    st.caption("**Treinos**")
    if st.session_state.historico_treino:
        df_pend_treino = pd.DataFrame(st.session_state.historico_treino)[["atividade", "calorias"]]
        df_pend_treino.columns = ["Item", "kcal"]
        st.dataframe(df_pend_treino, use_container_width=True)
        if st.button("🗑️ Limpar Treinos"):
            st.session_state.historico_treino = []
            st.rerun()
    else:
        st.caption("Nenhum treino.")

st.markdown("<br>", unsafe_allow_html=True)
if st.button(f"💾 ENVIAR REGISTROS PARA GOOGLE SHEETS"):
    if not url_sheets:
        st.error("Configure 'URL_SHEETS' nos Secrets.")
    else:
        try:
            dados_salvar = []
            for c in st.session_state.historico_comida:
                dados_salvar.append({"Data": c["data_str"], "Tipo": "Alimentação", "Descricao": c["alimento"], "Calorias_Kcal": c["calorias"]})
            for t in st.session_state.historico_treino:
                dados_salvar.append({"Data": t["data_str"], "Tipo": "Treino", "Descricao": t["atividade"], "Calorias_Kcal": t["calorias"]})
                
            if dados_salvar:
                response = requests.post(url_sheets, json={"action": "add", "data": dados_salvar})
                if response.status_code == 200:
                    st.balloons()
                    st.success("Salvo no Google Sheets!")
                    st.session_state.historico_comida = []
                    st.session_state.historico_treino = []
                    st.rerun()
            else:
                st.warning("Nenhum registro pendente.")
        except Exception as e:
            st.error(f"Erro: {e}")
