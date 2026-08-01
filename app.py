import streamlit as st
import pandas as pd
import json
import requests
from datetime import date, datetime
from google import genai
from google.genai import types
from PIL import Image

# Configuração da página
st.set_page_config(page_title="Diário Calórico Pro", page_icon="⚡", layout="centered")

# Secrets
api_key = st.secrets.get("GEMINI_API_KEY", None)
url_sheets = st.secrets.get("URL_SHEETS", None)

# --- FUNÇÃO DE NORMALIZAÇÃO DE DATA (Retorna Objeto Date) ---
def normalizar_data(val):
    if not val:
        return None
    val_str = str(val).strip().split("T")[0]  # Remove horário se for formato ISO
    formatos = ["%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"]
    for fmt in formatos:
        try:
            return datetime.strptime(val_str, fmt).date()
        except ValueError:
            pass
    return None

# --- FUNÇÃO PARA FORMATAR PARA EXIBIÇÃO DD/MM/AA ---
def formatar_data_br(val):
    dt = normalizar_data(val)
    if dt:
        return dt.strftime("%d/%m/%y")
    return str(val)

# --- FUNÇÃO PARA BUSCAR DADOS DA PLANILHA ---
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

# Carrega dados do Google Sheets
dados_remotos = buscar_dados_planilha()
perfil_remoto = dados_remotos.get("perfil", {})
dados_planilha = dados_remotos.get("historico", [])

# Inicialização de Variáveis de Sessão
if "historico_comida" not in st.session_state:
    st.session_state.historico_comida = []
if "historico_treino" not in st.session_state:
    st.session_state.historico_treino = []
if "temp_comida" not in st.session_state:
    st.session_state.temp_comida = None
if "temp_treino" not in st.session_state:
    st.session_state.temp_treino = None

# CORPO PRINCIPAL
st.title("⚡ Diário Calórico & Fitness")

# --- SELETOR DE DATA ---
col_dt1, col_dt2 = st.columns([2, 1])
data_selecionada = col_dt1.date_input("📅 Data de Registro / Visualização", value=date.today())
data_sel_br = data_selecionada.strftime("%d/%m/%y")

if col_dt2.button("🔄 Recarregar Dados"):
    st.rerun()

# --- SIDEBAR: PERFIL & PARÂMETROS ---
st.sidebar.header("📊 Perfil & Parâmetros")

if not api_key:
    api_key = st.sidebar.text_input("Chave da API Google Gemini", type="password")

sexo_def = perfil_remoto.get("Sexo", "Masculino")
idx_sexo = 0 if sexo_def == "Masculino" else 1

sexo = st.sidebar.selectbox("Sexo", ["Masculino", "Feminino"], index=idx_sexo)
idade = st.sidebar.number_input("Idade", value=int(perfil_remoto.get("Idade", 30)), step=1)
peso = st.sidebar.number_input("Peso (kg)", value=float(perfil_remoto.get("Peso", 75.0)), step=0.5)
altura = st.sidebar.number_input("Altura (cm)", value=int(perfil_remoto.get("Altura", 175)), step=1)

# Cálculo TMB
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
                "perfil": {
                    "Sexo": sexo,
                    "Idade": idade,
                    "Peso": peso,
                    "Altura": altura,
                    "Meta_Base": meta_base
                }
            }
            res = requests.post(url_sheets, json=payload)
            if res.status_code == 200:
                st.sidebar.success("Parâmetros atualizados na planilha!")
                st.rerun()
            else:
                st.sidebar.error("Erro ao salvar perfil.")
        except Exception as e:
            st.sidebar.error(f"Erro: {e}")

# --- CÁLCULO DE CALORIAS FILTRADAS PELA DATA SELECIONADA ---
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

# CÁLCULO DO DÉFICIT PURAMENTE PELA META BASE (Sem somar exercícios no teto de comida)
saldo_restante = meta_base - consumido_total

# PAINEL DE INDICADORES DO DIA SELECIONADO
st.caption(f"Exibindo dados para o dia: **{data_sel_br}**")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Meta Base", f"{meta_base} kcal")
col2.metric("Gasto Atividades", f"+{gasto_exercicio_total} kcal")
col3.metric("Consumido", f"{consumido_total} kcal")
col4.metric("Falta Consumir", f"{saldo_restante} kcal", delta_color="inverse")

