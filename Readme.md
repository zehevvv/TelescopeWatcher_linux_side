# 🔭 TelescopeWatcher — Raspberry Pi Network Setup

> **Device:** Raspberry Pi 5 · Raspberry Pi OS Lite
> **Goal:** Stream camera data via MJPEG-streamer, controlled remotely from Android or PC

---

## 📡 Choose Your Connection Method

Pick **one** of the two options below based on your setup:

| | 🔵 Option A — Wi-Fi Hotspot | 🟢 Option B — Ethernet Direct Connection |
|---|---|---|
| **How it works** | RPi creates a Wi-Fi network, client connects wirelessly | RPi acts as a router over Ethernet cable, Wi-Fi stays normal |
| **Wi-Fi on RPi** | ❌ Disabled (used for hotspot) | ✅ Works normally |
| **Client connects via** | Wi-Fi | Ethernet cable |
| **RPi IP address** | `192.168.4.1` | `192.168.4.1` |
| **Best for** | Mobile / outdoor use, no router available | Stationary setup, RPi needs internet |
| **Survives reboot?** | ✅ Yes | ✅ Yes |

---

## 🔵 Option A: Wi-Fi Hotspot

Turns the RPi into a Wi-Fi Access Point. The PC/Android connects to the RPi's own Wi-Fi network.

> ⚠️ **The RPi will NOT have normal Wi-Fi internet in this mode.**

### Step 1 · Stop Wi-Fi from connecting normally

```bash
sudo nmcli device disconnect wlan0
```

Edit the NetworkManager config:

```bash
sudo nano /etc/NetworkManager/NetworkManager.conf
```

Add this at the end:

```ini
[keyfile]
unmanaged-devices=interface-name:wlan0
```

Restart NetworkManager:

```bash
sudo systemctl restart NetworkManager
```

### Step 2 · Install required packages

```bash
sudo apt-get update
sudo apt install hostapd dnsmasq
```

### Step 3 · Configure hostapd

```bash
sudo nano /etc/hostapd/hostapd.conf
```

Paste:

```ini
interface=wlan0
driversupport=nl80211
ssid=RaspberryPiCam
hw_mode=g
channel=6
auth_algs=1
wmm_enabled=0
```

### Step 4 · Point hostapd to the config file

```bash
sudo nano /etc/default/hostapd
```

Find `#DAEMON_CONF=""` and change it to:

```
DAEMON_CONF="/etc/hostapd/hostapd.conf"
```

### Step 5 · Enable and start hostapd

```bash
sudo systemctl unmask hostapd
sudo systemctl enable hostapd
sudo systemctl restart hostapd
```

### Step 6 · Configure dnsmasq for DHCP

```bash
sudo nano /etc/dnsmasq.d/raspi-hotspot.conf
```

Paste:

```ini
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
address=/gateway/192.168.4.1
```

Disable the default config (recommended):

```bash
sudo mv /etc/dnsmasq.conf /etc/dnsmasq.conf.backup
```

### Step 7 · Enable and restart dnsmasq

```bash
sudo systemctl enable dnsmasq
sudo systemctl restart dnsmasq
```

Verify it's running:

```bash
journalctl -u dnsmasq
```

### Step 8 · Assign static IP to wlan0

```bash
sudo ip addr add 192.168.4.1/24 dev wlan0
```

### ✅ Done! Connect from PC/Android

Connect to Wi-Fi network **`RaspberryPiCam`** → RPi is at **`192.168.4.1`**

---

### 🔄 How to disable the hotspot and restore normal Wi-Fi

```bash
sudo systemctl stop hostapd
sudo systemctl disable hostapd
sudo systemctl stop dnsmasq
sudo systemctl disable dnsmasq
sudo ip addr del 192.168.4.1/24 dev wlan0
```

Edit NetworkManager config and remove the `[keyfile]` section:

```bash
sudo nano /etc/NetworkManager/NetworkManager.conf
```

**Remove** these lines:

```ini
[keyfile]
unmanaged-devices=interface-name:wlan0
```

Restart and reconnect to Wi-Fi:

```bash
sudo systemctl restart NetworkManager
sudo nmcli device wifi connect "YOUR_WIFI_NAME" password "YOUR_WIFI_PASSWORD"
```

---

## 🟢 Option B: Ethernet Direct Connection (Router Mode)

The RPi acts as a router over the Ethernet cable. The PC plugs in and gets an IP automatically.

> ✅ **Wi-Fi on the RPi continues to work normally.**
> ✅ **No configuration needed on the PC — just plug in the cable.**

### Step 1 · Set a static IP on eth0

```bash
sudo nmcli connection add type ethernet con-name eth0-router ifname eth0 \
  ipv4.addresses 192.168.4.1/24 \
  ipv4.method manual

sudo nmcli connection modify eth0-router connection.autoconnect yes
sudo nmcli connection up eth0-router
```

This gives the RPi the IP `192.168.4.1` on the Ethernet port.

### Step 2 · Install dnsmasq

```bash
sudo apt update
sudo apt install dnsmasq
```

### Step 3 · Configure dnsmasq for DHCP on eth0

```bash
sudo nano /etc/dnsmasq.d/eth0-router.conf
```

Paste:

```ini
interface=eth0
dhcp-range=192.168.4.50,192.168.4.150,255.255.255.0,24h
dhcp-option=3,192.168.4.1
dhcp-option=6,8.8.8.8
```

| Line | Meaning |
|------|---------|
| `interface=eth0` | Only serve DHCP on the Ethernet port |
| `dhcp-range` | Assigns IPs from `192.168.4.50` to `192.168.4.150` |
| `dhcp-option=3` | Tells clients the gateway is `192.168.4.1` (the RPi) |
| `dhcp-option=6` | DNS server for clients |

### Step 4 · Enable and restart dnsmasq

```bash
sudo systemctl enable dnsmasq
sudo systemctl restart dnsmasq
```

### ✅ Done! Connect from PC

Plug in an Ethernet cable between the RPi and your PC. The PC will automatically:
- 🔹 Get an IP address like `192.168.4.x`
- 🔹 See the RPi as the gateway at `192.168.4.1`

---

### ��� How to disable Ethernet router mode

```bash
sudo nmcli connection delete eth0-router
sudo rm /etc/dnsmasq.d/eth0-router.conf
sudo systemctl restart dnsmasq
```

---

## ✅ Verify Connection (Both Options)

From your PC, test connectivity:

```bash
ping 192.168.4.1
```

On the RPi, check network status:

```bash
nmcli device status
```
