import streamlit as st
import pandas as pd
import json
import requests
from datetime import date
from google import genai
from google.genai import types
from PIL import Image

# Configuração da página
st.set_page_config(page_title="Diário Calórico Pro", page_icon="⚡", layout="centered")

# Secrets
api_key = st.secrets.get("GEMINI_API_KEY", None)
url_sheets = st.secrets.get("URL_SHEETS", None)

# --- FUNÇÃO PARA BUSCAR DADOS DA PLANILHA ---
def buscar_dados_planilha():
    if not url_sheets:
        return []
    try:
        res = requests.get(url_sheets)
        if res.status_code == 200:
            dados = res.json()
            # Limpa o formato de data ISO (ex: "2026-08-01T03:00:00.000Z" -> "2026-08-01")
            for item in dados:
                if "Data" in item and item["Data"]:
                    item["Data"] = str(item["Data"]).split("T")[0]
            return dados
    except Exception:
        pass
    return []

# Inicialização de Variáveis de Sessão
if "historico_comida" not in st.session_state:
    st.session_state.historico_comida = []
if "historico_treino" not in st.session_state:
    st.session_state.historico_treino = []
if "temp_comida" not in st.session_state:
    st.session_state.temp_comida = None
if "temp_treino" not in st.session_state:
    st.session_state.temp_treino = None

# Busca os dados da planilha
dados_planilha = buscar_dados_planilha()
hoje_str = str(date.today())

# --- CÁLCULO DE CALORIAS SALVAS HOJE NA PLANILHA ---
kcal_comida_planilha_hoje = sum(
    int(item.get("Calorias_Kcal", 0)) 
    for item in dados_planilha 
    if item.get("Data") == hoje_str and item.get("Tipo") in ["Alimentação", "Alimentacao"]
)

kcal_treino_planilha_hoje = sum(
    int(item.get("Calorias_Kcal", 0)) 
    for item in dados_planilha 
    if item.get("Data") == hoje_str and item.get("Tipo") == "Treino"
)

# --- SIDEBAR: PERFIL & METAS ---
st.sidebar.header("📊 Perfil & Parâmetros")

if not api_key:
    api_key = st.sidebar.text_input("Chave da API Google Gemini", type="password")

sexo = st.sidebar.selectbox("Sexo", ["Masculino", "Feminino"])
idade = st.sidebar.number_input("Idade", value=30, step=1)
peso = st.sidebar.number_input("Peso (kg)", value=75.0, step=0.5)
altura = st.sidebar.number_input("Altura (cm)", value=175, step=1)

# Cálculo TMB
if sexo == "Masculino":
    tmb = (10 * peso) + (6.25 * altura) - (5 * idade) + 5
else:
    tmb = (10 * peso) + (6.25 * altura) - (5 * idade) - 161

st.sidebar.subheader("Taxa Basal")
st.sidebar.write(f"**TMB (Repouso):** {int(tmb)} kcal")

meta_base = st.sidebar.number_input("Meta Calórica Base (kcal)", value=int(tmb * 1.2), step=50)

# --- PASSOS DO DIA ---
st.sidebar.markdown("---")
st.sidebar.subheader("🏃‍♂️ Passos do Dia")
passos = st.sidebar.number_input("Número de Passos", value=0, step=500)
calorias_passos = int(passos * 0.04 * (peso / 70.0))
st.sidebar.caption(f"Gasto dos passos: ~{calorias_passos} kcal")

# CÁLCULOS TOTAIS DO DIA (Planilha + Sessão Atual)
consumido_sessao = sum(item["calorias"] for item in st.session_state.historico_comida)
gasto_treinos_sessao = sum(item["calorias"] for item in st.session_state.historico_treino)

consumido_total = kcal_comida_planilha_hoje + consumido_sessao
gasto_exercicio_total = kcal_treino_planilha_hoje + gasto_treinos_sessao + calorias_passos

meta_ajustada = meta_base + gasto_exercicio_total
saldo_restante = meta_ajustada - consumido_total

# CORPO PRINCIPAL
st.title("⚡ Diário Calórico & Fitness")

# Painel de Indicadores do Dia
col1, col2, col3, col4 = st.columns(4)
col1.metric("Meta Base", f"{meta_base} kcal")
col2.metric("Gasto Atividades", f"+{gasto_exercicio_total} kcal")
col3.metric("Consumido Hoje", f"{consumido_total} kcal")
col4.metric("Falta Consumir", f"{saldo_restante} kcal", delta_color="inverse")

