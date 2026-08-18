import os
import json
import gspread

from dotenv import load_dotenv
from datetime import datetime
from google.oauth2.service_account import Credentials
from datetime import time
from zoneinfo import ZoneInfo


from telegram import (
    Update,
    ReplyKeyboardMarkup,
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


# =========================================================
# CONFIG
# =========================================================

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

OWNER_CHAT_ID = int(
    os.getenv("OWNER_CHAT_ID")
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
WIB = ZoneInfo("Asia/Jakarta")

# =========================================================
# GOOGLE SHEETS
# =========================================================

if os.getenv("GOOGLE_CREDENTIALS"):

    # =========================
    # RAILWAY / HOSTING
    # =========================

    try:
        creds_data = json.loads(
            os.getenv("GOOGLE_CREDENTIALS")
        )

        print("Google credentials: Railway")
        print(
            "Google email:",
            creds_data.get("client_email")
        )
        print(
            "Google key ID:",
            creds_data.get("private_key_id")
        )

        creds = Credentials.from_service_account_info(
            creds_data,
            scopes=SCOPES,
        )

    except Exception as e:
        print("❌ Gagal membaca GOOGLE_CREDENTIALS")
        print(e)
        raise

else:

    # =========================
    # LOCAL
    # =========================

    print("Google credentials: Local")

    creds = Credentials.from_service_account_file(
        "credentials.json",
        scopes=SCOPES,
    )


client = gspread.authorize(creds)

sheet = client.open("keuangan diq").sheet1

print("✅ Google Sheets terhubung:", sheet.title)

# =========================================================
# REKAP
# =========================================================

def buat_rekap():

    rows = sheet.get_all_values()

    masuk = 0
    keluar = 0

    kategori = {}

    for row in rows:

        try:

            jenis = row[1]
            nama_kategori = row[2]
            nominal = int(row[3])

            if jenis == "Masuk":

                masuk += nominal

            elif jenis == "Keluar":

                keluar += nominal

                if nama_kategori not in kategori:

                    kategori[nama_kategori] = 0

                kategori[nama_kategori] += nominal

        except:

            pass

    saldo = masuk - keluar

    teks = (
        "📊 Rekap Keuangan\n\n"
        f"💰 Pemasukan : Rp{masuk:,}\n"
        f"💸 Pengeluaran : Rp{keluar:,}\n"
        f"🏦 Saldo : Rp{saldo:,}\n\n"
    )

    if kategori:

        teks += "📂 Pengeluaran berdasarkan kategori:\n\n"

        for nama, total in kategori.items():

            teks += f"• {nama}: Rp{total:,}\n"

    return teks



async def kirim_rekap_harian(context):

    pesan = buat_rekap()

    data = load_chat_id()

    await context.bot.send_message(
        chat_id=OWNER_CHAT_ID,
        text=pesan,
    )

    partner_id = data["partner"]["chat_id"]

    if partner_id:

        await context.bot.send_message(
            chat_id=partner_id,
            text=pesan,
        )


async def kirim_rekap_bulanan(context):

    if datetime.now().day != 27:

        return

    pesan = "📅 Rekap Bulanan\n\n"

    pesan += buat_rekap()

    data = load_chat_id()

    await context.bot.send_message(
        chat_id=OWNER_CHAT_ID,
        text=pesan,
    )

    partner_id = data["partner"]["chat_id"]

    if partner_id:

        await context.bot.send_message(
            chat_id=partner_id,
            text=pesan,
        )
# =========================================================
# STATE
# =========================================================

def load_state():
    try:
        with open("state.json", "r") as file:
            return json.load(file)
    except:
        return {}


def save_state(data):
    with open("state.json", "w") as file:
        json.dump(data, file)


# =========================================================
# CHAT ID
# =========================================================

def load_chat_id():

    try:

        with open(
            "chat_id.json",
            "r"
        ) as file:

            return json.load(file)

    except:

        return {
            "partner": {
                "chat_id": None
            }
        }


def save_chat_id(data):

    with open(
        "chat_id.json",
        "w"
    ) as file:

        json.dump(data, file)
        


# =========================================================
# HAPUS PESAN PROSES
# =========================================================

async def clear_transaction_messages(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user_id = str(update.message.from_user.id)

    state = load_state()

    if user_id not in state:
        return

    message_ids = state[user_id].get(
        "transaction_messages",
        []
    )

    for message_id in message_ids:

        try:

            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=message_id,
            )

        except Exception:
            pass

    state[user_id]["transaction_messages"] = []

    save_state(state)


# =========================================================
# SIMPAN MESSAGE ID
# =========================================================

def add_transaction_message(
    state,
    user_id,
    message_id,
):

    if "transaction_messages" not in state[user_id]:
        state[user_id]["transaction_messages"] = []

    state[user_id]["transaction_messages"].append(
        message_id
    )


# =========================================================
# PARSE NOMINAL
# =========================================================

def parse_nominal(text):

    text = text.lower().replace(".", "").replace(" ", "")

    if text.endswith("jt"):
        return int(float(text[:-2]) * 1000000)

    if text.endswith("rb"):
        return int(float(text[:-2]) * 1000)

    if text.endswith("k"):
        return int(float(text[:-1]) * 1000)

    return int(text)


# =========================================================
# KEYBOARD UTAMA
# =========================================================

keyboard = [
    ["➕ Masuk", "➖ Keluar"],
    ["💰 Total", "📊 Riwayat"],
]

reply_markup = ReplyKeyboardMarkup(
    keyboard,
    resize_keyboard=True,
)
partner_reply_markup = ReplyKeyboardMarkup(
    [["💰 Total"]],
    resize_keyboard=True,
)

# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    chat_id = update.effective_chat.id

    data = load_chat_id()

    if chat_id == OWNER_CHAT_ID:

        await update.message.reply_text(
            "👑 Selamat datang, Diq.",
            reply_markup=reply_markup,
        )

        return

    if data["partner"]["chat_id"] == chat_id:

        await update.message.reply_text(
            "❤️ Selamat datang.",
            reply_markup=partner_reply_markup,
        )

        return

    await update.message.reply_text(
        "🔒 Akun belum terhubung.\n\n"
        "Ketik /partner untuk menghubungkan akun."
    )

async def partner(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    chat_id = update.effective_chat.id

    if chat_id == OWNER_CHAT_ID:

        await update.message.reply_text(
            "❌ Owner tidak bisa menjadi pasangan."
        )

        return

    data = load_chat_id()

    if data["partner"]["chat_id"] is not None:

        await update.message.reply_text(
            "❌ Pasangan sudah terdaftar."
        )

        return

    data["partner"]["chat_id"] = chat_id

    save_chat_id(data)

    await update.message.reply_text(
        "❤️ Akun berhasil dihubungkan.",
        reply_markup=partner_reply_markup,
    )
# =========================================================
# MESSAGE HANDLER
# =========================================================

async def message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user_id = str(update.message.from_user.id)

    state = load_state()

    if user_id not in state:
        state[user_id] = {}

    text = update.message.text

    chat_id = update.effective_chat.id

    data = load_chat_id()

    is_owner = chat_id == OWNER_CHAT_ID

    is_partner = (
        data["partner"]["chat_id"] == chat_id
    )

    if not is_owner and not is_partner:

        await update.message.reply_text(
            "🔒 Akses ditolak."
        )

        return

    if is_partner and text != "💰 Total":

        await update.message.reply_text(
            "❤️ Kamu hanya bisa melihat saldo."
        )

        return

    # semua kode ➕ Masuk, ➖ Keluar,
    # 💰 Total, 📊 Riwayat, dan seterusnya
    # harus berada di bawah sini
   

    # =====================================================
    # ➕ MASUK
    # =====================================================

    if text == "➕ Masuk":

        state[user_id]["mode"] = "masuk"

        state[user_id]["transaction_messages"] = [
            update.message.message_id
        ]

        save_state(state)

        bot_message = await update.message.reply_text(
            "💰 Masukkan nominal.\n\n"
            
        )

        state = load_state()

        add_transaction_message(
            state,
            user_id,
            bot_message.message_id,
        )

        save_state(state)

        return


    # =====================================================
    # ➖ KELUAR
    # =====================================================

    if text == "➖ Keluar":

        state[user_id]["mode"] = "keluar"

        state[user_id]["transaction_messages"] = [
            update.message.message_id
        ]

        save_state(state)

        bot_message = await update.message.reply_text(
            "💸 Masukkan nominal.\n\n"
            "Contoh:\n"
            "25000\n"
            "25rb\n"
            "1jt"
        )

        state = load_state()

        add_transaction_message(
            state,
            user_id,
            bot_message.message_id,
        )

        save_state(state)

        return


    # =====================================================
    # 💰 TOTAL
    # =====================================================

    if text == "💰 Total":

        rows = sheet.get_all_values()

        masuk = 0
        keluar = 0

        for row in rows:

            try:

                if row[1] == "Masuk":
                    masuk += int(row[3])

                elif row[1] == "Keluar":
                    keluar += int(row[3])

            except:
                pass

        saldo = masuk - keluar

        await update.message.reply_text(
            f"💰 Saldo saat ini:\n\n"
            f"Rp{saldo:,}"
        )

        return


    # =====================================================
    # 📊 RIWAYAT
    # =====================================================

    if text == "📊 Riwayat":

        rows = sheet.get_all_values()

        if not rows:

            await update.message.reply_text(
                "📊 Belum ada transaksi."
            )

            return

        riwayat = []

        for row in rows[-10:]:

            try:

                tanggal = row[0]
                jenis = row[1]
                kategori = row[2]
                nominal = int(row[3])

                simbol = (
                    "➕"
                    if jenis == "Masuk"
                    else "➖"
                )

                riwayat.append(
                    f"{simbol} Rp{nominal:,}\n"
                    f"📂 {kategori}\n"
                    f"🕒 {tanggal}"
                )

            except:
                pass

        if not riwayat:

            await update.message.reply_text(
                "📊 Belum ada transaksi."
            )

            return

        await update.message.reply_text(
            "📊 10 transaksi terakhir:\n\n"
            + "\n\n".join(riwayat)
        )

        return


    # =====================================================
    # MODE MASUK
    # =====================================================

    if state[user_id].get("mode") == "masuk":

        try:

            nominal = parse_nominal(text)

            # Tambahkan pesan user
            add_transaction_message(
                state,
                user_id,
                update.message.message_id,
            )

            sheet.append_row([
                datetime.now().strftime(
                    "%d/%m/%Y %H:%M"
                ),
                "Masuk",
                "Pemasukan",
                nominal,
            ])

            save_state(state)

            # Bersihkan pesan proses
            await clear_transaction_messages(
                update,
                context,
            )

            await update.message.reply_text(
                f"✅ Rp{nominal:,} berhasil ditambahkan.",
                reply_markup=reply_markup,
            )

            state = load_state()

            state[user_id] = {}

            save_state(state)

        except:

            await update.message.reply_text(
                "❌ Nominal tidak valid."
            )

        return


    # =====================================================
    # MODE KELUAR
    # =====================================================

    if state[user_id].get("mode") == "keluar":

        try:

            nominal = parse_nominal(text)

            add_transaction_message(
                state,
                user_id,
                update.message.message_id,
            )

            state[user_id]["nominal"] = nominal

            state[user_id]["mode"] = "kategori"

            save_state(state)

            keyboard_kategori = [
                ["🍜 Makanan", "⛽ Transportasi"],
                ["💳 Cicilan", "🛒 Belanja"],
                ["🎮 Hiburan", "🧾 Tagihan"],
                ["📦 Lainnya"],
            ]

            bot_message = await update.message.reply_text(
                "📂 Pilih kategori.",
                reply_markup=ReplyKeyboardMarkup(
                    keyboard_kategori,
                    resize_keyboard=True,
                ),
            )

            state = load_state()

            add_transaction_message(
                state,
                user_id,
                bot_message.message_id,
            )

            save_state(state)

        except:

            await update.message.reply_text(
                "❌ Nominal tidak valid."
            )

        return


    # =====================================================
    # MODE KATEGORI
    # =====================================================

    if state[user_id].get("mode") == "kategori":

        kategori = (
            text
            .replace("🍜 ", "")
            .replace("⛽ ", "")
            .replace("💳 ", "")
            .replace("🛒 ", "")
            .replace("🎮 ", "")
            .replace("🧾 ", "")
            .replace("📦 ", "")
        )

        nominal = state[user_id]["nominal"]

        add_transaction_message(
            state,
            user_id,
            update.message.message_id,
        )

        save_state(state)

        sheet.append_row([
            datetime.now().strftime(
                "%d/%m/%Y %H:%M"
            ),
            "Keluar",
            kategori,
            nominal,
        ])

        # Bersihkan semua pesan proses
        await clear_transaction_messages(
            update,
            context,
        )

        await update.message.reply_text(
            f"✅ Pengeluaran Rp{nominal:,} berhasil disimpan.",
            reply_markup=reply_markup,
        )

        state = load_state()

        state[user_id] = {}

        save_state(state)

        return


    # =====================================================
    # PESAN TIDAK DIKENALI
    # =====================================================

    await update.message.reply_text(
        "🤔 Aku belum mengerti perintah itu.\n\n"
        "Silakan pilih menu di bawah.",
        reply_markup=reply_markup,
    )


# =========================================================
# RUN BOT
# =========================================================

app = Application.builder().token(TOKEN).build()

app.add_handler(
    CommandHandler(
        "start",
        start
    )
)
app.add_handler(
    CommandHandler(
        "partner",
        partner
    )
)
app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        message_handler,
    )
)

job_queue = app.job_queue

job_queue.run_daily(
    kirim_rekap_harian,
    time=time(
        hour=21,
        minute=0,
        tzinfo=WIB,
    ),
)

job_queue.run_daily(
    kirim_rekap_bulanan,
    time=time(
        hour=21,
        minute=0,
        tzinfo=WIB,
    ),
)

print("Bot berjalan...")

app.run_polling()