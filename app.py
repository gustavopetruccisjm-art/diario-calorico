import streamlit as st
import pandas as pd
from datetime import date
from google import genai
from PIL import Image

# Configuração da página
st.set_page_config(page_title="Meu Diário Calórico & Fitness", page_icon="⚡", layout="centered")

# Busca a chave de API dos Secrets do Streamlit ou do campo da Sidebar
api_key = st.secrets.get("GEMINI_API_KEY", None)

# Inicialização de Variáveis de Sessão
if "historico_comida" not in st.session_state:
    st.session_state.historico_comida = []
if "historico_treino" not in st.session_state:
    st.session_state.historico_treino = []

# --- SIDEBAR: PERFIL & METAS ---
st.sidebar.header("📊 Perfil & Parâmetros")

# Se não houver chave nos Secrets, exibe o campo para digitação manual
if not api_key:
    api_key = st.sidebar.text_input("Chave da API Google Gemini", type="password")

sexo = st.sidebar.selectbox("Sexo", ["Masculino", "Feminino"])
idade = st.sidebar.number_input("Idade", value=30, step=1)
peso = st.sidebar.number_input("Peso (kg)", value=75.0, step=0.5)
altura = st.sidebar.number_input("Altura (cm)", value=175, step=1)

# Cálculo da TMB (Mifflin-St Jeor)
if sexo == "Masculino":
    tmb = (10 * peso) + (6.25 * altura) - (5 * idade) + 5
else:
    tmb = (10 * peso) + (6.25 * altura) - (5 * idade) - 161

st.sidebar.subheader("Taxa Basal")
st.sidebar.write(f"**TMB (Repouso Absoluto):** {int(tmb)} kcal")

meta_base = st.sidebar.number_input("Meta Calórica Base (kcal)", value=int(tmb * 1.2), step=50)

# --- REGISTRO DE PASSOS E EXERCÍCIOS ---
st.sidebar.markdown("---")
st.sidebar.subheader("🏃‍♂️ Atividades do Dia")
passos = st.sidebar.number_input("Número de Passos", value=0, step=500)
calorias_passos = int(passos * 0.04 * (peso / 70.0))
st.sidebar.caption(f"Gasto estimado dos passos: ~{calorias_passos} kcal")

# --- CÁLCULOS TOTAIS DO DIA ---
consumido = sum(item["calorias"] for item in st.session_state.historico_comida)
gasto_treinos = sum(item["calorias"] for item in st.session_state.historico_treino)
gasto_exercicio_total = gasto_treinos + calorias_passos

meta_ajustada = meta_base + gasto_exercicio_total
saldo_restante = meta_ajustada - consumido

# --- CORPO PRINCIPAL DO APP ---
st.title("⚡ Diário Calórico & Treinos")

# Painel de Indicadores
col1, col2, col3, col4 = st.columns(4)
col1.metric("Meta Base", f"{meta_base} kcal")
col2.metric("Gasto Treinos/Passos", f"+{gasto_exercicio_total} kcal")
col3.metric("Consumido", f"{consumido} kcal")
col4.metric("Falta Consumir", f"{saldo_restante} kcal", delta_color="inverse")

progresso = min(max(consumido / meta_ajustada if meta_ajustada > 0 else 0.0, 0.0), 1.0)
st.progress(progresso)

st.markdown("---")

# ABAS DO APP
tab_foto, tab_manual, tab_exercicio = st.tabs(["📸 Foto Refeição", "✍️ Comida Manual", "🏋️‍♂️ Registrar Treino"])

with tab_foto:
    foto = st.file_uploader("Envie a foto do prato", type=["jpg", "jpeg", "png"])
    if foto and api_key:
        image = Image.open(foto)
        st.image(image, caption="Refeição enviada", use_container_width=True)
        if st.button("🔍 Analisar com IA"):
            try:
                client = genai.Client(api_key=api_key)
                prompt = (
                    "Analise esta imagem de refeição/comida. Liste os alimentos identificados "
                    "com suas estimativas de peso em gramas e calorias totais. "
                    "Retorne em formato legível no estilo: Alimento | Peso Estimado | Calorias."
                )
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[image, prompt]
                )
                st.subheader("Resultado da Análise:")
                st.markdown(response.text)
            except Exception as e:
                st.error(f"Erro ao processar imagem: {e}")
    elif foto and not api_key:
        st.warning("A chave da API Gemini não foi configurada nos Secrets nem informada manualmente.")

with tab_manual:
    with st.form("form_comida"):
        alimento = st.text_input("Alimento / Refeição")
        kcal_comida = st.number_input("Calorias (kcal)", min_value=0, step=10)
        if st.form_submit_button("Adicionar Alimento") and alimento:
            st.session_state.historico_comida.append({"alimento": alimento, "calorias": kcal_comida})
            st.rerun()

with tab_exercicio:
    with st.form("form_treino"):
        tipo_treino = st.selectbox("Atividade", ["Musculação", "Bicicleta / Ergométrica", "Corrida", "Caminhada", "Outro"])
        duracao = st.number_input("Duração (minutos)", min_value=1, value=30, step=5)
        kcal_queimadas = st.number_input("Calorias Queimadas (kcal)", min_value=0, value=150, step=10)
        if st.form_submit_button("Adicionar Treino"):
            st.session_state.historico_treino.append({
                "atividade": f"{tipo_treino} ({duracao} min)",
                "calorias": kcal_queimadas
            })
            st.rerun()

# TABELAS DE RESUMO
col_t1, col_t2 = st.columns(2)

with col_t1:
    st.subheader("📋 Comidas de Hoje")
    if st.session_state.historico_comida:
        st.dataframe(pd.DataFrame(st.session_state.historico_comida), use_container_width=True)

with col_t2:
    st.subheader("🏋️‍♂️ Treinos de Hoje")
    if st.session_state.historico_treino:
        st.dataframe(pd.DataFrame(st.session_state.historico_treino), use_container_width=True)

if st.button("🔄 Zerar Dia"):
    st.session_state.historico_comida = []
    st.session_state.historico_treino = []
    st.rerun()
