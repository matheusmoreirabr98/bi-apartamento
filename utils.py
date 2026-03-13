#utils.py

from datetime import datetime 
import pandas as pd
import streamlit as st

USUARIO_PODE_EDITAR = "Matheus Moreira"

STATUS_ORDEM = {
    "pendente": 1,
    "atrasado": 2,
    "pago": 3,
}

STATUS_MAP_FILTRO = {
    "Todos": None,
    "Pendente": "pendente",
    "Atrasado": "atrasado",
    "Pago": "pago",
}

CONTRATO_TODOS = "Todos os contratos"
CONTRATO_TAXAS = "Taxas Cartoriais"
CONTRATO_DIRECIONAL = "Entrada Direcional"


def inject_styles():
    st.markdown("""
    <style>
    .block-container{
        padding-top: 1rem;
        padding-bottom: 2rem;
        padding-left: 0.8rem;
        padding-right: 0.8rem;
    }

    .dash-grid-1,
    .dash-grid-2,
    .dash-grid-3,
    .dash-grid-4{
        display: grid;
        gap: 10px;
        margin-bottom: 10px;
        width: 100%;
    }

    .dash-grid-1{
        grid-template-columns: 1fr;
    }

    .dash-grid-2{
        grid-template-columns: 1fr 1fr;
    }

    .dash-grid-3{
        grid-template-columns: 1fr 1fr 1fr;
    }

    .dash-grid-4{
        grid-template-columns: 1fr 1fr 1fr 1fr;
    }

    .metric-card{
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 14px 10px;
        text-align: center;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
        min-height: 88px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }

    .metric-label{
        font-size: 0.78rem;
        color: #6b7280;
        margin-bottom: 6px;
        line-height: 1.2;
    }

    .metric-value{
        font-size: 1.5rem;
        font-weight: 700;
        color: #0f172a;
        line-height: 1.1;
    }

    .metric-value.small{
        font-size: 1.1rem;
    }

    @media (max-width: 768px){
        .dash-grid-2{
            grid-template-columns: 1fr 1fr;
        }

        .dash-grid-3{
            grid-template-columns: 1fr 1fr 1fr;
        }

        .dash-grid-4{
            grid-template-columns: 1fr 1fr 1fr 1fr;
        }

        .metric-card{
            padding: 12px 8px;
            min-height: 82px;
        }

        .metric-label{
            font-size: 0.70rem;
        }

        .metric-value{
            font-size: 1.15rem;
        }

        .metric-value.small{
            font-size: 0.95rem;
        }
    }
    </style>
    """, unsafe_allow_html=True)


def brl(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def card_html(label, value, small=False):
    css_class = "metric-value small" if small else "metric-value"
    return (
        f'<div class="metric-card">'
        f'<div class="metric-label">{label}</div>'
        f'<div class="{css_class}">{value}</div>'
        f'</div>'
    )


def render_cards_grid(cards_html, cols=1):
    grid_class = {
        1: "dash-grid-1",
        2: "dash-grid-2",
        3: "dash-grid-3",
        4: "dash-grid-4",
    }.get(cols, "dash-grid-1")

    html = f'<div class="{grid_class}">{"".join(cards_html)}</div>'
    st.markdown(html, unsafe_allow_html=True)


def now_iso():
    return datetime.utcnow().isoformat()


def normalizar_categoria(valor):
    if pd.isna(valor):
        return valor

    valor_str = str(valor).strip().lower()

    if valor_str == "registro":
        return "Taxas Cartoriais"

    return valor


def normalizar_status_banco(valor):
    if pd.isna(valor):
        return None
    return str(valor).strip().lower()


def normalizar_status(df):
    if df.empty:
        return df

    hoje = pd.Timestamp.today().normalize()

    df = df.copy()
    df["status_exibicao"] = df["status"].fillna("pendente")

    nao_pago = df["status_exibicao"] != "pago"

    df.loc[
        nao_pago & (df["data_vencimento"] < hoje),
        "status_exibicao",
    ] = "atrasado"

    df.loc[
        nao_pago & (df["data_vencimento"] >= hoje),
        "status_exibicao",
    ] = "pendente"

    df["status_ordem"] = df["status_exibicao"].map(STATUS_ORDEM).fillna(999)
    return df


def filtrar_contrato(df, contrato):
    if df.empty:
        return df
    if contrato == CONTRATO_TODOS:
        return df.copy()
    return df[df["contrato"] == contrato].copy()