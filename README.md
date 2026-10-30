# IoT Floodgate Monitoring & Control System

> **Submisi SIC8 (Samsung Innovation Campus) - Stage 2**  
> **Nama Tim:** Dikit Lagi KKN Men

Sistem monitoring ketinggian air dan pengendalian pintu air otomatis berbasis ESP32 menggunakan protokol MQTT, dilengkapi dashboard visualisasi real-time berbasis Python.

## Informasi Tim

Proyek ini disusun dan diajukan sebagai submisi untuk program **Samsung Innovation Campus (SIC) Batch 8 – Stage 2**:

- **Nama Tim:** Dikit Lagi KKN Men
- **Anggota Tim & Kontribusi:**

| No | Nama Anggota | Peran dan Kontribusi |
| :---: | :--- | :--- |
| 1 | **Yuma Hazza Yuditama** | Mengkoordinasikan perencanaan proyek, merumuskan masalah dan tujuan, serta menyusun bagian latar belakang, target pengguna, dan *use case* dalam laporan. |
| 2 | **Reynaldi Bertinus Hutagaol** | Merancang dan menyusun rangkaian simulasi Wokwi, menentukan koneksi komponen ke GPIO ESP32, serta mendokumentasikan komponen dan *wiring*. |
| 3 | **Raffie Aditya Akbar** | Mengembangkan program ESP32, termasuk pembacaan sensor, logika status NORMAL/SIAGA/BAHAYA, pengendalian aktuator, pengiriman telemetri MQTT, serta membuat video demo. |
| 4 | **Syuraih Umar Khotthob** | Mengembangkan dashboard Python berbasis Matplotlib, menguji penerimaan data MQTT dan tampilan grafik, serta membantu mengintegrasikan hasil pengujian dan dokumentasi proyek. |

> **Kontribusi Bersama (Seluruh Anggota):**  
> Membahas rancangan sistem, meninjau hasil simulasi dan pengujian, serta mengevaluasi dan menyepakati isi laporan akhir.

## Fitur Utama

- Monitoring jarak permukaan air secara berkala menggunakan sensor ultrasonik HC-SR04.
- Deteksi intensitas curah hujan menggunakan sensor analog.
- Logika level status otomatis: NORMAL, SIAGA, dan BAHAYA.
- Pengendalian aktuator:
  - Servo pintu air membuka bertahap (0 derajat, 45 derajat, 90 derajat).
  - Pompa air aktif otomatis saat status BAHAYA melalui relay.
  - Alarm buzzer dan indikator LED saat kondisi siaga/bahaya.
- Tampilan status lokal pada layar LCD 16x2 I2C.
- Pengiriman data telemetri melalui protokol MQTT terenkripsi (TLS/SSL).
- Dashboard visualisasi grafis real-time menggunakan Python (Matplotlib).
- Dukungan simulasi perangkat keras langsung dengan Wokwi.

## Pinout ESP32

| Komponen | Pin ESP32 | Keterangan |
| --- | --- | --- |
| HC-SR04 (Trig) | GPIO 5 | Output trigger ultrasonik |
| HC-SR04 (Echo) | GPIO 18 | Input echo ultrasonik |
| Rain Sensor | GPIO 34 | Input analog intensitas hujan |
| Servo Motor | GPIO 13 | Kontrol sudut buka pintu air |
| Relay Pompa | GPIO 4 | Kontrol pompa air (Active Low) |
| Buzzer | GPIO 2 | Alarm peringatan |
| Status LED | GPIO 15 | Indikator status |
| LCD I2C SDA | GPIO 21 | Jalur data I2C |
| LCD I2C SCL | GPIO 22 | Jalur clock I2C |

## Logika Status Sistem

Penentuan status didasarkan pada pembacaan jarak sensor ultrasonik ke permukaan air (HC-SR04) dan intensitas curah hujan analog:

- **NORMAL**: Jarak sensor ke permukaan air aman (> 100 cm) dan curah hujan rendah. Pintu air tertutup (0 derajat), pompa mati, LED dan buzzer nonaktif.
- **SIAGA**: Jarak sensor ke air 60–100 cm atau curah hujan sedang (ADC >= 2048 / hujan >= 50%). Pintu air terbuka sebagian (45 derajat), LED menyala, pompa mati.
- **BAHAYA**: Jarak sensor ke air <= 60 cm atau curah hujan lebat (ADC >= 3276 / hujan >= 80%) atau terjadi kesalahan pembacaan sensor ultrasonik. Pintu air terbuka penuh (90 derajat), pompa aktif menyala, alarm buzzer berbunyi, dan LED menyala.

## Struktur Direktori

```
iot-floodgate-monitoring/
├── include/
│   └── secrets.h          # Konfigurasi WiFi dan MQTT Broker
├── src/
│   └── main.cpp           # Source code firmware ESP32
├── dashboard.py           # Dashboard visualisasi data (Python)
├── diagram.json           # Rangkaian sirkuit simulasi Wokwi
├── platformio.ini         # Konfigurasi dependensi PlatformIO
├── wokwi.toml             # Konfigurasi simulator Wokwi
└── README.md              # Dokumentasi proyek
```

## Panduan Penggunaan

### 1. Firmware ESP32

#### Simulasi Menggunakan Wokwi:
1. Buka proyek pada VS Code yang telah terpasang ekstensi Wokwi Simulator.
2. Tekan `F1` atau `Ctrl + Shift + P`, lalu pilih perintah `Wokwi: Start Simulator` (atau buka file `diagram.json`).
3. Simulasi akan otomatis melakukan proses build dan menjalankan virtual hardware.

#### Upload ke Modul ESP32 Fisik:
1. Sesuaikan konfigurasi SSID, password WiFi, dan broker MQTT pada file `include/secrets.h`.
2. Hubungkan ESP32 ke komputer melalui kabel USB.
3. Jalankan perintah kompilasi dan upload menggunakan PlatformIO CLI:
   ```bash
   pio run --target upload
   ```
4. Buka monitor serial (baud rate 115200):
   ```bash
   pio device monitor
   ```

### 2. Dashboard Python

#### Kebutuhan Paket:
Pastikan Python telah terpasang, kemudian instal dependensi:
```bash
pip install paho-mqtt matplotlib
```

#### Menjalankan Dashboard:
Jalankan skrip dashboard:
```bash
python dashboard.py
```

Dashboard akan berlangganan ke topik MQTT dan menampilkan grafik tren ketinggian air, curah hujan, sudut pintu air, serta status pompa secara real-time.

## Format Payload MQTT

Data telemetri dikirimkan secara berkala setiap 3 detik ke topik `samsung/infokosumar/banjir` dalam format JSON:

```json
{
  "jarak_cm": 45.2,
  "hujan_adc": 3072,
  "hujan_persen": 75,
  "status": "BAHAYA",
  "servo_derajat": 90,
  "pompa": true
}
```

> **Catatan:** Jika sensor ultrasonik mengalami *timeout* atau gagal membaca, nilai `"jarak_cm"` akan dikirim berupa `null`, dan sistem secara otomatis masuk ke kondisi *fail-safe* dengan status `BAHAYA`.
