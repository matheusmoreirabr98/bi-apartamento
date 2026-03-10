import streamlit as st
from supabase import create_client

from database import load_parcelas
from dashboard import render_dashboard
from dashboard_todos import render_dashboard_todos
from pagamentos_view import render_pagamentos_tab, render_atualizar_parcelas_tab
from parcelas_view import render_parcelas_tab
from utils import (
    CONTRATO_TAXAS,
    CONTRATO_TODOS,
    CONTRATO_DIRECIONAL,
    USUARIO_PODE_EDITAR,
    filtrar_contrato,
    inject_styles,
    normalizar_status,
)

st.set_page_config(
    page_title="Apartamento",
    page_icon="imagens/icone_apartamento.png",
    layout="centered",
)

st.markdown(
    """
    <link rel="apple-touch-icon" href="app/static/icone_apartamento.png">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-title" content="Apartamento">
    """,
    unsafe_allow_html=True,
)

# =========================================================
# CONFIG
# =========================================================

inject_styles()
st.title("🏠 Apartamento")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

USUARIOS = {
    st.secrets["PASSWORD_ANA"]: "Ana Luiza",
    st.secrets["PASSWORD_MATHEUS"]: "Matheus Moreira",
}

# =========================================================
# LOGIN
# =========================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user_name" not in st.session_state:
    st.session_state.user_name = None

if not st.session_state.logged_in:
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        user = USUARIOS.get(senha)
        if user:
            st.session_state.logged_in = True
            st.session_state.user_name = user
            st.rerun()
        else:
            st.error("Senha incorreta")

    st.stop()

usuario_logado = st.session_state.user_name
pode_editar = usuario_logado == USUARIO_PODE_EDITAR

top_c1, top_c2 = st.columns([3, 1])

with top_c1:
    st.caption(f"Usuário logado: **{usuario_logado}**")

with top_c2:
    if st.button("Sair"):
        st.session_state.logged_in = False
        st.session_state.user_name = None
        st.rerun()

# =========================================================
# CARGA DE DADOS
# =========================================================

parcelas = load_parcelas(supabase)
parcelas = normalizar_status(parcelas)

if parcelas.empty:
    st.warning("Nenhuma parcela encontrada na tabela `parcelas`.")

contratos_disponiveis = []
opcoes_contrato = ["Sem dados"]

if not parcelas.empty and "contrato" in parcelas.columns:
    contratos_disponiveis = (
        parcelas["contrato"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
        .tolist()
    )

    aliases_contratos = {
        "Ato": ["Ato"],
        "Sinal": ["Sinal"],
        "Sinal Ato": ["Sinal Ato"],
        "Diferença": ["Diferença", "Diferenca"],
        "Evolução de Obra": ["Evolução de Obra", "Evolucao de Obra"],
        "Taxas Cartoriais": ["Taxas Cartoriais"],
        "Entrada Direcional": ["Entrada Direcional"],
        "Financiamento Caixa": ["Financiamento Caixa"],
    }

    grupos = [
        ("📄 Pagamentos Iniciais", ["Ato", "Sinal", "Sinal Ato"]),
        ("🏗️ Obra", ["Diferença", "Evolução de Obra", "Entrada Direcional"]),
        ("📑 Cartório", ["Taxas Cartoriais"]),
        ("🏦 Financiamento", ["Financiamento Caixa"]),
    ]

    opcoes_contrato = [CONTRATO_TODOS]
    contratos_ja_adicionados = set()

    for _, contratos_grupo in grupos:
        itens_do_grupo = []

        for nome_exibicao in contratos_grupo:
            possiveis_nomes = aliases_contratos.get(nome_exibicao, [nome_exibicao])

            contrato_encontrado = next(
                (
                    contrato_real
                    for contrato_real in contratos_disponiveis
                    if contrato_real in possiveis_nomes and contrato_real not in contratos_ja_adicionados
                ),
                None,
            )

            if contrato_encontrado:
                itens_do_grupo.append(contrato_encontrado)
                contratos_ja_adicionados.add(contrato_encontrado)

        if itens_do_grupo:
            opcoes_contrato.extend(itens_do_grupo)

    contratos_restantes = [
        contrato
        for contrato in contratos_disponiveis
        if contrato not in contratos_ja_adicionados
    ]

    opcoes_contrato.extend(contratos_restantes)

# contrato padrão: Diferença
contrato_padrao = (
    "Diferença"
    if "Diferença" in opcoes_contrato
    else (
        "Diferenca"
        if "Diferenca" in opcoes_contrato
        else (
            CONTRATO_DIRECIONAL
            if CONTRATO_DIRECIONAL in opcoes_contrato
            else (
                CONTRATO_TAXAS
                if CONTRATO_TAXAS in opcoes_contrato
                else (opcoes_contrato[0] if opcoes_contrato and opcoes_contrato[0] != "Sem dados" else "Sem dados")
            )
        )
    )
)

indice_padrao = 0
if contrato_padrao in opcoes_contrato:
    indice_padrao = opcoes_contrato.index(contrato_padrao)

contrato_selecionado = st.selectbox(
    "Selecione o contrato",
    options=opcoes_contrato,
    index=indice_padrao if opcoes_contrato and opcoes_contrato[0] != "Sem dados" else 0,
)

if contrato_selecionado == "Sem dados":
    st.stop()

parcelas_contrato = filtrar_contrato(parcelas, contrato_selecionado)

if "eh_linha_resumo" in parcelas_contrato.columns:
    parcelas_contagem = parcelas_contrato[~parcelas_contrato["eh_linha_resumo"]].copy()
else:
    parcelas_contagem = parcelas_contrato.copy()

# =========================================================
# TABS
# =========================================================

tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 Dashboard", "📁 Parcelas", "💸 Registrar / Editar Pagamento", "🛠 Atualizar Parcelas"]
)

with tab1:
    if contrato_selecionado == CONTRATO_TODOS:
        render_dashboard_todos(parcelas)
    else:
        render_dashboard(parcelas_contrato, parcelas_contagem, contrato_selecionado)

with tab2:
    render_parcelas_tab(parcelas_contrato, contrato_selecionado)

with tab3:
    render_pagamentos_tab(parcelas_contrato, contrato_selecionado, supabase, pode_editar)

with tab4:
    render_atualizar_parcelas_tab(parcelas_contrato, contrato_selecionado, supabase, pode_editar)