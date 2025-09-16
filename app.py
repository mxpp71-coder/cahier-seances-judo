import streamlit as st
import pandas as pd
from datetime import date
import io

# ============== CONFIG ==============
st.set_page_config(page_title="Cahier de séances Judo", page_icon="🥋", layout="centered")
SHEET_NAME = st.secrets["gsheets"]["sheet_name"]
WORKSHEET  = st.secrets["gsheets"]["worksheet"]

# ============== PASSWORD (simple) ==============
pwd = st.text_input("Mot de passe", type="password")
if pwd != st.secrets.get("APP_PASSWORD", ""):
    st.stop()

# ============== GOOGLE SHEETS CLIENT ==============
import gspread
from google.oauth2.service_account import Credentials

def gs_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    return gspread.authorize(creds)

# ============== DATA ACCESS HELPERS ==============
COLUMNS = ["id","date","saison","public","objectif","tags","duree_min",
           "echauffement","corps","retour","materiel","bilan","effectif","rpe","auteur"]

def to_season(d: date):
    return f"{d.year-1}-{d.year}" if d.month < 7 else f"{d.year}-{d.year+1}"

@st.cache_data(ttl=10)
def load_df():
    c = gs_client()
    sh = c.open(SHEET_NAME)
    try:
        ws = sh.worksheet(WORKSHEET)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(WORKSHEET, rows=1000, cols=len(COLUMNS))
        ws.append_row(COLUMNS)
    rows = ws.get_all_records()
    df = pd.DataFrame(rows, columns=COLUMNS)
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df