st.progress(min(max(consumido_total / meta_ajustada if meta_ajustada > 0 else 0.0, 0.0), 1.0))
st.markdown("---")

# ABAS DE NAVEGAÇÃO
tab_foto, tab_texto_comida, tab_atividade, tab_consulta = st.tabs([
    "📸 Foto de Comida", 
    "✍️ Comida por Texto", 
    "🎙️/✍️ Exercício",
    "📊 Histórico na Planilha"
])

# ---------------------------------------------------------
# ABA 1: FOTO DE COMIDA
# ---------------------------------------------------------
with tab_foto:
    foto = st.file_uploader("Tire uma foto ou envie do celular", type=["jpg", "jpeg", "png"])
    
    if foto and api_key:
        image = Image.open(foto)
        st.image(image, caption="Foto enviada", use_container_width=True)
        
        if st.button("🔍 Analisar Imagem com IA"):
            try:
                client = genai.Client(api_key=api_key)
                prompt = (
                    "Analise esta foto de comida. Estime o nome resumido da refeição e a quantidade "
                    "total de calorias. Responda ESTRITAMENTE em formato JSON com duas chaves: "
                    "'alimento' (string) e 'calorias' (integer)."
                )
                response = client.models.generate_content(
                    model='gemini-3.6-flash',
                    contents=[image, prompt]
                )
                
                texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
                dados = json.loads(texto_limpo)
                st.session_state.temp_comida = dados
                st.success("Análise concluída! Verifique abaixo antes de salvar.")
            except Exception as e:
                st.error(f"Erro ao analisar foto: {e}")

    if st.session_state.temp_comida:
        st.markdown("### ✏️ Confirmação do Registro")
        with st.form("form_confirmar_foto"):
            nome_editado = st.text_input("Descrição da Comida", value=st.session_state.temp_comida.get("alimento", ""))
            calorias_editadas = st.number_input("Calorias Estimadas (kcal)", value=int(st.session_state.temp_comida.get("calorias", 0)), step=10)
            
            if st.form_submit_button("✅ Confirmar e Adicionar"):
                st.session_state.historico_comida.append({
                    "data": hoje_str,
                    "alimento": nome_editado,
                    "calorias": calorias_editadas
                })
                st.session_state.temp_comida = None
                st.success("Refeição adicionada à fila do dia!")
                st.rerun()

# ---------------------------------------------------------
# ABA 2: COMIDA POR TEXTO
# ---------------------------------------------------------
with tab_texto_comida:
    st.write("Descreva o que você comeu em linguagem natural.")
    texto_refeicao = st.text_area("O que você comeu?", placeholder="Ex: 1 bife de frango grelhado do tamanho da palma da mão")
    
    if st.button("🧮 Calcular Calorias por Texto") and texto_refeicao and api_key:
        try:
            client = genai.Client(api_key=api_key)
            prompt = (
                f"O usuário descreveu a seguinte refeição: '{texto_refeicao}'. "
                "Estime o nome formatado e a quantidade total de calorias (kcal). "
                "Responda ESTRITAMENTE em formato JSON com as chaves 'alimento' (string) e 'calorias' (integer)."
            )
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=[prompt]
            )
            
            texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
            dados = json.loads(texto_limpo)
            st.session_state.temp_comida = dados
            st.success("Estimativa calculada! Confirme abaixo.")
        except Exception as e:
            st.error(f"Erro ao estimar refeição: {e}")