# --- BARRA DE PROGRESSO CALCULADA APENAS SOBRE A META BASE ---
porcentagem = (consumido_total / meta_base * 100) if meta_base > 0 else 0
largura_barra = min(porcentagem, 100)

if porcentagem < 80:
    cor_barra = "#28a745" # Verde
    mensagem_status = f"🟢 Consumo dentro da meta base ({porcentagem:.1f}%)"
elif porcentagem <= 100:
    cor_barra = "#ffc107" # Amarelo
    mensagem_status = f"⚠️ ATENÇÃO! Quase atingindo a meta base ({porcentagem:.1f}%)"
else:
    cor_barra = "#dc3545" # Vermelho
    mensagem_status = f"🚨 META BASE EXCEDIDA! ({porcentagem:.1f}%)"

st.markdown(f"""
    <div style="background-color: #262730; border-radius: 10px; padding: 4px; margin-top: 10px;">
        <div style="background-color: {cor_barra}; width: {largura_barra}%; height: 22px; border-radius: 8px; text-align: center; color: white; font-weight: bold; font-size: 13px; line-height: 22px;">
            {porcentagem:.0f}%
        </div>
    </div>
    <p style="text-align: center; font-weight: bold; margin-top: 6px; color: {cor_barra};">{mensagem_status}</p>
""", unsafe_allow_html=True)

st.markdown("---")

# ABAS DE NAVEGAÇÃO
tab_comida, tab_atividade, tab_consulta = st.tabs([
    "🍽️ Registrar Comida (Foto / Texto / Áudio)", 
    "🏃‍♂️/🎙️ Exercícios & Passos",
    "📊 Histórico & Gerenciar Registros"
])

# ---------------------------------------------------------
# ABA 1: REFEIÇÃO (FOTO, TEXTO OU ÁUDIO)
# ---------------------------------------------------------
with tab_comida:
    sub_foto, sub_texto, sub_audio = st.tabs(["📸 Foto", "✍️ Texto", "🎙️ Áudio"])
    
    # 📸 Sub-aba Foto
    with sub_foto:
        foto = st.file_uploader("Tire uma foto do prato", type=["jpg", "jpeg", "png"], key="upload_foto")
        obs_foto = st.text_input("Observação / Detalhes para a IA (opcional)", placeholder="Ex: Bananada sem açúcar, frango na air fryer sem óleo")
        
        if foto and api_key:
            image = Image.open(foto)
            st.image(image, caption="Foto enviada", use_container_width=True)
            if st.button("🔍 Analisar Foto com IA"):
                try:
                    client = genai.Client(api_key=api_key)
                    prompt = (
                        f"Analise esta foto de comida. Considere também a seguinte observação informada pelo usuário: '{obs_foto}'. "
                        "Estime o nome resumido da refeição e as calorias totais. "
                        "Responda ESTRITAMENTE em JSON com o formato: {\"alimento\": \"string\", \"calorias\": integer}"
                    )
                    response = client.models.generate_content(model='gemini-3.6-flash', contents=[image, prompt])
                    texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
                    st.session_state.temp_comida = json.loads(texto_limpo)
                    st.success("Análise concluída! Confirme abaixo.")
                except Exception as e:
                    st.error(f"Erro ao analisar foto: {e}")

    # ✍️ Sub-aba Texto
    with sub_texto:
        texto_refeicao = st.text_area("Descreva o que você comeu", placeholder="Ex: 1 bife de frango grelhado do tamanho da palma da mão")
        if st.button("🧮 Calcular Calorias por Texto") and texto_refeicao and api_key:
            try:
                client = genai.Client(api_key=api_key)
                prompt = f"O usuário comeu: '{texto_refeicao}'. Estime o nome resumido e as calorias. Responda ESTRITAMENTE em JSON: {{\"alimento\": \"string\", \"calorias\": integer}}"
                response = client.models.generate_content(model='gemini-3.6-flash', contents=[prompt])
                texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
                st.session_state.temp_comida = json.loads(texto_limpo)
                st.success("Calculado! Confirme abaixo.")
            except Exception as e:
                st.error(f"Erro ao estimar: {e}")

    # 🎙️ Sub-aba Áudio
    with sub_audio:
        audio_comida = st.audio_input("🎙️ Fale o que você comeu")
        if st.button("🎙️ Analisar Áudio da Comida") and audio_comida and api_key:
            try:
                client = genai.Client(api_key=api_key)
                audio_bytes = audio_comida.read()
                prompt = "Ouça o áudio onde o usuário descreve a refeição. Estime o nome do alimento e o total de calorias. Responda ESTRITAMENTE em JSON: {\"alimento\": \"string\", \"calorias\": integer}"
                contents = [prompt, types.Part.from_bytes(data=audio_bytes, mime_type=audio_comida.type)]
                response = client.models.generate_content(model='gemini-3.6-flash', contents=contents)
                texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
                st.session_state.temp_comida = json.loads(texto_limpo)
                st.success("Áudio processado! Confirme abaixo.")
            except Exception as e:
                st.error(f"Erro ao processar áudio: {e}")

    # Form de Confirmação Unificado
    if st.session_state.temp_comida:
        st.markdown("---")
        st.markdown("### ✏️ Confirmar / Retificar Refeição")
        with st.form("form_confirmar_comida"):
            nome_editado = st.text_input("Descrição", value=st.session_state.temp_comida.get("alimento", ""))
            calorias_editadas = st.number_input("Calorias (kcal)", value=int(st.session_state.temp_comida.get("calorias", 0)), step=10)
            if st.form_submit_button("✅ Adicionar à Fila do Dia"):
                st.session_state.historico_comida.append({
                    "data_str": data_sel_br,
                    "data_obj": data_selecionada,
                    "alimento": nome_editado,
                    "calorias": calorias_editadas
                })
                st.session_state.temp_comida = None
                st.success(f"Adicionado para o dia {data_sel_br}!")
                st.rerun()

