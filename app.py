import streamlit as st
import pandas as pd
import json
from datetime import date
from google import genai
from google.genai import types
from PIL import Image
from streamlit_gsheets import GSheetsConnection

# Configuração da página
st.set_page_config(page_title="Diário Calórico & Fitness Pro", page_icon="⚡", layout="centered")

# Busca a chave de API dos Secrets do Streamlit ou da Sidebar
api_key = st.secrets.get("GEMINI_API_KEY", None)

# Inicialização de Variáveis de Sessão
if "historico_comida" not in st.session_state:
    st.session_state.historico_comida = []
if "historico_treino" not in st.session_state:
    st.session_state.historico_treino = []
if "temp_comida" not in st.session_state:
    st.session_state.temp_comida = None
if "temp_treino" not in st.session_state:
    st.session_state.temp_treino = None

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

# CÁLCULOS TOTAIS
consumido = sum(item["calorias"] for item in st.session_state.historico_comida)
gasto_treinos = sum(item["calorias"] for item in st.session_state.historico_treino)
gasto_exercicio_total = gasto_treinos + calorias_passos

meta_ajustada = meta_base + gasto_exercicio_total
saldo_restante = meta_ajustada - consumido

# CORPO PRINCIPAL
st.title("⚡ Diário Calórico & Treinos")

# Painel de Indicadores
col1, col2, col3, col4 = st.columns(4)
col1.metric("Meta Base", f"{meta_base} kcal")
col2.metric("Gasto Atividades", f"+{gasto_exercicio_total} kcal")
col3.metric("Consumido", f"{consumido} kcal")
col4.metric("Falta Consumir", f"{saldo_restante} kcal", delta_color="inverse")

st.progress(min(max(consumido / meta_ajustada if meta_ajustada > 0 else 0.0, 0.0), 1.0))
st.markdown("---")

# ABAS DE REGISTRO
tab_foto, tab_texto_comida, tab_atividade = st.tabs([
    "📸 Foto de Comida", 
    "✍️ Comida por Texto Livre", 
    "🎙️/✍️ Exercício (Áudio ou Texto)"
])

# ---------------------------------------------------------
# ABA 1: FOTO DE COMIDA (COM CONFIRMAÇÃO E RETIFICAÇÃO)
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
                    "'alimento' (string) e 'calorias' (integer). Exemplo: {\"alimento\": \"Prato com Arroz, Feijão e Frango\", \"calorias\": 550}"
                )
                response = client.models.generate_content(
                    model='gemini-3.6-flash',
                    contents=[image, prompt]
                )
                
                # Trata a resposta JSON
                texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
                dados = json.loads(texto_limpo)
                st.session_state.temp_comida = dados
                st.success("Análise concluída! Verifique e ajuste abaixo antes de salvar.")
            except Exception as e:
                st.error(f"Erro ao analisar foto: {e}")

    # Formulário de Confirmação / Retificação da Foto
    if st.session_state.temp_comida:
        st.markdown("### ✏️ Confirmação do Registro")
        with st.form("form_confirmar_foto"):
            nome_editado = st.text_input("Descrição da Comida", value=st.session_state.temp_comida.get("alimento", ""))
            calorias_editadas = st.number_input("Calorias Estimadas (kcal)", value=int(st.session_state.temp_comida.get("calorias", 0)), step=10)
            
            if st.form_submit_button("✅ Confirmar e Salvar no Diário"):
                st.session_state.historico_comida.append({
                    "data": str(date.today()),
                    "alimento": nome_editado,
                    "calorias": calorias_editadas
                })
                st.session_state.temp_comida = None
                st.success("Refeição salva com sucesso!")
                st.rerun()