# ---------------------------------------------------------
# ABA 3: EXERCÍCIO
# ---------------------------------------------------------
with tab_atividade:
    st.write("Grave um áudio ou descreva seu treino.")
    
    audio_input = st.audio_input("🎙️ Gravador de Áudio")
    texto_treino = st.text_input("✍️ Ou digite seu treino aqui", placeholder="Ex: 40 minutos de corrida na esteira")
    
    if st.button("🔥 Calcular Gasto do Treino") and api_key:
        try:
            client = genai.Client(api_key=api_key)
            prompt = (
                f"O usuário tem {peso}kg. Analise a atividade física informada e estime o gasto energético em kcal. "
                "Responda ESTRITAMENTE em formato JSON com as chaves 'atividade' (string) e 'calorias' (integer)."
            )
            
            contents = [prompt]
            if audio_input:
                audio_bytes = audio_input.read()
                contents.append(types.Part.from_bytes(data=audio_bytes, mime_type=audio_input.type))
            elif texto_treino:
                contents.append(f"Texto do treino: {texto_treino}")
            
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=contents
            )
            
            texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
            dados = json.loads(texto_limpo)
            st.session_state.temp_treino = dados
            st.success("Gasto estimado com sucesso!")
        except Exception as e:
            st.error(f"Erro ao analisar atividade: {e}")
            
    if st.session_state.temp_treino:
        st.markdown("### ✏️ Confirmação do Treino")
        with st.form("form_confirmar_treino"):
            treino_editado = st.text_input("Atividade", value=st.session_state.temp_treino.get("atividade", ""))
            kcal_editada = st.number_input("Calorias Queimadas (kcal)", value=int(st.session_state.temp_treino.get("calorias", 0)), step=10)
            
            if st.form_submit_button("✅ Confirmar e Adicionar"):
                st.session_state.historico_treino.append({
                    "data": hoje_str,
                    "atividade": treino_editado,
                    "calorias": kcal_editada
                })
                st.session_state.temp_treino = None
                st.success("Treino adicionado à fila do dia!")
                st.rerun()

# ---------------------------------------------------------
# ABA 4: CONSULTA E GRÁFICOS DO HISTÓRICO DA PLANILHA
# ---------------------------------------------------------
with tab_consulta:
    st.subheader("📈 Consulta de Registros na Planilha")
    
    if st.button("🔄 Atualizar Dados da Planilha"):
        st.rerun()
        
    if dados_planilha:
        df_planilha = pd.DataFrame(dados_planilha)
        st.markdown("### 📋 Todos os Registros Salvos")
        st.dataframe(df_planilha, use_container_width=True)
        
        st.markdown("---")
        st.markdown("### 📊 Evolução por Data (kcal)")
        df_resumo = df_planilha.groupby(["Data", "Tipo"])["Calorias_Kcal"].sum().unstack().fillna(0)
        st.bar_chart(df_resumo)
    else:
        st.info("Nenhum registro encontrado na planilha até o momento.")

# ---------------------------------------------------------
# RESUMO DOS NOVOS REGISTROS DA SESSÃO ATUAL
# ---------------------------------------------------------
st.markdown("---")
col_t1, col_t2 = st.columns(2)

with col_t1:
    st.subheader("📋 Novos Comidas (A Salvar)")
    if st.session_state.historico_comida:
        st.dataframe(pd.DataFrame(st.session_state.historico_comida), use_container_width=True)

with col_t2:
    st.subheader("🏋️‍♂️ Novos Treinos (A Salvar)")
    if st.session_state.historico_treino:
        st.dataframe(pd.DataFrame(st.session_state.historico_treino), use_container_width=True)

if st.button("💾 Enviar Registro Novo do Dia para o Google Sheets"):
    if not url_sheets:
        st.error("Configure a variável 'URL_SHEETS' nos Secrets.")
    else:
        try:
            dados_salvar = []
            
            for c in st.session_state.historico_comida:
                dados_salvar.append({
                    "Data": hoje_str, 
                    "Tipo": "Alimentação", 
                    "Descricao": c["alimento"], 
                    "Calorias_Kcal": c["calorias"]
                })
            for t in st.session_state.historico_treino:
                dados_salvar.append({
                    "Data": hoje_str, 
                    "Tipo": "Treino", 
                    "Descricao": t["atividade"], 
                    "Calorias_Kcal": t["calorias"]
                })
                
            if dados_salvar:
                response = requests.post(url_sheets, json=dados_salvar)
                if response.status_code == 200:
                    st.balloons()
                    st.success("Novos registros salvos com sucesso na Planilha!")
                    st.session_state.historico_comida = []
                    st.session_state.historico_treino = []
                    st.rerun()
                else:
                    st.error(f"Erro ao enviar: Status {response.status_code}")
            else:
                st.warning("Nenhum registro novo pendente para salvar.")
        except Exception as e:
            st.error(f"Erro de conexão: {e}")

if st.button("🔄 Limpar Registros Não Salvos"):
    st.session_state.historico_comida = []
    st.session_state.historico_treino = []
    st.session_state.temp_comida = None
    st.session_state.temp_treino = None
    st.rerun()
