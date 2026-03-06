import time
import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client
import plotly.express as px

# ✅ TEM QUE SER O PRIMEIRO COMANDO STREAMLIT
st.set_page_config(page_title="Apartamento", layout="wide")
st.markdown("""
<script>
document.addEventListener("DOMContentLoaded", function() {
    const inputs = window.parent.document.querySelectorAll('input[data-testid="stTextInput"]');
    inputs.forEach(input => {
        input.setAttribute("inputmode", "numeric");
    });
});
</script>
""", unsafe_allow_html=True)
st.title("🏠Apartamento")
st.markdown("""
<style>
.stApp {
    background-color: #eef2f7;
}

.block-container {
    padding-top: 1rem;
    padding-bottom: 2rem;
}

.kpi-card {
    background: linear-gradient(135deg, #ffffff 0%, #f8fbff 100%);
    border: 1px solid #d9e2f1;
    border-radius: 18px;
    padding: 18px 20px;
    box-shadow: 0 4px 14px rgba(15, 23, 42, 0.06);
    min-height: 120px;
}

.kpi-label {
    font-size: 14px;
    color: #667085;
    font-weight: 600;
    margin-bottom: 10px;
}

.kpi-value {
    font-size: 34px;
    color: #0f172a;
    font-weight: 800;
    line-height: 1.1;
}

.kpi-sub {
    font-size: 13px;
    color: #475467;
    margin-top: 8px;
}

.section-title {
    font-size: 24px;
    font-weight: 800;
    color: #0f172a;
    margin: 8px 0 16px 0;
}

div[data-testid="stDataFrame"] {
    border-radius: 16px;
    overflow: hidden;
}
</style>
""", unsafe_allow_html=True)