def save_df(df: pd.DataFrame):
    c = gs_client()
    sh = c.open(SHEET_NAME)
    ws = sh.worksheet(WORKSHEET)
    ws.clear()
    ws.append_row(COLUMNS)
    df2 = df.copy()
    if "date" in df2.columns:
        df2["date"] = pd.to_datetime(df2["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    ws.append_rows(df2.fillna("").astype(str).values.tolist())
    load_df.clear()
# ---------- Helpers pour éditer une séance ----------
def _open_ws_seances():
    c = gs_client()
    sh = c.open(SHEET_NAME)  # on ouvre par NOM (comme ton app Judo actuelle)
    return sh.worksheet(WORKSHEET)

def _a1_col_letters(n):
    # 1 -> A, 26 -> Z, 27 -> AA ... (au cas où tu ajoutes des colonnes un jour)
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s

def _find_row_by_id(ws, session_id):
    # cherche l'ID uniquement dans la 1re colonne (A), où l'entête est "id"
    col = ws.col_values(1)  # 1 = colonne A
    for i, v in enumerate(col, start=1):
        if i == 1:
            continue  # ligne d'entête
        if str(v).strip() == str(session_id).strip():
            return i
    return None

def next_id(df: pd.DataFrame) -> int:
    return int(df["id"].max() + 1) if not df.empty else 1

# ============== CONSTANTES UI ==============
PUBLICS = [
    "Baby Judo (4–5)", "Mini-poussins (6–7)", "Poussins (8–9)",
    "Benjamins (10–11)", "Minimes (12–13)", "Cadets (14–15)",
    "Juniors (16–20)", "Adultes", "Loisir", "Compétiteurs"
]
OBJECTIFS_PRESETS = [
    "Ukemi (chutes)", "Nage-waza", "Ne-waza", "Randori", "Kumi-kata",
    "Coordination/jeux", "Prépa compét", "Rituels/étiquette", "Assouplissements"
]

# ============== UI ==============
st.title("🥋 Cahier de séances — Judo")
st.caption("Note tes séances par date, public, objectifs, contenu et bilan. Filtre et exporte pour suivre la saison.")

tab_saisie, tab_consult = st.tabs(["➕ Nouvelle séance", "🔎 Consulter / Exporter"])

with tab_saisie:
    df = load_df()
    st.subheader("Saisie")
    with st.form("form_seance", clear_on_submit=True):
        c1, c2 = st.columns(2)
        d = c1.date_input("Date", value=date.today(), format="DD/MM/YYYY")
        public = c2.selectbox("Public", PUBLICS, index=2)

        obj = st.multiselect("Objectifs (choix multiples)", OBJECTIFS_PRESETS, default=[])
        tags = st.text_input("Tags (virgules)", placeholder="ukemi, jeux, osaekomi…")

        c3, c4, c5 = st.columns([1,1,1])
        duree = c3.number_input("Durée (min)", min_value=15, max_value=180, value=60, step=5)
        effectif = c4.number_input("Effectif", min_value=1, max_value=60, value=15, step=1)
        rpe = c5.slider("Intensité perçue (RPE 1–10)", 1, 10, 5)

        st.markdown("**Contenu**")
        echauffement = st.text_area("Échauffement", height=100)
        corps = st.text_area("Corps de séance", height=180)
        retour = st.text_area("Retour au calme", height=100)
        materiel = st.text_area("Matériel", height=70)
        bilan = st.text_area("Bilan (ce qui a marché / à revoir)", height=100)
        auteur = st.text_input("Auteur (optionnel)", value="")

        submitted = st.form_submit_button("💾 Enregistrer la séance")
        if submitted:
            row = {
                "id": next_id(df),
                "date": pd.to_datetime(d),
                "saison": to_season(d),
                "public": public,
                "objectif": "; ".join(obj),
                "tags": tags.strip(),
                "duree_min": int(duree),
                "echauffement": echauffement.strip(),
                "corps": corps.strip(),
                "retour": retour.strip(),
                "materiel": materiel.strip(),
                "bilan": bilan.strip(),
                "effectif": int(effectif),
                "rpe": int(rpe),
                "auteur": auteur.strip(),
            }
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
            save_df(df)
            st.success("Séance enregistrée ✅")

    # Duplication rapide
    st.divider()
    st.subheader("✨ Dupliquer une séance passée")
    df = load_df()
    if not df.empty:
        choices = df.sort_values("date", ascending=False).head(30)
        label = choices.apply(lambda r: f"{r['date'].date()} — {r['public']} — {str(r['objectif'])[:40]}", axis=1)
        idx = st.selectbox("Séances récentes", options=choices.index.tolist(), format_func=lambda i: label.loc[i])
        if st.button("📋 Copier comme nouvelle (date du jour)"):
            base = choices.loc[idx].to_dict()
            base["id"] = next_id(df)
            base["date"] = pd.to_datetime(date.today())
            base["saison"] = to_season(date.today())
            df = pd.concat([df, pd.DataFrame([base])], ignore_index=True)
            save_df(df)
            st.success("Séance dupliquée ✅")

with tab_consult:
    df = load_df()
    if df.empty:
        st.info("Aucune séance pour le moment. Ajoute-en depuis l’onglet **Nouvelle séance**.")
        st.stop()

    st.subheader("Filtres")
    c1, c2, c3 = st.columns(3)
    saisons = sorted(df["saison"].dropna().unique())
    saison_sel = c1.selectbox("Saison", saisons, index=len(saisons)-1 if saisons else 0)
    publics = ["Tous"] + list(sorted(df["public"].dropna().unique()))
    public_sel = c2.selectbox("Public", publics, index=0)
    mot_cle = c3.text_input("Recherche mot-clé", placeholder="ukemi, o-goshi, jeu…")

    dff = df[df["saison"] == saison_sel].copy()
    if public_sel != "Tous":
        dff = dff[dff["public"] == public_sel]
    if mot_cle.strip():
        key = mot_cle.lower()
        dff = dff[dff.apply(lambda r: key in str(r.to_dict()).lower(), axis=1)]

    dff = dff.sort_values("date", ascending=False)

    st.subheader("Résultats")
    show = dff[["id","date","public","objectif","duree_min","effectif","rpe","tags"]].copy()
    show["date"] = pd.to_datetime(show["date"], errors="coerce").dt.strftime("%d/%m/%Y")
    st.dataframe(show, use_container_width=True, hide_index=True)
# ----- Mode édition -----
st.divider()
st.subheader("✏️ Modifier une séance")

if dff.empty:
    st.caption("Aucune séance à éditer avec les filtres actuels.")
else:
    # menu pour choisir la séance (dans les résultats filtrés)
    choix = dff.copy()
    choix["label"] = choix.apply(
        lambda r: f"{int(r['id'])} — {pd.to_datetime(r['date']).strftime('%d/%m/%Y')} — {r['public']}", axis=1
    )
    selected_id = st.selectbox(
        "Choisis une séance",
        options=choix["id"].tolist(),
        format_func=lambda sid: choix.loc[choix["id"]==sid, "label"].values[0]
    )

    # récupérer la ligne complète dans le df global
    row = df.loc[df["id"]==selected_id].iloc[0]

    with st.form("edit_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        new_date   = c1.date_input("Date", value=pd.to_datetime(row["date"]).date(), format="DD/MM/YYYY")
        # PUBLICS existe déjà plus haut dans ton app
        try:
            pub_index = PUBLICS.index(row["public"]) if pd.notna(row["public"]) else 0
        except ValueError:
            pub_index = 0
        new_public = c2.selectbox("Public", PUBLICS, index=pub_index)

        new_obj    = st.text_input("Objectifs (texte libre)", value=str(row.get("objectif","")))
        new_tags   = st.text_input("Tags", value=str(row.get("tags","")))
        c3, c4, c5 = st.columns(3)
        new_duree    = c3.number_input("Durée (min)", min_value=15, max_value=180, value=int(row.get("duree_min",60)), step=5)
        new_effectif = c4.number_input("Effectif", min_value=1, max_value=60, value=int(row.get("effectif",15)), step=1)
        base_rpe = int(row.get("rpe",5)) if pd.notna(row.get("rpe",5)) else 5
        new_rpe      = c5.slider("RPE (1–10)", 1, 10, base_rpe)

        st.markdown("**Contenu**")
        new_ech   = st.text_area("Échauffement", value=str(row.get("echauffement","")), height=100)
        new_corps = st.text_area("Corps de séance", value=str(row.get("corps","")), height=180)
        new_ret   = st.text_area("Retour au calme", value=str(row.get("retour","")), height=100)
        new_mat   = st.text_area("Matériel", value=str(row.get("materiel","")), height=70)
        new_bilan = st.text_area("Bilan", value=str(row.get("bilan","")), height=100)
        new_auteur= st.text_input("Auteur", value=str(row.get("auteur","")))

        submitted_edit = st.form_submit_button("💾 Enregistrer les modifications")

        if submitted_edit:
            # 1) recalcul saison (fonction to_season déjà définie dans ton app)
            new_saison = to_season(new_date)

            # 2) reconstruire la ligne dans l'ordre exact de COLUMNS
            updated = {
                "id": int(selected_id),
                "date": pd.to_datetime(new_date).strftime("%Y-%m-%d"),
                "saison": new_saison,
                "public": new_public,
                "objectif": new_obj.strip(),
                "tags": new_tags.strip(),
                "duree_min": int(new_duree),
                "echauffement": new_ech.strip(),
                "corps": new_corps.strip(),
                "retour": new_ret.strip(),
                "materiel": new_mat.strip(),
                "bilan": new_bilan.strip(),
                "effectif": int(new_effectif),
                "rpe": int(new_rpe),
                "auteur": new_auteur.strip(),
            }

            # 3) écrire dans Google Sheets à la bonne ligne
            ws = _open_ws_seances()
            row_idx = _find_row_by_id(ws, selected_id)
            if row_idx is None:
                st.error("Séance introuvable dans Google Sheets.")
            else:
                end_col = _a1_col_letters(len(COLUMNS))
                a1_range = f"A{row_idx}:{end_col}{row_idx}"
                ws.update(a1_range, [[updated.get(k,"") for k in COLUMNS]])

                # 4) refresh
                load_df.clear()
                st.success("Modifications enregistrées ✅")
                st.experimental_rerun()

    st.markdown("### Détails des séances")
    for _, row in dff.iterrows():
        header = f"📅 {pd.to_datetime(row['date']).strftime('%d/%m/%Y')} — 👥 {row['public']} — 🎯 {row['objectif'] or '—'}"
        with st.expander(header):
            c1, c2, c3 = st.columns(3)
            c1.metric("Durée", f"{int(row.get('duree_min',0))} min")
            c2.metric("Effectif", str(int(row.get('effectif',0))))
            c3.metric("RPE", str(int(row.get('rpe',0))))
            st.write("**Tags :**", row.get("tags","—") or "—")
            st.write("**Matériel :**", row.get("materiel","—") or "—")
            st.write("**Échauffement :**\n", row.get("echauffement","—") or "—")
            st.write("**Corps de séance :**\n", row.get("corps","—") or "—")
            st.write("**Retour au calme :**\n", row.get("retour","—") or "—")
            st.write("**Bilan :**\n", row.get("bilan","—") or "—")
            st.caption(f"ID: {int(row['id'])} — Saison: {row['saison']} — Auteur: {row.get('auteur','—')}")
    st.divider()
    st.subheader("Export")
    st.download_button(
        "⬇️ Export CSV (filtres appliqués)",
        data=dff.to_csv(index=False).encode("utf-8"),
        file_name=f"seances_{saison_sel}.csv",
        mime="text/csv"
    )
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        dff.to_excel(writer, index=False, sheet_name="Seances")
    st.download_button(
        "⬇️ Export Excel (xlsx)",
        data=out.getvalue(),
        file_name=f"seances_{saison_sel}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

st.caption("Données stockées dans Google Sheets. Partage l’URL de l’app pour y accéder depuis n’importe où (pense au mot de passe).")