# ---------------------------------------------------------
# ABA 2: EXERCÍCIOS & PASSOS
# ---------------------------------------------------------
with tab_atividade:
    st.subheader("🏃‍♂️ Contador de Passos")
    col_p1, col_p2 = st.columns([2, 1])
    passos = col_p1.number_input("Número de Passos do Dia", value=0, step=500)
    calorias_passos = int(passos * 0.04 * (peso / 70.0))
    col_p2.metric("Gasto Estimado", f"{calorias_passos} kcal")
    
    if col_p2.button("➕ Adicionar Passos"):
        if calorias_passos > 0:
            st.session_state.historico_treino.append({
                "data_str": data_sel_br,
                "data_obj": data_selecionada,
                "atividade": f"Caminhada / Passos ({passos} passos)",
                "calorias": calorias_passos
            })
            st.success("Passos adicionados à fila!")
            st.rerun()
            
    st.markdown("---")
    st.subheader("🏋️‍♂️ Exercícios (Áudio ou Texto)")
    audio_input = st.audio_input("🎙️ Gravador de Áudio do Treino")
    texto_treino = st.text_input("✍️ Ou digite seu treino aqui", placeholder="Ex: 30 minutos de bicicleta ergométrica")
    
    if st.button("🔥 Calcular Gasto do Treino") and api_key:
        try:
            client = genai.Client(api_key=api_key)
            prompt = f"O usuário tem {peso}kg. Analise a atividade e estime o gasto energético em kcal. Responda ESTRITAMENTE em JSON: {{\"atividade\": \"string\", \"calorias\": integer}}"
            contents = [prompt]
            if audio_input:
                contents.append(types.Part.from_bytes(data=audio_input.read(), mime_type=audio_input.type))
            elif texto_treino:
                contents.append(f"Texto do treino: {texto_treino}")
            
            response = client.models.generate_content(model='gemini-3.6-flash', contents=contents)
            texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
            st.session_state.temp_treino = json.loads(texto_limpo)
            st.success("Gasto estimado com sucesso!")
        except Exception as e:
            st.error(f"Erro ao analisar treino: {e}")
            
    if st.session_state.temp_treino:
        st.markdown("### ✏️ Confirmação do Treino")
        with st.form("form_confirmar_treino"):
            treino_editado = st.text_input("Atividade", value=st.session_state.temp_treino.get("atividade", ""))
            kcal_editada = st.number_input("Calorias Queimadas (kcal)", value=int(st.session_state.temp_treino.get("calorias", 0)), step=10)
            if st.form_submit_button("✅ Adicionar à Fila do Dia"):
                st.session_state.historico_treino.append({
                    "data_str": data_sel_br,
                    "data_obj": data_selecionada,
                    "atividade": treino_editado,
                    "calorias": kcal_editada
                })
                st.session_state.temp_treino = None
                st.success(f"Treino adicionado para {data_sel_br}!")
                st.rerun()

