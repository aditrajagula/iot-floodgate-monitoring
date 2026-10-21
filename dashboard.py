import json
import time
import threading
from collections import deque
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.gridspec import GridSpec
import paho.mqtt.client as mqtt

MQTT_BROKER   = "broker.hivemq.com"
MQTT_PORT     = 8883
MQTT_USERNAME = ""
MQTT_PASSWORD = ""
MQTT_TOPIC    = "samsung/infokosumar/banjir"
USE_TLS       = True

MAX_POINTS = 50
timestamps = deque(maxlen=MAX_POINTS)
jarak_air_data = deque(maxlen=MAX_POINTS)
hujan_persen_data = deque(maxlen=MAX_POINTS)
servo_derajat_data = deque(maxlen=MAX_POINTS)
pompa_status_data = deque(maxlen=MAX_POINTS)

latest_reading = {
    "jarak_cm": None,
    "hujan_persen": 0,
    "status": "MENUNGGU...",
    "servo_derajat": 0,
    "pompa": False,
    "waktu": "--:--:--"
}
data_lock = threading.Lock()
is_connected = False

def on_connect(client, userdata, flags, rc, properties=None):
    global is_connected
    if rc == 0:
        is_connected = True
        print(f"\n[OK] Terhubung ke Broker: {MQTT_BROKER}:{MQTT_PORT}")
        print(f"[OK] Subscribed ke topik: {MQTT_TOPIC}\n")
        client.subscribe(MQTT_TOPIC)
    else:
        is_connected = False
        print(f"[ERROR] Gagal terhubung ke MQTT Broker. Return Code: {rc}")

def on_message(client, userdata, msg):
    try:
        payload_str = msg.payload.decode("utf-8")
        data = json.loads(payload_str)
        now = datetime.now()

        with data_lock:
            jarak = data.get("jarak_cm")
            hujan = data.get("hujan_persen", 0)
            status = data.get("status", "NORMAL")
            servo = data.get("servo_derajat", 0)
            pompa = data.get("pompa", False)

            latest_reading["jarak_cm"] = jarak
            latest_reading["hujan_persen"] = hujan
            latest_reading["status"] = status
            latest_reading["servo_derajat"] = servo
            latest_reading["pompa"] = pompa
            latest_reading["waktu"] = now.strftime("%H:%M:%S")

            timestamps.append(now)
            jarak_air_data.append(jarak if (jarak is not None and jarak >= 0) else 0)
            hujan_persen_data.append(hujan)
            servo_derajat_data.append(servo)
            pompa_status_data.append(1 if pompa else 0)

        jarak_txt = f"{jarak:.1f} cm" if (jarak is not None and jarak >= 0) else "ERROR"
        status_badge = f"[{status:^7}]"
        pompa_badge = "[ON ]" if pompa else "[OFF]"
        print(f"{latest_reading['waktu']} | {status_badge} | Air: {jarak_txt:>8} | Hujan: {hujan:>3}% | Pintu: {servo:>2}° | Pompa: {pompa_badge}")

    except Exception as e:
        print(f"[ERROR] Gagal memproses payload: {e}")

def start_mqtt_client():
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="Python-Dashboard-Subscriber")
    except (AttributeError, TypeError):
        client = mqtt.Client(client_id="Python-Dashboard-Subscriber")

    if USE_TLS:
        client.tls_set()

    if MQTT_USERNAME and len(MQTT_USERNAME) > 0:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    client.on_connect = on_connect
    client.on_message = on_message

    print(f"[*] Menghubungkan ke broker {MQTT_BROKER}:{MQTT_PORT}...")
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_start()
        return client
    except Exception as e:
        print(f"[EXCEPTION] Gagal inisialisasi koneksi MQTT: {e}")
        return None

