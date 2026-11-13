

import csv
import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from functools import wraps
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash
)


# =========================================================
# KONFIGURASI APLIKASI
# =========================================================

app = Flask(__name__)

# Ganti dengan secret key acak sebelum digunakan di lingkungan produksi.
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "ganti-dengan-secret-key-acak-tanicontrol"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CSV_FILE = os.path.join(BASE_DIR, "transaksi.csv")
TRANSAKSI_FILE = CSV_FILE
BUDGET_FILE = os.path.join(BASE_DIR, "budget.csv")
USER_FILE = os.path.join(BASE_DIR, "users.csv")

UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "pdf"}

BLOK_LIST = ["Blok 1", "Blok 2", "Blok 3", "Blok 4"]
FILTER_LIST = ["Semua"] + BLOK_LIST
TRANSAKSI_FIELDS = [
    "Tanggal",
    "Blok",
    "Jenis",
    "Kategori",
    "Nominal",
    "Keterangan",
    "Metode",
    "Bukti",
    "Username"
]

BUDGET_FIELDS = ["Blok", "Budget"]

USER_FIELDS = ["username", "password", "role"]


# =========================================================
# INISIALISASI DATABASE CSV
# =========================================================

def init_csv():
    """Membuat file CSV awal jika belum tersedia."""

    # File transaksi
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=TRANSAKSI_FIELDS)
            writer.writeheader()

    
    else:
        # Migrasi kolom CSV lama agar data sebelumnya tetap aman.
        with open(CSV_FILE, "r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            rows = list(reader)

        # Pastikan semua kolom terbaru tersedia.
        with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=TRANSAKSI_FIELDS,
                extrasaction="ignore"
            )
            writer.writeheader()

            for row in rows:
                clean_row = {
                    field: row.get(field, "")
                    for field in TRANSAKSI_FIELDS
                }
                writer.writerow(clean_row)


    # File budget
    if not os.path.exists(BUDGET_FILE):
        with open(BUDGET_FILE, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=BUDGET_FIELDS)
            writer.writeheader()

            for blok in BLOK_LIST:
                writer.writerow({
                    "Blok": blok,
                    "Budget": 0
                })

    # File user
    if not os.path.exists(USER_FILE):
        default_users = [
            {"username": "admin", "password": "admin123", "role": "admin"},
            {"username": "owner", "password": "owner123", "role": "admin"},
            {"username": "danang", "password": "danang123", "role": "karyawan"},
            {"username": "karyawan", "password": "kerja123", "role": "karyawan"}
        ]

        with open(USER_FILE, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=USER_FIELDS)
            writer.writeheader()
            writer.writerows(default_users)


init_csv()


# =========================================================
# FUNGSI BANTUAN
# =========================================================

def to_number(value):
    """Mengubah nilai nominal menjadi angka dengan aman."""

    if value is None:
        return 0.0

    try:
        cleaned = str(value).strip()
        if not cleaned:
            return 0.0

        # Mendukung format angka dengan pemisah ribuan koma.
        cleaned = cleaned.replace(",", "")
        return float(cleaned)

    except (ValueError, TypeError):
        return 0.0


def get_valid_filter():
    """Mengambil filter blok dan memvalidasi nilainya."""

    selected_blok = request.args.get("blok_filter", "Semua")

    if selected_blok not in FILTER_LIST:
        selected_blok = "Semua"

    return selected_blok


def read_transactions():
    """Membaca semua transaksi dari CSV."""

    if not os.path.exists(CSV_FILE):
        init_csv()

    with open(CSV_FILE, "r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    return rows


def write_transactions(rows):
    """Menulis ulang transaksi dengan struktur kolom standar."""

    with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=TRANSAKSI_FIELDS,
            extrasaction="ignore"
        )
        writer.writeheader()

        for row in rows:
            clean_row = {
                field: row.get(field, "")
                for field in TRANSAKSI_FIELDS
            }
            writer.writerow(clean_row)