# ---------------------------------------------------------
# ABA 3: HISTÓRICO E EXCLUSÃO (DATAS FORMATADAS DD/MM/AA)
# ---------------------------------------------------------
with tab_consulta:
    st.subheader("📈 Registros Salvos na Planilha")
    
    if dados_planilha:
        df_planilha = pd.DataFrame(dados_planilha)
        
        # Formata explicitamente a coluna de datas para o formato limpo DD/MM/AA
        df_planilha["Data_Formatada"] = df_planilha["Data"].apply(formatar_data_br)
        
        df_exibir = df_planilha[["Data_Formatada", "Tipo", "Descricao", "Calorias_Kcal"]]
        df_exibir.columns = ["Data", "Tipo", "Descrição / Item", "Calorias (kcal)"]
        
        st.dataframe(df_exibir, use_container_width=True)
        
        st.markdown("---")
        st.subheader("🗑️ Apagar Registro Salvo")
        
        opcoes_deletar = {
            f"Linha {item['Linha']}: [{formatar_data_br(item['Data'])}] {item['Tipo']} - {item['Descricao']} ({item['Calorias_Kcal']} kcal)": item['Linha']
            for item in dados_planilha
        }
        
        item_selecionado = st.selectbox("Selecione o item para apagar permanentemente:", list(opcoes_deletar.keys()))
        
        if st.button("❌ Apagar Registro Selecionado"):
            linha_para_apagar = opcoes_deletar[item_selecionado]
            try:
                res = requests.post(url_sheets, json={"action": "delete", "rowIndex": linha_para_apagar})
                if res.status_code == 200:
                    st.success("Registro apagado com sucesso da Planilha!")
                    st.rerun()
                else:
                    st.error("Erro ao apagar registro.")
            except Exception as e:
                st.error(f"Erro de conexão: {e}")
    else:
        st.info("Nenhum registro encontrado na planilha.")

# ---------------------------------------------------------
# RESUMO DA SESSÃO ATUAL (REGISTROS PENDENTES)
# ---------------------------------------------------------
st.markdown("---")
st.subheader(f"📋 Registros Pendentes a Salvar ({data_sel_br})")
col_t1, col_t2 = st.columns(2)

with col_t1:
    st.markdown("**Alimentação**")
    if st.session_state.historico_comida:
        for idx, item in enumerate(st.session_state.historico_comida):
            col_a, col_b = st.columns([3, 1])
            col_a.write(f"• [{item['data_str']}] {item['alimento']} ({item['calorias']} kcal)")
            if col_b.button("🗑️", key=f"del_c_{idx}"):
                st.session_state.historico_comida.pop(idx)
                st.rerun()

with col_t2:
    st.markdown("**Treinos / Passos**")
    if st.session_state.historico_treino:
        for idx, item in enumerate(st.session_state.historico_treino):
            col_a, col_b = st.columns([3, 1])
            col_a.write(f"• [{item['data_str']}] {item['atividade']} ({item['calorias']} kcal)")
            if col_b.button("🗑️", key=f"del_t_{idx}"):
                st.session_state.historico_treino.pop(idx)
                st.rerun()

if st.button(f"💾 Enviar Fila ({data_sel_br}) para o Google Sheets"):
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
                    st.success("Salvo com sucesso na Planilha!")
                    st.session_state.historico_comida = []
                    st.session_state.historico_treino = []
                    st.rerun()
            else:
                st.warning("Nenhum registro pendente.")
        except Exception as e:
            st.error(f"Erro: {e}")