def run_live_dashboard():
    BG_COLOR       = "#0f172a"
    CARD_BG        = "#1e293b"
    TEXT_MAIN      = "#f8fafc"
    TEXT_MUTED     = "#94a3b8"
    GRID_COLOR     = "#334155"
    COLOR_CYAN     = "#38bdf8"
    COLOR_INDIGO   = "#818cf8"
    COLOR_PURPLE   = "#c084fc"
    COLOR_RED      = "#ef4444"
    COLOR_ORANGE   = "#f59e0b"
    COLOR_GREEN    = "#10b981"

    fig = plt.figure(figsize=(13, 8), layout="constrained", facecolor=BG_COLOR)
    fig.canvas.manager.set_window_title("Samsung IoT - Smart Flood WaterGate Dashboard")

    gs = GridSpec(4, 2, height_ratios=[0.16, 0.40, 1.2, 1.0], figure=fig)
    ax_hdr = fig.add_subplot(gs[0, :])
    ax_hdr.set_facecolor(BG_COLOR)
    ax_hdr.axis("off")

    gs_kpi = gs[1, :].subgridspec(1, 5, wspace=0.08)

    kpi_axes = [fig.add_subplot(gs_kpi[0, i]) for i in range(5)]
    ax_water = fig.add_subplot(gs[2, 0])
    ax_rain  = fig.add_subplot(gs[2, 1])
    ax_act   = fig.add_subplot(gs[3, :])

    def get_responsive_scale():
        fig_w, fig_h = fig.get_size_inches()
        scale = max(0.65, min(1.35, min(fig_w / 12.0, fig_h / 7.5)))
        is_narrow = (fig_w < 9.5)
        return {
            "header": max(9, int(13 * scale)),
            "sub": max(7, int(8.5 * scale)),
            "title": max(8, int(10.5 * scale)),
            "label": max(7, int(8.5 * scale)),
            "kpi_lbl": max(6.5, int(8.5 * scale)),
            "kpi_val": max(9, int(13.5 * scale)),
            "tick": max(6.5, int(8.0 * scale)),
            "legend": max(6.5, int(8.0 * scale)),
            "is_narrow": is_narrow
        }

    def style_chart_ax(ax, title, f):
        ax.set_facecolor(CARD_BG)
        ax.set_title(title, fontsize=f["title"], fontweight="bold", color=TEXT_MAIN, pad=6)
        ax.grid(True, linestyle="--", linewidth=0.6, color=GRID_COLOR, alpha=0.6)
        ax.tick_params(colors=TEXT_MUTED, labelsize=f["tick"], pad=2)
        for spine in ax.spines.values():
            spine.set_color(GRID_COLOR)
            spine.set_linewidth(1.0)

    try:
        while plt.fignum_exists(fig.number):
            with data_lock:
                times = list(timestamps)
                jarak_vals = list(jarak_air_data)
                hujan_vals = list(hujan_persen_data)
                servo_vals = list(servo_derajat_data)
                pompa_vals = list(pompa_status_data)
                curr_status = latest_reading["status"]
                curr_jarak = latest_reading["jarak_cm"]
                curr_hujan = latest_reading["hujan_persen"]
                curr_servo = latest_reading["servo_derajat"]
                curr_pompa = latest_reading["pompa"]
                curr_waktu = latest_reading["waktu"]

            f = get_responsive_scale()

            ax_hdr.clear()
            ax_hdr.set_facecolor(BG_COLOR)
            ax_hdr.axis("off")
            header_text = "SMART FLOOD WATERGATE - REAL-TIME TELEMETRY" if not f["is_narrow"] else "SMART FLOOD WATERGATE"
            ax_hdr.text(
                0.5, 0.65, header_text,
                ha="center", va="center",
                fontsize=f["header"], fontweight="bold", color=TEXT_MAIN
            )
            ax_hdr.text(
                0.5, 0.15, f"Topic: {MQTT_TOPIC}   |   Broker: {MQTT_BROKER}   |   Update: {curr_waktu}",
                ha="center", va="center",
                fontsize=f["sub"], color=TEXT_MUTED
            )

            if curr_status == "BAHAYA":
                status_color, status_bg = COLOR_RED, "#450a0a"
            elif curr_status == "SIAGA":
                status_color, status_bg = COLOR_ORANGE, "#451a03"
            elif curr_status == "NORMAL":
                status_color, status_bg = COLOR_GREEN, "#022c22"
            else:
                status_color, status_bg = TEXT_MUTED, CARD_BG

            jarak_str = f"{curr_jarak:.1f} cm" if (curr_jarak is not None and curr_jarak >= 0) else "MEMBACA..."
            pompa_str = "ON (AKTIF)" if curr_pompa else "OFF"
            pompa_color = COLOR_RED if curr_pompa else TEXT_MUTED
            pompa_bg = "#450a0a" if curr_pompa else CARD_BG

            if f["is_narrow"]:
                cards = [
                    ("STATUS", curr_status, status_color, status_bg),
                    ("JARAK", jarak_str, COLOR_CYAN, "#082f49"),
                    ("HUJAN", f"{curr_hujan}%", COLOR_INDIGO, "#1e1b4b"),
                    ("PINTU", f"{curr_servo}°", COLOR_PURPLE, "#3b0764"),
                    ("POMPA", pompa_str, pompa_color, pompa_bg)
                ]
            else:
                cards = [
                    ("STATUS SISTEM", curr_status, status_color, status_bg),
                    ("JARAK AIR", jarak_str, COLOR_CYAN, "#082f49"),
                    ("CURAH HUJAN", f"{curr_hujan} %", COLOR_INDIGO, "#1e1b4b"),
                    ("PINTU AIR", f"{curr_servo}°", COLOR_PURPLE, "#3b0764"),
                    ("POMPA RELAY", pompa_str, pompa_color, pompa_bg)
                ]

            for idx, (label, val, fg, bg) in enumerate(cards):
                ax = kpi_axes[idx]
                ax.clear()
                ax.set_facecolor(bg)
                ax.set_xticks([])
                ax.set_yticks([])
                for spine in ax.spines.values():
                    spine.set_color(fg)
                    spine.set_linewidth(1.3)

                ax.text(0.5, 0.72, label, ha="center", va="center",
                        fontsize=f["kpi_lbl"], fontweight="bold", color=fg, alpha=0.9)
                ax.text(0.5, 0.30, val, ha="center", va="center",
                        fontsize=f["kpi_val"], fontweight="bold", color=fg)

            ax_water.clear()
            style_chart_ax(ax_water, "Ketinggian Permukaan Air (HC-SR04)", f)
            ax_water.set_ylabel("Jarak Sensor (cm)", color=TEXT_MUTED, fontsize=f["label"])

            if len(times) > 1:
                ax_water.plot(times, jarak_vals, color=COLOR_CYAN, linewidth=2.0, label="Permukaan Air (cm)")
                ax_water.fill_between(times, jarak_vals, color=COLOR_CYAN, alpha=0.15)
                ax_water.axhline(100.0, color=COLOR_ORANGE, linestyle="--", linewidth=1.1, label="Siaga (100cm)")
                ax_water.axhline(60.0, color=COLOR_RED, linestyle="--", linewidth=1.1, label="Bahaya (60cm)")
                ax_water.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=5))
                ax_water.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
                plt.setp(ax_water.get_xticklabels(), rotation=15, ha="right")
                ax_water.legend(loc="upper right", facecolor=CARD_BG, edgecolor=GRID_COLOR, labelcolor=TEXT_MAIN, fontsize=f["legend"])
            else:
                ax_water.text(0.5, 0.5, "Menunggu data...", ha="center", va="center", color=TEXT_MUTED, fontsize=f["label"], transform=ax_water.transAxes)

            ax_rain.clear()
            style_chart_ax(ax_rain, "Intensitas Curah Hujan (%)", f)
            ax_rain.set_ylabel("Hujan (%)", color=TEXT_MUTED, fontsize=f["label"])
            ax_rain.set_ylim(-5, 105)

            if len(times) > 1:
                ax_rain.plot(times, hujan_vals, color=COLOR_INDIGO, linewidth=2.0, label="Curah Hujan (%)")
                ax_rain.fill_between(times, hujan_vals, color=COLOR_INDIGO, alpha=0.15)
                ax_rain.axhline(50.0, color=COLOR_ORANGE, linestyle=":", linewidth=1.1, label="Sedang (50%)")
                ax_rain.axhline(80.0, color=COLOR_RED, linestyle=":", linewidth=1.1, label="Lebat (80%)")
                ax_rain.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=5))
                ax_rain.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
                plt.setp(ax_rain.get_xticklabels(), rotation=15, ha="right")
                ax_rain.legend(loc="upper right", facecolor=CARD_BG, edgecolor=GRID_COLOR, labelcolor=TEXT_MAIN, fontsize=f["legend"])
            else:
                ax_rain.text(0.5, 0.5, "Menunggu data...", ha="center", va="center", color=TEXT_MUTED, fontsize=f["label"], transform=ax_rain.transAxes)

            ax_act.clear()
            style_chart_ax(ax_act, "Aktivitas Kontrol Aktuator (Pintu Air & Pompa)", f)
            ax_act.set_ylabel("Sudut Pintu (°)", color=COLOR_PURPLE, fontsize=f["label"])
            ax_act.set_xlabel("Waktu (HH:MM:SS)", color=TEXT_MUTED, fontsize=f["label"])
            ax_act.set_ylim(-5, 100)

            if len(times) > 1:
                ax_act.step(times, servo_vals, color=COLOR_PURPLE, linewidth=2.0, where="post", label="Pintu Air (0°-90°)")
                pompa_scaled = [p * 90 for p in pompa_vals]
                ax_act.step(times, pompa_scaled, color=COLOR_RED, linestyle="-.", linewidth=1.8, where="post", label="Pompa (ON=90/OFF=0)")
                ax_act.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=6))
                ax_act.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
                plt.setp(ax_act.get_xticklabels(), rotation=15, ha="right")
                ax_act.legend(loc="upper right", facecolor=CARD_BG, edgecolor=GRID_COLOR, labelcolor=TEXT_MAIN, fontsize=f["legend"])
            else:
                ax_act.text(0.5, 0.5, "Menunggu data...", ha="center", va="center", color=TEXT_MUTED, fontsize=f["label"], transform=ax_act.transAxes)

            plt.pause(1.0)

    except KeyboardInterrupt:
        print("\n[*] Menutup dashboard...")
    finally:
        plt.close("all")

if __name__ == "__main__":
    client = start_mqtt_client()
    time.sleep(1)
    run_live_dashboard()
    if client:
        client.loop_stop()
        client.disconnect()
