<div align="center">

# MLB-DISCORD-RPC

*Show live MLB scores on Discord*

<p>
  <img src="https://img.shields.io/badge/last%20commit-today-brightgreen" />
  <img src="https://img.shields.io/badge/python-100.0%25-blue" />
  <img src="https://img.shields.io/badge/languages-1-lightgrey" />
</p>

*Built with the tools and technologies:*

<p>
  <img src="https://img.shields.io/badge/Markdown-informational?logo=markdown" />
  <img src="https://img.shields.io/badge/Python-blue?logo=python" />
  <img src="https://img.shields.io/badge/GitHub%20Actions-blue?logo=github-actions" />
</p>

</div>

<br>

## Table of Contents
* [Overview](#overview)
* [Screenshots](#screenshots)
* [Getting Started](#getting-started)
  * [Prerequisites](#prerequisites)
  * [Installation](#installation)
  * [Usage](#usage)
* [Options & Configuration](#options--configuration)

## Overview
**mlb-discord-rpc** shows live Major League Baseball game updates as your Discord status. It uses Discord Rich Presence to display real-time scores, game status, and player info for your favorite team while you use Discord. When no live game is detected, it displays the upcoming matchup with your opponent's logo and shows the score from the previous game. The large and small image tooltips include each team's win–loss record.

## Screenshots

**Live Game Example:**  
will add when theres a live game :)

**Final Game Example:**  
![finalegameexample](https://github.com/user-attachments/assets/7216414d-e437-4e56-93e3-1e39977f5d46)


## Getting Started

### Prerequisites
This project requires the following dependencies:
* **Programming Language:** Python (3.9+)
* **Package Manager:** Pip

### Installation
Build mlb-discord-rpc from the source and install dependencies:
1. **Clone the repository:**
   ```sh
   git clone https://github.com/RoMinjun/mlb-discord-rpc
   ```
2. **Navigate to the project directory:**
   ```sh
   cd mlb-discord-rpc
   ```
3. **Install the dependencies:**
   Using pip:
   ```sh
   pip install -r requirements.txt
   ```

### Usage
Run the project with:
Example:
```sh
python mlb-discord-rpc.py --team TOR
```

Or use `remote_ui_server.py` on another machine to manage the script through a
web interface.

---

## Options & Configuration
You can configure **mlb-discord-rpc** via command-line options, a `config.toml` file, and environment variables (`.env` file).

### Command-Line Arguments
* `--team <TEAM_ABBR>`
  **(required)** Sets your favorite MLB team by its abbreviation (e.g., `LAD`, `TOR`, `CHC`, etc.).
* `--tz <TIMEZONE>`
  Override the detected local timezone. Use [IANA timezone names](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) (e.g., `America/Toronto`).
* `--live-only`
  Only show your Discord status when your team has a live game.
* `--remote-url <URL>`
  Send presence updates to a remote RPC server instead of local Discord.

**Example:**

```sh
python script.py --team TOR --tz America/Toronto --live-only
```

---

### (Optional) Configuration File: `config.toml`

You may also set options persistently by editing (or creating) a `config.toml` file in the project directory.
Example:
```toml
team = "TOR"
timezone = "America/Toronto"
live_only = true
remote_url = "http://<pc-ip>:6463"

[display]
base_icon_filled = "🟦"
base_icon_empty = "⚪"

[refresh]
live_interval = 15
idle_interval = 90
```

* `team` - Team abbreviation (required)
* `timezone` - IANA timezone string (optional)
* `live_only` - Only display presence when game is live (optional)
* `remote_url` - URL of remote RPC server (optional). If you run
  `remote_ui_server.py` on another machine, set this to the address of
  `remote_rpc_server.py` on the Discord PC.
* `[display]` - Customize base icons
* `[refresh]` - Customize update intervals in seconds

---

### Environment Variables (`.env`)

* `CLIENT_ID`
  Your Discord application's client ID. **Required** to connect to Discord RPC.

Example `.env`:

```
CLIENT_ID=your_discord_client_id_here
```

---

## Quick Start

1. Set your `CLIENT_ID` in `.env`.
2. Optionally configure your team and preferences in `config.toml`.
3. Or run directly with command-line options.
4. To run from another machine, start `remote_rpc_server.py` on the Discord PC
   and use `remote_ui_server.py` on the remote host. Configure the remote URL
   through the web UI at `http://<rpi-ip>:8080/` and point it to
   `http://<pc-ip>:6463`.
   Visit `http://<pc-ip>:6463/` if you ever want to run the script locally
   instead of remotely.


`remote_rpc_server.py` now serves a simple web UI for choosing **Local** or
**Remote** mode. In local mode it runs `mlb-discord-rpc.py` automatically with
your saved settings.

### Docker

You can also run everything in Docker. Build the image:

```sh
docker build -t mlb-rpc .
```

Run the main script (override the command to run the servers):

```sh
docker run --rm -it \
  -e CLIENT_ID=YOUR_CLIENT_ID \
  mlb-rpc --team TOR
```

To run the bridge server instead:

```sh
docker run --rm -it -p 6463:6463 \
  -e CLIENT_ID=YOUR_CLIENT_ID \
  mlb-rpc python remote_rpc_server.py
```

And the remote UI server:

```sh
docker run --rm -it -p 8080:8080 mlb-rpc python remote_ui_server.py
```

**Enjoy seamless MLB presence on Discord!**

---

[↑ Return](#table-of-contents)
