import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime
import secrets
import time

st.set_page_config(page_title="Aplikasi Arisan", page_icon="🎉", layout="wide")

# =========================
# State & Utils
# =========================
def init_state():
    st.session_state.setdefault("participants", [])     # daftar semua peserta (unik)
    st.session_state.setdefault("remaining", [])        # peserta yang belum menang pada siklus ini
    st.session_state.setdefault("history", [])          # list of {round, winner, timestamp, seed}
    st.session_state.setdefault("round", 0)             # putaran saat ini (0 -> belum mulai)
    st.session_state.setdefault("last_action", None)    # simpan untuk undo
    st.session_state.setdefault("winner_current", "")   # pemenang saat ini (untuk sinkronisasi)
init_state()

def clean_names(raw_names):
    # Bersihkan, unikkan, urutkan
    names = [str(n).strip() for n in raw_names if str(n).strip() != ""]
    names = pd.unique(pd.Series(names)).tolist()
    names.sort(key=lambda x: x.lower())
    return names

def set_participants(new_names):
    st.session_state.participants = clean_names(new_names)
    st.session_state.remaining = st.session_state.participants.copy()
    st.session_state.history = []
    st.session_state.round = 0
    st.session_state.last_action = None
    st.session_state.winner_current = ""

def make_template_excel() -> bytes:
    df = pd.DataFrame({"nama": ["Ani", "Budi", "Cici", "Dedi"]})
    file = BytesIO()
    with pd.ExcelWriter(file, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Peserta")
    file.seek(0)
    return file.read()

def export_history_to_excel(history):
    if not history:
        return b""
    df = pd.DataFrame([{
        "Putaran": h["round"],
        "Waktu": h["timestamp"],
        "Seed": h["seed"],
        "Pemenang": h["winner"]
    } for h in history])
    file = BytesIO()
    with pd.ExcelWriter(file, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Riwayat")
    file.seek(0)
    return file.read()

def roll_animation(candidates, duration=1.2):
    box = st.empty()
    end_time = time.time() + duration
    rng = np.random.default_rng()
    winner = ""
    while time.time() < end_time and candidates:
        winner = rng.choice(candidates)  # Pilih acak tiap putaran animasi
        box.markdown(f"🎡 {winner}")
        time.sleep(0.05)
    return winner  # kembalikan nama pemenang terakhir dari animasi

def draw_one_winner(seed=None):
    # Ambil satu pemenang dari remaining
    rem = st.session_state.remaining
    if not rem:
        return None, None
    if seed is not None:
        rng = np.random.default_rng(seed)
    else:
        rng = np.random.default_rng()
    idx = int(rng.integers(0, len(rem)))
    return rem[idx], idx

# =========================
# Sidebar: Input Data
# =========================
with st.sidebar:
    st.header("📥 Data Peserta (Nama saja)")
    st.download_button(
        "Unduh Template Excel",
        data=make_template_excel(),
        file_name="template_peserta_arisan_nama.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    up = st.file_uploader("Import Excel/CSV (kolom: nama)", type=["xlsx", "xls", "csv"])
    if up is not None:
        try:
            if up.name.lower().endswith(".csv"):
                df = pd.read_csv(up)
            else:
                df = pd.read_excel(up)
            if "nama" not in [c.strip().lower() for c in df.columns]:
                st.error("File harus memiliki kolom 'nama'.")
            else:
                # normalisasi kolom nama
                cols = {c.lower().strip(): c for c in df.columns}
                df.rename(columns={cols["nama"]: "nama"}, inplace=True)
                set_participants(df["nama"].tolist())
                st.success(f"Berhasil import {len(st.session_state.participants)} nama.")
        except Exception as e:
            st.error(f"Gagal membaca file: {e}")

    st.markdown("---")
    st.subheader("✍️ Input Manual")
    manual = st.text_area("Satu nama per baris", height=180, placeholder="Ani\nBudi\nCici\nDedi")
    col_add1, col_add2 = st.columns([1,1])
    with col_add1:
        if st.button("Tambahkan/Set Ulang dari Teks"):
            names = manual.splitlines()
            set_participants(names)
            st.success(f"Daftar di-set: {len(st.session_state.participants)} peserta.")
    with col_add2:
        if st.button("Bersihkan Semua Data", type="secondary"):
            set_participants([])
            st.success("Bersih.")

# =========================
# Main: Status & Editor
# =========================
st.title("🎉 Aplikasi Arisan")
st.caption("Putaran interaktif: setiap klik memilih 1 pemenang dan mengeluarkannya dari daftar.")

left, right = st.columns([1,1])

with left:
    st.subheader("👥 Peserta")
    if st.session_state.participants:
        edit_df = st.data_editor(
            pd.DataFrame({"nama": st.session_state.participants}),
            num_rows="dynamic",
            use_container_width=True,
            key="editor_peserta"
        )
        # Terapkan perubahan editor (tanpa menghapus riwayat, tapi reset siklus agar adil)
        new_names = edit_df["nama"].astype(str).tolist() if "nama" in edit_df else []
        new_clean = clean_names(new_names)
        if new_clean != st.session_state.participants:
            # jika ada perubahan, mulai siklus baru
            set_participants(new_clean)
            st.info("Data peserta berubah — siklus direset.")
    else:
        st.info("Belum ada peserta. Tambahkan lewat sidebar.")

with right:
    st.subheader("ℹ️ Status")
    tot = len(st.session_state.participants)
    rem = len(st.session_state.remaining)
    st.metric("Total Peserta", tot)
    st.metric("Belum Menang (Sisa)", rem)
    st.metric("Putaran Saat Ini", max(1, st.session_state.round + 1) if rem > 0 else st.session_state.round)

st.markdown("---")

# =========================
# Draw Controls
# =========================
st.subheader("🎲 Putaran Interaktif")

seed_str = st.text_input("Seed (opsional, angka untuk hasil bisa diulang)", value="")
seed_val = None
if seed_str.strip() != "":
    try:
        seed_val = int(seed_str.strip())
    except:
        st.warning("Seed harus bilangan bulat. Dihiraukan.")

col = st.columns([1,1,1,2])

with col[0]:
    if st.button("🎉 KOCOK Pemenang Putaran Ini", type="primary", disabled=len(st.session_state.remaining)==0):
        if len(st.session_state.remaining) == 0:
            st.warning("Tidak ada peserta tersisa.")
        else:
            # animasi
            winner_animated = roll_animation(st.session_state.remaining)
            # pilih pemenang yang sudah sesuai dengan animasi
            seed_to_use = seed_val if seed_val is not None else int.from_bytes(secrets.token_bytes(4), "little")
            winner, idx = draw_one_winner(seed=seed_to_use if seed_val is not None else None)
            if winner is None:
                st.warning("Gagal memilih pemenang.")
            else:
                # catat riwayat dan keluarkan dari remaining
                st.session_state.round += 1
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state.history.append({
                    "round": st.session_state.round,
                    "winner": winner,
                    "timestamp": ts,
                    "seed": seed_to_use if seed_val is not None else ""
                })
                removed = st.session_state.remaining.pop(idx)
                st.session_state.last_action = ("draw", removed)
                st.session_state.winner_current = winner  # Sinkronkan dengan animasi
                st.success(f"🏆 Pemenang Putaran #{st.session_state.round}: **{winner}** ({ts})")
                st.balloons()

with col[1]:
    if st.button("↩️ Batalkan Putaran Terakhir", disabled=(len(st.session_state.history)==0)):
        if st.session_state.history:
            last = st.session_state.history.pop()
            # kembalikan pemenang ke remaining di posisi acak
            name_to_restore = last["winner"]
            insert_pos = int(np.random.default_rng().integers(0, len(st.session_state.remaining)+1)) if st.session_state.remaining else 0
            st.session_state.remaining.insert(insert_pos, name_to_restore)
            st.session_state.round -= 1
            st.session_state.last_action = ("undo", name_to_restore)
            st.info(f"Putaran #{last['round']} dibatalkan. **{name_to_restore}** kembali ke daftar.")

with col[2]:
    if st.button("🔁 Reset Siklus (Semua Kembali Ikut)"):
        st.session_state.remaining = st.session_state.participants.copy()
        st.session_state.round = 0
        st.session_state.history = []
        st.session_state.last_action = ("reset", None)
        st.success("Siklus direset. Semua peserta kembali ikut undian.")

st.markdown("---")

# =========================
# Panels: Sisa & Riwayat
# =========================
a, b = st.columns(2)

with a:
    st.subheader("📝 Sisa Peserta (Belum Menang)")
    if st.session_state.remaining:
        st.dataframe(pd.DataFrame({"nama": st.session_state.remaining}), use_container_width=True, height=280)
    else:
        st.info("Semua peserta sudah menang dalam siklus ini.")

with b:
    st.subheader("📜 Riwayat Pemenang")
    if st.session_state.history:
        hist_df = pd.DataFrame(st.session_state.history)
        hist_df = hist_df[["round", "timestamp", "seed", "winner"]].sort_values("round")
        st.dataframe(hist_df, use_container_width=True, height=280)
        xlsx = export_history_to_excel(st.session_state.history)
        st.download_button("💾 Unduh Riwayat (Excel)",
                           data=xlsx,
                           file_name="riwayat_arisan_nama.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("Belum ada putaran.")

# =========================
# Tips
# =========================
with st.expander("💡 Tips"):
    st.markdown("""
- **Data hanya nama**. Import Excel/CSV dengan kolom `nama` atau input manual satu per baris.
- Setiap klik **KOCOK** memilih **1 pemenang** untuk putaran saat itu, lalu pemenang dikeluarkan dari daftar sisa.
- **Batalkan Putaran Terakhir** untuk mengembalikan pemenang ke daftar.
- **Reset Siklus** mengembalikan semua peserta ke kondisi awal (riwayat dihapus).
- **Seed** opsional bila ingin hasil undian yang **reproducible**.
""")