def read_budgets():
    """Membaca anggaran setiap blok."""

    budgets = {blok: 0.0 for blok in BLOK_LIST}

    if not os.path.exists(BUDGET_FILE):
        init_csv()

    with open(BUDGET_FILE, "r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        for row in reader:
            blok = row.get("Blok", "")
            if blok in budgets:
                budgets[blok] = to_number(row.get("Budget", 0))

    return budgets


def write_budgets(budgets):
    """Menyimpan anggaran setiap blok."""

    with open(BUDGET_FILE, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=BUDGET_FIELDS)
        writer.writeheader()

        for blok in BLOK_LIST:
            writer.writerow({
                "Blok": blok,
                "Budget": budgets.get(blok, 0)
            })


def get_financial_data(selected_blok="Semua"):
    """Menghitung ringkasan keuangan berdasarkan filter blok."""

    transactions = read_transactions()
    budgets = read_budgets()

    if selected_blok == "Semua":
        filtered = transactions
        total_budget = sum(budgets.values())
    else:
        filtered = [
            row for row in transactions
            if row.get("Blok") == selected_blok
        ]
        total_budget = budgets.get(selected_blok, 0)

    pemasukan = sum(
        to_number(row.get("Nominal"))
        for row in filtered
        if row.get("Jenis", "").strip().lower() == "pemasukan"
    )

    pengeluaran = sum(
        to_number(row.get("Nominal"))
        for row in filtered
        if row.get("Jenis", "").strip().lower() == "pengeluaran"
    )

    saldo = pemasukan - pengeluaran
    sisa_budget = total_budget - pengeluaran

    return {
        "budget": total_budget,
        "pemasukan": pemasukan,
        "pengeluaran": pengeluaran,
        "saldo": saldo,
        "sisa_budget": sisa_budget
    }


def get_chart_data():
    """Menyiapkan data grafik untuk Blok 1 sampai Blok 4."""

    transactions = read_transactions()
    budgets = read_budgets()

    chart_budget = []
    chart_pemasukan = []
    chart_pengeluaran = []
    chart_sisa = []

    for blok in BLOK_LIST:
        rows = [
            row for row in transactions
            if row.get("Blok") == blok
        ]

        pemasukan = sum(
            to_number(row.get("Nominal"))
            for row in rows
            if row.get("Jenis", "").strip().lower() == "pemasukan"
        )

        pengeluaran = sum(
            to_number(row.get("Nominal"))
            for row in rows
            if row.get("Jenis", "").strip().lower() == "pengeluaran"
        )

        budget = budgets.get(blok, 0)

        chart_budget.append(budget)
        chart_pemasukan.append(pemasukan)
        chart_pengeluaran.append(pengeluaran)
        chart_sisa.append(budget - pengeluaran)

    return {
        "chart_budget": chart_budget,
        "chart_pemasukan": chart_pemasukan,
        "chart_pengeluaran": chart_pengeluaran,
        "chart_sisa": chart_sisa
    }


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def save_proof(file):
    """Menyimpan file bukti transaksi dengan nama unik."""

    if not file or not file.filename:
        return ""

    if not allowed_file(file.filename):
        raise ValueError(
            "Format bukti tidak didukung. Gunakan JPG, PNG, WEBP, atau PDF."
        )

    original_name = secure_filename(file.filename)
    extension = original_name.rsplit(".", 1)[1].lower()
    new_filename = f"{uuid.uuid4().hex}.{extension}"

    file.save(os.path.join(UPLOAD_FOLDER, new_filename))

    return new_filename


def delete_proof(filename):
    """Menghapus file bukti jika tersedia."""

    if not filename:
        return

    safe_name = os.path.basename(filename)
    path = os.path.join(UPLOAD_FOLDER, safe_name)

    if os.path.isfile(path):
        os.remove(path)


# =========================================================
# AUTENTIKASI DAN PEMBATASAN AKSES
# =========================================================

def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))

        if session.get("role") != "admin":
            flash("Anda tidak memiliki akses ke halaman admin.", "danger")
            return redirect(url_for("index"))

        return view(*args, **kwargs)

    return wrapped_view


