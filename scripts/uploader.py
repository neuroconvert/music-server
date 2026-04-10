import os
import time
import re
import shutil
import asyncio
import threading
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, Response, send_file
import mutagen

app = Flask(__name__)
INBOX = "/inbox"
DRAFTS = "/upload_drafts"
LOGS = "/logs/processing.log"
ALLOWED_EXTENSIONS = {'.mp3', '.flac', '.m4a', '.ogg', '.wav'}
PROCESS_DELAY = 90 

USERNAME = os.environ.get("UPLOAD_USER", "admin")
PASSWORD = os.environ.get("UPLOAD_PASS", "password")

SHAZAM_CACHE = {}

VALID_GENRES = [
    "Pop", "Rock", "Hip-Hop", "Rap", "R&B", "Electronic", "Dance", "House", "Trance", "Techno",
    "Jazz", "Blues", "Classical", "Country", "Reggae", "Latin", "Metal", "Indie", "Alternative",
    "Soundtrack", "K-Pop", "J-Pop", "Lo-Fi", "Acoustic", "Folk", "Punk", "Soul", "Ambient",
    "Поп", "Рок", "Рэп", "Хип-хоп", "Шансон", "Электроника", "Танцевальная", "Классика", "Джаз",
    "Альтернатива", "Метал", "Инди", "Панк", "Фолк"
]
VALID_GENRES_MAP = {g.lower(): g for g in VALID_GENRES}

def normalize_genre(raw_genre):
    if not raw_genre: return ""
    clean_genre = str(raw_genre).strip().lower()
    return VALID_GENRES_MAP.get(clean_genre, "")

def make_safe_filename(filename):
    filename = os.path.basename(filename)
    return re.sub(r'[\\\\/*?:"<>|]', "_", filename)

def run_shazam_on_drafts():
    async def process():
        from shazamio import Shazam
        shazam_engine = Shazam()
        
        while True:
            if os.path.exists(DRAFTS):
                for f in os.listdir(DRAFTS):
                    if not allowed_file(f): continue
                    path = os.path.join(DRAFTS, f)
                    if not os.path.isfile(path): continue
                    
                    if f not in SHAZAM_CACHE:
                        try:
                            out = await asyncio.wait_for(shazam_engine.recognize(path), timeout=15.0)
                            track = out.get('track')
                            if track:
                                shazam_album = ""
                                for section in track.get('sections', []):
                                    if section.get('type') == 'SONG':
                                        for meta in section.get('metadata', []):
                                            if meta.get('title') == 'Album':
                                                shazam_album = meta.get('text', '')
                                
                                SHAZAM_CACHE[f] = {
                                    'status': 'success', 
                                    'artist': track.get('subtitle', ''), 
                                    'title': track.get('title', ''),
                                    'album': shazam_album,
                                    'genre': track.get('genres', {}).get('primary', '')
                                }
                            else:
                                SHAZAM_CACHE[f] = {'status': 'fail', 'artist': '', 'title': '', 'album': '', 'genre': ''}
                        except Exception as e:
                            print(f"Shazam UI error for {f}: {e}")
                            SHAZAM_CACHE[f] = {'status': 'fail', 'artist': '', 'title': '', 'album': '', 'genre': ''}
                        await asyncio.sleep(2)
            await asyncio.sleep(5)
            
    asyncio.run(process())

threading.Thread(target=run_shazam_on_drafts, daemon=True).start()

def check_auth(username, password):
    return username == USERNAME and password == PASSWORD

def authenticate():
    return Response('Login Required.', 401, {'WWW-Authenticate': 'Basic realm="Music Uploader"'})

def requires_auth(f):
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    decorated.__name__ = f.__name__
    return decorated

def allowed_file(filename):
    _, ext = os.path.splitext(filename)
    return ext.lower() in ALLOWED_EXTENSIONS