# ---------------------------------------------------------
# ABA 2: COMIDA POR TEXTO LIVRE (IA ESTIMADORA)
# ---------------------------------------------------------
with tab_texto_comida:
    st.write("Descreva o que você comeu em linguagem natural (ex: *'1 bife de peito de frango do tamanho da palma da mão grelhado'*).")
    texto_refeicao = st.text_area("O que você comeu?", placeholder="Ex: 2 ovos mexidos com 1 fatia de pão integral e café sem açúcar")
    
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
# ABA 3: EXERCÍCIO POR ÁUDIO OU TEXTO
# ---------------------------------------------------------
with tab_atividade:
    st.write("Grave um áudio ou descreva seu treino para a IA calcular o gasto calórico.")
    
    # Gravador de Áudio Nativo
    audio_input = st.audio_input("🎙️ Gravador de Áudio (Fale seu treino)")
    texto_treino = st.text_input("✍️ Ou digite seu treino aqui", placeholder="Ex: Fiz 40 minutos de musculação pesada")
    
    if st.button("🔥 Calcular Gasto do Treino") and api_key:
        try:
            client = genai.Client(api_key=api_key)
            prompt = (
                f"O usuário tem {peso}kg. Analise a atividade física informada (seja áudio ou texto) e estime o gasto energético em kcal. "
                "Responda ESTRITAMENTE em formato JSON com as chaves 'atividade' (string) e 'calorias' (integer). "
                "Exemplo: {\"atividade\": \"Musculação (40 min)\", \"calorias\": 220}"
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
            
    # Formulário de Confirmação do Treino
    if st.session_state.temp_treino:
        st.markdown("### ✏️ Confirmação do Treino")
        with st.form("form_confirmar_treino"):
            treino_editado = st.text_input("Atividade", value=st.session_state.temp_treino.get("atividade", ""))
            kcal_editada = st.number_input("Calorias Queimadas (kcal)", value=int(st.session_state.temp_treino.get("calorias", 0)), step=10)
            
            if st.form_submit_button("✅ Confirmar e Salvar Treino"):
                st.session_state.historico_treino.append({
                    "data": str(date.today()),
                    "atividade": treino_editado,
                    "calorias": kcal_editada
                })
                st.session_state.temp_treino = None
                st.success("Treino salvo!")
                st.rerun()

# ---------------------------------------------------------
# TABELAS DE RESUMO DO DIA E SALVAMENTO EM SHEETS
# ---------------------------------------------------------
st.markdown("---")
col_t1, col_t2 = st.columns(2)

with col_t1:
    st.subheader("📋 Comidas Registradas")
    if st.session_state.historico_comida:
        df_comida = pd.DataFrame(st.session_state.historico_comida)
        st.dataframe(df_comida, use_container_width=True)

with col_t2:
    st.subheader("🏋️‍♂️ Treinos Registrados")
    if st.session_state.historico_treino:
        df_treino = pd.DataFrame(st.session_state.historico_treino)
        st.dataframe(df_treino, use_container_width=True)

# BOTÃO DE ENVIAR PARA GOOGLE SHEETS
if st.button("💾 Enviar Registro do Dia para o Google Sheets"):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        # Consolida refeições e treinos
        dados_salvar = []
        hoje = str(date.today())
        
        for c in st.session_state.historico_comida:
            dados_salvar.append({"Data": hoje, "Tipo": "Alimentacao", "Descricao": c["alimento"], "Calorias_Kcal": c["calorias"]})
        for t in st.session_state.historico_treino:
            dados_salvar.append({"Data": hoje, "Tipo": "Treino", "Descricao": t["atividade"], "Calorias_Kcal": t["calorias"]})
            
        if dados_salvar:
            df_novos = pd.DataFrame(dados_salvar)
            # Lê planilha existente e adiciona novos dados
            df_existente = conn.read()
            df_final = pd.concat([df_existente, df_novos], ignore_index=True)
            conn.update(data=df_final)
            st.balloons()
            st.success("Dados salvos com sucesso na sua Planilha do Google!")
        else:
            st.warning("Nenhum registro para salvar hoje.")
    except Exception as e:
        st.error(f"Configure o conector do Google Sheets nos Secrets. Erro: {e}")

if st.button("🔄 Zerar Tela"):
    st.session_state.historico_comida = []
    st.session_state.historico_treino = []
    st.session_state.temp_comida = None
    st.session_state.temp_treino = None
    st.rerun()
