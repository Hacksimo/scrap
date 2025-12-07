import streamlit as st
import os
import subprocess
import threading
import json
import pandas as pd
from db import (
    create_tables, save_request, get_all_requests,
    get_request_by_id, update_request, delete_request
)

current_dir = os.path.dirname(__file__)

# ======================================================
# INITIAL SETUP
# ======================================================
create_tables()

scraper_path = os.path.join(current_dir, "..", "scrapper")

st.set_page_config(page_title="Scraper Manager", page_icon="🕷️", layout="wide")

if "running_jobs" not in st.session_state:
    st.session_state.running_jobs = {}

# ======================================================
# F U N C I O N E S
# ======================================================

def background_scraper(request_name, urls, fields, spider_mode, max_pages, callback):

    args = [
        "scrapy", "crawl", "contact",
        "-a", f"urls={','.join(urls)}",
        "-a", f"fields={','.join(fields)}",
        "-a", f"spider_mode={spider_mode}",
        "-a", f"max_pages={max_pages}",
    ]

    proc = subprocess.Popen(
        args,
        cwd=scraper_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    contacts = []

    for line in proc.stdout:
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                item = json.loads(line)
                for c in item.get("contacts", []):
                    c["url"] = item.get("url", "")
                    contacts.append(c)
            except:
                pass

    proc.wait()
    callback(request_name, contacts)


def on_scraper_finished(request_name, contacts):
    save_request(request_name, contacts)
    st.session_state.running_jobs.pop(request_name, None)


# ======================================================
# SIDEBAR
# ======================================================

img_path = os.path.join(current_dir, "resources", "logo3.png")
st.sidebar.image(img_path, use_container_width=True)
choice = st.sidebar.radio("Selecciona una sección",
    ["Nueva petición", "Historial", "Editar petición"])

# ======================================================
# NUEVA PETICIÓN
# ======================================================
if choice == "Nueva petición":
    st.title("Crear una nueva petición de scraping")

    col1, col2 = st.columns([2, 3])
    with col1:
        request_name = st.text_input("Nombre de la petición")
        spider_mode = st.toggle("🕷️ Modo Araña")
        max_pages = st.number_input("Máximo de páginas", min_value=0, value=0) if spider_mode else 0

        fields = st.multiselect(
            "Campos a extraer",
            ["email", "phone", "name", "role"],
            default=["email", "phone", "name", "role"]
        )

    with col2:
        urls_text = st.text_area(
            "URLs objetivo",
            placeholder="Introduce una URL por línea...",
            height=200
        )

    st.markdown("---")

    is_running = request_name in st.session_state.running_jobs

    if st.button("🚀 Ejecutar scraping",
                 disabled=is_running,
                 use_container_width=True):

        if not request_name.strip():
            st.error("⚠️ Debes asignar un nombre.")
            st.stop()

        urls = [u.strip() for u in urls_text.split("\n") if u.strip()]

        st.session_state.running_jobs[request_name] = True

        thread = threading.Thread(
            target=background_scraper,
            args=(request_name, urls, fields, spider_mode, max_pages, on_scraper_finished)
        )
        thread.daemon = True
        thread.start()

        st.success("🕷️ Scraping ejecutándose en background. Puedes ir al historial.")


# ======================================================
# HISTORIAL
# ======================================================
elif choice == "Historial":
    st.title("Historial de peticiones")

    all_requests = get_all_requests()

    if not all_requests:
        st.info("No hay solicitudes guardadas.")
        st.stop()

    col_left, col_right = st.columns([1, 4])

    with col_left:
        st.subheader("Peticiones")

        for row in all_requests:
            req_id, nombre, data_json, date_str = row
            if st.button(nombre, key=f"req_{req_id}", use_container_width=True):
                st.session_state.selected_request = req_id
                st.session_state.original_df = None

    with col_right:
        if "selected_request" not in st.session_state:
            st.info("Selecciona una petición.")
            st.stop()

        req = get_request_by_id(st.session_state.selected_request)
        if req:
            req_id, nombre, data_json, date_str = req
            parsed = json.loads(data_json)

            st.subheader(nombre)
            st.caption(f"📅 Fecha: {date_str}")

            df = pd.DataFrame(parsed["contacts"])
            df["_delete"] = False

            if st.button("⬇️ Exportar como Excel"):
                excel = df.drop(columns=["_delete"]).to_excel(index=False)
                st.download_button(
                    "Descargar Excel",
                    excel,
                    file_name=f"{nombre}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            edited_df = st.data_editor(
                df,
                num_rows="dynamic",
                use_container_width=True,
                height=600
            )

            edited_df = edited_df[edited_df["_delete"] == False].drop(columns=["_delete"])

            if st.button("🗑️ Eliminar petición", type="secondary"):
                if st.confirm("¿Seguro que quieres eliminar esta petición? Esta acción no se puede deshacer."):
                    delete_request(req_id)
                    st.success("Petición eliminada.")
                    st.session_state.selected_request = None
                    st.stop()

            if st.button("💾 Guardar cambios"):
                update_request(req_id, nombre, edited_df.to_dict(orient="records"))
                st.success("Cambios guardados.")


# ======================================================
# EDITAR PETICIÓN
# ======================================================
elif choice == "Editar petición":
    st.title("✏️ Editar petición")
    st.info("Esta sección permanece igual que antes.")