# UI v6.12 (Expanded Wide Container)
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Music Ingestion Pipeline</title>
    <script src="https://unpkg.com/dropzone@5/dist/min/dropzone.min.js"></script>
    <link rel="stylesheet" href="https://unpkg.com/dropzone@5/dist/min/dropzone.min.css" type="text/css" />
    <style>
        body { font-family: sans-serif; background: #121212; color: #ffffff; padding: 40px; text-align: center; }
        h1 { color: #bb86fc; }
        .container { max-width: 96%; margin: 0 auto; } /* EXPANDED WIDTH HERE */
        .dropzone { background: #1e1e1e; border: 2px dashed #bb86fc; border-radius: 10px; padding: 60px 40px 40px 40px; margin-bottom: 10px; }
        .dz-message { font-size: 1.2em; color: #a1a1a1; }
        .dropzone .dz-preview .dz-success-mark svg, .dropzone .dz-preview .dz-error-mark svg { fill: #bb86fc; }
        .dropzone .dz-preview.dz-error .dz-error-message { opacity: 1 !important; top: -70px !important; z-index: 1000 !important; }
        .dropzone .dz-preview .dz-remove { color: #ff7a90; font-weight: bold; margin-top: 15px; display: block; cursor: pointer; text-decoration: none;}
        .header-row { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #333; margin-top: 40px; padding-bottom: 10px; }
        h2 { margin: 0; color: #e0e0e0; }
        @keyframes pulse-border { 0% { box-shadow: 0 0 0 0 rgba(243, 156, 18, 0.4); } 70% { box-shadow: 0 0 0 10px rgba(243, 156, 18, 0); } }
        .shazam-processing-banner { color: #ffb74d; background-color: rgba(243, 156, 18, 0.15); border: 2px solid #f39c12; padding: 8px 20px; border-radius: 8px; font-weight: bold; margin-right: 20px; display: inline-block; animation: pulse-border 2s infinite; }
        .shazam-complete-banner { color: #81c784; background-color: rgba(76, 175, 80, 0.15); border: 2px solid #4caf50; padding: 8px 20px; border-radius: 8px; font-weight: bold; margin-right: 20px; display: inline-block; }
        table { width: 100%; border-collapse: collapse; background: #1e1e1e; border-radius: 8px; overflow: hidden; margin-bottom: 30px; margin-top: 15px;}
        th, td { padding: 15px; text-align: left; border-bottom: 1px solid #333; vertical-align: top; }
        th { background: #2c2c2c; color: #bb86fc; font-weight: bold; }
        tr:hover { background: #2a2a2a; }
        .status-waiting { color: #f39c12; font-weight: bold; }
        .status-processing { color: #00e676; font-weight: bold; }
        .badge-shazam { background: #2196f3; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.9em; margin-bottom:4px; display:inline-block; font-weight:bold; }
        .badge-fail { background: #cf6679; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.9em; margin-bottom:4px; display:inline-block; font-weight:bold; }
        .badge-waiting { padding: 4px 8px; font-size: 0.9em; margin-bottom:4px; display:inline-block; font-weight:bold; color:#aaa; border: 1px dashed #aaa; border-radius: 4px;}
        .btn-action { color: white; border: none; padding: 8px 14px; border-radius: 4px; cursor: pointer; font-weight: bold; margin-bottom: 5px; width: 100%; transition: 0.2s; }
        .btn-submit { background-color: #03dac6; color: #000; }
        .btn-submit:hover:not(:disabled) { background-color: #00b3a6; }
        .btn-submit-all { background-color: #bb86fc; color: #000; font-size: 1.1em; padding: 8px 16px; width: auto; margin:0; }
        .btn-submit-rec { background-color: #03dac6; color: #000; font-size: 1.1em; padding: 8px 16px; width: auto; margin:0; }
        .btn-delete { background-color: #cf6679; }
        .btn-delete-all { background-color: #cf6679; font-size: 1.1em; padding: 8px 16px; width: auto; margin:0; }
        button:disabled { opacity: 0.4; cursor: not-allowed !important; filter: grayscale(100%); }
        input[type="text"], select { background: #2c2c2c; border: 1px solid #444; color: white; padding: 10px; border-radius: 4px; width: 90%; font-size: 1em; margin-top:5px; outline:none; }
        input:focus, select:focus { border-color: #03dac6; box-shadow: 0 0 5px rgba(3, 218, 198, 0.5); }
        select:disabled { background: #1a1a1a; color: #888; cursor: not-allowed; border-color: #333; }
        audio { width: 100%; height: 45px; outline: none; margin-top: 10px; border-radius: 8px; }
        .log-box { background: #1e1e1e; padding: 15px; border-radius: 8px; margin-bottom: 30px; text-align: left; font-family: monospace; color: #a1a1a1; height: 250px; overflow-y: auto; border: 1px solid #333; line-height: 1.5; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎵 Music Ingestion Pipeline</h1>
        <form action="/add-music/upload" class="dropzone" id="musicDropzone"></form>
        <button id="btn-clear-dz" class="btn-action" onclick="clearDropzoneErrors()" style="display:none; width:auto; background:#555; float:right; padding: 10px 20px;">🧹 Clear Upload Errors</button>
        <div style="clear:both;"></div>

        <div class="header-row">
            <h2>📝 Step 1: Needs Review (Upload Drafts)</h2>
            <div style="display:flex; align-items:center; gap: 10px;">
                <div id="shazam-global-status" style="display:none;"></div>
                <button id="btn-del-all" class="btn-action btn-delete-all" onclick="deleteAll()">🗑️ Delete All</button>
                <button id="btn-sub-rec" class="btn-action btn-submit-rec" onclick="submitRecognized()">✨ Submit Recognized</button>
                <button id="btn-sub-all" class="btn-action btn-submit-all" onclick="submitAll()">🚀 Submit All</button>
            </div>
        </div>
        <div style="overflow-x: auto;">
            <table>
                <thead>
                    <tr>
                        <th width="25%">Filename & Player</th>
                        <th width="20%">Artist</th>
                        <th width="20%">Title</th>
                        <th width="15%">Album</th>
                        <th width="10%">Genre</th>
                        <th width="10%">Actions</th>
                    </tr>
                </thead>
                <tbody id="draft-body"><tr><td colspan="6" style="text-align:center;">Loading...</td></tr></tbody>
            </table>
        </div>

        <div class="header-row">
            <h2>⏳ Step 2: Live Processing Queue (Inbox)</h2>
            <button id="btn-cancel-all-queue" class="btn-action btn-delete-all" onclick="cancelAllQueue()" style="background-color:#ff9800; color:black; margin:0;">🛑 Cancel All</button>
        </div>
        <div style="overflow-x: auto;">
            <table>
                <thead>
                    <tr><th>Filename</th><th>Status / Time Left</th><th>Actions</th></tr>
                </thead>
                <tbody id="queue-body"><tr><td colspan="3" style="text-align:center;">Loading...</td></tr></tbody>
            </table>
        </div>

        <div class="header-row" style="margin-top: 50px;"><h2>📜 Step 3: Processing History</h2></div>
        <div class="log-box" id="logs-body">Loading logs...</div>
    </div>
    
    <script>
        const VALID_GENRES = ["Pop", "Rock", "Hip-Hop", "Rap", "R&B", "Electronic", "Dance", "House", "Trance", "Techno", "Jazz", "Blues", "Classical", "Country", "Reggae", "Latin", "Metal", "Indie", "Alternative", "Soundtrack", "K-Pop", "J-Pop", "Lo-Fi", "Acoustic", "Folk", "Punk", "Soul", "Ambient", "Поп", "Рок", "Рэп", "Хип-хоп", "Шансон", "Электроника", "Танцевальная", "Классика", "Джаз", "Альтернатива", "Метал", "Инди", "Панк", "Фолк"];
        
        window.DraftFiles = {};
        window.QueueFiles = {};

        function escapeHtml(str) {
            return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
        }

        Dropzone.options.musicDropzone = {
            acceptedFiles: ".mp3,.flac,.m4a,.ogg,.wav", maxFilesize: 200, parallelUploads: 5,
            dictDefaultMessage: "Drag & Drop audio files here to upload", addRemoveLinks: true, dictRemoveFile: "❌ Remove",
            init: function() {
                this.on("success", function(file) { setTimeout(() => { this.removeFile(file); }, 2000); fetchData(); });
                this.on("error", function(file, response) {
                    var msg = typeof response === "string" ? response : response.error;
                    file.previewElement.classList.add("dz-error");
                    let ref = file.previewElement.querySelectorAll("[data-dz-errormessage]");
                    for (let i = 0; i < ref.length; i++) { ref[i].textContent = msg; }
                    document.getElementById('btn-clear-dz').style.display = 'inline-block';
                });
                this.on("removedfile", function(file) {
                    if (this.getFilesWithStatus(Dropzone.ERROR).length === 0) document.getElementById('btn-clear-dz').style.display = 'none';
                });
            }
        };

        function clearDropzoneErrors() {
            if(Dropzone.instances.length > 0) {
                const dz = Dropzone.instances[0];
                const errorFiles = dz.getFilesWithStatus(Dropzone.ERROR);
                errorFiles.forEach(f => dz.removeFile(f));
                document.getElementById('btn-clear-dz').style.display = 'none';
            }
        }

        function deleteDraft(filename) { if(confirm(`Delete draft?`)) fetch(`/add-music/draft/${encodeURIComponent(filename)}`, { method: 'DELETE' }).then(() => fetchData()); }
        function deleteQueue(filename) { if(confirm(`Cancel processing?`)) fetch(`/add-music/queue/${encodeURIComponent(filename)}`, { method: 'DELETE' }).then(() => fetchData()); }
        function deleteAll() { if(confirm("Permanently delete ALL drafts?")) fetch('/add-music/draft/all', { method: 'DELETE' }).then(()=>fetchData()); }
        function cancelAllQueue() { if(confirm("Cancel processing for ALL files currently waiting in the live queue?")) fetch('/add-music/queue/all', { method: 'DELETE' }).then(()=>fetchData()); }

        function confirmFile(filename, safeId) {
            const row = document.getElementById(`row-${safeId}`);
            if (row) {
                const audioEl = row.querySelector('audio');
                if (audioEl) {
                    audioEl.pause();
                    audioEl.src = '';
                    audioEl.load();
                }
            }

            const artist = document.getElementById(`artist-${safeId}`).value;
            const title = document.getElementById(`title-${safeId}`).value;
            const album = document.getElementById(`album-${safeId}`).value;
            const genre = document.getElementById(`genre-${safeId}`).value;
            
            return fetch(`/add-music/confirm/${encodeURIComponent(filename)}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ artist, title, album, genre })
            }).then(async r => {
                if (!r.ok) {
                    let err = await r.text();
                    try { err = JSON.parse(err).error || err; } catch(e) {}
                    alert(`Failed to submit file!\\n\\nReason: ` + err);
                    throw new Error(err);
                }
                return r.json();
            });
        }

        async function submitRecognized() {
            const recognizedRows = document.querySelectorAll('#draft-body tr.shazam-recognized');
            if(recognizedRows.length === 0) return;
            
            const btn = document.getElementById('btn-sub-rec');
            btn.innerText = "Processing..."; btn.disabled = true;
            document.getElementById('btn-sub-all').disabled = true;
            
            for(let row of recognizedRows) {
                const safeId = row.id.replace('row-', '');
                const filename = window.DraftFiles[safeId];
                if(filename) {
                    try { await confirmFile(filename, safeId); } catch(e) {}
                }
            }
            btn.innerText = "✨ Submit Recognized"; btn.disabled = false;
            fetchData();
        }

        async function submitAll() {
            const rows = document.querySelectorAll('#draft-body tr[id^="row-"]');
            if(rows.length === 0) return;
            
            const unrecognizedRows = document.querySelectorAll('#draft-body tr.shazam-unrecognized');
            if (unrecognizedRows.length > 0) {
                if (!confirm(`Warning: You have ${unrecognizedRows.length} file(s) that were NOT matched by Shazam.\\n\\nAre you sure you want to submit them as-is?`)) {
                    return;
                }
            }

            const btn = document.getElementById('btn-sub-all');
            btn.innerText = "Processing..."; btn.disabled = true;
            document.getElementById('btn-sub-rec').disabled = true;
            
            for(let row of rows) {
                const safeId = row.id.replace('row-', '');
                const filename = window.DraftFiles[safeId];
                if(filename) {
                    try { await confirmFile(filename, safeId); } catch(e) {}
                }
            }
            btn.innerText = "🚀 Submit All"; btn.disabled = false;
            fetchData();
        }

        function fetchData() {
            fetch('/add-music/data')
                .then(r => r.json())
                .then(data => {
                    const draftBody = document.getElementById('draft-body');
                    const queueBody = document.getElementById('queue-body');
                    const logsBody = document.getElementById('logs-body');
                    
                    const totalDrafts = data.drafts.length;
                    const waitingCount = data.drafts.filter(d => d.shazam_status === 'waiting').length;
                    const recognizedCount = data.drafts.filter(d => d.shazam_status === 'success').length;
                    
                    document.getElementById('btn-del-all').disabled = (totalDrafts === 0);
                    document.getElementById('btn-sub-all').disabled = (totalDrafts === 0 || waitingCount > 0);
                    document.getElementById('btn-sub-rec').disabled = (recognizedCount === 0 || waitingCount > 0);
                    
                    const cancelableCount = data.live.filter(item => item.age_seconds < 90).length;
                    const btnCancelAll = document.getElementById('btn-cancel-all-queue');
                    if (btnCancelAll) btnCancelAll.disabled = (cancelableCount === 0);
                    
                    const statusEl = document.getElementById('shazam-global-status');
                    if (waitingCount > 0) {
                        statusEl.innerHTML = `⚙️ Shazam analyzing ${waitingCount} file(s)...`;
                        statusEl.className = 'shazam-processing-banner';
                        statusEl.style.display = 'inline-block';
                    } else if (totalDrafts > 0) {
                        statusEl.innerHTML = `✅ Analysis complete. All files are ready to submit!`;
                        statusEl.className = 'shazam-complete-banner';
                        statusEl.style.display = 'inline-block';
                    } else {
                        statusEl.innerHTML = '';
                        statusEl.className = '';
                        statusEl.style.display = 'none';
                    }
                    
                    if (data.logs && data.logs.length > 0) logsBody.innerHTML = data.logs.join('<br>');
                    else logsBody.innerHTML = '<i>No processing history yet. Logs will appear here once files are processed.</i>';
                    
                    if(data.drafts.length === 0) {
                        draftBody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:#888;">No files need review.</td></tr>';
                    } else {
                        if(draftBody.innerHTML.includes('No files need review')) draftBody.innerHTML = '';
                        
                        const existingRows = Array.from(draftBody.querySelectorAll('tr[id^="row-"]'));
                        const activeRowIds = new Set();
                        
                        data.drafts.forEach((item) => {
                            const safeId = 'f' + btoa(encodeURIComponent(item.filename)).replace(/[^a-zA-Z0-9]/g, '');
                            const rowId = `row-${safeId}`;
                            activeRowIds.add(rowId);
                            window.DraftFiles[safeId] = item.filename;
                            
                            let tr = document.getElementById(rowId);
                            
                            if (tr) {
                                let isFocused = false;
                                const inputs = tr.querySelectorAll('input, select');
                                inputs.forEach(input => { if(document.activeElement === input) isFocused = true; });
                                if (isFocused) return;
                            }

                            let badgeHtml = '';
                            let rowClass = '';
                            
                            if(item.shazam_status === 'success') {
                                badgeHtml += `<div class="badge-shazam">🎵 Shazam Match | ${escapeHtml(item.suggest_artist)} - ${escapeHtml(item.suggest_title)}</div><br>`;
                                rowClass = 'shazam-recognized';
                            } else if(item.shazam_status === 'fail') {
                                badgeHtml += `<div class="badge-fail">❌ Shazam Failed</div><br>`;
                                rowClass = 'shazam-unrecognized';
                            } else {
                                badgeHtml += `<div class="badge-waiting">⏳ Waiting for Shazam...</div><br>`;
                                rowClass = 'shazam-unrecognized';
                            }
                            
                            if(!tr) { 
                                tr = document.createElement('tr'); 
                                tr.id = rowId; 
                                draftBody.appendChild(tr); 
                            }
                            
                            tr.className = rowClass;
                            
                            let currentAudio = tr.querySelector('audio');
                            let audioHtml = currentAudio ? currentAudio.outerHTML : `<audio controls preload="metadata"><source src="/add-music/play/draft/${encodeURIComponent(item.filename)}" type="audio/mpeg"></audio>`;
                            
                            let artistVal = document.getElementById(`artist-${safeId}`) ? document.getElementById(`artist-${safeId}`).value : item.suggest_artist;
                            let titleVal = document.getElementById(`title-${safeId}`) ? document.getElementById(`title-${safeId}`).value : item.suggest_title;
                            let albumVal = document.getElementById(`album-${safeId}`) ? document.getElementById(`album-${safeId}`).value : item.suggest_album;
                            let savedGenreVal = document.getElementById(`genre-${safeId}`) ? document.getElementById(`genre-${safeId}`).value : null;
                            
                            let currentGenre = (item.shazam_status === 'success') ? item.suggest_genre : (savedGenreVal !== null ? savedGenreVal : item.suggest_genre);
                            
                            let genreOptions = `<option value="">-- Blank --</option>`;
                            let genreFound = false;
                            VALID_GENRES.forEach(g => {
                                let isSelected = (g === currentGenre);
                                if (isSelected) genreFound = true;
                                genreOptions += `<option value="${g}" ${isSelected ? 'selected' : ''}>${g}</option>`;
                            });
                            if (currentGenre && !genreFound) genreOptions += `<option value="${escapeHtml(currentGenre)}" selected>${escapeHtml(currentGenre)}</option>`;
                            
                            let readonlyAttr = (item.shazam_status === 'success') ? 'readonly style="background:#1a1a1a; color:#888; cursor:not-allowed;" title="Locked by Shazam"' : '';
                            let selectDisabledAttr = (item.shazam_status === 'success') ? 'disabled title="Locked by Shazam"' : '';
                            let disableSubmit = (item.shazam_status === 'waiting') ? 'disabled' : '';
                            
                            tr.innerHTML = `
                                <td>
                                    ${badgeHtml}
                                    <div style="word-break: break-all; font-weight:bold; margin-top:5px;">${escapeHtml(item.filename)}</div>
                                    ${audioHtml}
                                </td>
                                <td><div style="font-size:0.8em; color:#888; margin-bottom:4px;">Artist</div><input type="text" id="artist-${safeId}" value="${escapeHtml((item.shazam_status == 'success') ? item.suggest_artist : artistVal)}" ${readonlyAttr}></td>
                                <td><div style="font-size:0.8em; color:#888; margin-bottom:4px;">Title</div><input type="text" id="title-${safeId}" value="${escapeHtml((item.shazam_status == 'success') ? item.suggest_title : titleVal)}" ${readonlyAttr}></td>
                                <td><div style="font-size:0.8em; color:#888; margin-bottom:4px;">Album</div><input type="text" id="album-${safeId}" placeholder="Unknown Album" value="${escapeHtml((item.shazam_status == 'success') ? item.suggest_album : albumVal)}" ${readonlyAttr}></td>
                                <td><div style="font-size:0.8em; color:#888; margin-bottom:4px;">Genre</div><select id="genre-${safeId}" ${selectDisabledAttr}>${genreOptions}</select></td>
                                <td>
                                    <button class="btn-action btn-submit" ${disableSubmit} onclick="confirmFile(window.DraftFiles['${safeId}'], '${safeId}').then(()=> { document.getElementById('${rowId}').remove(); fetchData(); }).catch(e => console.log('Submit handled'))">✅ Submit</button>
                                    <button class="btn-action btn-delete" onclick="deleteDraft(window.DraftFiles['${safeId}'])">🗑️ Delete</button>
                                </td>
                            `;
                            if(currentAudio) tr.querySelector('audio').replaceWith(currentAudio);
                        });
                        
                        existingRows.forEach(row => { if(!activeRowIds.has(row.id)) row.remove(); });
                    }

                    if(data.live.length === 0) {
                        queueBody.innerHTML = '<tr><td colspan="3" style="text-align:center; color:#888;">Live queue is empty.</td></tr>';
                    } else {
                        queueBody.innerHTML = '';
                        data.live.forEach(item => {
                            const qSafeId = 'q' + btoa(encodeURIComponent(item.filename)).replace(/[^a-zA-Z0-9]/g, '');
                            window.QueueFiles[qSafeId] = item.filename;

                            const tr = document.createElement('tr');
                            let statusHtml = ''; let actionHtml = '';
                            if(item.age_seconds < 90) {
                                let sLeft = Math.floor(90 - item.age_seconds);
                                statusHtml = `<span class="status-waiting">⏳ Waiting (${Math.floor(sLeft/60)}m ${sLeft%60}s)</span>`;
                                actionHtml = `<button class="btn-action btn-delete" onclick="deleteQueue(window.QueueFiles['${qSafeId}'])" style="width:auto;">🗑️ Cancel</button>`;
                            } else {
                                statusHtml = `<span class="status-processing">⚙️ Locked by Processor</span>`;
                                actionHtml = `<span style="color:#666;">Locked</span>`;
                            }
                            tr.innerHTML = `<td>${escapeHtml(item.filename)}</td><td>${statusHtml}</td><td>${actionHtml}</td>`;
                            queueBody.appendChild(tr);
                        });
                    }
                });
        }

        fetchData();
        setInterval(fetchData, 3000);
    </script>
</body>
</html>
"""

@app.route('/add-music', methods=['GET'])
@requires_auth
def index():
    return render_template_string(HTML_PAGE)

@app.route('/add-music/data', methods=['GET'])
@requires_auth
def get_data():
    drafts, live, logs = [], [], []
    
    if os.path.exists(DRAFTS):
        for f in os.listdir(DRAFTS):
            path = os.path.join(DRAFTS, f)
            if not os.path.isfile(path): continue
            
            if allowed_file(f):
                stats = os.stat(path)
                shazam_data = SHAZAM_CACHE.get(f, {})
                status = shazam_data.get('status', 'waiting')
                
                if status == 'success':
                    shazam_artist = shazam_data.get('artist', '')
                    shazam_title = shazam_data.get('title', '')
                    shazam_album = shazam_data.get('album', '')
                    shazam_genre = shazam_data.get('genre', '')
                else:
                    name_no_ext, _ = os.path.splitext(f)
                    parts = re.split(r'\s+-\s+', name_no_ext, maxsplit=1)
                    if len(parts) == 2:
                        shazam_artist, shazam_title = parts[0].strip(), parts[1].strip()
                    else:
                        shazam_artist = ""
                        shazam_title = name_no_ext.strip()
                        
                    shazam_album = ""
                    shazam_genre = ""
                    try:
                        audio = mutagen.File(path, easy=True)
                        if audio:
                            if 'album' in audio: shazam_album = str(audio['album'][0])
                            if 'genre' in audio: shazam_genre = normalize_genre(audio['genre'][0])
                    except Exception:
                        pass
                    
                drafts.append({
                    'filename': f, 'mtime': stats.st_mtime,
                    'suggest_artist': shazam_artist, 'suggest_title': shazam_title, 
                    'suggest_album': shazam_album, 'suggest_genre': shazam_genre,
                    'shazam_status': status
                })
                
    if os.path.exists(INBOX):
        for f in os.listdir(INBOX):
            path = os.path.join(INBOX, f)
            if not os.path.isfile(path): continue
            if allowed_file(f):
                live.append({'filename': f, 'age_seconds': time.time() - os.stat(path).st_mtime, 'mtime': os.stat(path).st_mtime})
                
    if os.path.exists(LOGS):
        try:
            with open(LOGS, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                logs = [line.strip() for line in lines[-25:] if line.strip()]
                logs.reverse()
        except Exception:
            pass

    drafts.sort(key=lambda x: x['mtime'])
    live.sort(key=lambda x: x['mtime'])
    return jsonify({'drafts': drafts, 'live': live, 'logs': logs})

@app.route('/add-music/play/draft/<filename>', methods=['GET'])
@requires_auth
def play_draft(filename):
    return send_file(os.path.join(DRAFTS, make_safe_filename(filename)), mimetype="audio/mpeg")

@app.route('/add-music/draft/all', methods=['DELETE'])
@requires_auth
def delete_all_drafts():
    if os.path.exists(DRAFTS):
        for f in os.listdir(DRAFTS):
            if allowed_file(f):
                try: os.remove(os.path.join(DRAFTS, f))
                except Exception: pass
    return jsonify({'success': 'Deleted all'})

@app.route('/add-music/draft/<filename>', methods=['DELETE'])
@requires_auth
def delete_draft(filename):
    path = os.path.join(DRAFTS, make_safe_filename(filename))
    if os.path.exists(path):
        os.remove(path)
        return jsonify({'success': 'Deleted'})
    return jsonify({'error': 'Not found'}), 404

@app.route('/add-music/queue/all', methods=['DELETE'])
@requires_auth
def delete_all_queue():
    count = 0
    if os.path.exists(INBOX):
        for f in os.listdir(INBOX):
            path = os.path.join(INBOX, f)
            if os.path.isfile(path) and allowed_file(f):
                if (time.time() - os.path.getmtime(path)) < PROCESS_DELAY:
                    try:
                        os.remove(path)
                        count += 1
                    except Exception: pass
    return jsonify({'success': f'Cancelled {count} items'})

@app.route('/add-music/queue/<filename>', methods=['DELETE'])
@requires_auth
def delete_queue(filename):
    path = os.path.join(INBOX, make_safe_filename(filename))
    if os.path.exists(path) and (time.time() - os.path.getmtime(path)) < PROCESS_DELAY:
        os.remove(path)
        return jsonify({'success': 'Deleted'})
    return jsonify({'error': 'Not found or Locked'}), 400

@app.route('/add-music/confirm/<filename>', methods=['POST'])
@requires_auth
def confirm_file(filename):
    safe_filename = make_safe_filename(filename)
    draft_path = os.path.join(DRAFTS, safe_filename)
    if not os.path.exists(draft_path): return jsonify({'error': 'Not found in Drafts folder'}), 404
    
    time.sleep(0.5) 
    
    data = request.json or {}
    artist, title, album, genre = data.get('artist'), data.get('title'), data.get('album'), data.get('genre')
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            audio = mutagen.File(draft_path, easy=True)
            
            if audio is None and draft_path.lower().endswith('.mp3'):
                from mutagen.mp3 import MP3
                tmp = MP3(draft_path)
                try: tmp.add_tags()
                except Exception: pass
                tmp.save()
                audio = mutagen.File(draft_path, easy=True)
                
            if audio is not None:
                if artist: audio['artist'] = artist
                elif 'artist' in audio: del audio['artist']
                
                if title: audio['title'] = title
                elif 'title' in audio: del audio['title']
                
                if album: audio['album'] = album
                elif 'album' in audio: del audio['album']
                
                if genre: audio['genre'] = genre
                elif 'genre' in audio: del audio['genre']
                
                audio.save()
            break 
            
        except PermissionError:
            if attempt < max_retries - 1:
                time.sleep(1) 
            else:
                return jsonify({'error': 'File is heavily locked by Windows or another program. Please wait a moment and try again.'}), 500
        except Exception as e: 
            print(f"Tag error: {e}")
            break 
            
    inbox_path = os.path.join(INBOX, safe_filename)
    if os.path.exists(inbox_path):
        name, ext = os.path.splitext(safe_filename)
        inbox_path = os.path.join(INBOX, f"{name}_{int(time.time())}{ext}")
        
    try:
        shutil.move(draft_path, inbox_path)
        os.utime(inbox_path, None)
        return jsonify({'success': 'Moved to live queue'})
    except PermissionError:
        return jsonify({'error': 'Cannot move the file. Windows is blocking it (WinError 32). Please wait 5 seconds and try again.'}), 500
    except Exception as e:
        return jsonify({'error': f'Failed to move file: {str(e)}'}), 500

@app.route('/add-music/upload', methods=['POST'])
@requires_auth
def upload_file():
    if 'file' not in request.files: return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    if not allowed_file(file.filename): return jsonify({'error': 'Invalid format'}), 400
    
    filename = make_safe_filename(file.filename)
    draft_path = os.path.join(DRAFTS, filename)
    inbox_path = os.path.join(INBOX, filename)
    
    if os.path.exists(draft_path): return jsonify({'error': f'"{filename}" is already in the Drafts queue!'}), 400
    if os.path.exists(inbox_path): return jsonify({'error': f'"{filename}" is already in the Live Processing queue!'}), 400
        
    file.save(draft_path)
    return jsonify({'success': 'Saved'})

if __name__ == '__main__':
    os.makedirs(INBOX, exist_ok=True)
    os.makedirs(DRAFTS, exist_ok=True)
    app.run(host='0.0.0.0', port=5000)