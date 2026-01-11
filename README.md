# Raspberry Pi DNS Logger
Edge DNS Observability for QoE Analysis and Security Signal Detection

## Overview
Raspi DNS Logger is an edge observability system built on a Raspberry Pi that acts as a DNS Gateway and data collector for monitoring DNS traffic behavior in a home or
small-scale network. This project is designed to answer a practical and commonly observed question:
> *“Why does the internet feel slow even when speedtest results look fine?”*

Using a data-driven approach, where DNS behavior is treated as a lightweight proxy for application-layer activity and network conditions. In addition to QoS / QoE gap analysis, this system also enables early-stage security signal detection, such as:
- Abnormal DNS burst behavior
- NXDOMAIN storms
- Suspicious domain access

## Objectives
- Collect real-user DNS traffic centrally via a Raspberry Pi
- Provide a structured DNS dataset for QoE and QoS analysis, Background traffic investigation, and Basic DNS-based security threat triage
- Build a lightweight, reproducible, and explainable edge-to-database telemetry pipeline

## System Architecture

## Data Collected
DNS logs are parsed from **dnsmasq** and stored in PostgreSQL with the following fields:
| Field       | Description |
| ----------- | ----------- |
| ts          | DNS event timestamp       |
| client_ip   | Client device IP address        |
| cliend_id   | Hashed device identifier        |
| qtype       | DNS query type (A, AAAA, HTTPS, SVCB, etc.)        |
| domain      | Queried domain name        |
| result      | DNS resolution result (NOERROR, NXDOMAIN, NODATA, CNAME)        |
| answer      | DNS answer (IP, CNAME, or status)        |
| upstream    | Upstream DNS resolver        |
| event_hash  | Unique DNS event hash        |
| raw_line    | Original dnsmasq log line        |

## Use Case
### QoE & QoS Analysis
- Identify background traffic causing perceived latency
- Correlate DNS bursts with network instability
- Detect retry storms and resolution failures

### DNS-Based Security Signal Detection
- NXDOMAIN burst detection
- Periodic DNS behavior (possible beaconing)
- Suspicious domain access patterns
> This system provides *security signals*, not full intrusion detection

## Getting Started
### Prerequisites
- Raspberry Pi (recommended: Raspberry Pi 4)
- Python 3.9
- **dnsmasq** installed and running
- Supabase or other PostgreSQL based database 

### Clone Repository
```
git clone https://github.com/your-username/raspi-dns-logger.git
cd raspi-dns-logger
```

### Create Python Virtual Environment
```
python3 -m venv .venv
source .venv/bin/activate
```

### Install Dependencies
Before you start this project, you have to install some core dependencies, including
- supabase or other SQL based database
- python-dotenv
- python-dateutil
```
pip install -r requirements.txt
```

### Env Variables
Create a **.env** file and put this snippet inside your **.env** file
```
LOG_PATH="/var/log/dnsmasq.log"
SOURCE_HOST="raspi-home"
SALT="your-long-random-salt"
BATCH_SIZE="500"
SLEEP_SEC="0"

SUPABASE_URL="https://xxxx.supabase.co"
SUPABASE_API_KEY="your_service_role_key"

```

## DB Setup
The database allows you to store the DNS events. You could use other database, but mine preferred Supabase for this example.
Use these commands in your SQL editor to create the table and other recommend indexes.
### Create Table
```
create table if not exists public.dns_events (
  id bigserial primary key,
  ts timestamptz not null,
  source_host text,
  client_ip inet,
  client_id text,
  qtype text,
  domain text,
  result text,
  answer text,
  upstream inet,
  pid int,
  raw_line text,
  event_hash text unique,
  created_at timestamptz default now()
);
```
### Recommended Index
```
create index if not exists dns_events_ts_idx on dns_events (ts desc);
create index if not exists dns_events_client_idx on dns_events (client_id);
create index if not exists dns_events_result_idx on dns_events (result);
```

## Scheduler Setup
Scheduler setup allows you to run the python file automatically. You can set the timer and service file based on your use case.
But, these are my examples for scheduler and timer setup file.
### Service File
First, you have to create the service file using the command below.
```
sudo nano /etc/systemd/system/raspi-dns.service
```

Then, put this snippet in the service file

```
[Unit]
Description=Raspberry Pi DNS Logger
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=pi
WorkingDirectory=/home/pi/Project/raspi-dns-logger
EnvironmentFile=/home/pi/Project/raspi-dns-logger/.env
ExecStart=/home/pi/Project/raspi-dns-logger/.venv/bin/python main.py
```

### Timer File
Same as the scheduler setup, you have to create timer file first.
```
sudo nano /etc/systemd/system/dns-timer.timer
```
Then, put this snippet into your timer file
```
[Timer]
OnBootSec=30
OnUnitActiveSec=60
Persistent=true

[Install]
WantedBy=timers.target
```
To enable the scheduler, run this command in terminal:
```
sudo systemctl daemon-reload
sudo systemctl enable --now dns-timer.timer
```