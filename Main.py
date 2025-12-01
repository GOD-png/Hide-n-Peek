import tkinter as tk
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import socket
import qrcode
from PIL import Image, ImageTk
import io
import winsound

class HideAndSeekApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Hide And Seek Game Display")
        self.root.configure(bg="#1a1a1a")

        # Fullscreen
        self.root.attributes('-fullscreen', True)
        self.root.bind('<Escape>', lambda e: self.root.attributes('-fullscreen', False))

        # Players
        self.players = [
            {"name": "Player 1", "color": "#6B9BD1", "score": 0, "found": False},
            {"name": "Player 2", "color": "#7DB88A", "score": 0, "found": False},
            {"name": "Player 3", "color": "#D17B7B", "score": 0, "found": False}
        ]

        self.seeker_index = 0
        self.first_found_index = None

        # Timer state
        self.timer_running = False
        self.timer_phase = None       # "hiding" or "seeking"
        self.phase_start_time = 0
        self.round_start_time = 0
        self.last_minute_awarded = 0
        self.after_id = None

        # UI references
        self.score_labels = []
        self.name_labels = []
        self.seeker_indicators = []
        self.column_frames = []
        self.found_labels = []

        # For web control
        self.control_url = None

        self.setup_ui()
        self.start_web_server()

    # ------------- UI SETUP -------------

    def setup_ui(self):
        self.main_container = tk.Frame(self.root, bg="#1a1a1a")
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.update_grid_weights()
        self.main_container.grid_rowconfigure(0, weight=1)

        for i, player in enumerate(self.players):
            self.create_player_column(i, player)

    def update_grid_weights(self):
        for i in range(3):
            self.main_container.grid_columnconfigure(i, weight=0)
        for i in range(3):
            self.main_container.grid_columnconfigure(i, weight=2 if i == self.seeker_index else 1)

    def create_player_column(self, index, player):
        is_seeker = (index == self.seeker_index)

        col_frame = tk.Frame(
            self.main_container,
            bg=player["color"],
            relief=tk.RAISED,
            borderwidth=3,
            highlightbackground="#0a0a0a",
            highlightthickness=2
        )
        col_frame.grid(row=0, column=index, sticky="nsew", padx=5, pady=5)
        self.column_frames.append(col_frame)

        content_frame = tk.Frame(col_frame, bg=player["color"])
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Seeker indicator
        seeker_indicator = tk.Label(
            content_frame,
            text="★ SEEKER ★",
            font=("Arial", 16, "bold"),
            bg=player["color"],
            fg="#FFFFFF"
        )
        if is_seeker:
            seeker_indicator.pack(pady=10)
        self.seeker_indicators.append(seeker_indicator)

        # Name
        name_label = tk.Label(
            content_frame,
            text=player["name"],
            font=("Arial", 32, "bold"),
            bg=player["color"],
            fg="#FFFFFF"
        )
        name_label.pack(pady=20)
        self.name_labels.append(name_label)

        # Found status
        found_label = tk.Label(
            content_frame,
            text="",
            font=("Arial", 18, "bold"),
            bg=player["color"],
            fg="#FFFF00"
        )
        found_label.pack(pady=5)
        self.found_labels.append(found_label)

        # Score
        score_size = 72 if is_seeker else 56
        score_label = tk.Label(
            content_frame,
            text="0",
            font=("Arial", score_size, "bold"),
            bg=player["color"],
            fg="#FFFFFF"
        )
        score_label.pack(pady=30)
        self.score_labels.append(score_label)

        # Timer on seeker column
        if is_seeker:
            self.timer_container = content_frame
            self.create_timer_section(content_frame, player["color"])

    def create_timer_section(self, parent, bg_color):
        separator = tk.Frame(parent, bg="#FFFFFF", height=4)
        separator.pack(fill=tk.X, pady=30, padx=20)

        timer_container = tk.Frame(parent, bg=bg_color)
        timer_container.pack(fill=tk.BOTH, expand=True, pady=10)

        timer_title = tk.Label(
            timer_container,
            text="GAME TIMER",
            font=("Arial", 24, "bold"),
            bg=bg_color,
            fg="#FFFFFF"
        )
        timer_title.pack(pady=15)

        self.timer_frame = tk.Frame(
            timer_container,
            bg="#2a2a2a",
            relief=tk.RAISED,
            borderwidth=4
        )
        self.timer_frame.pack(pady=10)

        self.timer_title_label = tk.Label(
            self.timer_frame,
            text="READY",
            font=("Arial", 14, "bold"),
            bg="#2a2a2a",
            fg="#FFFFFF"
        )
        self.timer_title_label.pack(pady=5)

        self.timer_label = tk.Label(
            self.timer_frame,
            text="--:--",
            font=("Arial", 56, "bold"),
            bg="#2a2a2a",
            fg="#FFFFFF",
            padx=30,
            pady=20
        )
        self.timer_label.pack()

        self.phase_label = tk.Label(
            timer_container,
            text="Press START to begin",
            font=("Arial", 18, "bold"),
            bg=bg_color,
            fg="#FFFFFF"
        )
        self.phase_label.pack(pady=15)

        self.qr_label = tk.Label(timer_container, bg=bg_color)
        self.qr_label.pack(pady=20)

        self.url_label = tk.Label(
            timer_container,
            text="",
            font=("Arial", 12, "bold"),
            bg=bg_color,
            fg="#FFFFFF"
        )
        self.url_label.pack(pady=5)

    def rebuild_columns(self):
        for frame in self.column_frames:
            frame.destroy()

        self.column_frames = []
        self.score_labels = []
        self.name_labels = []
        self.seeker_indicators = []
        self.found_labels = []

        was_running = self.timer_running

        self.update_grid_weights()

        for i, player in enumerate(self.players):
            self.create_player_column(i, player)

        # Restore scores and found status
        for i, player in enumerate(self.players):
            self.score_labels[i].config(text=str(player["score"]))
            if player["found"]:
                self.found_labels[i].config(text="✓ FOUND")

        if was_running and hasattr(self, 'timer_label'):
            self.root.after(100, self.update_timer)

        if self.control_url:
            self.update_qr_code()

    # ------------- QR / SOUND / ALERT -------------

    def update_qr_code(self):
        if not self.control_url:
            return

        qr = qrcode.QRCode(version=1, box_size=6, border=2)
        qr.add_data(self.control_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)

        pil_img = Image.open(img_byte_arr)
        pil_img = pil_img.resize((150, 150), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(pil_img)

        self.qr_label.configure(image=photo)
        self.qr_label.image = photo
        self.url_label.configure(text=self.control_url)

    def play_sound(self, sound_type):
        """
        Use only built-in winsound.Beep patterns (no external files),
        but make them more playful than a single beep.
        """
        try:
            if sound_type == "start":
                # Upward "ready go" trill
                for f, d in [(600, 120), (800, 120), (1000, 150)]:
                    winsound.Beep(f, d)
            elif sound_type == "countdown_end":
                # Quick rising "GO!" burst
                for f, d in [(900, 80), (1100, 80), (1300, 120)]:
                    winsound.Beep(f, d)
            elif sound_type == "round_end":
                # Little descending "end" jingle
                for f, d in [(1000, 120), (800, 120), (600, 160)]:
                    winsound.Beep(f, d)
            elif sound_type == "point":
                # Short playful ping-pong
                for f, d in [(1200, 60), (900, 60)]:
                    winsound.Beep(f, d)
            elif sound_type == "minute":
                # Double "tick" to mark a minute
                for f, d in [(700, 80), (950, 80)]:
                    winsound.Beep(f, d)
        except Exception:
            # Ignore sound errors quietly
            pass

    def show_alert(self, message, color="#ffff00"):
        alert = tk.Label(
            self.root,
            text=message,
            font=("Arial", 32, "bold"),
            bg="#000000",
            fg=color,
            relief=tk.RAISED,
            borderwidth=5,
            padx=40,
            pady=20
        )
        alert.place(relx=0.5, rely=0.5, anchor='center')
        self.root.after(2000, alert.destroy)

    # ------------- TIMER / GAME LOGIC -------------

    def start_round(self):
        if self.timer_running:
            return

        # Reset all found flags
        for player in self.players:
            player["found"] = False
        self.first_found_index = None
        for label in self.found_labels:
            label.config(text="")

        self.timer_running = True
        self.timer_phase = "hiding"  # 1-minute hiding
        self.phase_start_time = time.time()
        self.round_start_time = self.phase_start_time
        self.last_minute_awarded = 0

        self.timer_frame.config(bg="#4a2020")
        self.timer_title_label.config(text="HIDING (1 min)", bg="#4a2020", fg="#FFFFFF")
        self.phase_label.config(text="HIDING...")

        self.play_sound("start")
        self.show_alert("🙈 GO HIDE! 🙈", "#00ff00")

        self.update_timer()

    def stop_timer(self):
        self.timer_running = False
        self.timer_phase = None

        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        self.timer_frame.config(bg="#2a2a2a")
        self.timer_title_label.config(text="READY", bg="#2a2a2a", fg="#FFFFFF")
        self.timer_label.config(text="--:--", bg="#2a2a2a", fg="#FFFFFF")
        self.phase_label.config(text="Press START to begin")

        self.show_alert("⏹ TIMER STOPPED ⏹", "#ff6666")

    def update_timer(self):
        if not self.timer_running:
            return

        elapsed = time.time() - self.phase_start_time

        # HIDING (1 min)
        if self.timer_phase == "hiding":
            remaining = max(0, 60 - int(elapsed))
            mins, secs = divmod(remaining, 60)

            self.timer_frame.config(bg="#4a2020")
            self.timer_title_label.config(text="HIDING (1 min)", bg="#4a2020", fg="#FFFFFF")
            self.timer_label.config(
                text=f"{mins:02d}:{secs:02d}",
                bg="#4a2020",
                fg="#ff6666"
            )
            self.phase_label.config(text="HIDING...")

            # Last 5 seconds warning
            if remaining <= 5 and remaining > 0:
                if int(elapsed * 10) % 10 == 0:
                    self.play_sound("minute")

            if elapsed >= 60:
                # Transition to SEEKING (5 min)
                self.timer_phase = "seeking"
                self.phase_start_time = time.time()
                self.round_start_time = self.phase_start_time
                self.last_minute_awarded = 0

                self.play_sound("countdown_end")
                self.show_alert("🎯 START SEEKING! 🎯", "#00ff00")

        # SEEKING (5 min)
        elif self.timer_phase == "seeking":
            elapsed_seeking = time.time() - self.phase_start_time
            remaining = max(0, 300 - int(elapsed_seeking))
            mins, secs = divmod(remaining, 60)

            self.timer_frame.config(bg="#204a20")
            self.timer_title_label.config(text="SEEKING (5 min)", bg="#204a20", fg="#FFFFFF")
            self.timer_label.config(
                text=f"{mins:02d}:{secs:02d}",
                bg="#204a20",
                fg="#66ff66"
            )
            self.phase_label.config(text="ROUND IN PROGRESS")

            current_minute = int(elapsed_seeking // 60)
            if current_minute > self.last_minute_awarded and current_minute <= 5:
                self.award_hider_points()
                self.last_minute_awarded = current_minute
                self.play_sound("minute")
                self.show_alert(f"⏰ MINUTE {current_minute} ⏰", "#ffff00")

            # Last 10 seconds warning
            if remaining <= 10 and remaining > 0:
                if int(elapsed_seeking * 10) % 10 == 0:
                    self.play_sound("countdown_end")

            if elapsed_seeking >= 300:
                self.stop_timer()
                self.timer_label.config(text="DONE!", bg="#2a2a2a", fg="#FFFFFF")
                self.phase_label.config(text="Round Complete!")
                self.play_sound("round_end")
                self.show_alert("🏁 ROUND COMPLETE! 🏁", "#00ffff")
                return

        self.after_id = self.root.after(100, self.update_timer)

    def end_round(self):
        self.stop_timer()
        self.timer_frame.config(bg="#2a2a2a")
        self.timer_title_label.config(text="DONE!", bg="#2a2a2a", fg="#FFFFFF")
        self.timer_label.config(text="00:00", bg="#2a2a2a", fg="#FFFFFF")
        self.phase_label.config(text="Round Complete!")
        self.play_sound("round_end")

        if self.first_found_index is not None:
            self.show_alert(
                f"🏁 ROUND OVER! Next seeker: {self.players[self.first_found_index]['name']} 🏁",
                "#00ffff"
            )
            self.root.after(2500, lambda: self.set_seeker(self.first_found_index))
        else:
            self.show_alert("🏁 ROUND COMPLETE! 🏁", "#00ffff")

    def award_hider_points(self):
        for i in range(len(self.players)):
            if i != self.seeker_index and not self.players[i]["found"]:
                self.players[i]["score"] += 1
                self.update_score_display(i)

    def update_score_display(self, player_index):
        self.score_labels[player_index].config(
            text=str(self.players[player_index]["score"])
        )
        self.play_sound("point")

    def update_name_display(self, player_index):
        self.name_labels[player_index].config(
            text=self.players[player_index]["name"]
        )

    def set_seeker(self, index):
        if self.seeker_index != index:
            self.seeker_index = index
            self.rebuild_columns()
            self.show_alert(
                f"👁 {self.players[index]['name']} is now SEEKER! 👁",
                "#ff9800"
            )

    def mark_player_found(self, player_index):
        if player_index == self.seeker_index:
            return

        if not self.players[player_index]["found"]:
            self.players[player_index]["found"] = True

            if self.first_found_index is None:
                self.first_found_index = player_index

            self.found_labels[player_index].config(text="✓ FOUND")

            self.players[self.seeker_index]["score"] += 3
            self.update_score_display(self.seeker_index)

            self.show_alert(
                f"🎯 {self.players[player_index]['name']} FOUND! 🎯",
                "#00ffff"
            )
            self.play_sound("point")

    # ------------- WEB SERVER -------------

    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def start_web_server(self):
        app = self

        class ControlHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_GET(self):
                if self.path == '/':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(self.get_control_html().encode())
                elif self.path == '/state':
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()

                    timer_info = {
                        'running': False,
                        'phase': None,
                        'time': '--:--',
                        'label': 'READY'
                    }

                    if app.timer_running:
                        elapsed = time.time() - app.phase_start_time
                        if app.timer_phase == 'hiding':
                            remaining_hiding = max(0, 60 - int(elapsed))
                            mins_h, secs_h = divmod(remaining_hiding, 60)
                            timer_info = {
                                'running': True,
                                'phase': 'hiding',
                                'time': f'{mins_h:02d}:{secs_h:02d}',
                                'label': 'HIDING (1 min)'
                            }
                        elif app.timer_phase == 'seeking':
                            elapsed_seeking = time.time() - app.phase_start_time
                            remaining_seeking = max(0, 300 - int(elapsed_seeking))
                            mins_s, secs_s = divmod(remaining_seeking, 60)
                            timer_info = {
                                'running': True,
                                'phase': 'seeking',
                                'time': f'{mins_s:02d}:{secs_s:02d}',
                                'label': 'SEEKING (5 min)'
                            }

                    state = {
                        'players': app.players,
                        'seeker_index': app.seeker_index,
                        'timer_running': app.timer_running,
                        'timer': timer_info
                    }
                    self.wfile.write(json.dumps(state).encode())

            def do_POST(self):
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode())

                action = data.get('action')

                if action == 'set_seeker':
                    app.root.after(0, lambda: app.set_seeker(data['index']))
                elif action == 'add_point':
                    app.players[data['index']]['score'] += 1
                    app.root.after(0, lambda: app.update_score_display(data['index']))
                elif action == 'player_found':
                    app.root.after(0, lambda: app.mark_player_found(data['index']))
                elif action == 'reset_scores':
                    for i, player in enumerate(app.players):
                        player['score'] = 0
                        app.root.after(0, lambda idx=i: app.update_score_display(idx))
                    app.root.after(0, lambda: app.show_alert("🔄 SCORES RESET 🔄", "#ff6666"))
                elif action == 'start_round':
                    app.root.after(0, app.start_round)
                elif action == 'stop_timer':
                    app.root.after(0, app.stop_timer)
                elif action == 'update_name':
                    app.players[data['index']]['name'] = data['name']
                    app.root.after(0, lambda: app.update_name_display(data['index']))

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'ok'}).encode())

            def get_control_html(self):
                return '''<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta charset="UTF-8">
    <title>Hide and Seek Control</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #1a1a1a;
            color: #fff;
            padding: 20px;
            margin: 0;
        }
        h1 {
            text-align: center;
            color: #fff;
        }
        .section {
            background: #2a2a2a;
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
        }
        .timer-display {
            display: flex;
            justify-content: center;
            margin: 20px 0;
        }
        .timer-box {
            background: #3a3a3a;
            border-radius: 10px;
            padding: 20px 40px;
            text-align: center;
            min-width: 200px;
        }
        .timer-box.active {
            border: 3px solid #4CAF50;
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0%, 100% { border-color: #4CAF50; }
            50% { border-color: #66ff66; }
        }
        .timer-label {
            font-size: 14px;
            color: #999;
            margin-bottom: 10px;
            text-transform: uppercase;
            font-weight: bold;
        }
        .timer-time {
            font-size: 42px;
            font-weight: bold;
            font-family: 'Courier New', monospace;
        }
        .timer-box.hiding .timer-time {
            color: #ffff66;
        }
        .timer-box.seeking .timer-time {
            color: #66ff66;
        }
        .timer-box.inactive .timer-time {
            color: #666;
        }
        .player-card {
            background: #3a3a3a;
            border-radius: 8px;
            padding: 15px;
            margin: 10px 0;
        }
        .player-name {
            font-size: 20px;
            font-weight: bold;
            margin-bottom: 10px;
        }
        .player-status {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 5px;
            font-size: 12px;
            font-weight: bold;
            margin-left: 10px;
        }
        .status-found {
            background: #ff9800;
            color: white;
        }
        input[type="text"] {
            width: 200px;
            padding: 8px;
            font-size: 16px;
            border-radius: 5px;
            border: none;
            margin: 5px 0;
        }
        button {
            background: #4CAF50;
            color: white;
            border: none;
            padding: 12px 24px;
            font-size: 16px;
            border-radius: 8px;
            margin: 5px;
            cursor: pointer;
            font-weight: bold;
        }
        button:active {
            transform: scale(0.95);
        }
        .seeker-btn {
            background: #ff9800;
        }
        .found-btn {
            background: #2196F3;
        }
        .timer-btn {
            background: #9C27B0;
            width: 100%;
            padding: 15px;
            font-size: 18px;
        }
        .reset-btn {
            background: #f44336;
            width: 100%;
            padding: 15px;
            font-size: 18px;
        }
        .btn-row {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
    </style>
</head>
<body>
    <h1>&#x1F3AE; Hide and Seek Control Panel</h1>
    
    <div class="section">
        <h2>Game Timer</h2>
        <div class="timer-display">
            <div class="timer-box" id="main-timer">
                <div class="timer-label" id="timer-label">READY</div>
                <div class="timer-time" id="timer-time">--:--</div>
            </div>
        </div>
        <button class="timer-btn" onclick="startRound()">START NEW ROUND</button>
        <button class="timer-btn" onclick="stopTimer()">STOP TIMER</button>
    </div>
    
    <div class="section">
        <h2>Players</h2>
        <div id="players"></div>
    </div>
    
    <div class="section">
        <h2>Game Control</h2>
        <button class="reset-btn" onclick="resetScores()">RESET ALL SCORES</button>
    </div>
    
    <script>
        const players = [
            {name: "Player 1", color: "#6B9BD1"},
            {name: "Player 2", color: "#7DB88A"},
            {name: "Player 3", color: "#D17B7B"}
        ];
        
        let currentState = null;
        
        function renderPlayers() {
            if (!currentState) return;
            
            const container = document.getElementById('players');
            container.innerHTML = currentState.players.map((player, i) => {
                const isSeeker = i === currentState.seeker_index;
                const foundBadge = player.found ? '<span class="player-status status-found">&#x2713; FOUND</span>' : '';
                const seekerBadge = isSeeker ? '<span class="player-status" style="background: #9C27B0; color: white;">&#x2605; SEEKER</span>' : '';
                
                return `
                <div class="player-card" style="border-left: 5px solid ${player.color}">
                    <div class="player-name" style="color: ${player.color}">
                        ${player.name} ${seekerBadge}${foundBadge}
                        <span style="float: right; color: white;">Score: ${player.score}</span>
                    </div>
                    <input type="text" id="name-${i}" value="${player.name}" 
                           onchange="updateName(${i})" placeholder="Player name">
                    <div class="btn-row">
                        <button class="seeker-btn" onclick="setSeeker(${i})">Set as Seeker</button>
                        <button onclick="addPoint(${i})">+1 Point</button>
                        <button class="found-btn" onclick="playerFound(${i})">Found This Player</button>
                    </div>
                </div>
            `}).join('');
        }
        
        function updateTimers() {
            if (!currentState || !currentState.timer) return;
            
            const timer = currentState.timer;
            const timerBox = document.getElementById('main-timer');
            const timerLabel = document.getElementById('timer-label');
            const timerTime = document.getElementById('timer-time');
            
            timerLabel.textContent = timer.label || 'READY';
            timerTime.textContent = timer.time || '--:--';
            
            timerBox.className = 'timer-box';
            
            if (timer.running && timer.phase === 'hiding') {
                timerBox.classList.add('active', 'hiding');
            } else if (timer.running && timer.phase === 'seeking') {
                timerBox.classList.add('active', 'seeking');
            } else {
                timerBox.classList.add('inactive');
            }
        }
        
        async function fetchState() {
            try {
                const response = await fetch('/state');
                currentState = await response.json();
                renderPlayers();
                updateTimers();
            } catch (error) {
                console.error('Error fetching state:', error);
            }
        }
        
        async function sendAction(action, data = {}) {
            await fetch('/state', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action, ...data})
            });
            setTimeout(fetchState, 100);
        }
        
        function setSeeker(index) {
            sendAction('set_seeker', {index});
        }
        
        function addPoint(index) {
            sendAction('add_point', {index});
        }
        
        function playerFound(index) {
            sendAction('player_found', {index});
        }
        
        function resetScores() {
            if(confirm('Reset all scores to 0?')) {
                sendAction('reset_scores');
            }
        }
        
        function startRound() {
            sendAction('start_round');
        }
        
        function stopTimer() {
            sendAction('stop_timer');
        }
        
        function updateName(index) {
            const name = document.getElementById('name-' + index).value;
            players[index].name = name;
            sendAction('update_name', {index, name});
        }
        
        fetchState();
        setInterval(fetchState, 500);
    </script>
</body>
</html>'''

        PORT = 8080
        server = HTTPServer(('0.0.0.0', PORT), ControlHandler)

        ip = self.get_local_ip()
        self.control_url = f"http://{ip}:{PORT}"

        print(f"\n{'='*50}")
        print(f"Control Panel URL: {self.control_url}")
        print(f"{'='*50}\n")

        self.root.after(500, self.update_qr_code)

        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()

if __name__ == "__main__":
    root = tk.Tk()
    app = HideAndSeekApp(root)
    root.mainloop()