def find_user(username):
    """Mencari akun berdasarkan username."""

    if not os.path.exists(USER_FILE):
        init_csv()

    with open(USER_FILE, "r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        for user in reader:
            if user.get("username") == username:
                return user

    return None


def verify_password(stored_password, entered_password):
    """Mendukung password lama berupa teks biasa dan hash Werkzeug."""

    if not stored_password:
        return False

    if stored_password.startswith(("pbkdf2:", "scrypt:")):
        try:
            return check_password_hash(stored_password, entered_password)
        except ValueError:
            return False

    # Kompatibilitas dengan users.csv versi lama.
    return stored_password == entered_password


# =========================================================
# ROUTE LOGIN DAN AUTENTIKASI PENGGUNA
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    # Menangani proses saat form dikirim (POST)
    if request.method == "POST":
        # Mengambil input dari form dan menghapus spasi berlebih
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # Mencari data user berdasarkan username
        user = find_user(username)

        # Memverifikasi apakah user ada dan passwordnya valid
        if user and verify_password(user.get("password", ""), password):
            session.clear() # Membersihkan sesi lama demi keamanan
            session["user"] = user.get("username")
            session["role"] = user.get("role", "karyawan")

            # Mengarahkan halaman berdasarkan hak akses (role)
            if session["role"] == "admin":
                return redirect(url_for("admin"))

            return redirect(url_for("index"))

        # Jika username atau password salah, berikan notifikasi merah
        flash("Username atau password salah.", "danger")

    # Menampilkan halaman login (GET)
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# =========================================================
# HALAMAN KARYAWAN
# =========================================================



@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    print("INDEX ROUTE TERPANGGIL")
    print("METHOD:", request.method)
    print("USER:", session.get("user"))
    print("ROLE:", session.get("role"))

    if session.get("role") == "admin":
        return redirect(url_for("admin"))

    if request.method == "POST":

        tanggal = request.form.get("tanggal", "").strip()
        blok = request.form.get("blok", "").strip()
        jenis = request.form.get("jenis", "").strip()
        kategori = request.form.get("kategori", "").strip()
        nominal = request.form.get("nominal", "").strip()
        keterangan = request.form.get("keterangan", "").strip()
        metode = request.form.get("metode", "").strip()

        if blok not in BLOK_LIST:
            flash("Blok yang dipilih tidak valid.", "danger")
            return redirect(url_for("index"))

        if jenis not in ["Pemasukan", "Pengeluaran"]:
            flash("Jenis transaksi tidak valid.", "danger")
            return redirect(url_for("index"))

        if to_number(nominal) <= 0:
            flash("Nominal transaksi harus lebih dari nol.", "danger")
            return redirect(url_for("index"))

        bukti = ""

        try:
            bukti = save_proof(request.files.get("bukti"))
        except ValueError as error:
            flash(str(error), "danger")
            return redirect(url_for("index"))

        new_transaction = {
            "Tanggal": tanggal,
            "Blok": blok,
            "Jenis": jenis,
            "Kategori": kategori,
            "Nominal": nominal,
            "Keterangan": keterangan,
            "Metode": metode,
            "Bukti": bukti,
            "Username": session.get("user", "")
        }

        rows = read_transactions()
        rows.append(new_transaction)
        write_transactions(rows)

        session["last_submission"] = {
            "waktu": datetime.now(
                ZoneInfo("Asia/Jakarta")
            ).strftime("%d-%m-%Y %H:%M:%S"),
            "nominal": f"Rp {to_number(nominal):,.0f}".replace(",", "."),
            "keterangan": keterangan
        }

        print("CEK 1 - DATA SESSION:", session.get("last_submission"))

        flash("Transaksi berhasil disimpan.", "success")
        return redirect(url_for("index"))

    # Halaman utama

    print("CEK 2 - SESSION SAAT HALAMAN DIBUKA:", session.get("last_submission"))
    return render_template(
        "index.html",
        last_submission=session.get("last_submission")
    )


# =========================================================
# ADMIN - DASHBOARD
# =========================================================

@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():

    # ==========================================
    # UPDATE BUDGET
    # ==========================================

    if request.method == "POST":

        action = request.form.get("action", "")

        if action == "update_budget":

            target_blok = request.form.get("target_blok", "")
            new_budget = to_number(request.form.get("new_budget", 0))

            if target_blok not in BLOK_LIST:
                flash("Blok budget tidak valid.", "danger")
                return redirect(url_for("admin"))

            if new_budget < 0:
                flash("Budget tidak boleh bernilai negatif.", "danger")
                return redirect(url_for("admin"))

            budgets = read_budgets()
            budgets[target_blok] = new_budget
            write_budgets(budgets)

            flash(f"Budget {target_blok} berhasil diperbarui.", "success")

            return redirect(url_for(
                "admin",
                blok_filter=target_blok
            ))

    # ==========================================
    # FILTER DASHBOARD
    # ==========================================

    selected_blok = get_valid_filter()

    # Data kartu keuangan
    financial = get_financial_data(selected_blok)

    # Data grafik seluruh blok
    chart_data = get_chart_data()

    # Data grafik batang
    if selected_blok == "Semua":
        chart_labels = BLOK_LIST

        chart_budget = chart_data["chart_budget"]
        chart_pemasukan = chart_data["chart_pemasukan"]
        chart_pengeluaran = chart_data["chart_pengeluaran"]
        chart_sisa = chart_data["chart_sisa"]

    else:
        idx = BLOK_LIST.index(selected_blok)

        chart_labels = [selected_blok]
        chart_budget = [chart_data["chart_budget"][idx]]
        chart_pemasukan = [chart_data["chart_pemasukan"][idx]]
        chart_pengeluaran = [chart_data["chart_pengeluaran"][idx]]
        chart_sisa = [chart_data["chart_sisa"][idx]]

    # Data Pie Chart
    all_transactions = read_transactions()

    filtered_transactions = [
        row for row in all_transactions
        if selected_blok == "Semua"
        or row.get("Blok") == selected_blok
    ]

    pengeluaran_kategori = {}

    for row in filtered_transactions:

        if row.get("Jenis", "").strip().lower() != "pengeluaran":
            continue

        kategori = (row.get("Kategori") or "Lainnya").strip()
        nominal = to_number(row.get("Nominal", 0))

        pengeluaran_kategori[kategori] = (
            pengeluaran_kategori.get(kategori, 0) + nominal
        )

    pie_labels = list(pengeluaran_kategori.keys())
    pie_values = list(pengeluaran_kategori.values())

    return render_template(
    "admin.html",
    active_page="dashboard",
    selected_blok=selected_blok,

    budget=financial["budget"],
    pemasukan=financial["pemasukan"],
    pengeluaran=financial["pengeluaran"],
    saldo=financial["saldo"],
    sisa_budget=financial["sisa_budget"],

    # Data grafik batang
    chart_labels=chart_labels,
    chart_budget=chart_budget,
    chart_pemasukan=chart_pemasukan,
    chart_pengeluaran=chart_pengeluaran,
    chart_sisa=chart_sisa,

    # Data pie chart
    pie_labels=pie_labels,
    pie_values=pie_values
)


# =========================================================
# RUTE ADMIN - FITUR LAINNYA
# =========================================================
# =========================================================
# RUTE MENU PENGAJUAN & TRANSAKSI
# =========================================================
@app.route("/admin/pengajuan")
@admin_required
def admin_pengajuan():

    return render_template(
        "admin.html",
        active_page="pengajuan"
    )



@app.route("/admin/transaksi")
@admin_required
def admin_transaksi():

    rows = read_transactions()

    transaksi_list = [
        {**row, "_index": index}
        for index, row in enumerate(rows)
    ]

    # Data pendukung template admin.html
    chart_data = get_chart_data()
    financial = get_financial_data("Semua")

    return render_template(
        "admin.html",
        active_page="transaksi",

        transaksi=transaksi_list,

        # Data dashboard agar tidak Undefined
        selected_blok="Semua",

        budget=financial["budget"],
        pemasukan=financial["pemasukan"],
        pengeluaran=financial["pengeluaran"],
        saldo=financial["saldo"],
        sisa_budget=financial["sisa_budget"],

        chart_labels=BLOK_LIST,
        chart_budget=chart_data["chart_budget"],
        chart_pemasukan=chart_data["chart_pemasukan"],
        chart_pengeluaran=chart_data["chart_pengeluaran"],
        chart_sisa=chart_data["chart_sisa"],

        pie_labels=[],
        pie_values=[]
    )



# ==========================================
# Rute Menu Laporan & Pengaturan (Baru)
# ==========================================

# Rute Menu Laporan
@app.route('/admin/laporan')
def admin_laporan():
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    # Membaca data transaksi untuk laporan
    rows = []
    if os.path.exists(TRANSAKSI_FILE):
        with open(TRANSAKSI_FILE, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
    return render_template('admin_laporan.html', rows=rows, active_page='laporan')

# Rute Menu Pengaturan
@app.route('/admin/pengaturan')
def admin_pengaturan():
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
        
    return render_template('admin_pengaturan.html', active_page='pengaturan')



# =========================================================
# EDIT TRANSAKSI
# =========================================================

@app.route("/edit/<int:index>", methods=["GET", "POST"])
@admin_required
def edit(index):

    rows = read_transactions()

    if index < 0 or index >= len(rows):
        flash("Data transaksi tidak ditemukan.", "danger")
        return redirect(url_for("admin_transaksi"))

    transaction = rows[index]

    if request.method == "POST":

        tanggal = request.form.get("tanggal", "").strip()
        blok = request.form.get("blok", "").strip()
        jenis = request.form.get("jenis", "").strip()
        kategori = request.form.get("kategori", "").strip()
        nominal = request.form.get("nominal", "").strip()
        keterangan = request.form.get("keterangan", "").strip()
        metode = request.form.get("metode", "").strip()

        if blok not in BLOK_LIST:
            flash("Blok yang dipilih tidak valid.", "danger")
            return redirect(url_for("edit", index=index))

        if jenis not in ["Pemasukan", "Pengeluaran"]:
            flash("Jenis transaksi tidak valid.", "danger")
            return redirect(url_for("edit", index=index))

        if to_number(nominal) <= 0:
            flash("Nominal transaksi harus lebih dari nol.", "danger")
            return redirect(url_for("edit", index=index))

        old_proof = transaction.get("Bukti", "")
        new_proof = old_proof

        uploaded_file = request.files.get("bukti")

        try:
            if uploaded_file and uploaded_file.filename:
                new_proof = save_proof(uploaded_file)

        except ValueError as error:
            flash(str(error), "danger")
            return redirect(url_for("edit", index=index))

        rows[index] = {
            "Tanggal": tanggal,
            "Blok": blok,
            "Jenis": jenis,
            "Kategori": kategori,
            "Nominal": nominal,
            "Keterangan": keterangan,
            "Metode": metode,
            "Bukti": new_proof,
            "Username": transaction.get("Username", "")
        }

        write_transactions(rows)

        if new_proof != old_proof:
            delete_proof(old_proof)

        flash("Transaksi berhasil diperbarui.", "success")
        return redirect(url_for("admin_transaksi"))

    return render_template(
        "edit.html",
        transaksi=transaction,
        data=transaction,
        index=index
    )


# =========================================================
# HAPUS TRANSAKSI
# =========================================================

@app.route("/hapus/<int:index>", methods=["POST", "GET"])
@admin_required
def hapus(index):

    rows = read_transactions()

    if index < 0 or index >= len(rows):
        flash("Data transaksi tidak ditemukan.", "danger")
        return redirect(url_for("admin_transaksi"))

    # Ambil bukti sebelum baris dihapus.
    proof = rows[index].get("Bukti", "")

    rows.pop(index)
    write_transactions(rows)

    delete_proof(proof)

    flash("Transaksi berhasil dihapus.", "success")
    return redirect(url_for("admin_transaksi"))
# ==========================================

# ==========================================
# Rute untuk Halaman Input Karyawan
# ==========================================

@app.route('/karyawan', methods=['GET', 'POST'])
@login_required
def karyawan():

    if request.method == 'POST':

        tanggal = request.form.get('tanggal', '').strip()
        blok = request.form.get('blok', '').strip()
        jenis = request.form.get('jenis', '').strip()
        kategori = request.form.get('kategori', '').strip()
        nominal = request.form.get('nominal', '').strip()
        keterangan = request.form.get('keterangan', '').strip()
        metode = request.form.get('metode', '').strip()

        # Format transaksi baru
        new_row = {
            "Tanggal": tanggal,
            "Blok": blok,
            "Jenis": jenis,
            "Kategori": kategori,
            "Nominal": nominal,
            "Keterangan": keterangan,
            "Metode": metode,
            "Bukti": "",
            "Username": session.get("user", "")
        }

        # Simpan menggunakan struktur database CSV standar
        rows = read_transactions()
        rows.append(new_row)
        write_transactions(rows)

        return redirect(url_for('karyawan'))

    # Tampilkan halaman input karyawan
    return render_template(
        'index.html',
        active_page='karyawan'
    )


# =========================================================
# MANIFEST
# =========================================================

@app.route("/manifest.json")
def manifest():
    return app.send_static_file("manifest.json")


# =========================================================
# ERROR HANDLER
# =========================================================

@app.errorhandler(404)
def page_not_found(error):
    return "Halaman tidak ditemukan (404).", 404


@app.errorhandler(500)
def internal_server_error(error):
    return "Terjadi kesalahan pada server (500).", 500


# =========================================================
# JALANKAN APLIKASI
# =========================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
