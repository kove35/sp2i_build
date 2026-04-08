"""
Composants visuels reutilisables pour Streamlit.
"""

from __future__ import annotations

import textwrap

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components


def _recommended_chart_height(dataframe: pd.DataFrame, horizontal: bool = False) -> int:
    """
    Ajuste la hauteur selon le nombre de categories a afficher.
    """
    row_count = max(len(dataframe.index), 1)
    if horizontal:
        return max(420, min(960, 110 + row_count * 34))
    return max(420, min(760, 360 + row_count * 12))


def apply_dashboard_style(page_title: str) -> None:
    """
    Applique le style commun a toutes les pages.
    """
    st.title(page_title)
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top right, rgba(0, 194, 255, 0.16), transparent 28%),
                radial-gradient(circle at top left, rgba(0, 255, 163, 0.10), transparent 22%),
                #0b1220;
            color: #f5f7fa;
        }

        .sp2i-card {
            background: linear-gradient(180deg, rgba(17, 24, 39, 0.92), rgba(15, 23, 42, 0.95));
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 18px;
            padding: 18px;
            box-shadow: 0 12px 32px rgba(2, 6, 23, 0.35);
            min-height: 135px;
        }

        .sp2i-label {
            color: #94a3b8;
            font-size: 0.92rem;
            margin-bottom: 8px;
        }

        .sp2i-value {
            color: #f8fafc;
            font-size: 2rem;
            font-weight: 700;
            line-height: 1.15;
        }

        .sp2i-caption {
            color: #38bdf8;
            font-size: 0.84rem;
            margin-top: 10px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def format_currency(value: float) -> str:
    return f"{value:,.0f} FCFA".replace(",", " ")


def format_percentage(value: float) -> str:
    return f"{value * 100:,.1f} %".replace(",", " ")


def render_kpi_cards(kpis: list[dict[str, str]]) -> None:
    columns = st.columns(len(kpis))

    for column, kpi in zip(columns, kpis):
        column.markdown(
            f"""
            <div class="sp2i-card">
                <div class="sp2i-label">{kpi["label"]}</div>
                <div class="sp2i-value">{kpi["value"]}</div>
                <div class="sp2i-caption">{kpi["caption"]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_proportional_bars(
    dataframe: pd.DataFrame,
    label_column: str,
    value_column: str,
    title: str,
    unit_suffix: str = "",
    percentage_mode: bool = False,
) -> None:
    """
    Rend un bar chart HTML simple avec des largeurs strictement proportionnelles.
    """
    if dataframe.empty:
        st.info("Aucune donnee disponible.")
        return

    chart_dataframe = dataframe.copy()
    chart_dataframe[value_column] = pd.to_numeric(
        chart_dataframe[value_column], errors="coerce"
    ).fillna(0.0)
    max_value = float(chart_dataframe[value_column].max()) if not chart_dataframe.empty else 0.0
    if max_value <= 0:
        st.info("Aucune valeur positive a afficher.")
        return

    rows_html: list[str] = []
    for _, row in chart_dataframe.iterrows():
        label = str(row[label_column])
        value = float(row[value_column])
        width_pct = max(2.0, (value / max_value) * 100.0)
        if percentage_mode:
            display_value = f"{value * 100:,.1f} %".replace(",", " ")
        else:
            display_value = (
                f"{value / 1_000_000:,.1f} M {unit_suffix}".replace(",", " ")
                if unit_suffix == "FCFA"
                else f"{value:,.0f} {unit_suffix}".replace(",", " ")
            ).strip()
        rows_html.append(
            f"""
            <div class="sp2i-bar-row">
                <div class="sp2i-bar-label">{label}</div>
                <div class="sp2i-bar-track">
                    <div class="sp2i-bar-fill" style="width:{width_pct:.2f}%"></div>
                    <div class="sp2i-bar-value inside">{display_value}</div>
                </div>
            </div>
            """
        )

    st.markdown(f"#### {title}")
    html = textwrap.dedent(
        f"""
        <style>
        .sp2i-bar-wrap {{
            display: flex;
            flex-direction: column;
            gap: 10px;
            margin-top: 0.5rem;
        }}
        .sp2i-bar-row {{
            display: grid;
            grid-template-columns: minmax(180px, 260px) 1fr;
            gap: 14px;
            align-items: center;
        }}
        .sp2i-bar-label {{
            color: #e5e7eb;
            font-size: 0.92rem;
            line-height: 1.2;
        }}
        .sp2i-bar-track {{
            position: relative;
            height: 28px;
            border-radius: 999px;
            background: rgba(148, 163, 184, 0.14);
            overflow: hidden;
        }}
        .sp2i-bar-fill {{
            position: absolute;
            inset: 0 auto 0 0;
            border-radius: 999px;
            background: linear-gradient(90deg, #60a5fa, #93c5fd);
            border: 1px solid rgba(219, 234, 254, 0.45);
        }}
        .sp2i-bar-value {{
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            font-size: 0.82rem;
            font-weight: 600;
            text-shadow: 0 1px 2px rgba(15, 23, 42, 0.8);
            white-space: nowrap;
        }}
        .sp2i-bar-value.inside {{
            right: 10px;
            color: #f8fafc;
        }}
        @media (max-width: 640px) {{
            .sp2i-bar-row {{
                grid-template-columns: 1fr;
                gap: 8px;
                align-items: stretch;
            }}
            .sp2i-bar-label {{
                font-size: 0.86rem;
            }}
            .sp2i-bar-track {{
                height: 26px;
            }}
            .sp2i-bar-value {{
                font-size: 0.74rem;
            }}
        }}
        </style>
        <div class="sp2i-bar-wrap">
            {''.join(rows_html)}
        </div>
        """
    )
    components.html(html, height=max(360, 96 + len(chart_dataframe.index) * 68), scrolling=False)


def render_decision_split(
    dataframe: pd.DataFrame,
    label_column: str,
    value_column: str,
    title: str,
) -> None:
    """
    Rend une structure IMPORT/LOCAL deterministe avec pourcentages calcules en Python.
    """
    if dataframe.empty:
        st.info("Aucune donnee disponible.")
        return

    chart_dataframe = dataframe.copy()
    chart_dataframe[value_column] = pd.to_numeric(
        chart_dataframe[value_column], errors="coerce"
    ).fillna(0.0)
    total_value = float(chart_dataframe[value_column].sum())
    if total_value <= 0:
        st.info("Aucune valeur positive a afficher.")
        return

    color_map = {
        "IMPORT": "#00c2ff",
        "LOCAL": "#00f5a0",
    }

    segments_html: list[str] = []
    legend_html: list[str] = []
    for _, row in chart_dataframe.iterrows():
        label = str(row[label_column])
        value = float(row[value_column])
        percent = (value / total_value) * 100.0
        color = color_map.get(label.upper(), "#93c5fd")
        segments_html.append(
            f'<div class="sp2i-split-segment" style="width:{percent:.2f}%; background:{color};"></div>'
        )
        legend_html.append(
            f"""
            <div class="sp2i-split-legend-row">
                <span class="sp2i-split-dot" style="background:{color};"></span>
                <span class="sp2i-split-name">{label}</span>
                <span class="sp2i-split-pct">{percent:,.1f} %</span>
                <span class="sp2i-split-val">{value:,.0f} FCFA</span>
            </div>
            """
        )

    html = textwrap.dedent(
        f"""
    <style>
    .sp2i-split-wrap {{
        display:flex;
        flex-direction:column;
        gap:16px;
        padding-top:6px;
    }}
    .sp2i-split-bar {{
        display:flex;
        width:100%;
        height:38px;
        border-radius:999px;
        overflow:hidden;
        background:rgba(148, 163, 184, 0.14);
        border:1px solid rgba(148, 163, 184, 0.18);
    }}
    .sp2i-split-segment {{
        height:100%;
    }}
    .sp2i-split-legend {{
        display:flex;
        flex-direction:column;
        gap:10px;
    }}
    .sp2i-split-legend-row {{
        display:grid;
        grid-template-columns: 14px 1fr auto auto;
        gap:12px;
        align-items:center;
        color:#f8fafc;
        font-size:0.92rem;
    }}
    .sp2i-split-dot {{
        width:12px;
        height:12px;
        border-radius:999px;
    }}
    .sp2i-split-name {{
        color:#e5e7eb;
        font-weight:600;
    }}
    .sp2i-split-pct {{
        color:#f8fafc;
        font-weight:700;
    }}
    .sp2i-split-val {{
        color:#93c5fd;
        font-weight:600;
    }}
    @media (max-width: 640px) {{
        .sp2i-split-legend-row {{
            grid-template-columns: 14px 1fr;
            gap:8px;
        }}
        .sp2i-split-pct {{
            grid-column: 2;
        }}
        .sp2i-split-val {{
            grid-column: 2;
        }}
    }}
    </style>
    <div class="sp2i-split-wrap">
        <div class="sp2i-split-bar">
            {''.join(segments_html)}
        </div>
        <div class="sp2i-split-legend">
            {''.join(legend_html)}
        </div>
    </div>
        """
    )
    st.markdown(f"#### {title}")
    components.html(html, height=220, scrolling=False)


def render_heat_grid(
    dataframe: pd.DataFrame,
    row_column: str,
    column_column: str,
    value_column: str,
    title: str,
    unit_suffix: str = "FCFA",
) -> None:
    """
    Rend une matrice proportionnelle simple en HTML.
    """
    if dataframe.empty:
        st.info("Aucune donnee disponible.")
        return

    pivot = (
        dataframe.pivot_table(
            index=row_column,
            columns=column_column,
            values=value_column,
            aggfunc="sum",
            fill_value=0.0,
        )
        .sort_index()
    )
    max_value = float(pivot.to_numpy().max()) if pivot.size else 0.0
    if max_value <= 0:
        st.info("Aucune valeur positive a afficher.")
        return

    header_cells = "".join(f"<th>{column}</th>" for column in pivot.columns)
    body_rows: list[str] = []
    for row_label, row_values in pivot.iterrows():
        cells = []
        for value in row_values:
            alpha = max(0.10, float(value) / max_value)
            display_value = (
                f"{value / 1_000_000:,.1f} M".replace(",", " ")
                if unit_suffix == "FCFA"
                else f"{value:,.0f}".replace(",", " ")
            )
            cells.append(
                f'<td style="background: rgba(96, 165, 250, {alpha:.3f});">{display_value}</td>'
            )
        body_rows.append(
            f"<tr><th>{row_label}</th>{''.join(cells)}</tr>"
        )

    html = textwrap.dedent(
        f"""
    <style>
    .sp2i-grid-wrap {{ overflow-x:auto; margin-top:0.5rem; }}
    .sp2i-grid {{
        width:100%;
        border-collapse:separate;
        border-spacing:6px;
        color:#f8fafc;
        font-size:0.88rem;
    }}
    .sp2i-grid th {{
        color:#cbd5e1;
        font-weight:600;
        text-align:left;
        padding:8px 10px;
        white-space:nowrap;
    }}
    .sp2i-grid td {{
        border-radius:12px;
        padding:10px 12px;
        text-align:right;
        font-weight:700;
        min-width:92px;
        white-space:nowrap;
    }}
    @media (max-width: 640px) {{
        .sp2i-grid {{
            font-size:0.76rem;
            border-spacing:4px;
        }}
        .sp2i-grid th,
        .sp2i-grid td {{
            padding:8px 8px;
            min-width:74px;
        }}
    }}
    </style>
    <div class="sp2i-grid-wrap">
        <table class="sp2i-grid">
            <thead><tr><th>{row_column}</th>{header_cells}</tr></thead>
            <tbody>{''.join(body_rows)}</tbody>
        </table>
    </div>
        """
    )
    st.markdown(f"#### {title}")
    components.html(html, height=max(320, 150 + len(pivot.index) * 54), scrolling=False)


def render_sourcing_matrix(
    dataframe: pd.DataFrame,
    label_column: str,
    title: str,
) -> None:
    """
    Rend une vue synthese stable pour la matrice de sourcing.
    """
    if dataframe.empty:
        st.info("Aucune donnee disponible.")
        return

    chart_dataframe = dataframe.copy()
    chart_dataframe["capex_importable"] = pd.to_numeric(
        chart_dataframe["capex_importable"], errors="coerce"
    ).fillna(0.0)
    chart_dataframe["taux_couverture"] = pd.to_numeric(
        chart_dataframe["taux_couverture"], errors="coerce"
    ).fillna(0.0)
    max_value = float(chart_dataframe["capex_importable"].max()) if not chart_dataframe.empty else 0.0
    if max_value <= 0:
        st.info("Aucune valeur positive a afficher.")
        return

    rows_html: list[str] = []
    for _, row in chart_dataframe.iterrows():
        label = str(row[label_column])
        capex = float(row["capex_importable"])
        width_pct = max(2.0, (capex / max_value) * 100.0)
        coverage = float(row.get("taux_couverture", 0.0)) * 100.0
        missing = int(row.get("articles_sans_prix", 0) or 0)
        rows_html.append(
            f"""
            <div class="sp2i-bar-row">
                <div class="sp2i-bar-label">{label}</div>
                <div class="sp2i-bar-track">
                    <div class="sp2i-bar-fill" style="width:{width_pct:.2f}%"></div>
                    <div class="sp2i-bar-value inside">{capex / 1_000_000:,.1f} M FCFA</div>
                </div>
                <div class="sp2i-bar-meta">{coverage:,.1f}% couv. | {missing} sans prix</div>
            </div>
            """
        )

    html = textwrap.dedent(
        f"""
    <style>
    .sp2i-sourcing-wrap {{ display:flex; flex-direction:column; gap:12px; margin-top:0.5rem; }}
    .sp2i-bar-row {{
        display:grid;
        grid-template-columns:minmax(180px,260px) 1fr auto;
        gap:14px;
        align-items:center;
    }}
    .sp2i-bar-label {{ color:#e5e7eb; font-size:0.92rem; line-height:1.2; }}
    .sp2i-bar-track {{
        position:relative; height:28px; border-radius:999px;
        background:rgba(148,163,184,0.14); overflow:hidden;
    }}
    .sp2i-bar-fill {{
        position:absolute; inset:0 auto 0 0; border-radius:999px;
        background:linear-gradient(90deg,#60a5fa,#93c5fd);
        border:1px solid rgba(219,234,254,0.45);
    }}
    .sp2i-bar-value.inside {{
        position:absolute; right:10px; top:50%; transform:translateY(-50%);
        color:#f8fafc; font-size:0.82rem; font-weight:600; white-space:nowrap;
    }}
    .sp2i-bar-meta {{ color:#93c5fd; font-size:0.82rem; white-space:nowrap; }}
    @media (max-width: 640px) {{
        .sp2i-bar-row {{
            grid-template-columns: 1fr;
            gap:8px;
            align-items:stretch;
        }}
        .sp2i-bar-label {{
            font-size:0.86rem;
        }}
        .sp2i-bar-meta {{
            white-space:normal;
            font-size:0.76rem;
        }}
    }}
    </style>
    <div class="sp2i-sourcing-wrap">{''.join(rows_html)}</div>
        """
    )
    st.markdown(f"#### {title}")
    components.html(html, height=max(380, 104 + len(chart_dataframe.index) * 76), scrolling=False)


def render_signed_bars(
    dataframe: pd.DataFrame,
    label_column: str,
    value_column: str,
    title: str,
    unit_suffix: str = "FCFA",
) -> None:
    """
    Rend des ecarts positifs / negatifs avec un axe central stable.
    """
    if dataframe.empty:
        st.info("Aucune donnee disponible.")
        return

    chart_dataframe = dataframe.copy()
    chart_dataframe[value_column] = pd.to_numeric(
        chart_dataframe[value_column], errors="coerce"
    ).fillna(0.0)
    max_abs = float(chart_dataframe[value_column].abs().max()) if not chart_dataframe.empty else 0.0
    if max_abs <= 0:
        st.info("Aucune valeur significative a afficher.")
        return

    rows_html: list[str] = []
    for _, row in chart_dataframe.iterrows():
        label = str(row[label_column])
        value = float(row[value_column])
        width_pct = max(2.0, (abs(value) / max_abs) * 50.0)
        side_class = "positive" if value >= 0 else "negative"
        display_value = (
            f"{value / 1_000_000:,.1f} M {unit_suffix}".replace(",", " ")
            if unit_suffix == "FCFA"
            else f"{value:,.0f} {unit_suffix}".replace(",", " ")
        ).strip()
        rows_html.append(
            f"""
            <div class="sp2i-signed-row">
                <div class="sp2i-signed-label">{label}</div>
                <div class="sp2i-signed-track">
                    <div class="sp2i-signed-axis"></div>
                    <div class="sp2i-signed-fill {side_class}" style="width:{width_pct:.2f}%"></div>
                    <div class="sp2i-signed-value {side_class}">{display_value}</div>
                </div>
            </div>
            """
        )

    html = textwrap.dedent(
        f"""
    <style>
    .sp2i-signed-wrap {{
        display:flex;
        flex-direction:column;
        gap:10px;
        margin-top:0.5rem;
    }}
    .sp2i-signed-row {{
        display:grid;
        grid-template-columns:minmax(180px,260px) 1fr;
        gap:14px;
        align-items:center;
    }}
    .sp2i-signed-label {{
        color:#e5e7eb;
        font-size:0.92rem;
        line-height:1.2;
    }}
    .sp2i-signed-track {{
        position:relative;
        height:30px;
        border-radius:999px;
        background:rgba(148,163,184,0.10);
        overflow:hidden;
    }}
    .sp2i-signed-axis {{
        position:absolute;
        left:50%;
        top:0;
        bottom:0;
        width:2px;
        background:rgba(226,232,240,0.45);
    }}
    .sp2i-signed-fill {{
        position:absolute;
        top:3px;
        bottom:3px;
        border-radius:999px;
    }}
    .sp2i-signed-fill.positive {{
        left:50%;
        background:linear-gradient(90deg,#60a5fa,#93c5fd);
        border:1px solid rgba(219,234,254,0.45);
    }}
    .sp2i-signed-fill.negative {{
        right:50%;
        background:linear-gradient(90deg,#fca5a5,#f87171);
        border:1px solid rgba(254,202,202,0.45);
    }}
    .sp2i-signed-value {{
        position:absolute;
        top:50%;
        transform:translateY(-50%);
        color:#f8fafc;
        font-size:0.80rem;
        font-weight:600;
        white-space:nowrap;
    }}
    .sp2i-signed-value.positive {{
        right:10px;
    }}
    .sp2i-signed-value.negative {{
        left:10px;
    }}
    @media (max-width: 640px) {{
        .sp2i-signed-row {{
            grid-template-columns: 1fr;
            gap:8px;
            align-items:stretch;
        }}
        .sp2i-signed-label {{
            font-size:0.86rem;
        }}
        .sp2i-signed-value {{
            font-size:0.74rem;
        }}
    }}
    </style>
    <div class="sp2i-signed-wrap">{''.join(rows_html)}</div>
        """
    )
    st.markdown(f"#### {title}")
    components.html(html, height=max(380, 104 + len(chart_dataframe.index) * 76), scrolling=False)


def _build_option_index(options: list[dict], selected_value) -> int:
    """
    Retrouve l'index correspondant a une valeur deja stockee.
    """
    for index, option in enumerate(options):
        if option["value"] == selected_value:
            return index
    return 0


def reset_shared_filters() -> None:
    """
    Reinitialise les filtres synchronises entre les pages.
    """
    st.session_state.shared_filters = {
        "lot_id": None,
        "fam_article_id": None,
        "batiment_id": None,
        "niveau_id": None,
    }


def render_sidebar_filters(filter_options: dict) -> dict:
    """
    Affiche des filtres synchronises entre toutes les pages Streamlit.
    """
    st.sidebar.header("Filtres")

    lot_options = [{"value": None, "label": "Tous les lots"}] + filter_options.get("lots", [])
    family_options = [{"value": None, "label": "Toutes les familles"}] + filter_options.get("familles", [])
    building_options = [{"value": None, "label": "Tous les batiments"}] + filter_options.get("batiments", [])
    level_options = [{"value": None, "label": "Tous les niveaux"}] + filter_options.get("niveaux", [])

    if "shared_filters" not in st.session_state:
        st.session_state.shared_filters = {
            "lot_id": None,
            "fam_article_id": None,
            "batiment_id": None,
            "niveau_id": None,
        }

    current_filters = st.session_state.shared_filters

    selected_lot = st.sidebar.selectbox(
        "Lot",
        options=lot_options,
        index=_build_option_index(lot_options, current_filters.get("lot_id")),
        format_func=lambda option: option["label"],
        key="sidebar_lot_id",
    )
    selected_family = st.sidebar.selectbox(
        "Famille d'article",
        options=family_options,
        index=_build_option_index(family_options, current_filters.get("fam_article_id")),
        format_func=lambda option: option["label"],
        key="sidebar_fam_article_id",
    )
    selected_building = st.sidebar.selectbox(
        "Batiment",
        options=building_options,
        index=_build_option_index(building_options, current_filters.get("batiment_id")),
        format_func=lambda option: option["label"],
        key="sidebar_batiment_id",
    )
    selected_level = st.sidebar.selectbox(
        "Niveau",
        options=level_options,
        index=_build_option_index(level_options, current_filters.get("niveau_id")),
        format_func=lambda option: option["label"],
        key="sidebar_niveau_id",
    )

    updated_filters = {
        "lot_id": selected_lot["value"],
        "fam_article_id": selected_family["value"],
        "batiment_id": selected_building["value"],
        "niveau_id": selected_level["value"],
    }

    st.session_state.shared_filters = updated_filters

    if st.sidebar.button("Reinitialiser les filtres", use_container_width=True):
        reset_shared_filters()
        st.rerun()

    return updated_filters


def render_active_filters(filters: dict, filter_options: dict) -> None:
    """
    Affiche un resume texte des filtres actifs.
    """
    def find_label(options: list[dict], value) -> str:
        for option in options:
            if option["value"] == value:
                return option["label"]
        return "Tous"

    labels = [
        f"Lot : {find_label(filter_options.get('lots', []), filters.get('lot_id')) if filters.get('lot_id') is not None else 'Tous'}",
        f"Famille : {find_label(filter_options.get('familles', []), filters.get('fam_article_id')) if filters.get('fam_article_id') else 'Toutes'}",
        f"Batiment : {find_label(filter_options.get('batiments', []), filters.get('batiment_id')) if filters.get('batiment_id') else 'Tous'}",
        f"Niveau : {find_label(filter_options.get('niveaux', []), filters.get('niveau_id')) if filters.get('niveau_id') else 'Tous'}",
    ]
    summary_col, action_col = st.columns([5, 1])
    with summary_col:
        st.caption(" | ".join(labels))
    with action_col:
        has_active_filters = any(value is not None for value in filters.values())
        if st.button(
            "Effacer",
            key="clear_shared_filters_button",
            disabled=not has_active_filters,
            use_container_width=True,
        ):
            reset_shared_filters()
            st.rerun()


def build_donut_chart(dataframe: pd.DataFrame, names: str, values: str, title: str) -> go.Figure:
    chart_dataframe = dataframe.copy()
    chart_dataframe[values] = pd.to_numeric(chart_dataframe[values], errors="coerce").fillna(0.0)
    figure = go.Figure(
        data=[
            go.Pie(
                labels=chart_dataframe[names],
                values=chart_dataframe[values],
                hole=0.6,
                sort=False,
                marker=dict(colors=["#00c2ff", "#00f5a0", "#ffb703", "#fb7185"][: len(chart_dataframe)]),
                textposition="inside",
                texttemplate="%{percent}",
                hovertemplate="%{label}<br>Valeur=%{value:,.0f}<br>Part=%{percent}<extra></extra>",
            )
        ]
    )
    figure.update_layout(
        title=title,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e5e7eb",
        margin=dict(l=20, r=20, t=60, b=20),
        showlegend=True,
    )
    return figure


def build_bar_chart(
    dataframe: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    horizontal: bool = False,
    scale_millions: bool = False,
) -> go.Figure:
    chart_dataframe = dataframe.copy()
    value_column = y
    original_value_column = "_original_value"

    if scale_millions and y in chart_dataframe.columns:
        chart_dataframe[original_value_column] = pd.to_numeric(
            chart_dataframe[y], errors="coerce"
        ).fillna(0.0)
        chart_dataframe[y] = chart_dataframe[original_value_column] / 1_000_000
    else:
        chart_dataframe[y] = pd.to_numeric(chart_dataframe[y], errors="coerce").fillna(0.0)

    if horizontal:
        bar = go.Bar(
            x=chart_dataframe[y],
            y=chart_dataframe[x],
            orientation="h",
            marker=dict(color="#7cc4ff", line=dict(color="#dbeafe", width=1.2)),
            opacity=0.95,
            text=chart_dataframe[y].map(lambda value: f"{value:,.1f} M" if scale_millions else f"{value:,.0f}"),
            textposition="inside",
            insidetextanchor="end",
            textfont=dict(color="#f8fafc", size=12),
            cliponaxis=False,
            hovertext=(
                chart_dataframe[original_value_column].map(lambda value: f"{value:,.0f} FCFA")
                if scale_millions
                else chart_dataframe[y].map(lambda value: f"{value:,.0f}")
            ),
        )
    else:
        bar = go.Bar(
            x=chart_dataframe[x],
            y=chart_dataframe[y],
            marker=dict(color="#7cc4ff", line=dict(color="#dbeafe", width=1.2)),
            opacity=0.95,
            text=chart_dataframe[y].map(lambda value: f"{value:,.1f} M" if scale_millions else f"{value:,.0f}"),
            textposition="inside",
            insidetextanchor="end",
            textfont=dict(color="#f8fafc", size=12),
            cliponaxis=False,
            hovertext=(
                chart_dataframe[original_value_column].map(lambda value: f"{value:,.0f} FCFA")
                if scale_millions
                else chart_dataframe[y].map(lambda value: f"{value:,.0f}")
            ),
        )

    figure = go.Figure(data=[bar])
    figure.update_layout(title=title)

    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e5e7eb",
        height=_recommended_chart_height(chart_dataframe, horizontal=horizontal),
        margin=dict(
            l=140 if horizontal else 40,
            r=32,
            t=64,
            b=110 if not horizontal else 36,
        ),
        bargap=0.22,
        uniformtext_minsize=10,
        uniformtext_mode="hide",
    )
    figure.update_xaxes(
        automargin=True,
        tickangle=0 if horizontal else -32,
        title_standoff=16,
        tickfont=dict(size=11),
        gridcolor="rgba(148, 163, 184, 0.18)",
    )
    figure.update_yaxes(
        automargin=True,
        title_standoff=16,
        tickfont=dict(size=11),
        gridcolor="rgba(148, 163, 184, 0.12)",
    )
    if horizontal:
        figure.update_xaxes(
            tickformat=",.0f",
            separatethousands=True,
            exponentformat="none",
            showexponent="none",
        )
        if scale_millions:
            figure.update_xaxes(title_text=f"{value_column} (M FCFA)")
            figure.update_traces(
                hovertemplate="%{y}<br>Valeur=%{hovertext}<extra></extra>"
            )
        else:
            figure.update_traces(hovertemplate="%{y}<br>Valeur=%{hovertext}<extra></extra>")
    else:
        figure.update_yaxes(
            tickformat=",.0f",
            separatethousands=True,
            exponentformat="none",
            showexponent="none",
        )
        if scale_millions:
            figure.update_yaxes(title_text=f"{value_column} (M FCFA)")
            figure.update_traces(
                hovertemplate="%{x}<br>Valeur=%{hovertext}<extra></extra>"
            )
        else:
            figure.update_traces(hovertemplate="%{x}<br>Valeur=%{hovertext}<extra></extra>")
    return figure


def build_heatmap(
    dataframe: pd.DataFrame,
    row: str,
    column: str,
    value: str,
    title: str,
) -> go.Figure:
    pivot_table = dataframe.pivot_table(
        index=row,
        columns=column,
        values=value,
        aggfunc="sum",
        fill_value=0,
    )

    figure = go.Figure(
        data=go.Heatmap(
            z=pivot_table.values,
            x=list(pivot_table.columns),
            y=list(pivot_table.index),
            colorscale="Blues",
            hoverongaps=False,
        )
    )
    figure.update_layout(
        title=title,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e5e7eb",
        height=max(460, min(900, 180 + len(pivot_table.index) * 26)),
        margin=dict(l=100, r=28, t=64, b=100),
    )
    figure.update_xaxes(automargin=True, tickangle=-32, tickfont=dict(size=11))
    figure.update_yaxes(automargin=True, tickfont=dict(size=11))
    return figure


def build_scatter_chart(
    dataframe: pd.DataFrame,
    x: str,
    y: str,
    size: str,
    color: str,
    hover_name: str,
    title: str,
) -> go.Figure:
    figure = px.scatter(
        dataframe,
        x=x,
        y=y,
        size=size,
        color=color,
        hover_name=hover_name,
        title=title,
        color_continuous_scale=["#f59e0b", "#10b981"],
        size_max=40,
    )
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e5e7eb",
        height=520,
        margin=dict(l=70, r=28, t=64, b=72),
    )
    figure.update_xaxes(automargin=True, title_standoff=16, tickfont=dict(size=11))
    figure.update_yaxes(automargin=True, title_standoff=16, tickfont=dict(size=11))
    return figure


def show_api_error(error_message: str) -> None:
    st.error(error_message)
    st.info(
        "Demarrez d'abord le backend FastAPI avec : "
        "`uvicorn backend.main:app --reload`"
    )