# ====== Secrets (Streamlit Cloud / Local) ======
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
APP_PASSWORD = st.secrets["APP_PASSWORD"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

CATEGORIAS = [
    "Sinal Ato",
    "Sinal",
    "Diferença",
    "Evolução de Obra",
    "ITBI e Registro",
    "Parc. Entrada Direcional",
    "Financiamento Caixa",
]

# ====== Limites por categoria ======
LIMITES = {
    "Sinal Ato": 3,
    "Sinal": 3,
    "Diferença": 6,
    "Evolução de Obra": 28,
    "ITBI e Registro": 43,
    "Parc. Entrada Direcional": 57,
    "Financiamento Caixa": 420,
}

def brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def get_df():
    res = supabase.table("pagamentos").select("*").order("data_pagamento").execute()
    df = pd.DataFrame(res.data)
    if df.empty:
        return df
    df["data_pagamento"] = pd.to_datetime(df["data_pagamento"])
    df["valor"] = pd.to_numeric(df["valor"])
    df["mes"] = df["data_pagamento"].dt.to_period("M").astype(str)
    return df

# ====== LOGIN ======
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    pw = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        if pw == APP_PASSWORD:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Senha incorreta")
    st.stop()


if "form_categoria" not in st.session_state:
    st.session_state.form_categoria = None

if "form_valor" not in st.session_state:
    st.session_state.form_valor = 0.0

if "form_obs" not in st.session_state:
    st.session_state.form_obs = ""

tab1, tab2, tab3 = st.tabs(["➕ Lançar", "📊 Dashboard", "🧾 Histórico"])

# ================== TAB 1: LANÇAR ==================
with tab1:
    st.subheader("Adicionar pagamento")

    c1, c2, c3 = st.columns([1, 1, 1])

    with c1:
        d = st.date_input("Data do pagamento", value=date.today(), format="DD/MM/YYYY")

    with c2:
        df_tmp = get_df()

        counts = {}
        if not df_tmp.empty and "categoria" in df_tmp.columns:
            counts = df_tmp["categoria"].value_counts().to_dict()

        opcoes = []
        label_to_cat = {}

        for c in CATEGORIAS:
            limite = LIMITES.get(c, None)
            atual = counts.get(c, 0)

            if limite is not None and atual >= limite:
                continue

            label = f"{c} ({atual}/{limite})" if limite is not None else c
            opcoes.append(label)
            label_to_cat[label] = c

        if not opcoes:
            st.warning("✅ Todas as categorias com limite já foram concluídas.")
            st.stop()

        label_escolhido = st.selectbox("Categoria", [""] + opcoes, index=0)
        cat = None if label_escolhido == "" else label_to_cat[label_escolhido]

    with c3:
        # estado do input com máscara
        if "valor_digits" not in st.session_state:
            st.session_state.valor_digits = ""
        if "valor_mask" not in st.session_state:
            st.session_state.valor_mask = ""
    
        def on_valor_change():
            s = st.session_state.valor_mask
            digits = "".join(ch for ch in s if ch.isdigit())
            st.session_state.valor_digits = digits
            v = (int(digits) / 100) if digits else 0.0
            st.session_state.valor_mask = brl(v)

        st.text_input(
            "Valor",
            key="valor_mask",
            on_change=on_valor_change,
            placeholder="0,00"
        )

        valor = (int(st.session_state.valor_digits) / 100) if st.session_state.valor_digits else 0.0
        st.caption(f"Valor: {brl(valor)}")

    if st.button("Salvar"):
        if cat is None or valor <= 0:
            st.error("Preencha a Categoria e um Valor maior que 0.")
        else:
            supabase.table("pagamentos").insert({
                "data_pagamento": str(d),
                "categoria": cat,
                "valor": float(valor)
            }).execute()

            # limpa o campo depois de salvar
            st.session_state.valor_digits = ""
            st.session_state.valor_mask = ""

            st.success("✅ Lançamento registrado!")
            time.sleep(0.8)
            st.rerun()


# ================== TAB 2: DASHBOARD ==================
with tab2:
    df = get_df()

    if df.empty:
        st.info("Ainda não há lançamentos.")
    else:
        df["ano"] = df["data_pagamento"].dt.year.astype(str)
        df["mes_ref"] = df["data_pagamento"].dt.strftime("%m/%Y")

        anos = sorted(df["ano"].unique().tolist())
        categorias_disp = sorted(df["categoria"].unique().tolist())
        meses_disp = sorted(
            df["mes_ref"].unique().tolist(),
            key=lambda x: pd.to_datetime(x, format="%m/%Y")
        )

        with st.sidebar:
            st.markdown("## 📊 Filtros")
            ano = st.selectbox("Ano", ["Todos"] + anos, key="dash_ano")
            categoria = st.selectbox("Categoria", ["Todas"] + categorias_disp, key="dash_categoria")
            meses_sel = st.multiselect("Meses", meses_disp, default=meses_disp, key="dash_meses")

        df_f = df.copy()

        if ano != "Todos":
            df_f = df_f[df_f["ano"] == ano]

        if categoria != "Todas":
            df_f = df_f[df_f["categoria"] == categoria]

        if meses_sel:
            df_f = df_f[df_f["mes_ref"].isin(meses_sel)]

        if df_f.empty:
            st.warning("Nenhum dado encontrado para os filtros selecionados.")
            st.stop()

        st.markdown('<div class="section-title">Dashboard Financeiro</div>', unsafe_allow_html=True)

        total_pago = df_f["valor"].sum()
        media_lanc = df_f["valor"].mean()
        qtd_lanc = len(df_f)
        maior_pag = df_f["valor"].max()

        total_previsto = 0
        for cat_lim, qtd_lim in LIMITES.items():
            cat_vals = df[df["categoria"] == cat_lim]["valor"]
            if not cat_vals.empty:
                total_previsto += cat_vals.mean() * qtd_lim

        total_geral_pago = df["valor"].sum()
        total_restante = max(total_previsto - total_geral_pago, 0)
        perc_concluido = (total_geral_pago / total_previsto * 100) if total_previsto > 0 else 0

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Total Pago</div>
                <div class="kpi-value">{brl(total_pago)}</div>
                <div class="kpi-sub">Com os filtros atuais</div>
            </div>
            """, unsafe_allow_html=True)

        with c2:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Média por Lançamento</div>
                <div class="kpi-value">{brl(media_lanc)}</div>
                <div class="kpi-sub">Valor médio filtrado</div>
            </div>
            """, unsafe_allow_html=True)

        with c3:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Nº de Lançamentos</div>
                <div class="kpi-value">{qtd_lanc}</div>
                <div class="kpi-sub">Registros filtrados</div>
            </div>
            """, unsafe_allow_html=True)

        with c4:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Maior Pagamento</div>
                <div class="kpi-value">{brl(maior_pag)}</div>
                <div class="kpi-sub">Maior valor no filtro</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("")

        prog1, prog2 = st.columns([2, 1])

        with prog1:
            with st.container(border=True):
                st.markdown("### Progresso geral")
                st.progress(min(max(perc_concluido / 100, 0), 1))
                a, b, c = st.columns(3)
                a.metric("Pago", brl(total_geral_pago))
                b.metric("Previsto", brl(total_previsto))
                c.metric("Restante", brl(total_restante))

        with prog2:
            with st.container(border=True):
                st.markdown("### Resumo")
                st.metric("Categorias com pagamentos", f"{df_f['categoria'].nunique()}")
                st.metric("Meses analisados", f"{len(meses_sel)}")

        por_mes = df_f.groupby("mes_ref", as_index=False)["valor"].sum()
        por_mes["mes_ord"] = pd.to_datetime(por_mes["mes_ref"], format="%m/%Y")
        por_mes = por_mes.sort_values("mes_ord")

        por_cat = (
            df_f.groupby("categoria", as_index=False)["valor"]
            .sum()
            .sort_values("valor", ascending=False)
        )

        resumo_cat = (
            df.groupby("categoria")
            .size()
            .reindex(CATEGORIAS, fill_value=0)
            .reset_index(name="qtd_paga")
            .rename(columns={"index": "categoria"})
        )
        resumo_cat["limite"] = resumo_cat["categoria"].map(LIMITES)
        resumo_cat["percentual"] = (resumo_cat["qtd_paga"] / resumo_cat["limite"] * 100).round(1)

        g1, g2 = st.columns([1.5, 1])

        with g1:
            with st.container(border=True):
                st.markdown("### Evolução mensal")
                fig1 = px.area(
                    por_mes,
                    x="mes_ord",
                    y="valor",
                    markers=True
                )
                fig1.update_traces(line=dict(width=3))
                fig1.update_layout(
                    template="plotly_white",
                    height=380,
                    margin=dict(l=10, r=10, t=10, b=10),
                    xaxis_title="",
                    yaxis_title="Valor (R$)",
                    paper_bgcolor="white",
                    plot_bgcolor="white",
                    font=dict(color="#0f172a")
                )
                fig1.update_xaxes(
                    tickformat="%m/%Y",
                    showgrid=False
                )
                fig1.update_yaxes(gridcolor="#e5e7eb")
                st.plotly_chart(fig1, use_container_width=True, config={"displayModeBar": False})

        with g2:
            with st.container(border=True):
                st.markdown("### Participação por categoria")
                fig2 = px.pie(
                    por_cat,
                    names="categoria",
                    values="valor",
                    hole=0.62
                )
                fig2.update_layout(
                    template="plotly_white",
                    height=380,
                    margin=dict(l=10, r=10, t=10, b=10),
                    paper_bgcolor="white",
                    font=dict(color="#0f172a"),
                    legend_title_text=""
                )
                st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

        g3, g4 = st.columns([1.5, 1])

        with g3:
            with st.container(border=True):
                st.markdown("### Ranking por categoria")
                fig3 = px.bar(
                    por_cat,
                    x="valor",
                    y="categoria",
                    orientation="h",
                    text="valor"
                )
                fig3.update_traces(
                    texttemplate="R$ %{text:,.2f}",
                    textposition="outside"
                )
                fig3.update_layout(
                    template="plotly_white",
                    height=380,
                    margin=dict(l=10, r=20, t=10, b=10),
                    xaxis_title="Valor (R$)",
                    yaxis_title="",
                    paper_bgcolor="white",
                    plot_bgcolor="white",
                    font=dict(color="#0f172a"),
                    yaxis={"categoryorder": "total ascending"}
                )
                fig3.update_yaxes(showgrid=False)
                fig3.update_xaxes(gridcolor="#e5e7eb")
                st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})

        with g4:
            with st.container(border=True):
                st.markdown("### Progresso por categoria")
                resumo_show = resumo_cat.copy()
                resumo_show["status"] = resumo_show["qtd_paga"].astype(str) + "/" + resumo_show["limite"].astype(str)
                resumo_show = resumo_show[["categoria", "status", "percentual"]]
                resumo_show.columns = ["Categoria", "Pago", "% Concluído"]
                st.dataframe(
                    resumo_show,
                    use_container_width=True,
                    hide_index=True,
                    height=380
                )

        with st.container(border=True):
            st.markdown("### Histórico filtrado")
            df_show = df_f.copy().sort_values("data_pagamento", ascending=False)
            df_show["data_pagamento"] = df_show["data_pagamento"].dt.strftime("%d/%m/%Y")
            df_show["valor"] = df_show["valor"].apply(brl)

            st.dataframe(
                df_show[["data_pagamento", "categoria", "valor"]],
                use_container_width=True,
                hide_index=True,
                height=300
            )


# ================== TAB 3: HISTÓRICO ==================
with tab3:
    st.subheader("Histórico")

    df = get_df()
    if df.empty:
        st.info("Sem lançamentos ainda.")
    else:
        df_show = df.copy()
        df_show["data_pagamento"] = df_show["data_pagamento"].dt.date
        df_show["valor"] = df_show["valor"].apply(lambda x: brl(float(x)))

        st.dataframe(
            df_show[["id", "data_pagamento", "categoria", "valor"]],
            use_container_width=True,
            hide_index=True
        )

        st.markdown("### 🗑️ Excluir lançamento por ID")
        del_id = st.number_input("ID", min_value=1, step=1)
        if st.button("Excluir", type="secondary"):
            supabase.table("pagamentos").delete().eq("id", int(del_id)).execute()
            st.success(f"Excluído ID {int(del_id)}. (Atualize a página)")
            st.rerun()