 const themen = [
        "Recht auf Gefühlsvorderung", "Wie werde ich Mensch", "Glaube an Friede",
        "Programm für Bürgerliche Rechte", "Moralische Pflicht und Verantwortung",
        "Menschlichkeit Wiederherstellung", "Kinderschutz-Pflicht-Elternrechte",
        "Wahre Richtung und Kunst", "LGBTQ und Kirche", "Trend und Tradition",
        "Religionsbekenntnis oder Selbstwahl", "Gesundheitswesen und Verhalten",
        "Arbeitswelt und Du", "Mobbing am Arbeitsplatz", "Jugendsprecher",
        "Ratgeber für Pensionisten", "Sozialgefallen und Widerkehr",
        "Nachbarschaft und Gemeinschaft", "Alleinerziehend", "Die Brücke",
        "Kapital und Verwaltung", "Globale Verbundenheit"
    ];
    // Sektor 21 & 22 (Index 20 & 21) sind statische Admin-Platzhalter: für User gesperrt.
    const GESPERRTE_THEMEN_IDX = new Set([20, 21]);

    const ADMIN_EMAIL = "mmcommunity22@gmail.com";
    let userEmail = "";
    let isAdmin = false;
    let meinProfil = { profilbild: "", biografie: "", benutzername: "", vorname: "", nachname: "" };
    // SYSTEM 3: serverseitig bestimmte Rolle + Rechte (Client spiegelt nur, Grenze bleibt am Server).
    let meineRolle = "basis";
    let meineRechte = { darf_profilsuche: false, darf_live: false, darf_reservieren: false, darf_einladen: false, post_limit: 1, verbleibende_posts: 1 };

    // SYSTEM 2: Google-Autofill-Popups ("Adressen verwalten …") restlos unterbinden –
    // autocomplete="off" auf ALLE (auch dynamisch erzeugten) Eingabefelder erzwingen.
    (function unterbindeAutofill() {
        function killAC(root) {
            if (!root || !root.querySelectorAll) return;
            root.querySelectorAll('input, textarea, select').forEach(el => {
                el.setAttribute('autocomplete', 'off');
                el.setAttribute('autocorrect', 'off');
                el.setAttribute('autocapitalize', 'off');
                if (!el.getAttribute('name')) el.setAttribute('name', 'mm-' + Math.random().toString(36).slice(2, 9));
            });
        }
        document.addEventListener('DOMContentLoaded', () => killAC(document));
        try {
            const mo = new MutationObserver(muts => muts.forEach(m => m.addedNodes.forEach(n => {
                if (n.nodeType === 1) { if (n.matches && n.matches('input, textarea, select')) n.setAttribute('autocomplete', 'off'); killAC(n); }
            })));
            mo.observe(document.documentElement, { childList: true, subtree: true });
        } catch (e) {}
    })();

    let aktivesThemaIdx = null;         // 0-basiert; backend sektor = idx + 1

    // Stream (Infinite Scroll): geladene Beiträge + Render-Zeiger
    let streamBeitraege = [];
    let streamGerendert = 0;
    const STREAM_BATCH = 6;
    let streamObserver = null;
    let currentSocket = null;

    window.verbindeLive = function(beitragId) {
    if (currentSocket) currentSocket.close();
    currentSocket = new WebSocket(`ws://${window.location.host}/ws/forum/${beitragId}`);
    currentSocket.onmessage = function(event) {
        const data = JSON.parse(event.data);
        if (data.type === "neuer_kommentar") {
            const kContainer = document.getElementById('komm-' + data.beitrag_id);
            const box = document.getElementById('komm-box-' + data.beitrag_id);
            const postHandle = box ? box.getAttribute('data-ersteller-handle') : '';
            const postName = box ? box.getAttribute('data-ersteller-name') : '';
            if (kContainer) {
                kContainer.insertAdjacentHTML('beforeend', renderKommentar(data.kommentar, postHandle, postName, data.beitrag_id));
                const zaehlerSpan = document.getElementById('komm-zaehler-' + data.beitrag_id);
                if (zaehlerSpan) zaehlerSpan.textContent = parseInt(zaehlerSpan.textContent) + 1;
            }
        }
    };
};

    function backendSektor() { return (aktivesThemaIdx === null) ? null : (aktivesThemaIdx + 1); }
    function escapeHtml(s) { return (s || "").replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

    // =====================================================================
    // AUTH-SCHLEUSE
    // =====================================================================
    let authProfilbildBase64 = "";
    function authZeige(panel) {
        ['login','register','verify','profil'].forEach(p => {
            const el = document.getElementById('auth-panel-'+p);
            if (el) el.classList.toggle('aktiv', p === panel);
        });
    }
    function authMsg(id, text, ok) { const el = document.getElementById(id); if (el){ el.textContent = text||""; el.classList.toggle('ok', !!ok);} }

    async function authRegister() {
        const name = document.getElementById('reg-name').value.trim();
        const email = document.getElementById('reg-email').value.trim().toLowerCase();
        const pass = document.getElementById('reg-pass').value;
        if (!name) return authMsg('reg-msg', "Bitte deinen echten Vor- und Nachnamen angeben.");
        if (!email || !email.includes('@')) return authMsg('reg-msg', "Bitte eine gültige E-Mail angeben.");
        if (pass.length < 6) return authMsg('reg-msg', "Das Passwort braucht mindestens 6 Zeichen.");
        authMsg('reg-msg', "Sende …", true);
        try {
            const res = await fetch('/auth/register', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email, real_name: name, passwort: pass }) });
            const data = await res.json();
            if (data.success) {
                userEmail = email;
                document.getElementById('verify-email-anzeige').textContent = email;
                const teile = name.split(/\s+/);
                document.getElementById('prof-vorname').value = teile[0] || "";
                document.getElementById('prof-nachname').value = teile.slice(1).join(' ');
                authMsg('reg-msg', data.message, true);
                authZeige('verify');
            } else {
                authMsg('reg-msg', data.message || "Registrierung fehlgeschlagen.");
                if (data.status === 'existiert') authZeige('login');
            }
        } catch (e) { authMsg('reg-msg', "Server-Verbindung fehlgeschlagen."); }
    }

    async function authVerify() {
        const email = userEmail || document.getElementById('reg-email').value.trim().toLowerCase();
        const code = document.getElementById('verify-code').value.trim();
        if (code.length !== 6) return authMsg('verify-msg', "Bitte den 6-stelligen Code eingeben.");
        authMsg('verify-msg', "Prüfe …", true);
        try {
            const res = await fetch('/auth/verify-code', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email, code }) });
            const data = await res.json();
            if (data.success) { userEmail = email; authMsg('verify-msg', "E-Mail bestätigt!", true); authZeige('profil'); }
            else authMsg('verify-msg', data.message || "Code ungültig.");
        } catch (e) { authMsg('verify-msg', "Server-Verbindung fehlgeschlagen."); }
    }

    async function authResend() {
        const email = userEmail || document.getElementById('reg-email').value.trim().toLowerCase();
        if (!email) return;
        try { await fetch('/auth/resend-code', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email }) }); authMsg('verify-msg', "Code erneut gesendet.", true); } catch (e) {}
    }

    function authBildVorschau() {
        const file = document.getElementById('prof-bild').files[0];
        if (!file) { authProfilbildBase64 = ""; return; }
        const reader = new FileReader();
        reader.onload = e => { authProfilbildBase64 = e.target.result; document.getElementById('auth-avatar-vorschau').style.backgroundImage = `url(${authProfilbildBase64})`; };
        reader.readAsDataURL(file);
    }

    async function authProfil() {
        const email = userEmail;
        const vorname = document.getElementById('prof-vorname').value.trim();
        const nachname = document.getElementById('prof-nachname').value.trim();
        const handle = document.getElementById('prof-handle').value.trim();
        if (!vorname || !nachname) return authMsg('prof-msg', "Echter Vor- und Nachname sind Pflicht.");
        if (!handle) return authMsg('prof-msg', "Bitte einen Benutzernamen / Handle wählen.");
        authMsg('prof-msg', "Speichere …", true);
        try {
            const res = await fetch('/auth/profil', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email, vorname, nachname, benutzername: handle, profilbild: authProfilbildBase64 }) });
            const data = await res.json();
            if (data.success) { authMsg('prof-msg', "Zugang freigeschaltet!", true); authAbschluss(email, data); }
            else authMsg('prof-msg', data.message || "Speichern fehlgeschlagen.");
        } catch (e) { authMsg('prof-msg', "Server-Verbindung fehlgeschlagen."); }
    }

    async function authLogin() {
        const email = document.getElementById('login-email').value.trim().toLowerCase();
        const pass = document.getElementById('login-pass').value;
        if (!email || !pass) return authMsg('login-msg', "Bitte E-Mail und Passwort eingeben.");
        authMsg('login-msg', "Prüfe …", true);
        try {
            const res = await fetch('/auth/login', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email, passwort: pass }) });
            const data = await res.json();
            if (data.success) {
                userEmail = email;
                if (data.stufe === 'verify') { document.getElementById('verify-email-anzeige').textContent = email; authMsg('login-msg', data.message, true); authZeige('verify'); }
                else if (data.stufe === 'profil') { authMsg('login-msg', data.message, true); authZeige('profil'); }
                else authAbschluss(email, data);
            } else authMsg('login-msg', data.message || "Login fehlgeschlagen.");
        } catch (e) { authMsg('login-msg', "Server-Verbindung fehlgeschlagen."); }
    }

    // Zugang gewährt -> Schleuse schließen, 3-Spalten-Dashboard freigeben.
    function authAbschluss(email, data) {
        userEmail = email;
        isAdmin = (data.role === "admin") || (data.co_assistent_modus === true) || (email.toLowerCase() === ADMIN_EMAIL);
        // TEMPORÄR (bis zur DB-Migration): Profil-ID lokal ablegen -> wird an Posts gehängt.
        localStorage.setItem('mm_profil_id', (data.profil && data.profil.benutzername) ? data.profil.benutzername : email);
        const p = data.profil || {};
        meinProfil = {
            profilbild: p.profilbild || "", biografie: p.biografie || "",
            benutzername: p.benutzername || "", vorname: p.vorname || "", nachname: p.nachname || ""
        };
        setzeHeaderAvatar();
        baueSidebar();
        document.getElementById('auth-gate').style.display = 'none';
        document.getElementById('app-header').classList.add('aktiv');
        document.getElementById('dashboard').classList.add('aktiv');
        ladeMeineRolle();
        // Griff/Button des schwebenden Live-Panels initial setzen (Admin = sofort grün).
        aktualisiereLivePanelStatus();
    }

    // SYSTEM 3: Rolle + Rechte vom Server holen und im Header anzeigen.
    async function ladeMeineRolle() {
        try {
            const res = await fetch(`/api/rolle?email=${encodeURIComponent(userEmail)}`);
            const d = await res.json();
            if (d.success) { meineRolle = d.rolle; meineRechte = d; }
        } catch (e) {}
        const badge = document.getElementById('header-rolle');
        if (badge) {
            const label = { admin: '👑 Admin', premium: '⭐ Premium', verifiziert: '✅ Verifiziert', basis: '• Basis', gast: 'Gast' };
            badge.textContent = label[meineRolle] || meineRolle;
            badge.className = 'header-rolle rolle-' + meineRolle;
        }
    }

    function setzeHeaderAvatar() {
        const av = document.getElementById('header-avatar');
        if (!av) return;
        if (meinProfil.profilbild) { av.style.backgroundImage = `url(${meinProfil.profilbild})`; av.textContent = ""; }
        else { av.style.backgroundImage = "none"; av.textContent = (meinProfil.vorname || userEmail || "M").charAt(0).toUpperCase(); }
    }

    // =====================================================================
    // LINKS: HAMBURGER-MENÜ (8 eigenständige Hauptkacheln, keine Untermenüs)
    // Konfigurationsgetrieben: neue Bereiche docken über SIDEBAR_KACHELN und
    // PANEL_HANDLER an, OHNE die Menü-Logik selbst zu verändern.
    // =====================================================================
    function schubladeToggle() { document.getElementById('drawer').classList.toggle('zu'); }

    // Themen-Hub baut die 20 Sektoren (21/22 liegen in 'Gemeinschaft & Transparenz').
    function baueThemenHubInhalt(container) {
        for (let i = 0; i < 20; i++) {
            const btn = document.createElement('button');
            btn.className = 'thema-btn'; btn.id = 'thema-' + i;
            btn.innerHTML = `<span class="nr">${i + 1}</span>${escapeHtml(themen[i])}`;
            btn.addEventListener('click', () => waehleThema(i));
            container.appendChild(btn);
        }
    }

    // Inhalt der Kachel 'Gemeinschaft & Transparenz' (Sektoren 21/22).
    function baueGemeinschaftInhalt(container) {
        const kinder = [
            { label: 'Kapital & Verantwortung', action: () => waehleThema(20), sektor: 21 },
            { label: 'Kollektiv', action: () => waehleThema(21), sektor: 22 },
        ];
        kinder.forEach(kind => {
            const gesperrt = kind.sektor && GESPERRTE_THEMEN_IDX.has(kind.sektor - 1) && !isAdmin;
            const b = document.createElement('button');
            b.className = 'menu-sub' + (gesperrt ? ' gesperrt' : '');
            b.innerHTML = escapeHtml(kind.label) + (gesperrt ? `<span class="schloss">🔒</span>` : "");
            b.addEventListener('click', kind.action);
            container.appendChild(b);
        });
    }

    // Zentrale Menü-Struktur: 8 EIGENSTÄNDIGE HAUPTKACHELN – keine Untermenüs.
    // Kacheln mit 'bauInhalt' klappen ihren Inhalt inline auf (Themen/Gemeinschaft);
    // alle übrigen sind Ein-Klick-Aktionen, die direkt ihr Panel/Overlay öffnen.
    const SIDEBAR_KACHELN = [
        { id: 'themen',       titel: '🗂️ Themen-Hub',                        offen: true, bauInhalt: baueThemenHubInhalt },
        { id: 'gemeinschaft', titel: '🤝 Gemeinschaft & Transparenz',        bauInhalt: baueGemeinschaftInhalt },
        { id: 'profil',       titel: '👤 Profil-Einstellungen',              action: oeffneProfilHub },
        { id: 'konto',        titel: '🔐 Konto & Sicherheit',                action: () => oeffnePanel('konto-sicherheit') },
        { id: 'account',      titel: '📇 Mein Account',                      action: () => oeffnePanel('mein-account') },
        { id: 'zugang',       titel: '🪪 Zugangsdaten',                      action: () => oeffnePanel('zugangsdaten') },
        { id: 'tisch',        titel: '🍽️ Tisch-Reservierungen',             action: () => oeffneSchublade('reservierung') },
        { id: 'live',         titel: '🎥 Anmeldeoptionen für Live-Sektoren', action: () => oeffneSchublade('live-anmeldung') },
    ];

    function baueSidebar() {
        const liste = document.getElementById('drawer-liste');
        if (!liste) return;
        liste.innerHTML = "";
        SIDEBAR_KACHELN.forEach(kachel => {
            const g = document.createElement('div');
            g.className = 'menu-gruppe' + (kachel.offen ? ' offen' : '');
            const kopf = document.createElement('div');
            kopf.className = 'menu-gruppe-kopf';
            if (kachel.bauInhalt) {
                kopf.innerHTML = `<span>${kachel.titel}</span><span class="chev">▶</span>`;
                kopf.addEventListener('click', () => g.classList.toggle('offen'));
                const inhalt = document.createElement('div');
                inhalt.className = 'menu-gruppe-inhalt';
                kachel.bauInhalt(inhalt);
                g.appendChild(kopf); g.appendChild(inhalt);
            } else {
                kopf.classList.add('menu-kachel-aktion');
                kopf.innerHTML = `<span>${kachel.titel}</span>`;
                kopf.addEventListener('click', kachel.action);
                g.appendChild(kopf);
            }
            liste.appendChild(g);
        });
    }

    // Statische Rechtsseiten: direkt aus dem static/-Ordner (Backend-Routen).
    function oeffneStatik(name) { window.open('/' + name, '_blank'); }

    // ---- Generisches Panel-System (modularer Andockpunkt) ----
    const PANEL_HANDLER = {
        'support': panelSupport,
        'tisch': panelTischReservierungen,
        'live-optionen': panelLiveOptionen,
        'konto-sicherheit': panelKontoSicherheit,
        'mein-account': panelMeinAccount,
        'zugangsdaten': panelZugangsdaten,
    };
    function setzePanelKopf(titel, hint) {
        document.getElementById('menu-panel-titel').textContent = titel;
        document.getElementById('menu-panel-hint').textContent = hint || "";
    }
    function oeffnePanel(key) {
        const handler = PANEL_HANDLER[key];
        if (!handler) return;
        const body = document.getElementById('menu-panel-body');
        body.innerHTML = "";
        handler(body);
        document.getElementById('menu-panel').classList.add('aktiv');
    }
    function schliesseMenuPanel() { document.getElementById('menu-panel').classList.remove('aktiv'); }

    // =====================================================================
    // MITTE: IN-SPALTEN-SCHUBLADE (8 Navigations-Kacheln des hellblauen Bereichs)
    // Die Schublade ist exakt auf die stream-spalte begrenzt und entfaltet sich
    // unter der fixierten Navigationsleiste von oben nach unten.
    // =====================================================================
    let aktiveSchublade = null;
    function ssHinweis(text) { return `<div class="ss-card" style="text-align:center; color:#cfd8e3;">${text}</div>`; }
    function setzeSchubladeKopf(titel, hint) {
        document.getElementById('ss-titel').textContent = titel;
        document.getElementById('ss-hint').textContent = hint || "";
    }
    function oeffneSchublade(key) {
        const handler = SCHUBLADE_HANDLER[key];
        if (!handler) return;
        // Beim Wechsel WEG von der Live-Schleuse deren Kamera/Mikro/Timer freigeben.
        if (aktiveSchublade === 'live-anmeldung' && key !== 'live-anmeldung' && typeof laTeardown === 'function') laTeardown();
        aktiveSchublade = key;
        document.querySelectorAll('.sn-kachel').forEach(b => b.classList.toggle('aktiv', b.dataset.key === key));
        const body = document.getElementById('ss-body');
        body.innerHTML = "";
        handler(body);
        document.getElementById('sektor-schublade').classList.add('offen');
    }
    function schliesseSchublade() {
        // Live-Schleuse sauber herunterfahren (Kamera/Mikro-Vorschau + Poll-Timer).
        if (aktiveSchublade === 'live-anmeldung' && typeof laTeardown === 'function') laTeardown();
        const sch = document.getElementById('sektor-schublade');
        if (sch) sch.classList.remove('offen');
        aktiveSchublade = null;
        document.querySelectorAll('.sn-kachel').forEach(b => b.classList.remove('aktiv'));
    }

    // ---- 1) Sektoren-Support (sektor-sensitive KI-Seele) ----
    function schubladeSupport(body) {
        const sektor = backendSektor() || 1;
        const thema = themen[sektor - 1] || 'die Community';
        setzeSchubladeKopf('Sektoren-Support', `Sektor-sensitive Begleitung · Sektor ${sektor}: ${thema}`);
        body.innerHTML = `
            <div class="ss-card">
                <div class="support-chat" id="support-chat">
                    <div class="s-ki"><b>M&M Support:</b> Die Begleit-Seele für „${escapeHtml(thema)}" ist bereit. Wie kann ich dir helfen?</div>
                </div>
                <div class="support-eingabe">
                    <input type="text" id="support-in" placeholder="Deine Frage …" onkeypress="if(event.key==='Enter')sendeSupport()">
                    <button onclick="sendeSupport()">Senden</button>
                </div>
            </div>`;
    }

    // ---- 2) Beitrag erstellen (öffnet je Beitragsart die Eingabe-Maske) ----
    function schubladeBeitrag(body) {
        setzeSchubladeKopf('Beitrag erstellen', 'Wähle eine Beitragsart – die Eingabe öffnet sich als Maske.');
        if (aktivesThemaIdx === null) { body.innerHTML = ssHinweis('Bitte wähle zuerst links ein Thema, um zu posten.'); return; }
        if (GESPERRTE_THEMEN_IDX.has(aktivesThemaIdx) && !isAdmin) { body.innerHTML = ssHinweis('Dieses Thema ist noch nicht zum Posten freigeschaltet.'); return; }
        body.innerHTML = `
            <div class="ss-chips">
                <div class="ss-chip" onclick="oeffneBeitragMaske('gedanke')"><span class="cs-icon">💭</span>Gedanke</div>
                <div class="ss-chip" onclick="oeffneBeitragMaske('medien')"><span class="cs-icon">🖼️</span>Medien</div>
                <div class="ss-chip" onclick="oeffneBeitragMaske('diskurs')"><span class="cs-icon">💬</span>Diskurs</div>
                <div class="ss-chip" onclick="oeffneBeitragMaske('ressource')"><span class="cs-icon">🔗</span>Ressource</div>
            </div>`;
    }

    // ---- 3-5) Archive: gefilterter Stream nach Beitragsart ----
    async function schubladeArchiv(body, typ, titel, hint) {
        setzeSchubladeKopf(titel, hint);
        const sektor = backendSektor();
        if (!sektor) { body.innerHTML = ssHinweis('Bitte wähle zuerst links ein Thema.'); return; }
        body.innerHTML = `<p style="color:#123; text-align:center;">Lade …</p>`;
        try {
            const res = await fetch(`/api/forum/posts?email=${encodeURIComponent(userEmail)}&sektor=${sektor}&typ=${encodeURIComponent(typ)}`);
            const d = await res.json();
            if (!d.success) { body.innerHTML = ssHinweis(escapeHtml(d.message) || 'Kein Zugriff.'); return; }
            const items = d.beitraege || [];
            if (!items.length) { body.innerHTML = ssHinweis('Noch keine Einträge dieser Art in diesem Sektor.'); return; }
            body.innerHTML = `<div class="stream-liste">${items.map(renderBeitrag).join('')}</div>`;
        } catch (e) { body.innerHTML = ssHinweis('Fehler beim Laden.'); }
    }

    // ---- 6) Profilsuche (Mitglieder, nur öffentliche Felder) ----
    // ---- 6) Profilsuche (SYSTEM 2: geleerte Fläche · Land/Stadt · Fotokacheln) ----
    // ===== STÖBER- & ENTDECKUNGS-SUITE (Zwei-Modus: gezielte Suche <-> Radar) =====
    let psState = null, psDebounce = null, psObserver = null;
    function schubladeProfilsuche(body) {
        setzeSchubladeKopf('Community-Radar', 'Tippe einen Namen für die gezielte Suche – oder lass das Feld leer und stöbere per Ort, Umkreis, Status und Buchstabe.');
        if (!(meineRechte.darf_profilsuche || isAdmin)) {
            body.innerHTML = ssHinweis('🔒 Die Profilsuche ist erst für verifizierte Mitglieder verfügbar. Vervollständige dein Profil inklusive Profilbild, um freigeschaltet zu werden.');
            return;
        }
        psState = { q:'', land:'', stadt:'', umkreis:'land', status:'alle', buchstabe:'', offset:0, mehr:false, laden:false };
        const statusLabels = { alle:'Alle', online:'🟢 Online', verifiziert:'✔ Verifiziert', neu:'✨ Neu' };
        body.innerHTML = `
            <div class="ps-suite">
                <div class="ps-filter">
                    <div class="ps-feld"><label class="b-label">Name / @Handle</label>
                        <input type="text" id="ps-q" placeholder="leer = Radar-Modus (stöbern)" autocomplete="off" oninput="psFilterGeaendert()"></div>
                    <div class="ps-feld"><label class="b-label">Land</label>
                        <input type="text" id="ps-land" placeholder="z. B. Österreich" autocomplete="off" oninput="psFilterGeaendert()"></div>
                    <div class="ps-feld"><label class="b-label">Stadt</label>
                        <input type="text" id="ps-stadt" placeholder="z. B. Bregenz" autocomplete="off" oninput="psFilterGeaendert()"></div>
                    <div class="ps-feld"><label class="b-label">Umkreis</label>
                        <select id="ps-umkreis" onchange="psFilterGeaendert()">
                            <option value="stadt">Nur Stadt</option>
                            <option value="5">5 km</option><option value="20">20 km</option>
                            <option value="50">50 km</option><option value="100">100 km</option>
                            <option value="land" selected>Ganzes Land</option>
                        </select></div>
                </div>
                <div class="ps-status" id="ps-status">${
                    Object.keys(statusLabels).map(s => `<button class="ps-status-btn ${s==='alle'?'an':''}" data-s="${s}" onclick="psStatus('${s}')">${statusLabels[s]}</button>`).join('')
                }</div>
                <div class="ps-azleiste" id="ps-az">${
                    ['#'].concat('ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')).map(b => `<button class="ps-az-btn" data-b="${b}" onclick="psBuchstabe('${b}')">${b}</button>`).join('')
                }</div>
                <div id="ps-ergebnis" class="ps-ergebnis">
                    <div class="ps-grid" id="ps-grid"></div>
                    <div id="ps-status-text" class="ps-status-text"></div>
                    <div id="ps-sentinel"></div>
                </div>
            </div>`;
        praesenzPing();
        psInfiniteScrollBinden();
        psNeuLaden();   // Radar startet sofort -> die Community ist direkt sichtbar
    }
    // Beim Tippen/Filtern entprellt neu laden. Gezielter Modus (Name gefüllt) entschärft die Geo-Felder optisch.
    function psFilterGeaendert() { clearTimeout(psDebounce); psDebounce = setTimeout(psNeuLaden, 300); }
    function psStatus(s) {
        if (!psState) return; psState.status = s;
        document.querySelectorAll('#ps-status .ps-status-btn').forEach(b => b.classList.toggle('an', b.dataset.s === s));
        psNeuLaden();
    }
    function psBuchstabe(b) {
        if (!psState) return; psState.buchstabe = (psState.buchstabe === b) ? '' : b;   // erneuter Klick hebt auf
        document.querySelectorAll('#ps-az .ps-az-btn').forEach(x => x.classList.toggle('an', x.dataset.b === psState.buchstabe));
        psNeuLaden();
    }
    async function psNeuLaden() {
        if (!psState) return;
        psState.q = (document.getElementById('ps-q')||{}).value || '';
        psState.land = (document.getElementById('ps-land')||{}).value || '';
        psState.stadt = (document.getElementById('ps-stadt')||{}).value || '';
        psState.umkreis = (document.getElementById('ps-umkreis')||{}).value || 'land';
        psState.offset = 0; psState.mehr = false;
        const grid = document.getElementById('ps-grid'); if (grid) grid.innerHTML = '';
        // Gezielte Suche ignoriert Geo -> Land/Stadt/Umkreis ausgrauen (reines Signal, Server ignoriert sie ohnehin).
        const gezielt = !!psState.q.trim();
        const felder = document.querySelectorAll('.ps-filter .ps-feld');
        felder.forEach((f, i) => { if (i > 0) f.style.opacity = gezielt ? 0.4 : 1; });
        await psLadeSeite();
    }
    async function psLadeSeite() {
        if (!psState || psState.laden) return;
        psState.laden = true;
        const grid = document.getElementById('ps-grid'), stt = document.getElementById('ps-status-text');
        if (stt && !grid.children.length) stt.textContent = 'Lade …';
        try {
            const p = new URLSearchParams({ email:userEmail, q:psState.q, land:psState.land, stadt:psState.stadt,
                umkreis:psState.umkreis, status:psState.status, buchstabe:psState.buchstabe, offset:psState.offset, limit:48 });
            const res = await fetch('/api/profil/suche?' + p.toString());
            const d = await res.json();
            if (!d.success) { if (stt) stt.textContent = ''; grid.innerHTML = ssHinweis(escapeHtml(d.message) || 'Suche nicht verfügbar.'); psState.laden = false; return; }
            grid.insertAdjacentHTML('beforeend', (d.treffer || []).map(psKachel).join(''));
            psState.offset += (d.treffer || []).length;
            psState.mehr = !!d.mehr;
            if (stt) stt.textContent = grid.children.length
                ? (d.mehr ? '' : `Alle ${d.anzahl} Treffer geladen.`)
                : (psState.q.trim() ? 'Kein Mitglied mit diesem Namen gefunden.' : 'Keine Mitglieder für diese Filter gefunden.');
        } catch (e) { if (stt) stt.textContent = 'Fehler bei der Suche.'; }
        psState.laden = false;
    }
    function psKachel(t) {
        const ref = escapeHtml(t.ref || t.handle || '');
        const foto = t.profilbild
            ? `<div class="ps-kachel-foto" style="background-image:url('${t.profilbild}')"></div>`
            : `<div class="ps-kachel-foto ps-kein-foto">${escapeHtml((t.name||t.handle||'M').charAt(0).toUpperCase())}</div>`;
        const ort = [t.stadt, t.land].filter(Boolean).map(escapeHtml).join(', ');
        const badges = (t.verifiziert ? '<span class="ps-badge ver" title="Verifiziert">✔</span>' : '')
                     + (t.neu ? '<span class="ps-badge neu" title="Neu dabei">✨</span>' : '');
        return `<div class="ps-kachel" onclick="oeffneFremdprofil('${ref}')">
            ${foto}
            <span class="ps-dot ${t.online?'on':''}" title="${t.online?'Online':'Offline'}"></span>
            <div class="ps-kachel-info">
                <div class="ps-kachel-name">${escapeHtml(t.name || '@'+t.handle)}${t.ich?' · du':''} ${badges}</div>
                ${ort ? `<div class="ps-kachel-ort">📍 ${ort}</div>` : ''}
            </div>
        </div>`;
    }
    // Infinite Scroll: Sentinel am Listenende beobachten (root = nächster scrollbarer Vorfahr oder Viewport).
    function psInfiniteScrollBinden() {
        const sentinel = document.getElementById('ps-sentinel'); if (!sentinel) return;
        if (psObserver) psObserver.disconnect();
        let root = sentinel.parentElement;
        while (root && root !== document.body) { const oy = getComputedStyle(root).overflowY; if (oy === 'auto' || oy === 'scroll') break; root = root.parentElement; }
        psObserver = new IntersectionObserver(entries => {
            if (entries[0].isIntersecting && psState && psState.mehr && !psState.laden) psLadeSeite();
        }, { root: (root && root !== document.body) ? root : null, rootMargin: '300px' });
        psObserver.observe(sentinel);
    }
    // Präsenz-Heartbeat: hält den echten Online-Indikator aktuell, solange die App offen ist.
    function praesenzPing() {
        if (!userEmail) return;
        fetch('/api/praesenz', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email: userEmail }) }).catch(() => {});
    }
    setInterval(praesenzPing, 60000);

    // Zielprofil GENAU so öffnen, wie es der Besitzer auf seinem Canvas gestaltet hat.
    async function oeffneFremdprofil(ref) {
        if (!ref) return;
        const ov = document.getElementById('fremdprofil-overlay');
        const inhalt = document.getElementById('fremdprofil-inhalt');
        inhalt.innerHTML = `<p style="color:#fff; padding:30px; text-align:center;">Lade Profil …</p>`;
        ov.classList.add('aktiv');
        try {
            const res = await fetch(`/api/profil/oeffentlich?email=${encodeURIComponent(userEmail)}&ref=${encodeURIComponent(ref)}`);
            const d = await res.json();
            if (!d.success) { inhalt.innerHTML = `<p style="color:#ff9b9b; padding:30px; text-align:center;">${escapeHtml(d.message||'Profil nicht verfügbar.')}</p>`; return; }
            fremdprofilDaten = d;                                   // Daten für den Zwei-Button-Umschalter merken
            inhalt.innerHTML = fpUmschalter('profil') + rendereCanvasAnsicht(d);
        } catch (e) { inhalt.innerHTML = `<p style="color:#ff9b9b; padding:30px;">Fehler beim Laden.</p>`; }
    }
    function schliesseFremdprofil() { document.getElementById('fremdprofil-overlay').classList.remove('aktiv'); }

    // ---- Besucher-Umschalter: zwei klare Buttons (Profil <-> Galerie), reine Read-only-Ansicht ----
    let fremdprofilDaten = null;
    function fpUmschalter(aktiv) {
        const gs = fremdprofilDaten && fremdprofilDaten.galerie_seite;
        const hatGalerie = gs && ((Array.isArray(gs.elemente) && gs.elemente.length) || (Array.isArray(gs.bilder) && gs.bilder.length));
        return `<div class="fp-umschalter">
            <button class="fp-um-btn ${aktiv==='profil'?'an':''}" onclick="fpZeigeProfil()">👤 Profil anschauen</button>
            <button class="fp-um-btn ${aktiv==='galerie'?'an':''}" ${hatGalerie?'':'disabled'} onclick="fpZeigeGalerie()">🖼 Galerie anschauen</button>
        </div>`;
    }
    function fpZeigeProfil() {
        const inhalt = document.getElementById('fremdprofil-inhalt');
        if (!inhalt || !fremdprofilDaten) return;
        inhalt.innerHTML = fpUmschalter('profil') + rendereCanvasAnsicht(fremdprofilDaten);
    }
    function fpZeigeGalerie() {
        const inhalt = document.getElementById('fremdprofil-inhalt');
        if (!inhalt || !fremdprofilDaten) return;
        inhalt.innerHTML = fpUmschalter('galerie') + rendereGalerieAnsicht(fremdprofilDaten);
    }

    // ---- 7) Workflow-Cockpit (persönlicher Überblick + Schnellaktionen) ----
    async function schubladeWorkflow(body) {
        setzeSchubladeKopf('Workflow-Cockpit', 'Dein persönlicher Überblick: Status, Sektor und schnelle Aktionen.');
        body.innerHTML = `<p style="color:#123;">Lade Cockpit …</p>`;
        try {
            const res = await fetch(`/auth/status?email=${encodeURIComponent(userEmail)}`);
            const s = await res.json();
            const jaNein = v => v ? '✅ Ja' : '—';
            const sektorName = (aktivesThemaIdx !== null) ? `${aktivesThemaIdx + 1}. ${themen[aktivesThemaIdx]}` : 'kein Thema gewählt';
            body.innerHTML = `
                <div class="ss-card">
                    <div class="mp-liste-zeile"><span>Aktueller Sektor</span><b style="color:#ffd700;">${escapeHtml(sektorName)}</b></div>
                    <div class="mp-liste-zeile"><span>Konto-Status</span><b>${escapeHtml(s.konto_status || 'aktiv')}</b></div>
                    <div class="mp-liste-zeile"><span>Zugang frei</span><b>${jaNein(s.zugang_frei)}</b></div>
                    <div class="mp-liste-zeile"><span>Aktives Abo</span><b>${jaNein(s.abo_aktiv)}</b></div>
                    <div class="mp-liste-zeile"><span>Wahrheits-Zertifikat</span><b>${jaNein(s.hat_zertifikat)}</b></div>
                </div>
                <div class="ss-chips">
                    <div class="ss-chip" onclick="oeffneSchublade('beitrag')"><span class="cs-icon">➕</span>Beitrag erstellen</div>
                    <div class="ss-chip" onclick="oeffneSchublade('status')"><span class="cs-icon">📊</span>Sektoren-Status</div>
                    <div class="ss-chip" onclick="schliesseSchublade(); oeffneProfil();"><span class="cs-icon">👤</span>Profil bearbeiten</div>
                    <div class="ss-chip" onclick="oeffneSchublade('profilsuche')"><span class="cs-icon">🔎</span>Profilsuche</div>
                </div>`;
        } catch (e) { body.innerHTML = ssHinweis('Cockpit konnte nicht geladen werden.'); }
    }

    // ---- 8) Sektoren-Status (Übersicht aller 22 Sektoren) ----
    async function schubladeStatus(body) {
        setzeSchubladeKopf('Sektoren-Status', 'Übersicht aller 22 Sektoren: Freigabe, Beiträge und aktive Live-Teilnehmer.');
        body.innerHTML = `<p style="color:#123;">Lade Status …</p>`;
        try {
            const res = await fetch(`/api/sektoren/status?email=${encodeURIComponent(userEmail)}`);
            const d = await res.json();
            if (!d.success) { body.innerHTML = ssHinweis('Status nicht verfügbar.'); return; }
            const zeilen = (d.sektoren || []).map(s => {
                const pill = s.gesperrt ? `<span class="ss-pill gesperrt">gesperrt</span>` : `<span class="ss-pill frei">frei</span>`;
                const klick = s.gesperrt ? '' : `onclick="schliesseSchublade(); waehleThema(${s.sektor - 1});" style="cursor:pointer;"`;
                return `<tr ${klick}><td><b>${s.sektor}</b></td><td>${escapeHtml(s.thema)}</td><td>${pill}</td><td>${s.beitraege}</td><td>${s.live_teilnehmer}</td></tr>`;
            }).join('');
            body.innerHTML = `<table class="ss-status-tabelle">
                <tr><th>#</th><th>Thema</th><th>Status</th><th>Beiträge</th><th>Live</th></tr>
                ${zeilen}</table>`;
        } catch (e) { body.innerHTML = ssHinweis('Status konnte nicht geladen werden.'); }
    }

    // ==================================================================
    // SYSTEM 4: TISCH-RESERVIERUNG & LIVE-HUB (volle mittlere Fläche)
    // ==================================================================
    async function schubladeReservierung(body) {
        setzeSchubladeKopf('Tisch-Reservierungen', 'Plane einen 7+1-Tisch oder betritt den Live-Bereich direkt.');
        const sektor = backendSektor();
        const themaName = (sektor && themen[sektor - 1]) ? themen[sektor - 1] : '— erst links ein Thema wählen —';
        const premium = !!meineRechte.darf_reservieren || isAdmin;
        // Direkter Einstieg + geplante Reservierung als zwei klare Elemente.
        const liveHinweis = premium
            ? 'Betritt sofort den Live-Bereich dieses Themas – ohne Umweg über eine Reservierung.'
            : 'Der Live-Sektor ist Premium-Mitgliedern vorbehalten.';
        const planFormular = premium ? `
            <div class="res-form">
                <label class="b-label">Identität / Anzeigename</label>
                <input type="text" class="p-field" id="res-identitaet" placeholder="Wie du am Tisch erscheinst" value="${escapeHtml((meinProfil.vorname||'') + ' ' + (meinProfil.nachname||'')).trim()}">
                <label class="b-label">Uhrzeit / Zeitraum</label>
                <input type="text" class="p-field" id="res-zeit" placeholder="z. B. Heute 20:00 Uhr">
                <label class="b-label">Thema</label>
                <input type="text" class="p-field" id="res-thema" value="${escapeHtml(sektor ? themen[sektor-1] : '')}" placeholder="z. B. Recht auf Gefühlsvorderung">
                <button class="p-btn" style="margin-top:12px;" onclick="reservierungAnlegen()">Reservierung planen</button>
            </div>`
            : ssHinweis('🔒 Geplante Reservierungen sind Premium-Mitgliedern vorbehalten.');

        body.innerHTML = `
            <div class="res-hub">
                <div class="res-spalte res-live">
                    <h3>🎥 Direkter Einstieg</h3>
                    <p class="res-p">${liveHinweis}</p>
                    <div class="mp-liste-zeile"><span>Aktuelles Thema</span><b style="color:#ffd700;">${escapeHtml(themaName)}</b></div>
                    <button class="res-live-btn" ${premium ? '' : 'disabled'} onclick="liveBetreten()">▶ Live betreten</button>
                </div>
                <div class="res-spalte res-plan">
                    <h3>🗓️ Geplante Reservierung</h3>
                    ${planFormular}
                </div>
            </div>
            <div id="res-msg" class="p-msg"></div>
            <h3 class="res-abschnitt">Meine Tische & Einladungen</h3>
            <div id="res-meine"><p style="color:#123;">Lade …</p></div>`;
        ladeMeineReservierungen();
    }

    function resMsg(text, ok) { const el = document.getElementById('res-msg'); if (el){ el.textContent = text||""; el.classList.toggle('ok', !!ok);} }

    async function liveBetreten() {
        if (!(meineRechte.darf_live || isAdmin)) { resMsg('Der Live-Sektor ist Premium-Mitgliedern vorbehalten.'); return; }
        if (aktivesThemaIdx === null) { resMsg('Bitte wähle zuerst links ein Thema.'); return; }
        schliesseSchublade();
        starteVideo();
    }

    async function reservierungAnlegen() {
        const sektor = backendSektor();
        if (!sektor) { resMsg('Bitte wähle zuerst links ein Thema.'); return; }
        resMsg('Reserviere …', true);
        try {
            const res = await fetch('/api/tisch/reservieren', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({
                email: userEmail, sektor,
                identitaet: (document.getElementById('res-identitaet')||{}).value || '',
                zeitpunkt: (document.getElementById('res-zeit')||{}).value || '',
                thema: (document.getElementById('res-thema')||{}).value || '',
            }) });
            const d = await res.json();
            if (d.success) { resMsg('Reservierung geplant. Lade jetzt Gäste ein.', true); ladeMeineReservierungen(); }
            else resMsg(d.message || 'Reservierung fehlgeschlagen.');
        } catch (e) { resMsg('Server-Verbindung fehlgeschlagen.'); }
    }

    async function ladeMeineReservierungen() {
        const box = document.getElementById('res-meine');
        if (!box) return;
        try {
            const res = await fetch(`/api/tisch/meine?email=${encodeURIComponent(userEmail)}`);
            const d = await res.json();
            if (!d.success) { box.innerHTML = ssHinweis('Konnte nicht geladen werden.'); return; }
            let html = '';
            if (d.eigene.length) {
                html += `<div class="res-gruppe-titel">Von mir erstellt</div>`;
                html += d.eigene.map(r => resKarte(r, true)).join('');
            }
            if (d.einladungen.length) {
                html += `<div class="res-gruppe-titel">Einladungen an mich</div>`;
                html += d.einladungen.map(r => resKarte(r, false)).join('');
            }
            box.innerHTML = html || ssHinweis('Noch keine Tische oder Einladungen.');
        } catch (e) { box.innerHTML = ssHinweis('Fehler beim Laden.'); }
    }

    function resKarte(r, bin_ersteller) {
        const statusPill = { geplant: 'geplant', live: 'LIVE', abgeschlossen: 'beendet', abgelehnt: 'abgelehnt' }[r.status] || r.status;
        const pillCls = r.status === 'live' ? 'frei' : (r.status === 'abgelehnt' ? 'gesperrt' : '');
        const gaeste = (r.eingeladene||[]).map(g =>
            `<span class="res-gast res-${g.status}">${g.online?'🟢 ':''}${escapeHtml(g.name)} · ${g.status}</span>`).join('') || '<span style="color:#9db8dd;">noch niemand eingeladen</span>';
        let aktionen = '';
        if (bin_ersteller) {
            aktionen += `<div class="res-einladen">
                <input type="text" class="p-field" id="res-inv-${r.id}" placeholder="@handle eines Mitglieds" style="max-width:260px;">
                <button class="p-btn sekundaer" style="width:auto;margin:0;" onclick="gastEinladen('${r.id}')">Einladen</button></div>`;
            if (r.status === 'live') aktionen += `<button class="res-live-btn klein" onclick="liveBetreten()">▶ Meinen Tisch betreten</button>`;
            else aktionen += `<button class="p-btn" style="width:auto;" onclick="reservierungLive('${r.id}')">Jetzt live schalten</button>`;
        } else {
            if (r.mein_status === 'eingeladen') {
                aktionen += `<button class="p-btn" style="width:auto;" onclick="einladungAntwort('${r.id}',true)">Annehmen</button>
                             <button class="p-btn schliessen" style="width:auto;" onclick="einladungAntwort('${r.id}',false)">Ablehnen</button>`;
            } else if (r.mein_status === 'angenommen' && r.status === 'live') {
                aktionen += `<button class="res-live-btn klein" onclick="liveBetreten()">▶ Tisch betreten</button>`;
            } else {
                aktionen += `<span style="color:#9db8dd;">Status: ${escapeHtml(r.mein_status||'—')}</span>`;
            }
        }
        return `<div class="res-karte">
            <div class="res-karte-kopf">
                <b>${escapeHtml(r.thema || ('Sektor ' + r.sektor))}</b>
                <span class="ss-pill ${pillCls}">${statusPill}</span>
            </div>
            <div class="res-karte-meta">Ersteller: ${escapeHtml(r.ersteller_name)}${r.zeitpunkt?(' · '+escapeHtml(r.zeitpunkt)):''} · ${r.angenommen}/${r.eingeladen_gesamt} zugesagt</div>
            <div class="res-gaeste">${gaeste}</div>
            <div class="res-aktionen">${aktionen}</div>
        </div>`;
    }

    async function gastEinladen(resId) {
        const el = document.getElementById('res-inv-' + resId);
        const handle = (el ? el.value : '').trim().replace(/^@/, '');
        if (!handle) { resMsg('Bitte einen @handle angeben.'); return; }
        try {
            const res = await fetch('/api/tisch/einladen', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email: userEmail, reservierung_id: resId, gast_handle: handle }) });
            const d = await res.json();
            if (d.success) { resMsg('Einladung verschickt.', true); ladeMeineReservierungen(); }
            else resMsg(d.message || 'Einladung fehlgeschlagen.');
        } catch (e) { resMsg('Server-Verbindung fehlgeschlagen.'); }
    }

    async function einladungAntwort(resId, annehmen) {
        try {
            const res = await fetch('/api/tisch/einladung/antwort', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email: userEmail, reservierung_id: resId, annehmen }) });
            const d = await res.json();
            if (d.success) { resMsg(annehmen ? (d.live ? 'Angenommen – der Tisch ist jetzt LIVE!' : 'Angenommen.') : 'Abgelehnt.', true); ladeMeineReservierungen(); }
            else resMsg(d.message || 'Antwort fehlgeschlagen.');
        } catch (e) { resMsg('Server-Verbindung fehlgeschlagen.'); }
    }

    async function reservierungLive(resId) {
        try {
            const res = await fetch('/api/tisch/live-freischalten', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email: userEmail, reservierung_id: resId }) });
            const d = await res.json();
            if (d.success) { resMsg('Tisch ist live geschaltet.', true); ladeMeineReservierungen(); }
            else resMsg(d.message || 'Live-Schaltung fehlgeschlagen.');
        } catch (e) { resMsg('Server-Verbindung fehlgeschlagen.'); }
    }

    const SCHUBLADE_HANDLER = {
        'support': schubladeSupport,
        'beitrag': schubladeBeitrag,
        'medien': b => schubladeArchiv(b, 'medien', 'Medien-Archiv', 'Alle Fotos und Videos dieses Sektors.'),
        'diskurs': b => schubladeArchiv(b, 'diskurs', 'Diskurs-Forum', 'Alle Diskussions-Beiträge dieses Sektors.'),
        'ressourcen': b => schubladeArchiv(b, 'ressource', 'Ressourcen-Datenbank', 'Alle geteilten Quellen und Links dieses Sektors.'),
        'profilsuche': schubladeProfilsuche,
        'workflow': schubladeWorkflow,
        'status': schubladeStatus,
        'reservierung': schubladeReservierung,
        'live-anmeldung': schubladeLiveAnmeldung,
    };

    // ---- SUPPORT: sektor-sensitive KI-Seele ----
    function panelSupport(body) {
        const sektor = backendSektor() || 1;
        const thema = themen[sektor - 1] || 'die Community';
        setzePanelKopf('Support', `Sektor-sensitive Begleitung · Sektor ${sektor}: ${thema}`);
        body.innerHTML = `
            <div class="support-chat" id="support-chat">
                <div class="s-ki"><b>M&M Support:</b> Die Begleit-Seele für „${escapeHtml(thema)}" ist bereit. Wie kann ich dir helfen?</div>
            </div>
            <div class="support-eingabe">
                <input type="text" id="support-in" placeholder="Deine Frage …" onkeypress="if(event.key==='Enter')sendeSupport()">
                <button onclick="sendeSupport()">Senden</button>
            </div>`;
    }
    async function sendeSupport() {
        const input = document.getElementById('support-in');
        const msg = (input.value || "").trim();
        if (!msg) return;
        const sektor = backendSektor() || 1;
        const chat = document.getElementById('support-chat');
        chat.innerHTML += `<div class="s-du"><b>Du:</b> ${escapeHtml(msg)}</div>`;
        input.value = ""; chat.scrollTop = chat.scrollHeight;
        try {
            const res = await fetch('/api/support', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email: userEmail, sektor, message: msg }) });
            const d = await res.json();
            const seele = d.seele || 'Support';
            chat.innerHTML += `<div class="s-ki"><b>${escapeHtml(seele)}:</b> ${escapeHtml(d.reply || 'Ich bin gleich wieder für dich da.')}</div>`;
            chat.scrollTop = chat.scrollHeight;
        } catch (e) { chat.innerHTML += `<div class="s-ki">Verbindung zum Support fehlgeschlagen.</div>`; }
    }

    // ---- TISCH-RESERVIERUNGEN ----
    async function panelTischReservierungen(body) {
        setzePanelKopf('Tisch-Reservierungen', 'Reserviere deinen Platz an einem Live-Tisch (8 pro Tisch · 7+1-System).');
        const sektor = backendSektor();
        if (!sektor) { body.innerHTML = `<p style="color:#9db8dd;">Wähle zuerst links ein Thema.</p>`; return; }
        if (GESPERRTE_THEMEN_IDX.has(aktivesThemaIdx) && !isAdmin) { body.innerHTML = `<p style="color:#9db8dd;">Dieses Thema hat noch keinen Live-Raum.</p>`; return; }
        body.innerHTML = `<p style="color:#9db8dd;">Lade Belegung …</p>`;
        try {
            const res = await fetch('/api/video/heartbeat', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email: userEmail, sektor }) });
            const d = await res.json();
            const teil = (d.teilnehmer || []).length;
            body.innerHTML = `
                <div class="mp-liste-zeile"><span>Thema</span><b style="color:#ffd700;">${escapeHtml(themen[sektor-1])}</b></div>
                <div class="mp-liste-zeile"><span>Aktive Teilnehmer</span><b>${teil}</b></div>
                <div class="mp-liste-zeile"><span>Offene Tische</span><b>${d.anzahl_tische || 1}</b></div>
                <div class="mp-liste-zeile"><span>Warteliste</span><b>${d.warteliste || 0}</b></div>
                <button class="p-btn" onclick="schliesseMenuPanel(); starteVideo();">Platz reservieren & Live beitreten</button>`;
        } catch (e) { body.innerHTML = `<p style="color:#ff6b6b;">Belegung konnte nicht geladen werden.</p>`; }
    }

    // ---- ANMELDEOPTIONEN FÜR LIVE-SEKTOREN ----
    function panelLiveOptionen(body) {
        setzePanelKopf('Anmeldeoptionen für Live-Sektoren', 'Lege fest, wie du Live-Sektoren betrittst.');
        const kam = localStorage.getItem('mm_live_kamera') !== 'aus';
        const mik = localStorage.getItem('mm_live_mikro') !== 'aus';
        const auto = localStorage.getItem('mm_live_autojoin') === 'an';
        body.innerHTML = `
            <div class="mp-option"><span>Kamera beim Beitritt aktiv</span><input type="checkbox" ${kam?'checked':''} onchange="setzeLiveOption('mm_live_kamera', this.checked?'an':'aus')"></div>
            <div class="mp-option"><span>Mikrofon beim Beitritt aktiv</span><input type="checkbox" ${mik?'checked':''} onchange="setzeLiveOption('mm_live_mikro', this.checked?'an':'aus')"></div>
            <div class="mp-option"><span>Beim Themen-Wechsel automatisch beitreten</span><input type="checkbox" ${auto?'checked':''} onchange="setzeLiveOption('mm_live_autojoin', this.checked?'an':'aus')"></div>
            <p style="color:#9db8dd; font-size:0.76rem; margin-top:12px;">Diese Optionen gelten für alle Live-Sektoren, in die du eintrittst.</p>`;
    }
    function setzeLiveOption(key, wert) { localStorage.setItem(key, wert); }

    // =====================================================================
    // ZENTRALE SCHLEUSE: Anmelde-Zentrale für Live-Sektoren (in der Mitte).
    // Themen-Wahl -> Zeitfenster-Anmeldung -> technischer Vor-Check ->
    // Rot→Grün-Statuslogik des "Live-betreten"-Buttons.  (Phase 1)
    // =====================================================================
    let laSessions = [];
    let laGewaehlteSession = null;      // session_id des gewählten Zeitfensters
    let laStatusTimer = null;           // Poll-Timer für die Rot→Grün-Umschaltung
    let laVorschauStream = null;        // getUserMedia-Stream der Kamera-Vorschau
    let laAudioCtx = null, laAnalyser = null, laPegelTimer = null;
    const LA_SLOT_LABEL = { vormittag: 'Vormittag', nachmittag: 'Nachmittag' };

    function laZeit(iso) {
        if (!iso) return '—';
        const d = new Date(iso);
        return isNaN(d) ? '—' : d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
    }
    function laDatum(iso) {
        if (!iso) return '';
        const d = new Date(iso);
        return isNaN(d) ? '' : d.toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: '2-digit' });
    }

    function schubladeLiveAnmeldung(body) {
        setzeSchubladeKopf('Anmeldeoptionen für Live-Sektoren',
            'Die zentrale Schleuse: Thema wählen · Zeitfenster buchen · Technik-Check · Live betreten.');
        // Themen-Wahl (gesperrte Sektoren nur für Admin sichtbar).
        let optionen = '<option value="">— Thema wählen —</option>';
        themen.forEach((t, i) => {
            if (GESPERRTE_THEMEN_IDX.has(i) && !isAdmin) return;
            const sel = (i === aktivesThemaIdx) ? ' selected' : '';
            optionen += `<option value="${i}"${sel}>${i + 1}. ${escapeHtml(t)}</option>`;
        });
        body.innerHTML = `
            <div class="la-wrap">
                <div class="ss-card la-block">
                    <label class="la-label">1 · Themen-Wahl</label>
                    <select id="la-thema" class="la-select" onchange="laThemaGewaehlt(this.value)">${optionen}</select>
                    <p class="la-hint">Live-Sessions sind auf zweimal täglich (je ~1 Stunde) begrenzt. Wähle ein festes Zeitfenster.</p>
                </div>
                <div class="ss-card la-block">
                    <label class="la-label">2 · Zeitliche Bindung — verfügbare Zeitfenster</label>
                    <div id="la-fenster"><p class="la-hint">Wähle zuerst oben ein Thema.</p></div>
                </div>
                <div class="ss-card la-block">
                    <label class="la-label">3 · Technischer Vor-Check</label>
                    <div class="la-vorcheck">
                        <div class="la-preview-box">
                            <video id="la-vorschau" autoplay playsinline muted></video>
                            <div class="la-preview-hint" id="la-preview-hint">Kamera-Vorschau aus</div>
                        </div>
                        <div class="la-pegel-box">
                            <span class="la-pegel-label">🎤 Mikrofon-Pegel</span>
                            <div class="la-pegel"><div class="la-pegel-fill" id="la-pegel-fill"></div></div>
                            <div class="la-vorcheck-btns">
                                <button class="p-btn sekundaer" id="la-preview-btn" onclick="laVorschauStart()">Kamera &amp; Mikro testen</button>
                                <button class="p-btn" id="la-technik-btn" onclick="laTechnikBestanden()" disabled>Technik-Check bestanden ✓</button>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="ss-card la-block la-betreten-block">
                    <label class="la-label">4 · Status</label>
                    <div class="la-status-zeile" id="la-status-text">Melde dich für ein Zeitfenster an und bestehe den Technik-Check.</div>
                    <button class="la-betreten rot" id="la-betreten" onclick="laLiveBetreten()" disabled>● Live-betreten (gesperrt)</button>
                </div>
            </div>`;
        // Wenn schon ein Thema aktiv ist, direkt dessen Fenster laden.
        if (aktivesThemaIdx !== null && !(GESPERRTE_THEMEN_IDX.has(aktivesThemaIdx) && !isAdmin)) {
            laLadeSessions(aktivesThemaIdx);
        }
    }

    function laThemaGewaehlt(val) {
        if (val === "") { document.getElementById('la-fenster').innerHTML = `<p class="la-hint">Wähle zuerst oben ein Thema.</p>`; return; }
        const idx = parseInt(val, 10);
        // Nur das aktive Thema setzen – NICHT das volle waehleThema(), da dieses die
        // Schublade schließen würde. Die endgültige Kopplung an Stream + Live-Raum
        // erfolgt erst beim tatsächlichen "Live-betreten".
        aktivesThemaIdx = idx;
        laGewaehlteSession = null; laStoppeStatusPoll(); laStatusAnwenden(null);
        laLadeSessions(idx);
    }

    async function laLadeSessions(themaIdx) {
        const box = document.getElementById('la-fenster');
        if (!box) return;
        box.innerHTML = `<p class="la-hint">Lade Zeitfenster …</p>`;
        try {
            const res = await fetch(`/api/live/sessions?email=${encodeURIComponent(userEmail)}&sektor=${themaIdx + 1}`);
            const d = await res.json();
            if (!d.success) { box.innerHTML = `<p class="la-hint" style="color:#ff9b9b;">${escapeHtml(d.error || 'Zeitfenster konnten nicht geladen werden.')}</p>`; return; }
            laSessions = d.sessions || [];
            laRenderFenster();
        } catch (e) { box.innerHTML = `<p class="la-hint" style="color:#ff9b9b;">Server-Verbindung fehlgeschlagen.</p>`; }
    }

    function laRenderFenster() {
        const box = document.getElementById('la-fenster');
        if (!box) return;
        if (!laSessions.length) {
            box.innerHTML = `<p class="la-hint">Für dieses Thema ist aktuell kein Zeitfenster geplant. Schau später wieder vorbei.</p>`;
            return;
        }
        box.innerHTML = laSessions.map(s => {
            const gewaehlt = (s.session_id === laGewaehlteSession);
            const voll = s.anzahl_angemeldet >= s.max_teilnehmer && !s.angemeldet;
            const badge = s.angemeldet ? `<span class="la-badge ok">angemeldet</span>` : (voll ? `<span class="la-badge voll">ausgebucht</span>` : "");
            const btn = s.angemeldet
                ? `<button class="p-btn sekundaer la-mini" onclick="laAbmelden('${s.session_id}')">Abmelden</button>`
                : `<button class="p-btn la-mini" ${voll ? 'disabled' : ''} onclick="laAnmelden('${s.session_id}')">Anmelden</button>`;
            return `
                <div class="la-fenster-zeile ${gewaehlt ? 'gewaehlt' : ''}" onclick="laWaehleSession('${s.session_id}')">
                    <div class="la-fenster-info">
                        <b>${LA_SLOT_LABEL[s.slot] || s.slot || ''} · ${laDatum(s.start)}</b>
                        <span>${laZeit(s.start)}–${laZeit(s.ende)} Uhr · ${s.anzahl_angemeldet}/${s.max_teilnehmer} Plätze ${badge}</span>
                    </div>
                    <div class="la-fenster-akt" onclick="event.stopPropagation()">${btn}</div>
                </div>`;
        }).join("");
        // Auswahl-Status auffrischen (Button + Poll).
        if (laGewaehlteSession) laStatusAnwenden(laSessions.find(s => s.session_id === laGewaehlteSession));
    }

    function laWaehleSession(sid) {
        laGewaehlteSession = sid;
        laRenderFenster();
        laStartStatusPoll();
    }

    async function laAnmelden(sid) {
        try {
            const res = await fetch('/api/live/anmelden', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email: userEmail, session_id: sid }) });
            const d = await res.json();
            if (!d.success) { alert(d.error || 'Anmeldung fehlgeschlagen.'); return; }
            laGewaehlteSession = sid;
            if (d.session) laMergeSession(d.session);
            laRenderFenster();
            laStartStatusPoll();
        } catch (e) { alert('Server-Verbindung fehlgeschlagen.'); }
    }

    async function laAbmelden(sid) {
        try {
            const res = await fetch('/api/live/abmelden', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email: userEmail, session_id: sid }) });
            const d = await res.json();
            if (d.session) laMergeSession(d.session);
            if (laGewaehlteSession === sid) { laGewaehlteSession = null; laStoppeStatusPoll(); }
            laRenderFenster();
            laStatusAnwenden(null);
        } catch (e) { alert('Server-Verbindung fehlgeschlagen.'); }
    }

    function laMergeSession(sess) {
        const i = laSessions.findIndex(s => s.session_id === sess.session_id);
        if (i >= 0) laSessions[i] = sess; else laSessions.push(sess);
    }

    // ---- Technischer Vor-Check: Kamera-Vorschau + Mikro-Pegel ----
    async function laVorschauStart() {
        if (laVorschauStream) { laVorschauStop(); return; }
        try {
            laVorschauStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        } catch (e) { alert('Kamera-/Mikrofon-Zugriff wurde verweigert.'); return; }
        const vid = document.getElementById('la-vorschau');
        if (vid) { vid.srcObject = laVorschauStream; vid.play().catch(()=>{}); }
        const hint = document.getElementById('la-preview-hint'); if (hint) hint.style.display = 'none';
        const pb = document.getElementById('la-preview-btn'); if (pb) pb.textContent = 'Vorschau stoppen';
        // Mikro-Pegel-Meter über WebAudio.
        try {
            laAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const quelle = laAudioCtx.createMediaStreamSource(laVorschauStream);
            laAnalyser = laAudioCtx.createAnalyser();
            laAnalyser.fftSize = 512;
            quelle.connect(laAnalyser);
            const daten = new Uint8Array(laAnalyser.frequencyBinCount);
            laPegelTimer = setInterval(() => {
                laAnalyser.getByteTimeDomainData(daten);
                let summe = 0;
                for (let i = 0; i < daten.length; i++) { const v = (daten[i] - 128) / 128; summe += v * v; }
                const rms = Math.sqrt(summe / daten.length);
                const proz = Math.min(100, Math.round(rms * 240));
                const fill = document.getElementById('la-pegel-fill');
                if (fill) fill.style.width = proz + '%';
            }, 100);
        } catch (e) {}
        // Technik-Check-Button freigeben, sobald ein Zeitfenster gewählt ist.
        const tb = document.getElementById('la-technik-btn'); if (tb) tb.disabled = false;
    }

    function laVorschauStop() {
        if (laPegelTimer) { clearInterval(laPegelTimer); laPegelTimer = null; }
        if (laAudioCtx) { try { laAudioCtx.close(); } catch(e){} laAudioCtx = null; laAnalyser = null; }
        if (laVorschauStream) { laVorschauStream.getTracks().forEach(t => t.stop()); laVorschauStream = null; }
        const vid = document.getElementById('la-vorschau'); if (vid) vid.srcObject = null;
        const hint = document.getElementById('la-preview-hint'); if (hint) hint.style.display = 'flex';
        const pb = document.getElementById('la-preview-btn'); if (pb) pb.textContent = 'Kamera & Mikro testen';
        const fill = document.getElementById('la-pegel-fill'); if (fill) fill.style.width = '0%';
    }

    async function laTechnikBestanden() {
        if (!laGewaehlteSession) { alert('Bitte zuerst ein Zeitfenster wählen und dich anmelden.'); return; }
        if (!laVorschauStream) { alert('Bitte zuerst Kamera & Mikro testen.'); return; }
        try {
            const res = await fetch('/api/live/technik-check', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email: userEmail, session_id: laGewaehlteSession, ok: true }) });
            const d = await res.json();
            if (!d.success) { alert(d.error || 'Technik-Check konnte nicht gespeichert werden.'); return; }
            if (d.session) { laMergeSession(d.session); laStatusAnwenden(d.session); }
            const tb = document.getElementById('la-technik-btn'); if (tb) { tb.textContent = 'Technik-Check bestanden ✓'; tb.disabled = true; }
        } catch (e) { alert('Server-Verbindung fehlgeschlagen.'); }
    }

    // ---- Rot→Grün-Statuslogik ----
    function laStartStatusPoll() {
        laStoppeStatusPoll();
        laStatusJetzt();
        laStatusTimer = setInterval(laStatusJetzt, 8000);
    }
    function laStoppeStatusPoll() { if (laStatusTimer) { clearInterval(laStatusTimer); laStatusTimer = null; } }

    async function laStatusJetzt() {
        if (!laGewaehlteSession) return;
        try {
            const res = await fetch(`/api/live/status?email=${encodeURIComponent(userEmail)}&session_id=${encodeURIComponent(laGewaehlteSession)}`);
            const d = await res.json();
            if (d.success && d.session) { laMergeSession(d.session); laStatusAnwenden(d.session); }
        } catch (e) {}
    }

    function laStatusAnwenden(sess) {
        const btn = document.getElementById('la-betreten');
        const txt = document.getElementById('la-status-text');
        // Schleuse-Status -> rechtes Panel koppeln (gelb->grün "Scharfschaltung").
        liveBetretenFrei = !!(sess && sess.betreten_frei);
        aktualisiereLivePanelStatus();
        if (!btn || !txt) return;
        if (!sess) {
            btn.disabled = true; btn.className = 'la-betreten rot'; btn.textContent = '● Live-betreten (gesperrt)';
            txt.textContent = 'Melde dich für ein Zeitfenster an und bestehe den Technik-Check.';
            return;
        }
        if (sess.betreten_frei) {
            btn.disabled = false; btn.className = 'la-betreten gruen'; btn.textContent = '● Live-betreten (bereit)';
            txt.textContent = 'Dein Zeitfenster ist freigegeben und läuft. Öffne rechts das grüne „7+1 Live-Sektor öffnen".';
        } else {
            btn.disabled = true; btn.className = 'la-betreten rot'; btn.textContent = '● Live-betreten (gesperrt)';
            let grund = 'Warte auf die Freigabe des Zeitfensters.';
            if (!sess.angemeldet) grund = 'Melde dich zuerst für dieses Zeitfenster an.';
            else if (!sess.technik_ok) grund = 'Bestehe zuerst den technischen Vor-Check.';
            else if (!sess.freigegeben) grund = 'Deine Anmeldung wartet auf die Freigabe durch die Regie.';
            else if (!sess.im_fenster) grund = 'Freigegeben – der Button wird grün, sobald das Zeitfenster beginnt.';
            txt.textContent = grund;
        }
    }

    function laLiveBetreten() {
        const sess = laSessions.find(s => s.session_id === laGewaehlteSession);
        // Admin-Ausnahme: darf ohne Freigabe/Fenster betreten.
        if (!isAdmin && (!sess || !sess.betreten_frei)) return;
        // Sicherstellen, dass das aktive Thema zum Zeitfenster passt.
        if (sess && aktivesThemaIdx !== (sess.sektor - 1)) waehleThema(sess.sektor - 1);
        laTeardown();
        schliesseSchublade();
        starteVideo();     // bestehender PeerJS-Beitritt + eingepasstes Video-Grid
    }

    // Vollständiges Aufräumen beim Schließen der Schleuse.
    function laTeardown() {
        laVorschauStop();
        laStoppeStatusPoll();
    }

    // ---- KONTO & SICHERHEIT (Passwort ändern + E-Mail-Änderung + Zugangsdaten) ----
    function ksMsg(text, ok) { const el = document.getElementById('ks-msg'); if (!el) return; el.textContent = text||""; el.classList.toggle('ok', !!ok); }
    function panelKontoSicherheit(body) {
        setzePanelKopf('Konto & Sicherheit', 'Passwort ändern und deine Login-E-Mail anpassen. Diese Funktionen sind bewusst vom Profil getrennt.');
        body.innerHTML = `
            <div class="mp-liste-zeile"><span>Aktuelle Login-E-Mail</span><b style="color:#ffd700;">${escapeHtml(userEmail)}</b></div>

            <div class="p-trenner"></div>
            <label class="p-label">Passwort ändern</label>
            <input type="password" id="ks-pass-alt" class="p-field" placeholder="Aktuelles Passwort" style="margin-bottom:8px;">
            <input type="password" id="ks-pass-neu" class="p-field" placeholder="Neues Passwort (min. 6 Zeichen)">
            <button class="p-btn sekundaer" onclick="aenderePasswort()">Passwort ändern</button>

            <div class="p-trenner"></div>
            <label class="p-label">E-Mail-Adresse ändern</label>
            <input type="email" id="ks-email-neu" class="p-field" placeholder="Neue E-Mail-Adresse" style="margin-bottom:8px;">
            <input type="password" id="ks-email-pass" class="p-field" placeholder="Passwort zur Bestätigung">
            <button class="p-btn sekundaer" onclick="aendereEmail()">E-Mail ändern</button>

            <div id="ks-msg" class="p-msg"></div>`;
    }

    async function aenderePasswort() {
        const alt = document.getElementById('ks-pass-alt').value;
        const neu = document.getElementById('ks-pass-neu').value;
        if (!alt || !neu) return ksMsg("Bitte aktuelles und neues Passwort eingeben.");
        if (neu.length < 6) return ksMsg("Das neue Passwort braucht mindestens 6 Zeichen.");
        ksMsg("Ändere …", true);
        try {
            const res = await fetch('/auth/passwort-aendern', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email: userEmail, altes_passwort: alt, neues_passwort: neu }) });
            const d = await res.json();
            if (d.success) { ksMsg("Passwort geändert.", true); document.getElementById('ks-pass-alt').value=""; document.getElementById('ks-pass-neu').value=""; }
            else ksMsg(d.message || "Passwort-Wechsel fehlgeschlagen.");
        } catch (e) { ksMsg("Server-Verbindung fehlgeschlagen."); }
    }

    async function aendereEmail() {
        const neue = (document.getElementById('ks-email-neu').value || "").trim().toLowerCase();
        const pass = document.getElementById('ks-email-pass').value;
        if (!neue || !neue.includes('@')) return ksMsg("Bitte eine gültige neue E-Mail angeben.");
        if (!pass) return ksMsg("Bitte dein Passwort zur Bestätigung eingeben.");
        ksMsg("Ändere …", true);
        try {
            const res = await fetch('/auth/email-aendern', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email: userEmail, neue_email: neue, passwort: pass }) });
            const d = await res.json();
            if (d.success) {
                userEmail = d.neue_email || neue;
                localStorage.setItem('mm_profil_id', (meinProfil.benutzername || userEmail));
                ksMsg("E-Mail geändert. Du bist jetzt mit " + userEmail + " angemeldet.", true);
                document.getElementById('ks-email-neu').value=""; document.getElementById('ks-email-pass').value="";
            } else ksMsg(d.message || "E-Mail-Änderung fehlgeschlagen.");
        } catch (e) { ksMsg("Server-Verbindung fehlgeschlagen."); }
    }

    // ---- MEIN ACCOUNT (Status-Überblick) ----
    async function panelMeinAccount(body) {
        setzePanelKopf('Mein Account', 'Status deiner Mitgliedschaft im Überblick.');
        body.innerHTML = `<p style="color:#9db8dd;">Lade Account-Daten …</p>`;
        try {
            const [statusRes, profilRes] = await Promise.all([
                fetch(`/auth/status?email=${encodeURIComponent(userEmail)}`),
                fetch(`/auth/profil-daten?email=${encodeURIComponent(userEmail)}`),
            ]);
            const s = await statusRes.json();
            const p = await profilRes.json();
            const jaNein = v => v ? '✅ Ja' : '—';
            const name = ((p.vorname||"") + " " + (p.nachname||"")).trim() || "—";
            body.innerHTML = `
                <div class="mp-liste-zeile"><span>Name</span><b>${escapeHtml(name)}</b></div>
                <div class="mp-liste-zeile"><span>Rolle</span><b>${p.ist_admin ? 'Administrator' : 'Mitglied'}</b></div>
                <div class="mp-liste-zeile"><span>Konto-Status</span><b>${escapeHtml(s.konto_status || 'aktiv')}</b></div>
                <div class="mp-liste-zeile"><span>Zugang freigeschaltet</span><b>${jaNein(s.zugang_frei)}</b></div>
                <div class="mp-liste-zeile"><span>Aktives Abo</span><b>${jaNein(s.abo_aktiv)}</b></div>
                <div class="mp-liste-zeile"><span>Wahrheits-Zertifikat</span><b>${jaNein(s.hat_zertifikat)}</b></div>
                <button class="p-btn sekundaer" onclick="schliesseMenuPanel(); oeffneProfil();">Profil bearbeiten</button>`;
        } catch (e) { body.innerHTML = `<p style="color:#ff6b6b;">Account-Daten konnten nicht geladen werden.</p>`; }
    }

    // ---- ZUGANGSDATEN (Login- & Identitätsdaten) ----
    async function panelZugangsdaten(body) {
        setzePanelKopf('Zugangsdaten', 'Deine Anmelde- und Identitätsdaten. Änderungen an E-Mail/Passwort unter „Konto & Sicherheit“.');
        body.innerHTML = `<p style="color:#9db8dd;">Lade Zugangsdaten …</p>`;
        try {
            const res = await fetch(`/auth/profil-daten?email=${encodeURIComponent(userEmail)}`);
            const d = await res.json();
            const name = ((d.vorname||"") + " " + (d.nachname||"")).trim() || "—";
            body.innerHTML = `
                <div class="mp-liste-zeile"><span>Login-E-Mail</span><b style="color:#ffd700;">${escapeHtml(d.email || userEmail)}</b></div>
                <div class="mp-liste-zeile"><span>Benutzername / Handle</span><b>${escapeHtml(d.benutzername || '—')}</b></div>
                <div class="mp-liste-zeile"><span>Echter Name</span><b>${escapeHtml(name)}</b></div>
                <div class="mp-liste-zeile"><span>Konto-Status</span><b>${escapeHtml(d.konto_status || 'aktiv')}</b></div>
                <div class="mp-liste-zeile"><span>Passwort</span><b>••••••••</b></div>
                <button class="p-btn sekundaer" onclick="schliesseMenuPanel(); oeffnePanel('konto-sicherheit');">E-Mail / Passwort ändern</button>`;
        } catch (e) { body.innerHTML = `<p style="color:#ff6b6b;">Zugangsdaten konnten nicht geladen werden.</p>`; }
    }

    async function waehleThema(i) {
        aktivesThemaIdx = i;
        document.querySelectorAll('.thema-btn').forEach(b => b.classList.remove('aktiv'));
        const btn = document.getElementById('thema-'+i); if (btn) btn.classList.add('aktiv');

        document.getElementById('stream-willkommen').style.display = 'none';
        document.getElementById('stream-inhalt').style.display = 'block';
        document.getElementById('stream-titel').textContent = `${i+1}. ${themen[i]}`;
        document.getElementById('stream-sub').textContent = "Content-Stream · Fotos, Artikel und Diskussion";

        // Live-Sektor an das aktive Thema koppeln (Info-Panel-Kopf).
        setText('live-thema', `Sektor ${i+1}: ${themen[i]}`);
        await stoppeVideo(true);   // evtl. laufenden Raum sauber verlassen (stiller Wechsel)

        const gesperrt = GESPERRTE_THEMEN_IDX.has(i) && !isAdmin;
        document.getElementById('composer-gesperrt').style.display = gesperrt ? 'block' : 'none';
        // Beim Themenwechsel eine ggf. offene Schublade auf den frischen Stream zurücksetzen.
        if (typeof schliesseSchublade === 'function') schliesseSchublade();

        if (!gesperrt && localStorage.getItem('mm_live_autojoin') === 'an' && (liveBetretenFrei || isAdmin)) {
            starteVideo();   // Auto-Beitritt nur wenn scharfgeschaltet (oder Admin)
        }
        // Rechtes Info-Panel auffrischen, falls offen.
        if (livePanelOffen) ladeLiveInfo();
        await ladeStream(i+1);
    }

    // =====================================================================
    // MITTE: CONTENT-STREAM + Content-Schublade (Eingabe-Masken als Overlay)
    // =====================================================================
    let aktiveBeitragTyp = "gedanke";
    let beitragMediaBase64 = "", beitragMediaTyp = "";

    // Sichtbarkeits-Control für jeden Post: Öffentlich vs. Tisch-Gruppe.
    function sichtbarkeitSelect() {
        return `<label class="b-label">Sichtbarkeit</label>
            <select class="b-field" id="beitrag-sicht">
                <option value="oeffentlich">🌍 Öffentlich (alle Mitglieder)</option>
                <option value="tisch-gruppe">👥 Tisch-Gruppe (nur mein Live-Tisch)</option>
            </select>`;
    }

    const BEITRAG_MASKEN = {
        gedanke: {
            titel: '💭 Gedanke', hint: 'Teile einen Gedanken – mit optionaler Reflektion (Recht auf Gefühlsvorderung).',
            body: () => `
                <label class="b-label">Dein Gedanke</label>
                <textarea class="b-field" id="beitrag-text" placeholder="Was bewegt dich gerade?" style="min-height: 120px;"></textarea>
                <label class="b-label">Kurze Reflektion (Recht auf Gefühlsvorderung)</label>
                <textarea class="b-field" id="beitrag-reflektion" placeholder="Wie fühlt sich das für dich an? (optional)" style="min-height: 90px;"></textarea>
                <label class="b-check"><input type="checkbox" id="beitrag-einspeisen"> Reflektion direkt in den Sektoren-Support einspeisen</label>
                <label class="b-check"><input type="checkbox" id="beitrag-kommentare-erlauben" checked> Kommentare für diesen Gedanken erlauben</label>
                ${sichtbarkeitSelect()}`
        },
        medien: {
            titel: '🖼️ Medien', hint: 'Lade ein Foto oder kurzes Video hoch und gib ihm einen Rahmen.',
            body: () => `
                <label class="b-label">Foto / kurzes Video</label>
                <input type="file" id="beitrag-media" accept="image/*,video/*" onchange="beitragDateiVorschau()" class="b-field" style="padding: 10px;">
                <img id="beitrag-media-vorschau" alt="Vorschau">
                <label class="b-label">Bildunterschrift / Kontext (optional)</label>
                <textarea class="b-field" id="beitrag-text" placeholder="Beschreibe dein Medium …" style="min-height: 90px;"></textarea>
                <!-- HIER DAS HÄCKCHEN FÜR KOMMENTARE EINFÜGEN -->
                <label class="b-check"><input type="checkbox" id="beitrag-kommentare-erlauben" checked> Kommentare für diese Medien erlauben</label>
                ${sichtbarkeitSelect()}`
        },
        diskurs: {
            titel: '💬 Diskurs', hint: 'Starte eine tiefgreifende Diskussion mit einer klaren Leitfrage.',
            body: () => `
                <label class="b-label">Diskurs-Frage / Titel</label>
                <input type="text" class="b-field" id="beitrag-diskurs-titel" placeholder="Deine Leitfrage …">
                <label class="b-label">Beschreibung</label>
                <textarea class="b-field" id="beitrag-text" placeholder="Worüber möchtest du diskutieren?" style="min-height: 110px;"></textarea>
                ${sichtbarkeitSelect()}`
        },
        ressource: {
            titel: '🔗 Ressource', hint: 'Teile eine hilfreiche Quelle oder einen stabilen Link.',
            body: () => `
                <label class="b-label">Link zur Ressource (URL)</label>
                <input type="text" class="b-field" id="beitrag-url" placeholder="https://…">
                <label class="b-label">Beschreibung</label>
                <textarea class="b-field" id="beitrag-text" placeholder="Warum ist diese Ressource wertvoll?" style="min-height: 110px;"></textarea>
                ${sichtbarkeitSelect()}`
        },
    };

    function oeffneBeitragMaske(typ) {
        const maske = BEITRAG_MASKEN[typ]; if (!maske) return;
        if (aktivesThemaIdx === null) { alert("Bitte zuerst links ein Thema wählen."); return; }
        if (GESPERRTE_THEMEN_IDX.has(aktivesThemaIdx) && !isAdmin) { alert("Dieses Thema ist noch nicht zum Posten freigeschaltet."); return; }
        aktiveBeitragTyp = typ; beitragMediaBase64 = ""; beitragMediaTyp = "";
        document.getElementById('beitrag-titel').textContent = maske.titel;
        document.getElementById('beitrag-hint').textContent = maske.hint;
        document.getElementById('beitrag-body').innerHTML = maske.body();
        beitragMsg("");
        document.getElementById('beitrag-overlay').classList.add('aktiv');
    }
    function schliesseBeitrag() { document.getElementById('beitrag-overlay').classList.remove('aktiv'); }
    function beitragMsg(text, ok) { const el = document.getElementById('beitrag-msg'); el.textContent = text||""; el.classList.toggle('ok', !!ok); }

    function beitragDateiVorschau() {
        const file = document.getElementById('beitrag-media').files[0];
        const vorschau = document.getElementById('beitrag-media-vorschau');
        if (!file) { beitragMediaBase64=""; beitragMediaTyp=""; vorschau.style.display='none'; return; }
        beitragMediaTyp = file.type.startsWith('video') ? 'video' : 'bild';
        const reader = new FileReader();
        reader.onload = e => { beitragMediaBase64 = e.target.result; if (beitragMediaTyp==='bild'){ vorschau.src=beitragMediaBase64; vorschau.style.display='block'; } else vorschau.style.display='none'; };
        reader.readAsDataURL(file);
    }

    async function sendeBeitrag() {
    const sektor = backendSektor(); if (!sektor) return;
    const typ = aktiveBeitragTyp;
    let text = (document.getElementById('beitrag-text') ? document.getElementById('beitrag-text').value : "").trim();
    let reflektion = "", ressource_url = "", einspeisen = false;

    // Kommentare erlauben gilt jetzt universell für alle Typen (Gedanke, Medien, Diskurs, Ressource)
    const kEl = document.getElementById('beitrag-kommentare-erlauben');
    const kommentareErlaubt = kEl ? kEl.checked : true; // Standardmäßig auf true, falls nicht vorhanden

    if (typ === 'diskurs') {
        const el = document.getElementById('beitrag-diskurs-titel');
        const titel = el ? el.value.trim() : "";
        if (titel) text = text ? (titel + "\n\n" + text) : titel;
    }
    if (typ === 'gedanke') {
        const rEl = document.getElementById('beitrag-reflektion');
        reflektion = rEl ? rEl.value.trim() : "";
        const cEl = document.getElementById('beitrag-einspeisen');
        einspeisen = cEl ? cEl.checked : false;
    }
    if (typ === 'ressource') {
        const uEl = document.getElementById('beitrag-url');
        ressource_url = uEl ? uEl.value.trim() : "";
    }
    const sEl = document.getElementById('beitrag-sicht');
    const sichtbarkeit = sEl ? sEl.value : "oeffentlich";

    if (typ === 'medien' && !beitragMediaBase64) { beitragMsg("Bitte ein Foto oder Video wählen."); return; }
    if (typ === 'ressource' && !ressource_url && !text) { beitragMsg("Bitte einen Link oder eine Beschreibung angeben."); return; }
    if ((typ === 'gedanke' || typ === 'diskurs') && !text) { beitragMsg("Bitte einen Text schreiben."); return; }

    beitragMsg("Sende …", true);
    const payload = {
        email: userEmail,
        profil_id: localStorage.getItem('mm_profil_id') || userEmail,   // temporär bis DB-Migration
        sektor, beitrag_typ: typ, sichtbarkeit, text, reflektion, ressource_url,
        media: beitragMediaBase64, media_typ: beitragMediaTyp,
        kommentare_erlauben: kommentareErlaubt,
    };
    try {
        const res = await fetch('/api/forum/post', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
        const data = await res.json();
        if (data.success) {
            schliesseBeitrag();
            await ladeStream(sektor);
            // Ein offenes Schubfach (z. B. ein Archiv) nach dem Posten aktualisieren.
            if (aktiveSchublade) oeffneSchublade(aktiveSchublade);
            // Gefühlsvorderung: Reflektion direkt in den Sektoren-Support-Flow einspeisen.
            if (typ === 'gedanke' && einspeisen && reflektion) speiseSupportEin(reflektion);
        } else beitragMsg(data.message || "Beitrag konnte nicht gesendet werden.");
    } catch (e) { beitragMsg("Server-Verbindung fehlgeschlagen."); }
}
    function speiseSupportEin(reflektion) {
        oeffnePanel('support');
        setTimeout(() => {
            const inp = document.getElementById('support-in');
            if (inp) { inp.value = `Reflektion zu meinem Gedanken: ${reflektion}`; sendeSupport(); }
        }, 120);
    }

    async function ladeStream(sektor) {
        const liste = document.getElementById('stream-liste');
        liste.innerHTML = `<p style="color:#123; text-align:center;">Lade Stream …</p>`;
        streamBeitraege = []; streamGerendert = 0;
        try {
            const res = await fetch(`/api/forum/posts?email=${encodeURIComponent(userEmail)}&sektor=${sektor}`);
            const data = await res.json();
            if (!data.success) { liste.innerHTML = `<p style="color:#a00; text-align:center;">${escapeHtml(data.message) || 'Kein Zugriff.'}</p>`; return; }
            streamBeitraege = data.beitraege || [];
            liste.innerHTML = "";
            if (!streamBeitraege.length) {
                liste.innerHTML = `<p style="color:#123; text-align:center;">Noch keine Beiträge. Sei der erste Mensch, der hier spricht.</p>`;
                return;
            }
            rendereNaechsteBeitraege();
            beobachteSentinel();
        } catch (e) { liste.innerHTML = `<p style="color:#a00; text-align:center;">Fehler beim Laden des Streams.</p>`; }
    }

    function rendereNaechsteBeitraege() {
        const liste = document.getElementById('stream-liste');
        const bis = Math.min(streamGerendert + STREAM_BATCH, streamBeitraege.length);
        for (let k = streamGerendert; k < bis; k++) liste.insertAdjacentHTML('beforeend', renderBeitrag(streamBeitraege[k]));
        streamGerendert = bis;
    }

    function beobachteSentinel() {
        if (streamObserver) streamObserver.disconnect();
        const sentinel = document.getElementById('stream-sentinel');
        streamObserver = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting && streamGerendert < streamBeitraege.length) rendereNaechsteBeitraege();
        }, { root: document.getElementById('stream-body'), rootMargin: '120px' });
        streamObserver.observe(sentinel);
    }

    const TYP_LABEL = { gedanke: '💭 Gedanke', medien: '🖼️ Medien', diskurs: '💬 Diskurs', ressource: '🔗 Ressource' };
    function renderBeitrag(b) {
        const name = escapeHtml(b.autor_name || "Mensch");
        const handle = b.autor_handle ? `<span class="bk-handle">@${escapeHtml(b.autor_handle)}</span>` : "";
        const avatar = b.autor_bild ? `<div class="avatar-klein" style="background-image:url('${b.autor_bild}');"></div>` : `<div class="avatar-klein">${name.charAt(0).toUpperCase()}</div>`;
        let zeit = ""; try { zeit = new Date(b.erstellt_am).toLocaleString('de-DE'); } catch(e){ zeit = b.erstellt_am || ""; }

        // Typ- und Sichtbarkeits-Badges.
        const typLabel = TYP_LABEL[b.beitrag_typ] || TYP_LABEL.gedanke;
        const tisch = (b.sichtbarkeit === 'tisch-gruppe');
        const sichtBadge = tisch
            ? `<span class="bk-badge badge-sicht-tisch">👥 Tisch-Gruppe</span>`
            : `<span class="bk-badge badge-sicht-oeffentlich">🌍 Öffentlich</span>`;
        const badges = `<span class="bk-badges"><span class="bk-badge badge-typ">${typLabel}</span>${sichtBadge}</span>`;

        let media = "";
        if (b.media) media = (b.media_typ === 'video') ? `<video class="bk-media" src="${b.media}" controls></video>` : `<img class="bk-media" src="${b.media}" alt="Beitragsbild">`;
        const text = b.text ? `<div class="bk-text">${escapeHtml(b.text)}</div>` : "";
        const reflektion = b.reflektion ? `<div class="bk-reflektion"><span class="r-label">Reflektion · Recht auf Gefühlsvorderung</span>${escapeHtml(b.reflektion)}</div>` : "";
        let ressource = "";
        if (b.ressource_url) {
            const safeUrl = escapeHtml(b.ressource_url);
            ressource = `<div class="bk-ressource">🔗 <a href="${safeUrl}" target="_blank" rel="noopener noreferrer">${safeUrl}</a></div>`;
        }
        const komm = (b.kommentare || []).map(renderKommentar).join('');
        return `<div class="beitrag" id="beitrag-${b.id}">
            <div class="bk-kopf">${avatar}<div><span class="bk-name">${name}</span> ${handle}</div>${badges}<span class="bk-zeit">${escapeHtml(zeit)}</span></div>
            ${text}${reflektion}${ressource}${media}
            <div class="kommentare" id="komm-${b.id}">${komm}</div>
            <div class="komm-input-row">
                <input type="text" id="komm-in-${b.id}" placeholder="Kommentar schreiben …" onkeypress="if(event.key==='Enter')sendeKommentar('${b.id}')">
                <button onclick="sendeKommentar('${b.id}')">Senden</button>
            </div>
        </div>`;
    }

   // Globaler State für offene Beitrags-Ansichten
    const geöffneteKommentare = new Set();

    window.toggleBeitrag = function(beitragId) {
        const beitragEl = document.getElementById('beitrag-' + beitragId);
        const kommBox = document.getElementById('komm-box-' + beitragId);
        if (!kommBox) return;
        
        if (geöffneteKommentare.has(beitragId)) {
            geöffneteKommentare.delete(beitragId);
            kommBox.style.display = 'none';
            if (beitragEl) beitragEl.classList.remove('offen');
        } else {
            geöffneteKommentare.add(beitragId);
            kommBox.style.display = 'block';
            if (beitragEl) beitragEl.classList.add('offen');
            window.verbindeLive(beitragId);
        }
    };

    function renderBeitrag(b) {
        const name = escapeHtml(b.autor_name || "Mensch");
        const handle = b.autor_handle ? escapeHtml(b.autor_handle) : "";
        const avatar = b.autor_bild ? `<div class="avatar-klein" style="background-image:url('${b.autor_bild}');"></div>` : `<div class="avatar-klein">${name.charAt(0).toUpperCase()}</div>`;
        let zeit = ""; try { zeit = new Date(b.erstellt_am).toLocaleString('de-DE'); } catch(e){ zeit = b.erstellt_am || ""; }

        const typLabel = TYP_LABEL[b.beitrag_typ] || TYP_LABEL.gedanke;
        const tisch = (b.sichtbarkeit === 'tisch-gruppe');
        const sichtBadge = tisch ? `<span class="bk-badge badge-sicht-tisch">👥 Tisch-Gruppe</span>` : `<span class="bk-badge badge-sicht-oeffentlich">🌍 Öffentlich</span>`;
        const badges = `<span class="bk-badges"><span class="bk-badge badge-typ">${typLabel}</span>${sichtBadge}</span>`;

        let media = b.media ? `<div class="media-container">${(b.media_typ === 'video') ? `<video class="bk-media" src="${b.media}" controls></video>` : `<img class="bk-media" src="${b.media}" alt="Beitragsbild">`}</div>` : "";
        const text = b.text ? `<div class="bk-text">${escapeHtml(b.text)}</div>` : "";
        const reflektion = b.reflektion ? `<div class="bk-reflektion"><span class="r-label">Reflektion · Recht auf Gefühlsvorderung</span>${escapeHtml(b.reflektion)}</div>` : "";
        let ressource = "";
        if (b.ressource_url) {
            const safeUrl = escapeHtml(b.ressource_url);
            ressource = `<div class="bk-ressource">🔗 <a href="${safeUrl}" target="_blank" rel="noopener noreferrer">${safeUrl}</a></div>`;
        }

        const bId = String(b.id);
        const kommentareListe = b.kommentare || [];
        const anzahl = kommentareListe.length;
        const istOffen = geöffneteKommentare.has(bId);
        
        const kommentareErlaubt = (b.kommentare_erlauben !== false);
        const istErsteller = (b.autor_email === userEmail) || (handle && handle === meinProfil.benutzername);
        const kommHtml = kommentareListe.map(k => renderKommentar(k, handle, name, bId)).join('');
        const inputDisplay = istErsteller ? 'none' : 'flex';

        // Typ-Erkennung für die saubere sprachliche Trennung
        const isDiskurs = (b.beitrag_typ === 'diskurs');
        const isRessource = (b.beitrag_typ === 'ressource');
        
        const labelZaehler = isDiskurs ? `${anzahl} Diskurs-Beiträge` : (isRessource ? `${anzahl} Anwendungs-Hinweise` : `${anzahl} Kommentare`);
        const placeholderText = isDiskurs ? "Deine Antwort zum Diskurs formulieren ..." : (isRessource ? "Wie hast du diese Ressource angewendet?" : "Kommentar schreiben …");
        const buttonText = isDiskurs ? "Absenden" : (isRessource ? "Hinweis teilen" : "Senden");

        const interaktionsHtml = kommentareErlaubt ? `
            <div style="margin-top:10px; color:var(--gold); font-weight:bold; font-size:0.85rem;">
                💬 <span id="komm-zaehler-${bId}">${labelZaehler}</span> (Klick auf Kachel zum Öffnen)
            </div>
        ` : `
            <div style="margin-top:10px; color:#888; font-weight:normal; font-size:0.85rem;">
                🚫 ${isDiskurs ? 'Diskurs geschlossen' : (isRessource ? 'Ressource gesperrt' : 'Kommentare nicht erlaubt')}
            </div>
        `;

        const kommBoxHtml = kommentareErlaubt ? `
            <div id="komm-box-${bId}" data-ersteller-handle="${handle}" data-ersteller-name="${name}" style="display: ${istOffen ? 'block' : 'none'}; border-top:1px solid #1e3a5f; padding-top:10px; margin-top:10px;" onclick="event.stopPropagation()">
                <div class="kommentare" id="komm-${bId}">${kommHtml}</div>
                <div class="komm-input-row" style="display: ${inputDisplay}; margin-top:10px; gap:8px;">
                    <input type="text" id="komm-in-${bId}" placeholder="${placeholderText}">
                    <button type="button" onclick="window.sendeKommentar('${bId}')">${buttonText}</button>
                </div>
            </div>
        ` : '';

        return `<div class="beitrag ${istOffen ? 'offen' : ''}" id="beitrag-${bId}" onclick="window.toggleBeitrag('${bId}')" style="cursor:pointer;">
            <div class="bk-kopf">${avatar}<div><span class="bk-name">${name}</span> ${handle ? `<span class="bk-handle">@${handle}</span>` : ''}</div>${badges}<span class="bk-zeit">${escapeHtml(zeit)}</span></div>
            <div class="bk-text">${escapeHtml(b.text || "")}</div>
            ${reflektion}${ressource}${media}
            ${interaktionsHtml}
            ${kommBoxHtml}
        </div>`;
}
    function renderKommentar(k, postHandle, postName, beitragId) {
        const name = escapeHtml(k.autor_name || "Mensch");
        const handle = k.autor_handle ? escapeHtml(k.autor_handle) : "";
        const avatar = k.autor_bild ? `<div class="avatar-mini" style="background-image:url('${k.autor_bild}');"></div>` : `<div class="avatar-mini">${name.charAt(0).toUpperCase()}</div>`;
        
        // 1. BOMBENFESTER ERSTELLER-CHECK über Handle (oder Name als Fallback)
        let istVomErsteller = false;
        if (handle && postHandle && handle === postHandle) {
            istVomErsteller = true;
        } else if (name && postName && name === postName) {
            istVomErsteller = true;
        }
        
        const erstellerBadge = istVomErsteller ? `<span style="background:var(--gold); color:#000; font-size:0.55rem; padding:2px 6px; border-radius:10px; margin-left:6px; font-weight:bold;">Ersteller</span>` : "";

        // 2. KLARES ANTWORT-DESIGN (Verhindert Verwirrung)
        let textInhalt = escapeHtml(k.text || "");
        let replyTo = "";
        
        // Prüft, ob der Text mit @ beginnt (z.B. "@sasa Hallo")
        const match = textInhalt.match(/^@([^\s]+)/i);
        if (match) {
            replyTo = match[1]; // Schneidet den Namen aus
            textInhalt = textInhalt.replace(/^@([^\s]+)\s*/i, ''); // Entfernt das @Sasa aus dem Haupttext
        }

        // Wenn es eine Antwort ist, bekommt sie eine klare Überschrift und wird eingerückt
        const replyHeader = replyTo ? `<div style="font-size: 0.7rem; color: #7ab8ff; margin-bottom: 4px; font-weight: 600;">↳ Antwort an @${replyTo}</div>` : "";
        const indentStyle = replyTo ? "margin-left: 24px; border-left: 2px solid #1e3a5f; padding-left: 10px;" : "";

        // 3. GESAMTE KOMMENTAR-BLASE KLICKBAR MACHEN (Mit Selbstantwort-Sperre)
        const istMeinEigenerKommentar = (k.autor_email === userEmail) || (handle && handle === meinProfil.benutzername);
        
        const klickAktion = istMeinEigenerKommentar 
            ? `style="background: #091321; border-radius: 6px; padding: 8px 12px; flex: 1;"`
            : `onclick="window.toggleAntwortFeld(event, '${beitragId}', '${handle || name}', this)" style="background: #0c1a2e; border-radius: 6px; padding: 8px 12px; flex: 1; cursor: pointer; transition: all 0.2s ease; border: 1px solid transparent;" onmouseover="this.style.borderColor='rgba(255,215,0,0.4)'" onmouseout="this.style.borderColor='transparent'" title="Klicken zum Öffnen/Schließen der Antwort"`;

        const klickHinweis = istMeinEigenerKommentar ? "" : `<span style="margin-left:auto; font-size:0.65rem; color:#4a658a; font-style:italic;">Antworten</span>`;

        return `<div class="kommentar-wrapper" style="margin-bottom: 10px; ${indentStyle}">
            <div class="kommentar" style="display: flex; gap: 8px;">
                ${avatar}
                <div class="k-body" ${klickAktion}>
                    ${replyHeader}
                    <div style="display:flex; align-items:center;">
                        <span class="k-name" style="color: var(--gold); font-weight: 700; font-size: 0.76rem;">${name}</span> 
                        ${handle ? `<span class="bk-handle" style="font-size: 0.7rem; color: #6f8fbf; margin-left:4px;">@${handle}</span>` : ''}
                        ${erstellerBadge}
                        ${klickHinweis}
                    </div>
                    <div class="k-text" style="color: #dfe8f3; font-size: 0.85rem; margin-top: 5px; line-height: 1.4;">${textInhalt}</div>
                </div>
            </div>
        </div>`;
    }

    // Toggle-Funktion für die klickbare Kommentar-Blase (öffnen oder schließen mit einem Klick/Tap)
    window.toggleAntwortFeld = function(event, beitragId, replyTarget, element) {
        event.stopPropagation();
        
        const wrapper = element.closest('.kommentar-wrapper');
        const existierendeBox = wrapper.querySelector('.inline-antwort-box');
        const warOffen = !!existierendeBox;
        
        // Alle anderen offenen Antwortfelder im Dokument schließen
        document.querySelectorAll('.inline-antwort-box').forEach(el => el.remove());
        
        // Wenn es bereits offen war, schließt es sich hiermit wieder
        if (warOffen) return;

        // Andernfalls das neue Inline-Antwortfeld direkt erzeugen und einhängen
        const box = document.createElement('div');
        box.className = 'inline-antwort-box';
        box.style.display = 'flex';
        box.style.gap = '8px';
        box.style.marginTop = '8px';
        box.onclick = e => e.stopPropagation();
        
        const input = document.createElement('input');
        input.type = 'text';
        input.placeholder = `Antwort an @${replyTarget} schreiben...`;
        input.style.flex = '1';
        input.style.background = '#050a14';
        input.style.border = '1px solid #1e3a5f';
        input.style.borderLeft = '2px solid var(--gold)';
        input.style.color = '#fff';
        input.style.padding = '8px 10px';
        input.style.borderRadius = '5px';
        input.style.outline = 'none';
        input.style.fontSize = '0.8rem';

        input.onkeypress = e => {
            if (e.key === 'Enter') {
                e.stopPropagation();
                window.sendeAntwortInline(beitragId, replyTarget, input.value, element);
            }
        };

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.textContent = 'Senden';
        btn.style.background = 'var(--gold)';
        btn.style.color = '#000';
        btn.style.border = 'none';
        btn.style.padding = '0 14px';
        btn.style.borderRadius = '5px';
        btn.style.fontWeight = 'bold';
        btn.style.cursor = 'pointer';

        btn.onclick = e => {
            e.stopPropagation();
            window.sendeAntwortInline(beitragId, replyTarget, input.value, element);
        };

        box.appendChild(input);
        box.appendChild(btn);

        wrapper.appendChild(box);
        input.focus();
    };

    // Sendet die Antwort, die beim Klick auf einen Kommentar geschrieben wurde
    window.sendeAntwortInline = async function(beitragId, replyTarget, text, element) {
        if (!text.trim()) return;
        
        const finalerText = `@${replyTarget} ${text.trim()}`;

        const box = document.getElementById('komm-box-' + beitragId);
        const postHandle = box ? box.getAttribute('data-ersteller-handle') : '';
        const postName = box ? box.getAttribute('data-ersteller-name') : '';

        try {
            const res = await fetch('/api/forum/kommentar', { 
                method: 'POST', 
                headers: { 'Content-Type': 'application/json' }, 
                body: JSON.stringify({ email: userEmail, beitrag_id: beitragId, text: finalerText }) 
            });
            const data = await res.json();
            
            if (data.success && data.kommentar) {
                document.querySelectorAll('.inline-antwort-box').forEach(el => el.remove());
                
                const wrapper = element.closest('.kommentar-wrapper');
                const neuHtml = renderKommentar(data.kommentar, postHandle, postName, beitragId);
                wrapper.insertAdjacentHTML('afterend', neuHtml); // Platziert die Antwort exakt darunter
                
                const zaehlerSpan = document.getElementById('komm-zaehler-' + beitragId);
                if (zaehlerSpan) zaehlerSpan.textContent = parseInt(zaehlerSpan.textContent) + 1;
            } else {
                alert(data.message || "Antwort fehlgeschlagen.");
            }
        } catch (e) {
            alert("Server-Verbindung fehlgeschlagen.");
        }
    };

    // Die Standard-Senden-Funktion für das Hauptfeld unten (nur für Besucher)
    window.sendeKommentar = async function(beitragId) {
        const input = document.getElementById('komm-in-' + beitragId);
        if (!input) return;
        const text = input.value.trim();
        if (!text) return;
        
        const box = document.getElementById('komm-box-' + beitragId);
        const postHandle = box ? box.getAttribute('data-ersteller-handle') : '';
        const postName = box ? box.getAttribute('data-ersteller-name') : '';

        try {
            const res = await fetch('/api/forum/kommentar', { 
                method: 'POST', 
                headers: { 'Content-Type': 'application/json' }, 
                body: JSON.stringify({ email: userEmail, beitrag_id: beitragId, text: text }) 
            });
            const data = await res.json();
            
            if (data.success && data.kommentar) {
                const kContainer = document.getElementById('komm-' + beitragId);
                if (kContainer) {
                    kContainer.insertAdjacentHTML('beforeend', renderKommentar(data.kommentar, postHandle, postName, beitragId));
                }
                
                input.value = "";
                const zaehlerSpan = document.getElementById('komm-zaehler-' + beitragId);
                if (zaehlerSpan) zaehlerSpan.textContent = parseInt(zaehlerSpan.textContent) + 1;
            } else {
                alert(data.message || "Kommentar fehlgeschlagen.");
            }
        } catch (e) {
            alert("Server-Verbindung fehlgeschlagen.");
        }
    };

    // Globaler Listener für Enter-Taste (Hauptfeld)
    document.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            const activeEl = document.activeElement;
            if (activeEl && activeEl.id && activeEl.id.startsWith('komm-in-')) {
                const beitragId = activeEl.id.replace('komm-in-', '');
                window.sendeKommentar(beitragId);
            }
        }
    });
    // =====================================================================
    // RECHTS: LIVE-VIDEO-SEKTOR (PeerJS-Mesh, 7+1 pro Thema)
    // =====================================================================
    let videoPeer = null, videoStream = null, videoHeartbeatTimer = null;
    let videoConfig = { plaetze_pro_tisch: 8 };
    let videoTeilnehmer = [], videoRemoteStreams = {}, meinPeerId = null, meinVideoRaum = null;

    async function initLiveSektor() {
        // Stiller Heartbeat-Probe nach Themenwechsel/Verlassen: hält den Belegungsstand aktuell.
        const sektor = backendSektor(); if (!sektor) return;
        try {
            const res = await fetch('/api/video/heartbeat', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email: userEmail, sektor }) });
            const data = await res.json();
            if (data.success) { videoConfig.plaetze_pro_tisch = data.plaetze_pro_tisch || 8; videoTeilnehmer = data.teilnehmer || []; renderLiveTische(data.warteliste || 0); }
        } catch (e) {}
    }

    let liveOverlayOffen = false;
    function setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }

    function renderLiveTische(warteliste) {
        const plaetze = videoConfig.plaetze_pro_tisch || 8;
        const seated = videoTeilnehmer.filter(t => t.status === 'aktiv');
        const tische = seated.length ? Math.max(...seated.map(t => t.tisch)) + 1 : (videoStream ? 1 : 0);
        const anzTische = Math.max(tische, videoStream ? 1 : 0);

        // Zähler im eingepassten Video-Grid aktuell halten.
        setText('lo-tisch-count', anzTische); setText('lo-teil-count', videoTeilnehmer.length); setText('lo-warte-count', warteliste || 0);

        // Das Video-Grid lebt ausschließlich im eingepassten Overlay (kein Video im Info-Panel).
        const container = document.getElementById('live-overlay-tische');
        if (!container) return;

        if (!videoStream && !videoTeilnehmer.length) {
            container.innerHTML = `<div class="live-gesperrt">Drücke START, um dem Live-Raum dieses Themas beizutreten.</div>`;
            return;
        }
        const n = Math.max(anzTische, 1);
        let html = "";
        for (let t = 0; t < n; t++) {
            html += `<div class="live-tisch-titel">Tisch ${t+1}</div><div class="tisch-grid">`;
            for (let s = 0; s < plaetze; s++) html += `<div class="v-slot" id="v-slot-${t}-${s}">frei</div>`;
            html += `</div>`;
        }
        if (warteliste > 0) html += `<div class="warteliste-box">⏳ Warteliste: <b>${warteliste}</b> Person(en) warten auf den nächsten Tisch (Split ab dem 10. Gast).</div>`;
        container.innerHTML = html;
        platziereStreams();
    }

    // Overlay legt sich dynamisch über die Seite, sobald eine Sektor-Sitzung aktiv ist.
    function oeffneLiveOverlay() {
        if (aktivesThemaIdx === null) { alert("Bitte zuerst ein Thema wählen."); return; }
        if (GESPERRTE_THEMEN_IDX.has(aktivesThemaIdx) && !isAdmin) { alert("Dieses Thema hat noch keinen Live-Raum."); return; }
        liveOverlayOffen = true;
        setText('lo-thema', `Sektor ${aktivesThemaIdx + 1}: ${themen[aktivesThemaIdx] || ""}`);
        document.getElementById('live-overlay').classList.add('aktiv');
        renderLiveTische(0);
        videoHeartbeat();
    }
    function schliesseLiveOverlay() {
        liveOverlayOffen = false;
        document.getElementById('live-overlay').classList.remove('aktiv');
        renderLiveTische(0);
    }

    // =====================================================================
    // SCHWEBENDES LIVE-PANEL (rechts): Info-Ansicht + gelb→grün-Scharfschaltung.
    // Fährt wie das Hamburger-Menü ein/aus. Zeigt "What's up" (aktive Sektoren,
    // Zeiten, anonyme Tischbesetzung) – KEIN Video. Das Video-Grid öffnet erst
    // über das grüne "7+1 Live-Sektor öffnen".
    // =====================================================================
    let liveBetretenFrei = false;    // von der mittleren Schleuse gekoppelt (Rot→Grün)
    let livePanelOffen = false;
    let liveInfoTimer = null;

    function toggleLivePanel() { livePanelOffen ? schliesseLivePanel() : oeffneLivePanel(); }
    function oeffneLivePanel() {
        livePanelOffen = true;
        const p = document.getElementById('live-spalte'); if (p) p.classList.add('aktiv');
        aktualisiereLivePanelStatus();
        ladeLiveInfo();
        if (!liveInfoTimer) liveInfoTimer = setInterval(ladeLiveInfo, 15000);
    }
    function schliesseLivePanel() {
        livePanelOffen = false;
        const p = document.getElementById('live-spalte'); if (p) p.classList.remove('aktiv');
        if (liveInfoTimer) { clearInterval(liveInfoTimer); liveInfoTimer = null; }
    }

    // Gelb (gesperrt) ↔ Grün (scharf). Admin ist immer scharf (Admin-Ausnahme).
    function aktualisiereLivePanelStatus() {
        const btn = document.getElementById('live-oeffnen-btn');
        const griff = document.getElementById('live-panel-griff');
        const frei = liveBetretenFrei || isAdmin;
        if (btn) {
            btn.className = 'live-oeffnen-btn ' + (frei ? 'gruen' : 'gelb');
            btn.textContent = (frei ? '▶ 7+1 Live-Sektor öffnen' : '🔒 7+1 Live-Sektor öffnen');
        }
        if (griff) griff.classList.toggle('gruen', frei);
    }

    function klickLiveOeffnen() {
        if (!(liveBetretenFrei || isAdmin)) {
            alert('Noch gesperrt: Durchlaufe zuerst in der Mitte die Schleuse „Anmeldeoptionen für Live-Sektor" (Thema → Zeitfenster → Technik-Check). Sobald „Live-betreten" grün ist, wird dieses Element scharfgeschaltet.');
            return;
        }
        if (aktivesThemaIdx === null) { alert('Bitte zuerst ein Thema wählen.'); return; }
        starteVideo();   // öffnet das eingepasste 7+1-Video-Grid in der Mittel-Fläche
    }

    function liveSlotLabel(slot) { return ({ vormittag: 'Vormittag', nachmittag: 'Nachmittag' })[slot] || slot || ''; }
    function liveUhr(iso) { if (!iso) return '—'; const d = new Date(iso); return isNaN(d) ? '—' : d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' }); }

    async function ladeLiveInfo() {
        const box = document.getElementById('live-info');
        if (!box) return;
        try {
            const res = await fetch(`/api/live/uebersicht?email=${encodeURIComponent(userEmail)}`);
            const d = await res.json();
            if (!d.success) { box.innerHTML = `<div class="live-gesperrt">Übersicht nicht verfügbar.</div>`; return; }
            let html = "";
            if (d.pausiert) html += `<div class="li-pausiert">⛔ Der Live-Sektor ist gerade durch die Regie pausiert (Not-Aus).</div>`;
            // Heutige Zeitfenster (Termine).
            html += `<div class="li-block-titel">🗓️ Heutige Zeitfenster</div>`;
            const sessions = d.sessions || [];
            if (!sessions.length) {
                html += `<div class="li-karte"><div class="li-meta">Für heute sind keine Zeitfenster geplant.</div></div>`;
            } else {
                sessions.forEach(s => {
                    const live = (s.status === 'live' || s.im_fenster);
                    const badge = live ? `<span class="li-badge b-live">läuft</span>` : `<span class="li-badge b-plan">geplant</span>`;
                    html += `<div class="li-karte ${live ? 'live' : ''}">${badge}
                        <div class="li-thema">Sektor ${s.sektor}: ${escapeHtml(s.thema || '')}</div>
                        <div class="li-meta">${liveSlotLabel(s.slot)} · ${liveUhr(s.start)}–${liveUhr(s.ende)} Uhr · ${s.anzahl_angemeldet}/${s.max_teilnehmer} angemeldet</div></div>`;
                });
            }
            // Aktive Sektoren mit anonymer Tischbesetzung (keine Namen).
            html += `<div class="li-block-titel">🎥 Aktive Live-Sektoren</div>`;
            const raeume = (d.raeume || []).filter(r => r.teilnehmer > 0);
            if (!raeume.length) {
                html += `<div class="li-karte"><div class="li-meta">Aktuell ist kein Live-Sektor besetzt.</div></div>`;
            } else {
                raeume.forEach(r => {
                    html += `<div class="li-karte live">
                        <div class="li-thema">Sektor ${r.sektor}: ${escapeHtml(r.thema || '')}</div>
                        <div class="li-meta">${r.tische} Tisch(e) · ${r.teilnehmer} Teilnehmer (anonym)</div></div>`;
                });
            }
            html += `<div class="li-meta" style="margin-top:12px; color:#66788f;">Gesamt aktiv: ${d.aktive_teilnehmer || 0} · Info-Ansicht, kein Video.</div>`;
            box.innerHTML = html;
        } catch (e) { box.innerHTML = `<div class="live-gesperrt">Server-Verbindung fehlgeschlagen.</div>`; }
    }

    function platziereStreams() {
        videoTeilnehmer.forEach(t => {
            if (t.status !== 'aktiv') return;
            const slot = document.getElementById(`v-slot-${t.tisch}-${t.platz_am_tisch}`);
            if (!slot) return;
            const istIch = (t.peer_id === meinPeerId);
            const stream = istIch ? videoStream : videoRemoteStreams[t.peer_id];
            const label = istIch ? 'DU' : (t.email ? t.email.split('@')[0] : 'Gast');
            if (stream) {
                if (!slot.querySelector('video')) {
                    slot.innerHTML = `<video autoplay playsinline ${istIch?'muted':''} style="width:100%;height:100%;object-fit:cover;"></video><div style="position:absolute;bottom:2px;left:4px;font-size:0.58rem;color:#ffd700;text-shadow:0 0 3px #000;">${label}</div>`;
                }
                const v = slot.querySelector('video');
                if (v && v.srcObject !== stream) { v.srcObject = stream; if (istIch) v.muted = true; v.play().catch(()=>{}); }
            } else if (!slot.querySelector('video')) {
                slot.innerHTML = `${label} <span style="color:#666;">(verbindet…)</span>`;
            }
        });
    }

    async function starteVideo() {
        const sektor = backendSektor();
        if (!sektor) { alert("Bitte zuerst ein Thema wählen."); return; }
        if (GESPERRTE_THEMEN_IDX.has(aktivesThemaIdx) && !isAdmin) { alert("Dieses Thema hat noch keinen Live-Raum."); return; }
        if (typeof Peer === 'undefined') { alert("Video-Engine (PeerJS) nicht geladen."); return; }
        if (videoPeer) return;
        // Anmeldeoptionen für Live-Sektoren berücksichtigen (Kamera/Mikrofon).
        const kamOn = localStorage.getItem('mm_live_kamera') !== 'aus';
        const mikOn = localStorage.getItem('mm_live_mikro') !== 'aus';
        const constraints = { video: kamOn, audio: mikOn };
        if (!kamOn && !mikOn) constraints.video = true;   // getUserMedia braucht mind. eine Spur
        try { videoStream = await navigator.mediaDevices.getUserMedia(constraints); }
        catch (err) { alert("Kamera-/Mikrofon-Zugriff wurde verweigert."); return; }
        meinVideoRaum = sektor;
        videoPeer = new Peer();
        videoPeer.on('open', async (peerId) => {
            meinPeerId = peerId;
            try {
                const res = await fetch('/api/video/join', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email: userEmail, peer_id: peerId, sektor }) });
                const data = await res.json();
                if (!data.success) { alert(data.error || "Beitritt fehlgeschlagen."); return; }
                videoConfig.plaetze_pro_tisch = data.plaetze_pro_tisch || 8;
                videoTeilnehmer = data.teilnehmer || [];
                (data.andere || []).forEach(o => rufePeerAn(o.peer_id));
                if (data.status === 'warteliste') alert("Der Tisch ist voll – du stehst auf der Warteliste. Ab dem 10. Gast öffnet automatisch Tisch 2.");
                renderLiveTische(data.warteliste || 0);
                // Sektor-Sitzung ist aktiv -> 7+1 Live-Overlay dynamisch einblenden.
                oeffneLiveOverlay();
            } catch (e) {}
            if (!videoHeartbeatTimer) videoHeartbeatTimer = setInterval(videoHeartbeat, 15000);
        });
        videoPeer.on('call', (call) => { call.answer(videoStream); call.on('stream', rs => { videoRemoteStreams[call.peer] = rs; platziereStreams(); }); });
        videoPeer.on('error', (err) => console.warn("PeerJS:", err));
    }

    function rufePeerAn(peerId) {
        if (!peerId || peerId === meinPeerId || !videoPeer || !videoStream || videoRemoteStreams[peerId]) return;
        const call = videoPeer.call(peerId, videoStream);
        if (!call) return;
        call.on('stream', rs => { videoRemoteStreams[peerId] = rs; platziereStreams(); });
    }

    async function videoHeartbeat() {
        if (!meinVideoRaum) return;
        try {
            const res = await fetch('/api/video/heartbeat', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email: userEmail, sektor: meinVideoRaum }) });
            const data = await res.json();
            if (data.success) {
                videoConfig.plaetze_pro_tisch = data.plaetze_pro_tisch || 8;
                videoTeilnehmer = data.teilnehmer || [];
                const mein = videoTeilnehmer.find(t => t.peer_id === meinPeerId);
                if (videoPeer && videoStream && mein && mein.status === 'aktiv') {
                    videoTeilnehmer.forEach(t => { if (t.status==='aktiv' && t.tisch===mein.tisch && t.peer_id!==meinPeerId && !videoRemoteStreams[t.peer_id]) rufePeerAn(t.peer_id); });
                }
                renderLiveTische(data.warteliste || 0);
            }
        } catch (e) {}
    }

    async function stoppeVideo(still) {
        liveOverlayOffen = false;
        const ovEl = document.getElementById('live-overlay'); if (ovEl) ovEl.classList.remove('aktiv');
        if (videoHeartbeatTimer) { clearInterval(videoHeartbeatTimer); videoHeartbeatTimer = null; }
        if (videoStream) { videoStream.getTracks().forEach(t => t.stop()); videoStream = null; }
        if (videoPeer) { try { videoPeer.destroy(); } catch(e){} videoPeer = null; }
        videoRemoteStreams = {}; meinPeerId = null;
        const raumVorher = meinVideoRaum; meinVideoRaum = null;
        if (raumVorher) { try { await fetch('/api/video/leave', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email: userEmail }) }); } catch (e) {} }
        if (!still && aktivesThemaIdx !== null && !(GESPERRTE_THEMEN_IDX.has(aktivesThemaIdx) && !isAdmin)) initLiveSektor();
    }

    // =====================================================================
    // PROFIL-EINSTELLUNGEN (Klick auf Profilfoto)
    // =====================================================================
    // ---- SYSTEM 2: PROFIL-CANVAS-Zustand (freies Gestaltungssystem statt starrer Kästen) ----
    let profilNeuesBild = null;          // neues Profilbild (Data-URL) oder null
    let profilGeburtsdatum = "";
    let profilGalerie = [];
    // ENTKOPPELTE GALERIE (eigener Raum, unabhängig vom Profil-Canvas). Verlustsicherer Bild-Pool +
    // reservierte Canvas-Elemente (elemente[] befüllt der Galerie-Editor in Schritt 2). Persistiert als 'galerie_seite'.
    let galerieSeite = { hintergrund_url: '', hintergrund_farbe: '#0c1a2e', farbschema: 'nachtblau', rahmen: '', bilder: [], elemente: [] };
    let profilSichtbarkeit = {};
    let profilSchema = 'nachtblau';
    let profilLand = "", profilStadt = "";
    // Frei platzierbare, frei skalierbare Module. Jedes Modul trägt Position (x,y),
    // Dimension (w,h) und alle WYSIWYG-Design-Attribute – wie eine eigene Mini-Webseite.
    let canvasElemente = [];
    let canvasBgUrl = "", canvasBgFarbe = "#0c1a2e", canvasRahmen = "";
    // Malermodus (Feature 1): Hintergrund-Verschiebung (X/Y %) + Skalierung (% der Breite). 50/50/100 == altes center/cover.
    let canvasBgPosX = 50, canvasBgPosY = 50, canvasBgSkala = 100;
    let ceElementSeq = 1, ceAktion = null, ceSelektiert = null, ceCtxNeuPos = null;
    // Galerie ist KEIN Profil-Canvas-Typ mehr (entkoppelt -> eigener Galerie-Canvas, Schritt 2).
    const CANVAS_TYPEN = ['bio','motto','text','foto','name','datum','standort'];

    const PROFIL_SICHT_STANDARD = { foto:'oeffentlich', vorname:'oeffentlich', nachname:'privat', geburtsdatum:'privat', biografie:'oeffentlich', galerie:'oeffentlich', standort:'oeffentlich' };
    const PROFIL_SICHT_FELDER = [ ['foto','Foto'], ['vorname','Name'], ['geburtsdatum','Geburtsdatum'], ['biografie','Biografie'], ['galerie','Galerie'], ['standort','Standort'] ];
    const PROFIL_FILTER = ['', 'grayscale(1)', 'sepia(0.7)', 'contrast(1.3)', 'saturate(1.7)', 'brightness(1.2)', 'blur(1.5px)'];
    const PROFIL_SCHEMATA = {
        nachtblau: { label: 'Nachtblau',  bg: 'linear-gradient(135deg,#001a3a 0%,#000 100%)', accent: '#ffd700', rand: '#003d8f' },
        smaragd:   { label: 'Smaragd',    bg: 'linear-gradient(135deg,#04241c 0%,#000 100%)', accent: '#39e6a8', rand: '#0c6b4f' },
        purpur:    { label: 'Purpur',     bg: 'linear-gradient(135deg,#1e0a33 0%,#000 100%)', accent: '#c39bff', rand: '#5a2b9e' },
        bernstein: { label: 'Bernstein',  bg: 'linear-gradient(135deg,#2a1603 0%,#000 100%)', accent: '#ffb347', rand: '#8a5a12' },
        graphit:   { label: 'Graphit',    bg: 'linear-gradient(135deg,#161a1f 0%,#000 100%)', accent: '#8fd0ff', rand: '#3a4656' },
    };

    // ---- Galerie-Datenmodell + verlustfreie Migration aus Alt-Canvas-Modulen ----
    function galerieStandardSeite() {
        return { hintergrund_url: '', hintergrund_farbe: '#0c1a2e', farbschema: 'nachtblau', rahmen: '', bilder: [], elemente: [] };
    }
    // Ein Galerie-Bild normalisieren: akzeptiert String (nur URL) ODER {url,titel,filter}. -> {url,titel,filter} | null
    function ceGalerieBildNorm(b) {
        if (typeof b === 'string') return b ? { url: b, titel: '', filter: '' } : null;
        if (b && typeof b === 'object' && b.url) return { url: String(b.url), titel: String(b.titel || ''), filter: String(b.filter || '') };
        return null;
    }
    // Löst Alt-Galerie-Module aus dem Profil-Canvas heraus und schmilzt alle Bildquellen verlustfrei
    // (deduped nach url) in galerie_seite ein. -> { profilElemente (ohne Galerie), galerieSeite }
    function galerieMigrieren(rohElemente, d) {
        d = d || {};
        const vorhanden = (d.galerie_seite && typeof d.galerie_seite === 'object') ? d.galerie_seite : {};
        const gs = galerieStandardSeite();
        gs.hintergrund_url = vorhanden.hintergrund_url || '';
        gs.hintergrund_farbe = vorhanden.hintergrund_farbe || '#0c1a2e';
        gs.farbschema = (vorhanden.farbschema && PROFIL_SCHEMATA[vorhanden.farbschema]) ? vorhanden.farbschema : 'nachtblau';
        gs.rahmen = vorhanden.rahmen || '';
        gs.elemente = Array.isArray(vorhanden.elemente) ? vorhanden.elemente.slice() : [];
        gs.bilder = Array.isArray(vorhanden.bilder) ? vorhanden.bilder.map(ceGalerieBildNorm).filter(Boolean) : [];
        const gesehen = new Set(gs.bilder.map(b => b.url));
        const uebernehmen = (b, filter) => {
            const bild = ceGalerieBildNorm(b); if (!bild) return;
            if (filter && !bild.filter) bild.filter = filter;
            if (!gesehen.has(bild.url)) { gs.bilder.push(bild); gesehen.add(bild.url); }
        };
        const profilElemente = [];
        (rohElemente || []).forEach(el => {
            if (el && el.typ === 'galerie') (el.bilder || []).forEach(b => uebernehmen(b, el.filter || ''));  // Alt-Modul -> Pool
            else if (el) profilElemente.push(el);                                                             // Rest bleibt 100% unverändert
        });
        if (Array.isArray(d.galerie)) d.galerie.forEach(b => uebernehmen(b, ''));    // Legacy-Flachliste einschmelzen
        return { profilElemente, galerieSeite: gs };
    }

    async function oeffneProfil() {
        profilNeuesBild = null; profilMsg(""); canvasElemente = []; ceElementSeq = 1; ceSelektiert = null;
        galerieSeite = galerieStandardSeite();
        try {
            const res = await fetch(`/auth/profil-daten?email=${encodeURIComponent(userEmail)}`);
            const d = await res.json();
            if (d.success) {
                meinProfil.benutzername = d.benutzername || ""; meinProfil.biografie = d.biografie || ""; meinProfil.profilbild = d.profilbild || "";
                meinProfil.vorname = d.vorname || ""; meinProfil.nachname = d.nachname || "";
                profilGeburtsdatum = d.geburtsdatum || "";
                profilGalerie = Array.isArray(d.galerie) ? d.galerie.slice() : [];
                profilSichtbarkeit = Object.assign({}, PROFIL_SICHT_STANDARD, d.sichtbarkeit || {});
                profilLand = d.land || ""; profilStadt = d.stadt || "";
                const c = d.canvas || {};
                canvasBgUrl = c.hintergrund_url || "";
                canvasBgFarbe = c.hintergrund_farbe || "#0c1a2e";
                canvasRahmen = c.rahmen || "";
                // Malermodus (Feature 1): Hintergrund-Offset/Skalierung laden (Fallback = altes center/cover).
                canvasBgPosX = (typeof c.hintergrund_pos_x === 'number') ? c.hintergrund_pos_x : 50;
                canvasBgPosY = (typeof c.hintergrund_pos_y === 'number') ? c.hintergrund_pos_y : 50;
                canvasBgSkala = (typeof c.hintergrund_skala === 'number') ? c.hintergrund_skala : 100;
                profilSchema = (c.farbschema && PROFIL_SCHEMATA[c.farbschema]) ? c.farbschema : ((d.farbschema && PROFIL_SCHEMATA[d.farbschema]) ? d.farbschema : 'nachtblau');
                // ENTKOPPLUNG + verlustfreie Migration: Alt-Galerie-Module VOR ceNorm herauslösen
                // (galerie ist kein gültiger Canvas-Typ mehr) und ihre Bilder in galerie_seite überführen.
                const mig = galerieMigrieren(Array.isArray(c.elemente) ? c.elemente : [], d);
                canvasElemente = mig.profilElemente.map(el => ceNorm(el));
                galerieSeite = mig.galerieSeite;
            }
        } catch (e) {}
        if (!canvasElemente.length) {
            // Sinnvolle Start-Komposition: jedes Profil-Attribut ist ein frei platzierbares Modul.
            canvasElemente = ceStartKomposition({ bild: meinProfil.profilbild || '', biografie: meinProfil.biografie || 'Erzähle der Community, wer du bist …' });
        }
        ceSchemaSelectBauen();
        document.getElementById('ce-bg-url').value = canvasBgUrl;
        document.getElementById('ce-bg-farbe').value = /^#/.test(canvasBgFarbe) ? canvasBgFarbe : '#0c1a2e';
        document.getElementById('ce-schema').value = profilSchema;
        document.getElementById('ce-rahmen').value = canvasRahmen;
        // Malermodus (Feature 1): Regler-Positionen aus dem geladenen Zustand setzen.
        document.getElementById('ce-bg-posx').value = canvasBgPosX;
        document.getElementById('ce-bg-posy').value = canvasBgPosY;
        document.getElementById('ce-bg-skala').value = canvasBgSkala;
        document.getElementById('ce-land').value = profilLand;
        document.getElementById('ce-stadt').value = profilStadt;
        document.getElementById('ce-geburtsdatum').value = profilGeburtsdatum;
        baueSichtRow();
        ceCanvasStil();
        baueCanvas();
        document.getElementById('profil-overlay').classList.add('aktiv');
    }
    function schliesseProfil() { document.getElementById('profil-overlay').classList.remove('aktiv'); }
    // Werkzeug-Dock ein-/ausklappen -> gibt die volle Bühne frei (jeder Pixel gehört dem Canvas).
    function ceDockToggle() {
        const dock = document.getElementById('ce-dock'), btn = document.getElementById('ce-dock-btn');
        if (!dock) return;
        const zu = dock.classList.toggle('eingeklappt');
        if (btn) btn.textContent = zu ? '▼ Werkzeuge' : '▲ Werkzeuge';
    }
    function profilMsg(text, ok) { const el = document.getElementById('profil-msg'); if (el){ el.textContent = text||""; el.classList.toggle('ok', !!ok);} }

    // ---- Farbschema / Canvas-Stil ----
    function ceSchemaSelectBauen() {
        const sel = document.getElementById('ce-schema');
        if (!sel) return;
        sel.innerHTML = Object.entries(PROFIL_SCHEMATA).map(([k,v]) => `<option value="${k}">${escapeHtml(v.label)}</option>`).join('');
        sel.value = profilSchema;
    }
    function ceSchemaWechsel(key) { profilSchema = key; ceCanvasStil(); }
    function ceCanvasStil() {
        canvasBgUrl = (document.getElementById('ce-bg-url')||{}).value || "";
        canvasBgFarbe = (document.getElementById('ce-bg-farbe')||{}).value || "#0c1a2e";
        canvasRahmen = (document.getElementById('ce-rahmen')||{}).value || "";
        // Malermodus (Feature 1): Hintergrund-Verschiebung/Skalierung aus den Reglern lesen + Labels aktualisieren.
        canvasBgPosX = parseFloat((document.getElementById('ce-bg-posx')||{}).value); if (isNaN(canvasBgPosX)) canvasBgPosX = 50;
        canvasBgPosY = parseFloat((document.getElementById('ce-bg-posy')||{}).value); if (isNaN(canvasBgPosY)) canvasBgPosY = 50;
        canvasBgSkala = parseFloat((document.getElementById('ce-bg-skala')||{}).value); if (isNaN(canvasBgSkala)) canvasBgSkala = 100;
        const setLab = (id, v) => { const n = document.getElementById(id); if (n) n.textContent = Math.round(v) + '%'; };
        setLab('ce-bg-posx-lab', canvasBgPosX); setLab('ce-bg-posy-lab', canvasBgPosY); setLab('ce-bg-skala-lab', canvasBgSkala);
        const cv = document.getElementById('ce-canvas');
        if (!cv) return;
        const schema = PROFIL_SCHEMATA[profilSchema] || PROFIL_SCHEMATA.nachtblau;
        Object.assign(cv.style, ceHintergrund(canvasBgUrl, canvasBgFarbe, schema, canvasBgPosX, canvasBgPosY, canvasBgSkala));
        const rahmen = { gold: '3px solid #ffd700', doppelt: '6px double #ffd700', neon: '2px solid #00ffcc' };
        cv.style.border = rahmen[canvasRahmen] || `1px solid ${schema.rand}`;
        cv.style.boxShadow = canvasRahmen === 'neon' ? '0 0 22px rgba(0,255,204,0.55)' : (canvasRahmen === 'weich' ? '0 18px 50px rgba(0,0,0,0.6)' : 'none');
    }

    // ---- Sichtbarkeit: welche Felder in der Profilsuche/Öffentlichkeit erscheinen ----
    function baueSichtRow() {
        const row = document.getElementById('ce-sicht');
        if (!row) return;
        row.innerHTML = `<span class="ce-sicht-titel">Für Besucher sichtbar (steuert Ansicht + Suche):</span>` + PROFIL_SICHT_FELDER.map(([k,label]) => {
            const oeff = (profilSichtbarkeit[k]||'oeffentlich') !== 'privat';
            return `<button class="ce-sicht-btn ${oeff?'an':''}" onclick="ceSichtToggle('${k}')">${oeff?'🌍':'🔒'} ${escapeHtml(label)}</button>`;
        }).join('');
    }
    function ceSichtToggle(k) {
        profilSichtbarkeit[k] = ((profilSichtbarkeit[k]||'oeffentlich') !== 'privat') ? 'privat' : 'oeffentlich';
        baueSichtRow();
    }
    // Werte aus dem Werkzeug-Dock (Land/Stadt/Geburtsdatum) live in die datengebundenen Module spiegeln.
    function ceDatenGeaendert() {
        profilLand = (document.getElementById('ce-land')||{}).value || '';
        profilStadt = (document.getElementById('ce-stadt')||{}).value || '';
        profilGeburtsdatum = (document.getElementById('ce-geburtsdatum')||{}).value || profilGeburtsdatum;
        canvasElemente.filter(e => e.typ === 'name' || e.typ === 'datum' || e.typ === 'standort')
                      .forEach(e => ceAktualisiereElement(e.id));
    }

    // =====================================================================
    // FREIES MODUL-SYSTEM (CSS-Grid-Editor): jedes Modul trägt Position (x,y),
    // Dimension (w,h) und alle WYSIWYG-Design-Attribute. Editor UND Read-only-Ansicht
    // rendern über DIESELBEN Helfer -> das Profil erscheint exakt wie gestaltet.
    // =====================================================================

    // Sicheres Einbetten einer Bild-Quelle in eine CSS url(): Data-URLs sind sicher,
    // freie URLs entzerren wir von zeichen, die die CSS-Deklaration brechen könnten.
    function ceCssUrl(u) { return String(u || '').replace(/["'()\\]/g, ''); }

    // Malermodus (Feature 1): EINE Wahrheit für den Canvas-Hintergrund (Editor-DOM + Read-only-Ansicht).
    // Liefert ein Style-Objekt; bei Standardwerten (50/50/100) exakt das alte center/cover -> Bestandsprofile bleiben identisch.
    function ceHintergrund(url, farbe, schema, px, py, sk) {
        px = (px == null) ? 50 : +px; py = (py == null) ? 50 : +py; sk = (sk == null) ? 100 : +sk;
        const grund = farbe || (schema && schema.bg) || '#0c1a2e';
        if (!url) return { background: grund, backgroundImage: 'none' };
        const basis = { background: grund, backgroundImage: `url('${ceCssUrl(url)}')`, backgroundRepeat: 'no-repeat' };
        if (px === 50 && py === 50 && sk === 100)
            return Object.assign(basis, { backgroundSize: 'cover', backgroundPosition: 'center' });
        return Object.assign(basis, { backgroundSize: sk + '%', backgroundPosition: px + '% ' + py + '%' });
    }
    // Dasselbe Objekt als CSS-Deklarationsstring (für die read-only Besucheransicht, die per Template-String rendert).
    function ceHintergrundStr(url, farbe, schema, px, py, sk) {
        const o = ceHintergrund(url, farbe, schema, px, py, sk);
        return Object.keys(o).map(k => k.replace(/[A-Z]/g, m => '-' + m.toLowerCase()) + ':' + o[k]).join('; ') + ';';
    }

    // ISO-Datum (YYYY-MM-DD) hübsch als DD.MM.YYYY darstellen.
    function ceFormatDatum(iso) {
        const s = String(iso || '').trim(); if (!s) return '';
        const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
        return m ? `${m[3]}.${m[2]}.${m[1]}` : s;
    }
    // Aktuelle Profil-Datenquelle des EDITORS (füttert die datengebundenen Module Name/Datum/Standort).
    function ceEditorDaten() {
        const g = (document.getElementById('ce-geburtsdatum') || {}).value;
        return {
            name: `${(meinProfil.vorname || '').trim()} ${(meinProfil.nachname || '').trim()}`.trim(),
            geburtsdatum: g || profilGeburtsdatum || '',
            land: ((document.getElementById('ce-land') || {}).value) || profilLand || '',
            stadt: ((document.getElementById('ce-stadt') || {}).value) || profilStadt || '',
        };
    }
    // Anzeigetext eines datengebundenen Moduls – Editor UND Besucheransicht nutzen dieselbe Logik.
    function ceDatenText(el, daten) {
        daten = daten || {};
        if (el.typ === 'name') return (daten.name || '').trim();
        if (el.typ === 'datum') return ceFormatDatum(daten.geburtsdatum);
        if (el.typ === 'standort') return [daten.stadt, daten.land].filter(Boolean).join(', ');
        return '';
    }

    // Neues Modul mit sinnvollen Startwerten (danach voll frei formbar).
    function ceStandard(typ) {
        const el = {
            id: ceElementSeq++, typ, x: 28, y: 26, w: 42, h: 22,
            radius: 12, bg_farbe: '', rahmen_farbe: '', rahmen_breite: 0, polster: (typ === 'foto') ? 0 : 12,
            farbe: '#ffffff', groesse: 1, zeilenabstand: 1.35, ausrichtung: 'links', fett: false,
            bild: '', filter: '', text: '', label: '',
            // Malermodus: Z-Index (Feature 2) + Kreis-Maske/Freistellung/Passung (Feature 3).
            z: 0, maske: '', freistellen: false, bild_passung: 'cover',
        };
        if (typ === 'foto') { el.w = 24; el.h = 40; el.radius = 14; }
        else if (typ === 'motto') { el.text = 'Dein Motto …'; el.farbe = '#ffd700'; el.groesse = 1.8; el.fett = true; el.h = 14; }
        else if (typ === 'bio') { el.text = 'Deine Biografie …'; el.h = 40; }
        // Datengebundene Module: Inhalt kommt aus den Profildaten, frei positionierbar wie jedes andere Modul.
        else if (typ === 'name') { el.farbe = '#ffd700'; el.groesse = 1.9; el.fett = true; el.h = 12; }
        else if (typ === 'datum') { el.label = 'Geboren am '; el.groesse = 1; el.h = 9; }
        else if (typ === 'standort') { el.label = '📍 '; el.groesse = 1; el.h = 9; }
        else { el.text = 'Freitext …'; }
        return el;
    }

    // Standard-Komposition für ein noch nie gestaltetes Profil. IDENTISCH für Editor und
    // Besucheransicht -> ohne eigenes Zutun sieht der Besucher exakt dasselbe Grundlayout.
    // Foto, Name, Datum, Standort und Bio sind allesamt frei positionierbare Module.
    function ceStartKomposition(q) {
        q = q || {};
        const foto = ceStandard('foto');       Object.assign(foto,     { x:6,  y:8,  w:22, h:44, bild: q.bild || '' });
        const name = ceStandard('name');        Object.assign(name,     { x:32, y:9,  w:60, h:11 });
        const datum = ceStandard('datum');      Object.assign(datum,    { x:32, y:22, w:60, h:8 });
        const standort = ceStandard('standort');Object.assign(standort, { x:32, y:31, w:60, h:8 });
        const bio = ceStandard('bio');          Object.assign(bio,      { x:32, y:42, w:60, h:48, text: q.biografie || '' });
        return [foto, name, datum, standort, bio];
    }

    // Normalisiert ein gespeichertes/älteres Modul auf das aktuelle Schema (Migration).
    function ceNorm(raw) {
        const t = CANVAS_TYPEN.includes(raw.typ) ? raw.typ : 'text';
        const el = Object.assign(ceStandard(t), raw, { id: ceElementSeq++, typ: t });
        // Textvorgaben aus ceStandard nicht über echte (auch leere) gespeicherte Texte stülpen.
        el.text = (typeof raw.text === 'string') ? raw.text : (el.text || '');
        // Altes Rahmen-Preset -> explizite Rahmen-Attribute überführen.
        if (raw.rahmen && !raw.rahmen_breite) {
            if (raw.rahmen === 'gold') { el.rahmen_farbe = '#ffd700'; el.rahmen_breite = 3; }
            else if (raw.rahmen === 'neon') { el.rahmen_farbe = '#00ffcc'; el.rahmen_breite = 2; }
            else if (raw.rahmen === 'doppelt') { el.rahmen_farbe = '#ffd700'; el.rahmen_breite = 5; }
        }
        if (typeof el.h !== 'number' || !el.h) el.h = (t === 'foto') ? 40 : 20;
        return el;
    }

    function ceFindeEl(id) { return canvasElemente.find(e => e.id === id); }

    // ---- Gemeinsame Render-Helfer (Editor + Read-only identisch) ----
    function ceBoxStyle(el) {
        const w = el.w || 30, h = el.h || ((el.typ === 'foto') ? 40 : 20);
        let s = `left:${el.x}%; top:${el.y}%; width:${w}%; height:${h}%;`;
        // Malermodus (Feature 3): Kreis-Maske erzwingt einen sauberen runden Rahmen + Clipping (kein hartes Viereck),
        // sonst der freie Radius. overflow:hidden beschneidet Bild + eckige Ränder exakt auf die Form.
        if (el.maske === 'kreis') s += `border-radius:50%; overflow:hidden;`;
        else s += `border-radius:${el.radius || 0}px;`;
        if (el.bg_farbe) s += `background:${el.bg_farbe};`;
        if (el.rahmen_breite) s += `border:${el.rahmen_breite}px solid ${el.rahmen_farbe || '#ffd700'};`;
        if (el.polster) s += `padding:${el.polster}px;`;
        // Malermodus (Feature 2): expliziter Z-Index -> Bild-im-Bild-Tiefe (z. B. Sonne HINTER Gebirge/Logo legen).
        if (el.z) s += `z-index:${el.z};`;
        return s;
    }
    function ceTextStyle(el) {
        const align = el.ausrichtung === 'zentriert' ? 'center' : (el.ausrichtung === 'rechts' ? 'right' : 'left');
        return `color:${el.farbe || '#fff'}; font-size:${el.groesse || 1}rem; line-height:${el.zeilenabstand || 1.35}; text-align:${align}; font-weight:${el.fett ? '800' : '400'};`;
    }
    // Innerer Modul-Inhalt. readonly=true -> keine Editier-Hooks (für Profilansicht/Suche).
    // daten = Profil-Datenkontext für datengebundene Module (Editor: eigene Daten, Ansicht: Zielprofil).
    function ceInner(el, readonly, daten) {
        if (el.typ === 'foto') {
            // Malermodus (Feature 3): 'frei' entfernt die dunkle Box (transparente Verschmelzung),
            // 'einpassen' (contain) zeigt runde Logos/Sonnen komplett statt sie zu beschneiden.
            const cls = 'ce-foto-fill' + (el.freistellen ? ' frei' : '') + (el.bild_passung === 'contain' ? ' einpassen' : '');
            return `<div class="${cls}" style="background-image:url('${ceCssUrl(el.bild)}'); filter:${el.filter || 'none'};"${readonly ? '' : ` ondblclick="ceFotoWaehlen(${el.id})"`}></div>`;
        }
        // Datengebundene Module (Name/Datum/Standort): Inhalt stammt aus den Profildaten,
        // NICHT aus frei eingegebenem Text -> eine einzige Wahrheit, Editor == Ansicht.
        if (el.typ === 'name' || el.typ === 'datum' || el.typ === 'standort') {
            const wert = ceDatenText(el, daten);
            const platzhalter = { name: 'Dein Name', datum: 'Dein Geburtsdatum', standort: 'Dein Standort' }[el.typ] || '';
            const inhalt = wert ? (escapeHtml(el.label || '') + escapeHtml(wert))
                                : (readonly ? '' : `<span style="opacity:.45">${platzhalter}</span>`);
            return `<div class="ce-text" style="${ceTextStyle(el)}">${inhalt}</div>`;
        }
        // Freitext-Module (bio/motto/text)
        const editHook = readonly ? '' : ` ondblclick="ceTextEdit(${el.id}, this)"`;
        return `<div class="ce-text" style="${ceTextStyle(el)}"${editHook}>${escapeHtml(el.text || '')}</div>`;
    }
    function ceChrome(el) {
        return `<div class="ce-el-tools">
                <button onclick="ceSelect(${el.id})" title="Attribute formen">⚙</button>
                <button onclick="ceElementLoeschen(${el.id})" title="Modul löschen">✕</button>
            </div><div class="ce-resize" onpointerdown="ceResizeStart(event, ${el.id})" title="Größe ziehen"></div>`;
    }

    // ---- Editor: Module hinzufügen / löschen / auswählen ----
    function ceElementHinzufuegen(typ, beiKlick) {
        const el = ceStandard(typ);
        if (typ === 'bio' && meinProfil.biografie) el.text = meinProfil.biografie;
        if (typ === 'foto') el.bild = meinProfil.profilbild || '';
        // Über das Bühnen-Kontextmenü hinzugefügt -> exakt am Klickpunkt platzieren (geklemmt).
        if (beiKlick && ceCtxNeuPos) {
            el.x = Math.max(0, Math.min(100 - el.w, ceCtxNeuPos.x));
            el.y = Math.max(0, Math.min(100 - el.h, ceCtxNeuPos.y));
        }
        canvasElemente.push(el);
        baueCanvas();
        ceSelect(el.id);
        if (typ === 'foto' && !el.bild) ceFotoWaehlen(el.id);
    }
    function ceElementLoeschen(id) {
        ceCtxSchliessen();
        canvasElemente = canvasElemente.filter(e => e.id !== id);
        if (ceSelektiert === id) ceSelektiert = null;
        baueCanvas();
    }
    // Sauberer Klon über den Serialisierer (inkl. Galerie-Bilder), leicht versetzt, mit neuer id.
    function ceElementDuplizieren(id) {
        const el = ceFindeEl(id); if (!el) return;
        const kopie = ceNorm(ceSerialisiere(el));
        kopie.x = Math.max(0, Math.min(100 - kopie.w, (el.x || 0) + 4));
        kopie.y = Math.max(0, Math.min(100 - kopie.h, (el.y || 0) + 4));
        canvasElemente.push(kopie);
        baueCanvas();
        ceSelect(kopie.id);
    }
    // Z-Reihenfolge = DOM-Reihenfolge: ans Array-Ende -> zuletzt gerendert -> liegt oben.
    function ceElementNachVorne(id) {
        const i = canvasElemente.findIndex(e => e.id === id); if (i < 0) return;
        const [el] = canvasElemente.splice(i, 1);
        canvasElemente.push(el);
        baueCanvas();
        ceSelect(id);
    }
    // Malermodus (Feature 2): Gegenstück – ans Array-ANFANG -> zuerst gerendert -> liegt hinten
    // (z. B. Sonne hinter das Gebirge legen). Ergänzt den expliziten Z-Index im Attribut-Panel.
    function ceElementNachHinten(id) {
        const i = canvasElemente.findIndex(e => e.id === id); if (i < 0) return;
        const [el] = canvasElemente.splice(i, 1);
        canvasElemente.unshift(el);
        baueCanvas();
        ceSelect(id);
    }
    function ceFotoWaehlen(id) {
        const inp = document.createElement('input'); inp.type = 'file'; inp.accept = 'image/*';
        inp.onchange = () => {
            const f = inp.files[0]; if (!f) return;
            const r = new FileReader();
            r.onload = e => {
                const el = ceFindeEl(id); if (!el) return;
                el.bild = e.target.result;
                if (!meinProfil.profilbild) { meinProfil.profilbild = e.target.result; profilNeuesBild = e.target.result; }
                baueCanvas();
            };
            r.readAsDataURL(f);
        };
        inp.click();
    }
    // Galerie-Bildverwaltung ENTKOPPELT -> eigener Galerie-Canvas (Schritt 2). Keine modul-
    // gebundenen ceGalerie*-Funktionen mehr im Profil-Canvas.

    // ---- Inline-Text (WYSIWYG, contenteditable) ----
    function ceTextEdit(id, node) {
        node.setAttribute('contenteditable', 'true');
        node.focus();
        const speichere = () => { const el = ceFindeEl(id); if (el) el.text = node.innerText; };
        node.oninput = speichere;
        node.onblur = () => { node.removeAttribute('contenteditable'); speichere(); };
    }

    // ---- Auswahl + Live-Update ohne kompletten Neuaufbau ----
    function ceSelect(id) {
        ceSelektiert = id;
        const cv = document.getElementById('ce-canvas');
        if (cv) cv.querySelectorAll('.ce-el').forEach(n => n.classList.toggle('ausgewaehlt', +n.dataset.id === id));
        ceBaueAttr();
    }
    function ceAktualisiereElement(id) {
        const el = ceFindeEl(id), cv = document.getElementById('ce-canvas'); if (!el || !cv) return;
        const node = cv.querySelector(`.ce-el[data-id="${id}"]`); if (!node) return;
        node.setAttribute('style', ceBoxStyle(el));
        node.innerHTML = ceInner(el, false, ceEditorDaten()) + ceChrome(el);
    }

    function baueCanvas() {
        const cv = document.getElementById('ce-canvas');
        if (!cv) return;
        cv.querySelectorAll('.ce-el').forEach(n => n.remove());
        canvasElemente.forEach(el => {
            const node = document.createElement('div');
            node.className = 'ce-el ce-el-' + el.typ + (el.id === ceSelektiert ? ' ausgewaehlt' : '');
            node.dataset.id = el.id;
            node.setAttribute('style', ceBoxStyle(el));
            node.innerHTML = ceInner(el, false, ceEditorDaten()) + ceChrome(el);
            node.addEventListener('pointerdown', e => ceDragStart(e, el.id));
            cv.appendChild(node);
        });
        ceBaueAttr();
    }

    // ---- Freies Ziehen (Position) & Skalieren (Dimension) in % · Maus-Events direkt am Modul ----
    // baueCanvas() hängt an jedes .ce-el ein 'mousedown' -> ceDragStart. Die %-Umrechnung im
    // globalen mousemove schreibt LIVE in das State-Objekt el (Referenz aus canvasElemente),
    // d. h. die geänderten Koordinaten stehen ohne Umweg für ceSerialisiere bereit.
    function ceDragStart(e, id) {
        if (e.button !== 0) return;                                                     // nur primärer Zeiger (linke Maustaste / erster Finger)
        if (e.target.closest('.ce-el-tools') || e.target.closest('.ce-resize')) return;
        if (e.target.getAttribute && e.target.getAttribute('contenteditable') === 'true') return;  // Textbearbeitung ≠ Drag
        const cv = document.getElementById('ce-canvas');
        const el = ceFindeEl(id); if (!el || !cv) return;
        ceSelect(id);
        ceCtxSchliessen();                                                              // Menü schließt beim Greifen
        const rect = cv.getBoundingClientRect();
        ceAktion = {
            modus: 'drag', id, bewegt: false, downX: e.clientX, downY: e.clientY,
            offx: e.clientX - (rect.left + rect.width * el.x / 100),
            offy: e.clientY - (rect.top + rect.height * el.y / 100),
        };
        try { e.currentTarget.setPointerCapture(e.pointerId); } catch (_) {}            // Maus/Touch/Pen: Zeiger festhalten
        e.preventDefault();                                                             // keine Textauswahl / kein Touch-Scroll beim Ziehen
    }
    function ceResizeStart(e, id) {
        e.stopPropagation(); e.preventDefault();
        const cv = document.getElementById('ce-canvas');
        const el = ceFindeEl(id); if (!el || !cv) return;
        ceSelect(id); ceCtxSchliessen();
        ceAktion = { modus: 'resize', id, bewegt: true, startX: e.clientX, startY: e.clientY, startW: el.w, startH: el.h };
        try { e.target.setPointerCapture(e.pointerId); } catch (_) {}                   // Zeiger auch beim Skalieren festhalten
    }
    document.addEventListener('pointermove', e => {
        if (!ceAktion) return;
        const cv = document.getElementById('ce-canvas'); if (!cv) return;
        const rect = cv.getBoundingClientRect();
        const el = ceFindeEl(ceAktion.id); if (!el) return;
        // Erst ab ~3px Bewegung als echtes Ziehen werten -> ein reiner Klick öffnet stattdessen das Menü.
        if (!ceAktion.bewegt && ceAktion.modus === 'drag' &&
            Math.abs(e.clientX - ceAktion.downX) + Math.abs(e.clientY - ceAktion.downY) < 3) return;
        ceAktion.bewegt = true;
        if (ceAktion.modus === 'drag') {
            el.x = Math.max(0, Math.min(100 - el.w, ((e.clientX - ceAktion.offx - rect.left) / rect.width) * 100));
            el.y = Math.max(0, Math.min(100 - el.h, ((e.clientY - ceAktion.offy - rect.top) / rect.height) * 100));
        } else {
            el.w = Math.max(3, Math.min(100 - el.x, ceAktion.startW + ((e.clientX - ceAktion.startX) / rect.width) * 100));
            el.h = Math.max(3, Math.min(100 - el.y, ceAktion.startH + ((e.clientY - ceAktion.startY) / rect.height) * 100));
        }
        const node = cv.querySelector(`.ce-el[data-id="${ceAktion.id}"]`);
        if (node) node.setAttribute('style', ceBoxStyle(el));
        ceSyncMasze(el);
    });
    document.addEventListener('pointerup', e => {
        if (!ceAktion) return;
        const war = ceAktion; ceAktion = null;
        // Reiner Klick/Tap (kein Ziehen -> unter Schwellenwert geblieben) auf ein Modul
        // -> schwebendes Kontextmenü an seiner Position. Gilt für Maus UND Touch/Pen.
        if (war.modus === 'drag' && !war.bewegt) ceCtxFuerElement(war.id, e.clientX, e.clientY);
    });

    // =====================================================================
    // SCHWEBENDES KONTEXTMENÜ (ersetzt die starre obere Formularleiste)
    //  · Klick auf ein Modul   -> Modul-Aktionen, am Modul verankert.
    //  · Klick auf leere Bühne -> "Modul hinzufügen"-Liste am Klickpunkt.
    // =====================================================================
    function ceCtxSchliessen() { const m = document.getElementById('ce-ctx'); if (m) m.classList.remove('auf'); }
    function ceCtxPositionieren(clientX, clientY) {
        const m = document.getElementById('ce-ctx'), wrap = document.getElementById('canvas-editor');
        if (!m || !wrap) return;
        const r = wrap.getBoundingClientRect();
        m.classList.add('auf');                                     // erst einblenden, dann Maße messen
        let x = clientX - r.left, y = clientY - r.top;
        x = Math.min(x, r.width  - m.offsetWidth  - 8);
        y = Math.min(y, r.height - m.offsetHeight - 8);
        m.style.left = Math.max(8, x) + 'px';
        m.style.top  = Math.max(8, y) + 'px';
    }
    function ceCtxFuerElement(id, clientX, clientY) {
        const el = ceFindeEl(id), m = document.getElementById('ce-ctx'); if (!el || !m) return;
        ceSelect(id);
        const istFreitext = (el.typ === 'bio' || el.typ === 'motto' || el.typ === 'text');
        let h = `<div class="ce-ctx-titel">${CE_TITEL[el.typ] || 'Modul'}</div>`;
        if (istFreitext)          h += `<button onclick="ceCtxSchliessen();ceTextViaPanel(${id})">✎ Text bearbeiten</button>`;
        if (el.typ === 'foto')    h += `<button onclick="ceCtxSchliessen();ceFotoWaehlen(${id})">🖼️ Bild wählen</button>`;
        h += `<button onclick="ceCtxSchliessen();ceSelect(${id})">⚙ Attribute formen</button>`;
        h += `<button onclick="ceCtxSchliessen();ceElementNachVorne(${id})">⬆️ Nach vorne holen</button>`;
        h += `<button onclick="ceCtxSchliessen();ceElementNachHinten(${id})">⬇️ Nach hinten legen</button>`;
        h += `<button onclick="ceCtxSchliessen();ceElementDuplizieren(${id})">⧉ Duplizieren</button>`;
        h += `<button class="gefahr" onclick="ceCtxSchliessen();ceElementLoeschen(${id})">🗑️ Modul löschen</button>`;
        m.innerHTML = h;
        // Bevorzugt an der unteren linken Ecke des Moduls verankern, sonst am Klickpunkt.
        const node = document.querySelector(`#ce-canvas .ce-el[data-id="${id}"]`);
        if (node) { const b = node.getBoundingClientRect(); ceCtxPositionieren(b.left, b.bottom + 6); }
        else ceCtxPositionieren(clientX, clientY);
    }
    function ceCtxFuerCanvas(clientX, clientY) {
        const m = document.getElementById('ce-ctx'), cv = document.getElementById('ce-canvas'); if (!m || !cv) return;
        ceSelect(null);
        const rect = cv.getBoundingClientRect();
        // Klickpunkt als Start-Position (%) für das neue Modul merken.
        ceCtxNeuPos = {
            x: Math.max(0, Math.min(92, ((clientX - rect.left) / rect.width) * 100)),
            y: Math.max(0, Math.min(88, ((clientY - rect.top) / rect.height) * 100)),
        };
        const knopf = t => `<button onclick="ceCtxSchliessen();ceElementHinzufuegen('${t}',true)">＋ ${CE_TITEL[t] || t}</button>`;
        m.innerHTML = `<div class="ce-ctx-titel">Modul hinzufügen</div>` +
            ['foto','name','datum','standort','bio','motto','text'].map(knopf).join('');
        ceCtxPositionieren(clientX, clientY);
    }
    // Klick auf die leere Bühne öffnet das Hinzufügen-Menü; Esc schließt jedes Menü.
    // Bindung auf document (immer vorhanden) statt auf #ce-canvas -> unabhängig von der Script-Position.
    document.addEventListener('pointerdown', e => {
        if (e.button !== 0) return;
        if (e.target.closest('#ce-canvas') && !e.target.closest('.ce-el')) ceCtxFuerCanvas(e.clientX, e.clientY);
    });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') ceCtxSchliessen(); });

    // ---- WYSIWYG-Attributpanel (live) ----
    const CE_TITEL = { bio: 'Biografie-Modul', motto: 'Motto-Modul', text: 'Text-Modul', foto: 'Foto-Modul', name: 'Name-Modul', datum: 'Geburtsdatum-Modul', standort: 'Standort-Modul' };
    function ceAttr(id, feld, wert) {
        const el = ceFindeEl(id); if (!el) return;
        if (['x','y','w','h','groesse','zeilenabstand','radius','rahmen_breite','polster','luecke','spalten','z'].includes(feld)) wert = parseFloat(wert);
        el[feld] = wert;
        ceAktualisiereElement(id);
    }
    function ceAttrToggle(id, feld, wert) { const el = ceFindeEl(id); if (!el) return; el[feld] = wert; ceAktualisiereElement(id); ceBaueAttr(); }
    function ceSyncMasze(el) {
        [['x',el.x],['y',el.y],['w',el.w],['h',el.h]].forEach(([f,v]) => {
            const inp = document.getElementById('attr-' + f), lab = document.getElementById('attrlab-' + f);
            if (inp) inp.value = Math.round(v);
            if (lab) lab.textContent = Math.round(v) + '%';
        });
    }
    function ceSchieber(id, feld, label, val, min, max, step, einheit) {
        const v = (val != null) ? val : 0;
        return `<div class="ce-attr-feld">
            <label>${label}<span id="attrlab-${feld}">${(Math.round(v*100)/100)}${einheit||''}</span></label>
            <input type="range" id="attr-${feld}" min="${min}" max="${max}" step="${step}" value="${v}"
                oninput="document.getElementById('attrlab-${feld}').textContent=(Math.round(this.value*100)/100)+'${einheit||''}'; ceAttr(${id},'${feld}',this.value)">
        </div>`;
    }
    function ceFarbFeld(id, feld, label, val, mitTransparent) {
        const leer = !val;
        return `<div class="ce-attr-feld">
            <label>${label}</label>
            <input type="color" value="${leer ? '#0c1a2e' : val}" oninput="ceAttr(${id},'${feld}',this.value)">
            ${mitTransparent ? `<button class="ce-attr-btn" onclick="ceAttr(${id},'${feld}','')">Transparent</button>` : ''}
        </div>`;
    }
    function ceBaueAttr() {
        const box = document.getElementById('ce-attr'); if (!box) return;
        const el = ceFindeEl(ceSelektiert);
        if (!el) {
            box.innerHTML = `<div class="ce-attr-leer">Wähle ein Modul (Klick), um es frei zu formen: Position, Größe, Schrift, Zeilenabstand, Rahmen-Radius, Farben und Box.<br><br>Neue Module fügst du oben über die <b>＋</b>-Knöpfe hinzu.</div>`;
            return;
        }
        let h = `<div class="ce-attr-titel">${CE_TITEL[el.typ] || 'Modul'}</div>`;
        // Position + Dimension (für JEDES Modul)
        h += `<div class="ce-attr-row">${ceSchieber(el.id,'x','Position X',el.x,0,100,1,'%')}${ceSchieber(el.id,'y','Position Y',el.y,0,100,1,'%')}</div>`;
        h += `<div class="ce-attr-row">${ceSchieber(el.id,'w','Breite',el.w,3,100,1,'%')}${ceSchieber(el.id,'h','Höhe',el.h,3,100,1,'%')}</div>`;
        // Text-Attribute – gelten für Freitext (bio/motto/text) UND datengebundene Module (name/datum/standort)
        const istFreitext = (el.typ === 'bio' || el.typ === 'motto' || el.typ === 'text');
        const istDaten = (el.typ === 'name' || el.typ === 'datum' || el.typ === 'standort');
        if (istFreitext || istDaten) {
            h += ceSchieber(el.id,'groesse','Schriftgröße',el.groesse,0.4,6,0.05,'rem');
            h += ceSchieber(el.id,'zeilenabstand','Zeilenabstand',el.zeilenabstand,0.8,3,0.05,'');
            h += ceFarbFeld(el.id,'farbe','Textfarbe',el.farbe||'#ffffff',false);
            const al = el.ausrichtung||'links';
            h += `<div class="ce-attr-feld"><label>Ausrichtung</label><div class="ce-attr-toggle">
                <button class="${al==='links'?'an':''}" onclick="ceAttrToggle(${el.id},'ausrichtung','links')">Links</button>
                <button class="${al==='zentriert'?'an':''}" onclick="ceAttrToggle(${el.id},'ausrichtung','zentriert')">Mitte</button>
                <button class="${al==='rechts'?'an':''}" onclick="ceAttrToggle(${el.id},'ausrichtung','rechts')">Rechts</button></div></div>`;
            h += `<div class="ce-attr-feld"><label>Schriftstärke</label><div class="ce-attr-toggle">
                <button class="${!el.fett?'an':''}" onclick="ceAttrToggle(${el.id},'fett',false)">Normal</button>
                <button class="${el.fett?'an':''}" onclick="ceAttrToggle(${el.id},'fett',true)">Fett</button></div></div>`;
            if (istFreitext) h += `<button class="ce-attr-btn" onclick="ceTextViaPanel(${el.id})">✎ Text bearbeiten</button>`;
            if (istDaten) {
                const quelle = { name:'Vor- und Nachname', datum:'Geburtsdatum', standort:'Stadt & Land' }[el.typ];
                h += `<div class="ce-attr-feld"><label>Beschriftung (Präfix)</label>
                    <input type="text" value="${escapeHtml(el.label||'')}" oninput="ceAttr(${el.id},'label',this.value)" placeholder="z. B. Geboren am "></div>`;
                h += `<div class="ce-attr-leer">Inhalt stammt automatisch aus deinen Profildaten (<b>${quelle}</b>) – pflege den Wert im Werkzeug-Dock oben. Editor- und Besucheransicht bleiben dadurch identisch.</div>`;
            }
        }
        // Foto-Attribute
        if (el.typ === 'foto') {
            h += `<button class="ce-attr-btn" onclick="ceFotoWaehlen(${el.id})">🖼️ Bild wählen</button>`;
            h += ceFilterSelect(el);
            // Malermodus (Feature 3): Freistellen (transparente Box) + Bild-Passung (Füllen/Einpassen).
            h += `<div class="ce-attr-feld"><label>Freistellen (transparent)</label><div class="ce-attr-toggle">
                <button class="${!el.freistellen?'an':''}" onclick="ceAttrToggle(${el.id},'freistellen',false)">Box sichtbar</button>
                <button class="${el.freistellen?'an':''}" onclick="ceAttrToggle(${el.id},'freistellen',true)">Freigestellt</button></div></div>`;
            const pas = el.bild_passung || 'cover';
            h += `<div class="ce-attr-feld"><label>Bild-Passung</label><div class="ce-attr-toggle">
                <button class="${pas!=='contain'?'an':''}" onclick="ceAttrToggle(${el.id},'bild_passung','cover')">Füllen</button>
                <button class="${pas==='contain'?'an':''}" onclick="ceAttrToggle(${el.id},'bild_passung','contain')">Einpassen</button></div></div>`;
        }
        // Malermodus (Feature 2): Z-Index für Bild-im-Bild-Tiefe (für JEDES Modul).
        h += ceSchieber(el.id,'z','Ebene (Z-Index)',el.z||0,0,999,1,'');
        h += `<div class="ce-attr-row">
            <button class="ce-attr-btn" onclick="ceElementNachHinten(${el.id})">⬇️ Nach hinten</button>
            <button class="ce-attr-btn" onclick="ceElementNachVorne(${el.id})">⬆️ Nach vorne</button></div>`;
        // Malermodus (Feature 3): rahmenloser Kreis-Modus (für JEDES Modul) – hartes Viereck verschwindet.
        h += `<div class="ce-attr-feld"><label>Maske / Form</label><div class="ce-attr-toggle">
            <button class="${el.maske!=='kreis'?'an':''}" onclick="ceAttrToggle(${el.id},'maske','')">Rechteck</button>
            <button class="${el.maske==='kreis'?'an':''}" onclick="ceAttrToggle(${el.id},'maske','kreis')">Kreis</button></div></div>`;
        // Box-Attribute (für JEDES Modul)
        h += ceSchieber(el.id,'radius','Rahmen-Radius',el.radius,0,200,1,'px');
        h += ceSchieber(el.id,'polster','Innenabstand',el.polster,0,80,1,'px');
        h += ceSchieber(el.id,'rahmen_breite','Rahmenstärke',el.rahmen_breite,0,40,1,'px');
        h += ceFarbFeld(el.id,'rahmen_farbe','Rahmenfarbe',el.rahmen_farbe||'#ffd700',false);
        h += ceFarbFeld(el.id,'bg_farbe','Box-Hintergrund',el.bg_farbe,true);
        h += `<button class="ce-attr-btn" style="background:var(--rot); border-color:var(--rot); color:#fff;" onclick="ceElementLoeschen(${el.id})">Modul löschen</button>`;
        box.innerHTML = h;
    }
    function ceFilterSelect(el) {
        const opts = PROFIL_FILTER.map(f => `<option value="${f}" ${el.filter===f?'selected':''}>${f||'kein Filter'}</option>`).join('');
        return `<div class="ce-attr-feld"><label>Bildfilter</label><select onchange="ceAttr(${el.id},'filter',this.value)">${opts}</select></div>`;
    }
    function ceTextViaPanel(id) {
        const el = ceFindeEl(id); if (!el) return;
        const neu = prompt('Text bearbeiten (oder Doppelklick direkt im Canvas):', el.text || '');
        if (neu !== null) { el.text = neu; ceAktualisiereElement(id); }
    }

    async function speichereProfil() {
        profilLand = (document.getElementById('ce-land')||{}).value || "";
        profilStadt = (document.getElementById('ce-stadt')||{}).value || "";
        profilGeburtsdatum = (document.getElementById('ce-geburtsdatum')||{}).value || profilGeburtsdatum;
        const bioEl = canvasElemente.find(e => e.typ === 'bio');
        const bioText = bioEl ? (bioEl.text||"") : meinProfil.biografie;
        profilMsg("Speichere …", true);
        const canvas = {
            hintergrund_url: canvasBgUrl, hintergrund_farbe: canvasBgFarbe,
            // Malermodus (Feature 1): Hintergrund-Offset/Skalierung verlustsicher mitspeichern.
            hintergrund_pos_x: canvasBgPosX, hintergrund_pos_y: canvasBgPosY, hintergrund_skala: canvasBgSkala,
            farbschema: profilSchema, rahmen: canvasRahmen,
            elemente: canvasElemente.map(ceSerialisiere),
        };
        const payload = {
            email: userEmail,
            vorname: (meinProfil.vorname||"").trim(), nachname: (meinProfil.nachname||"").trim(),
            biografie: bioText, geburtsdatum: profilGeburtsdatum,
            galerie: profilGalerie, sichtbarkeit: profilSichtbarkeit, farbschema: profilSchema,
            land: profilLand, stadt: profilStadt, canvas,
            galerie_seite: galerieSeite,   // entkoppelte Galerie verlustsicher mitspeichern
        };
        if (profilNeuesBild !== null) payload.profilbild = profilNeuesBild;
        try {
            const res = await fetch('/auth/profil-update', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
            const d = await res.json();
            if (d.success) {
                meinProfil.biografie = d.biografie;
                if (profilNeuesBild !== null) { meinProfil.profilbild = d.profilbild; profilNeuesBild = null; }
                if (typeof d.geburtsdatum === 'string') profilGeburtsdatum = d.geburtsdatum;
                setzeHeaderAvatar();
                profilMsg("Profil-Canvas gespeichert.", true);
                ladeMeineRolle();   // ggf. jetzt automatisch verifiziert
            } else profilMsg(d.message || "Speichern fehlgeschlagen.");
        } catch (e) { profilMsg("Server-Verbindung fehlgeschlagen."); }
    }
    // Serialisiert ein Modul als vollständiges, sauberes JSON-Paket (ohne interne id).
    function ceSerialisiere(e) {
        const o = {
            typ: e.typ, x: e.x, y: e.y, w: e.w, h: e.h,
            text: e.text || '', label: e.label || '', bild: e.bild || '', farbe: e.farbe || '', groesse: e.groesse || 1,
            zeilenabstand: e.zeilenabstand || 1.35, ausrichtung: e.ausrichtung || 'links', fett: !!e.fett,
            radius: e.radius || 0, bg_farbe: e.bg_farbe || '', rahmen_farbe: e.rahmen_farbe || '',
            rahmen_breite: e.rahmen_breite || 0, polster: e.polster || 0, filter: e.filter || '',
            // Malermodus: Z-Index (Feature 2) + Maske/Freistellung/Passung (Feature 3).
            z: e.z || 0, maske: e.maske || '', freistellen: !!e.freistellen, bild_passung: e.bild_passung || 'cover',
        };
        return o;
    }

    // ---- Read-only-Ansicht eines fremden Canvas-Profils: rendert GENAU dieselben Module ----
    function rendereCanvasAnsicht(d) {
        const c = d.canvas || {};
        const schema = PROFIL_SCHEMATA[c.farbschema] || PROFIL_SCHEMATA.nachtblau;
        // Malermodus (Feature 1): identischer Hintergrund-Helfer wie im Editor -> Offset/Skalierung 1:1 sichtbar.
        const bgStil = ceHintergrundStr(c.hintergrund_url, c.hintergrund_farbe, schema, c.hintergrund_pos_x, c.hintergrund_pos_y, c.hintergrund_skala);
        const rahmen = { gold:'3px solid #ffd700', doppelt:'6px double #ffd700', neon:'2px solid #00ffcc' }[c.rahmen] || `1px solid ${schema.rand}`;
        // Entkoppelt: etwaige Alt-Galerie-Module ignorieren (leben jetzt in galerie_seite).
        let roh = (c.elemente || []).filter(r => r && r.typ !== 'galerie');
        if (!roh.length) {
            // Fallback nur, wenn der Nutzer NIE etwas gestaltet hat – IDENTISCH zum Editor-Start.
            roh = ceStartKomposition({ bild: d.profilbild || '', biografie: d.biografie || '' });
        }
        // Datenkontext des ZIELPROFILS -> datengebundene Module (Name/Datum/Standort) rendern exakt
        // wie im Editor, an exakt der gestalteten Position. Kein festes Kopf-Layout mehr.
        const daten = { name: d.name || '', geburtsdatum: d.geburtsdatum || '', land: d.land || '', stadt: d.stadt || '' };
        const els = roh.map(r => {
            const el = ceNorm(r);
            return `<div class="ce-el ce-el-${el.typ}" style="${ceBoxStyle(el)}">${ceInner(el, true, daten)}</div>`;
        }).join('');
        return `<div class="ce-canvas fp-canvas" style="${bgStil} border:${rahmen};">${els}</div>`;
    }

    // ---- Read-only Galerie-Ansicht für Besucher: rendert GENAU die im Galerie-Editor gestalteten Module ----
    function rendereGalerieAnsicht(d) {
        const gs = (d && d.galerie_seite && typeof d.galerie_seite === 'object') ? d.galerie_seite : {};
        const schema = PROFIL_SCHEMATA[gs.farbschema] || PROFIL_SCHEMATA.nachtblau;
        // Malermodus (Feature 1): identischer Hintergrund-Helfer wie im Galerie-Editor -> Offset/Skalierung 1:1.
        const bgStil = ceHintergrundStr(gs.hintergrund_url, gs.hintergrund_farbe, schema, gs.hintergrund_pos_x, gs.hintergrund_pos_y, gs.hintergrund_skala);
        const rahmen = { gold:'3px solid #ffd700', doppelt:'6px double #ffd700', neon:'2px solid #00ffcc' }[gs.rahmen] || `1px solid ${schema.rand}`;
        const elemente = Array.isArray(gs.elemente) ? gs.elemente : [];
        if (elemente.length) {
            // Editor ↔ Ansicht identisch: dieselbe Box-Mathematik (ceBoxStyle) + geInner, read-only.
            const els = elemente.map(r => { const el = geNorm(r); return `<div class="ce-el ce-el-${el.typ}" style="${ceBoxStyle(el)}">${geInner(el, true)}</div>`; }).join('');
            return `<div class="ce-canvas fp-canvas" style="${bgStil} border:${rahmen};">${els}</div>`;
        }
        // Fallback: schlichtes Grid aus dem Bild-Pool, falls noch kein Galerie-Canvas gestaltet wurde.
        const bilder = Array.isArray(gs.bilder) ? gs.bilder : [];
        const kacheln = bilder.map(b => {
            const url = ceCssUrl(b && b.url); if (!url) return '';
            const titel = escapeHtml((b && b.titel) || ''); const filter = (b && b.filter) || 'none';
            return `<figure class="ga-kachel"><div class="ga-bild" style="background-image:url('${url}'); filter:${filter};"></div>${titel ? `<figcaption class="ga-titel">${titel}</figcaption>` : ''}</figure>`;
        }).join('');
        const leer = kacheln ? '' : `<p style="grid-column:1/-1; color:#cfe0ff; text-align:center; padding:40px;">Diese Galerie ist noch leer.</p>`;
        return `<div class="ce-canvas fp-canvas ga-ansicht" style="${bgStil} border:${rahmen};"><div class="ga-grid">${kacheln}${leer}</div></div>`;
    }

    // =====================================================================
    // PROFIL-HUB + DESIGN-VORSCHAU (Einstieg: Profil / Galerie / Vorschau)
    // =====================================================================
    function oeffneProfilHub() { document.getElementById('profil-hub-overlay').classList.add('aktiv'); }
    function schliesseProfilHub() { document.getElementById('profil-hub-overlay').classList.remove('aktiv'); }
    function hubOeffne(was) {
        schliesseProfilHub();
        if (was === 'profil') oeffneProfil();
        else if (was === 'galerie') oeffneGalerieEditor();
        else if (was === 'vorschau') oeffneDesignVorschau();
    }
    // Eigenes Profil read-only ansehen – exakt wie ein Besucher (inkl. Zwei-Button-Umschalter).
    async function oeffneDesignVorschau() {
        const ov = document.getElementById('fremdprofil-overlay'), inhalt = document.getElementById('fremdprofil-inhalt');
        inhalt.innerHTML = `<p style="color:#fff; padding:30px; text-align:center;">Lade Vorschau …</p>`;
        ov.classList.add('aktiv');
        try {
            const res = await fetch(`/auth/profil-daten?email=${encodeURIComponent(userEmail)}`);
            const p = await res.json();
            fremdprofilDaten = {
                canvas: p.canvas || {}, galerie_seite: p.galerie_seite || {},
                name: `${(p.vorname||'').trim()} ${(p.nachname||'').trim()}`.trim(),
                geburtsdatum: p.geburtsdatum || '', land: p.land || '', stadt: p.stadt || '',
                profilbild: p.profilbild || '', biografie: p.biografie || '',
            };
            inhalt.innerHTML = fpUmschalter('profil') + rendereCanvasAnsicht(fremdprofilDaten);
        } catch (e) { inhalt.innerHTML = `<p style="color:#ff9b9b; padding:30px;">Fehler beim Laden.</p>`; }
    }

    // =====================================================================
    // GALERIE-CANVAS-ENGINE (ge*): vollständig isoliert vom Profil-Canvas.
    // Eigener State, eigenes DOM (#ge-canvas/#ge-attr/#ge-ctx), eigene Handler.
    // Wiederverwendet NUR zustandslose Helfer (ceBoxStyle/ceTextStyle/ceCssUrl).
    // Modell = galerie_seite.elemente[]  ·  Modultypen: 'bild' (+ optional 'text').
    // =====================================================================
    let geElemente = [];
    let geSelektiert = null, geAktion = null, geElementSeq = 1, geCtxNeuPos = null;
    let geBgUrl = '', geBgFarbe = '#0c1a2e', geRahmen = '', geSchema = 'nachtblau';
    // Malermodus (Feature 1): Galerie-Hintergrund-Verschiebung/Skalierung (50/50/100 == altes center/cover).
    let geBgPosX = 50, geBgPosY = 50, geBgSkala = 100;
    const GE_TITEL = { bild: 'Bild-Modul', text: 'Text-Modul' };
    const GE_PRESETS = {
        '2x2':  [ {x:4,y:4,w:45,h:44},{x:51,y:4,w:45,h:44},{x:4,y:52,w:45,h:44},{x:51,y:52,w:45,h:44} ],
        '3er':  [ {x:3,y:20,w:30.6,h:60},{x:34.7,y:20,w:30.6,h:60},{x:66.4,y:20,w:30.6,h:60} ],
        'hero': [ {x:4,y:4,w:92,h:52},{x:4,y:58,w:29.3,h:38},{x:35.3,y:58,w:29.3,h:38},{x:66.6,y:58,w:29.4,h:38} ],
    };

    function geStandard(typ) {
        typ = (typ === 'text') ? 'text' : 'bild';
        const el = { id: geElementSeq++, typ, x: 30, y: 26, w: 30, h: 34,
            radius: 10, bg_farbe: '', rahmen_farbe: '', rahmen_breite: 0, polster: 0,
            bild: '', filter: '', titel: '',
            farbe: '#ffffff', groesse: 1, ausrichtung: 'zentriert', fett: false, zeilenabstand: 1.3, text: '',
            // Malermodus: Z-Index (Feature 2) + Kreis-Maske/Freistellung/Passung (Feature 3).
            z: 0, maske: '', freistellen: false, bild_passung: 'cover' };
        if (typ === 'text') { el.text = 'Beschriftung …'; el.w = 40; el.h = 8; el.polster = 6; el.groesse = 1.1; }
        return el;
    }
    function geNorm(raw) {
        const t = (raw && raw.typ === 'text') ? 'text' : 'bild';
        const el = Object.assign(geStandard(t), raw, { id: geElementSeq++, typ: t });
        if (typeof el.h !== 'number' || !el.h) el.h = 30;
        return el;
    }
    function geFindeEl(id) { return geElemente.find(e => e.id === id); }
    function geSerialisiere(e) {
        return { typ: e.typ, x: e.x, y: e.y, w: e.w, h: e.h,
            bild: e.bild || '', filter: e.filter || '', titel: e.titel || '', text: e.text || '',
            farbe: e.farbe || '', groesse: e.groesse || 1, ausrichtung: e.ausrichtung || 'zentriert',
            fett: !!e.fett, zeilenabstand: e.zeilenabstand || 1.3,
            radius: e.radius || 0, bg_farbe: e.bg_farbe || '', rahmen_farbe: e.rahmen_farbe || '',
            rahmen_breite: e.rahmen_breite || 0, polster: e.polster || 0,
            // Malermodus: Z-Index (Feature 2) + Maske/Freistellung/Passung (Feature 3).
            z: e.z || 0, maske: e.maske || '', freistellen: !!e.freistellen, bild_passung: e.bild_passung || 'cover' };
    }
    // Innerer Modul-Inhalt (readonly=true -> keine Editier-Hooks, für die Besucheransicht).
    function geInner(el, readonly) {
        if (el.typ === 'text') {
            const editHook = readonly ? '' : ` ondblclick="geTextEdit(${el.id}, this)"`;
            return `<div class="ce-text" style="${ceTextStyle(el)}"${editHook}>${escapeHtml(el.text || '')}</div>`;
        }
        const dbl = readonly ? '' : ` ondblclick="geBildWaehlen(${el.id})"`;
        const titel = el.titel ? `<figcaption class="ge-cap" style="color:${el.farbe || '#fff'};">${escapeHtml(el.titel)}</figcaption>` : '';
        // Malermodus (Feature 3): Freistellen (transparent) + Einpassen (contain) – identisch zum Profil-Canvas.
        const cls = 'ce-foto-fill' + (el.freistellen ? ' frei' : '') + (el.bild_passung === 'contain' ? ' einpassen' : '');
        return `<div class="${cls}"${dbl} style="background-image:url('${ceCssUrl(el.bild)}'); filter:${el.filter || 'none'};"></div>${titel}`;
    }
    function geChrome(el) {
        return `<div class="ce-el-tools">
                <button onclick="geSelect(${el.id})" title="Attribute formen">⚙</button>
                <button onclick="geElementLoeschen(${el.id})" title="Modul löschen">✕</button>
            </div><div class="ce-resize" onpointerdown="geResizeStart(event, ${el.id})" title="Größe ziehen"></div>`;
    }
    function baueGalerieCanvas() {
        const cv = document.getElementById('ge-canvas'); if (!cv) return;
        cv.querySelectorAll('.ce-el').forEach(n => n.remove());
        geElemente.forEach(el => {
            const node = document.createElement('div');
            node.className = 'ce-el ce-el-' + el.typ + (el.id === geSelektiert ? ' ausgewaehlt' : '');
            node.dataset.id = el.id;
            node.setAttribute('style', ceBoxStyle(el));
            node.innerHTML = geInner(el, false) + geChrome(el);
            node.addEventListener('pointerdown', e => geDragStart(e, el.id));
            cv.appendChild(node);
        });
        geBaueAttr();
    }
    function geSelect(id) {
        geSelektiert = id;
        const cv = document.getElementById('ge-canvas');
        if (cv) cv.querySelectorAll('.ce-el').forEach(n => n.classList.toggle('ausgewaehlt', +n.dataset.id === id));
        geBaueAttr();
    }
    function geAktualisiereElement(id) {
        const el = geFindeEl(id), cv = document.getElementById('ge-canvas'); if (!el || !cv) return;
        const node = cv.querySelector(`.ce-el[data-id="${id}"]`); if (!node) return;
        node.setAttribute('style', ceBoxStyle(el));
        node.innerHTML = geInner(el, false) + geChrome(el);
    }
    function geTextEdit(id, node) {
        node.setAttribute('contenteditable', 'true'); node.focus();
        const speichere = () => { const el = geFindeEl(id); if (el) el.text = node.innerText; };
        node.oninput = speichere;
        node.onblur = () => { node.removeAttribute('contenteditable'); speichere(); };
    }

    // ---- Ziehen/Skalieren in % · eigener geAktion-State, #ge-canvas-scoped (Pointer = Maus+Touch+Pen) ----
    function geDragStart(e, id) {
        if (e.button !== 0) return;
        if (e.target.closest('.ce-el-tools') || e.target.closest('.ce-resize')) return;
        if (e.target.getAttribute && e.target.getAttribute('contenteditable') === 'true') return;
        const cv = document.getElementById('ge-canvas'); const el = geFindeEl(id); if (!el || !cv) return;
        geSelect(id); geCtxSchliessen();
        const rect = cv.getBoundingClientRect();
        geAktion = { modus: 'drag', id, bewegt: false, downX: e.clientX, downY: e.clientY,
            offx: e.clientX - (rect.left + rect.width * el.x / 100),
            offy: e.clientY - (rect.top + rect.height * el.y / 100) };
        try { e.currentTarget.setPointerCapture(e.pointerId); } catch (_) {}
        e.preventDefault();
    }
    function geResizeStart(e, id) {
        e.stopPropagation(); e.preventDefault();
        const cv = document.getElementById('ge-canvas'); const el = geFindeEl(id); if (!el || !cv) return;
        geSelect(id); geCtxSchliessen();
        geAktion = { modus: 'resize', id, bewegt: true, startX: e.clientX, startY: e.clientY, startW: el.w, startH: el.h };
        try { e.target.setPointerCapture(e.pointerId); } catch (_) {}
    }
    document.addEventListener('pointermove', e => {
        if (!geAktion) return;
        const cv = document.getElementById('ge-canvas'); if (!cv) return;
        const rect = cv.getBoundingClientRect(); const el = geFindeEl(geAktion.id); if (!el) return;
        if (!geAktion.bewegt && geAktion.modus === 'drag' &&
            Math.abs(e.clientX - geAktion.downX) + Math.abs(e.clientY - geAktion.downY) < 3) return;
        geAktion.bewegt = true;
        if (geAktion.modus === 'drag') {
            el.x = Math.max(0, Math.min(100 - el.w, ((e.clientX - geAktion.offx - rect.left) / rect.width) * 100));
            el.y = Math.max(0, Math.min(100 - el.h, ((e.clientY - geAktion.offy - rect.top) / rect.height) * 100));
        } else {
            el.w = Math.max(3, Math.min(100 - el.x, geAktion.startW + ((e.clientX - geAktion.startX) / rect.width) * 100));
            el.h = Math.max(3, Math.min(100 - el.y, geAktion.startH + ((e.clientY - geAktion.startY) / rect.height) * 100));
        }
        const node = cv.querySelector(`.ce-el[data-id="${geAktion.id}"]`);
        if (node) node.setAttribute('style', ceBoxStyle(el));
        geSyncMasze(el);
    });
    document.addEventListener('pointerup', e => {
        if (!geAktion) return;
        const war = geAktion; geAktion = null;
        if (war.modus === 'drag' && !war.bewegt) geCtxFuerElement(war.id, e.clientX, e.clientY);
    });

    // ---- Galerie-Kontextmenü (#ge-ctx, verankert an #galerie-editor) ----
    function geCtxSchliessen() { const m = document.getElementById('ge-ctx'); if (m) m.classList.remove('auf'); }
    function geCtxPositionieren(clientX, clientY) {
        const m = document.getElementById('ge-ctx'), wrap = document.getElementById('galerie-editor'); if (!m || !wrap) return;
        const r = wrap.getBoundingClientRect(); m.classList.add('auf');
        let x = clientX - r.left, y = clientY - r.top;
        x = Math.min(x, r.width - m.offsetWidth - 8); y = Math.min(y, r.height - m.offsetHeight - 8);
        m.style.left = Math.max(8, x) + 'px'; m.style.top = Math.max(8, y) + 'px';
    }
    function geCtxFuerElement(id, clientX, clientY) {
        const el = geFindeEl(id), m = document.getElementById('ge-ctx'); if (!el || !m) return;
        geSelect(id);
        let h = `<div class="ce-ctx-titel">${GE_TITEL[el.typ] || 'Modul'}</div>`;
        if (el.typ === 'bild') h += `<button onclick="geCtxSchliessen();geBildWaehlen(${id})">🖼️ Bild wählen</button>`;
        if (el.typ === 'text') h += `<button onclick="geCtxSchliessen();geTextViaPanel(${id})">✎ Text bearbeiten</button>`;
        h += `<button onclick="geCtxSchliessen();geSelect(${id})">⚙ Attribute formen</button>`;
        h += `<button onclick="geCtxSchliessen();geElementNachVorne(${id})">⬆️ Nach vorne holen</button>`;
        h += `<button onclick="geCtxSchliessen();geElementNachHinten(${id})">⬇️ Nach hinten legen</button>`;
        h += `<button onclick="geCtxSchliessen();geElementDuplizieren(${id})">⧉ Duplizieren</button>`;
        h += `<button class="gefahr" onclick="geCtxSchliessen();geElementLoeschen(${id})">🗑️ Modul löschen</button>`;
        m.innerHTML = h;
        const node = document.querySelector(`#ge-canvas .ce-el[data-id="${id}"]`);
        if (node) { const b = node.getBoundingClientRect(); geCtxPositionieren(b.left, b.bottom + 6); }
        else geCtxPositionieren(clientX, clientY);
    }
    function geCtxFuerCanvas(clientX, clientY) {
        const m = document.getElementById('ge-ctx'), cv = document.getElementById('ge-canvas'); if (!m || !cv) return;
        geSelect(null);
        const rect = cv.getBoundingClientRect();
        geCtxNeuPos = { x: Math.max(0, Math.min(92, ((clientX - rect.left) / rect.width) * 100)),
                        y: Math.max(0, Math.min(88, ((clientY - rect.top) / rect.height) * 100)) };
        m.innerHTML = `<div class="ce-ctx-titel">Hinzufügen</div>` +
            `<button onclick="geCtxSchliessen();geBildHinzufuegen(true)">🖼️ Bild laden</button>` +
            `<button onclick="geCtxSchliessen();geTextModulHinzufuegen(true)">✎ Textlabel</button>`;
        geCtxPositionieren(clientX, clientY);
    }
    // Eigene, #ge-canvas-scoped Listener (früh-return, wenn nicht die Galerie im Fokus).
    document.addEventListener('pointerdown', e => {
        if (e.button !== 0) return;
        if (e.target.closest('#ge-canvas') && !e.target.closest('.ce-el')) geCtxFuerCanvas(e.clientX, e.clientY);
    });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') geCtxSchliessen(); });

    // ---- Galerie-Attributpanel (#ge-attr, eigener gattr-Namespace) ----
    function geAttr(id, feld, wert) {
        const el = geFindeEl(id); if (!el) return;
        if (['x','y','w','h','groesse','zeilenabstand','radius','rahmen_breite','polster','z'].includes(feld)) wert = parseFloat(wert);
        el[feld] = wert; geAktualisiereElement(id);
    }
    function geAttrToggle(id, feld, wert) { const el = geFindeEl(id); if (!el) return; el[feld] = wert; geAktualisiereElement(id); geBaueAttr(); }
    function geSyncMasze(el) {
        [['x',el.x],['y',el.y],['w',el.w],['h',el.h]].forEach(([f,v]) => {
            const inp = document.getElementById('gattr-' + f), lab = document.getElementById('gattrlab-' + f);
            if (inp) inp.value = Math.round(v); if (lab) lab.textContent = Math.round(v) + '%';
        });
    }
    function geSchieber(id, feld, label, val, min, max, step, einheit) {
        const v = (val != null) ? val : 0;
        return `<div class="ce-attr-feld">
            <label>${label}<span id="gattrlab-${feld}">${(Math.round(v*100)/100)}${einheit||''}</span></label>
            <input type="range" id="gattr-${feld}" min="${min}" max="${max}" step="${step}" value="${v}"
                oninput="document.getElementById('gattrlab-${feld}').textContent=(Math.round(this.value*100)/100)+'${einheit||''}'; geAttr(${id},'${feld}',this.value)">
        </div>`;
    }
    function geFarbFeld(id, feld, label, val, mitTransparent) {
        return `<div class="ce-attr-feld"><label>${label}</label>
            <input type="color" value="${val || '#0c1a2e'}" oninput="geAttr(${id},'${feld}',this.value)">
            ${mitTransparent ? `<button class="ce-attr-btn" onclick="geAttr(${id},'${feld}','')">Transparent</button>` : ''}
        </div>`;
    }
    function geFilterSelect(el) {
        const opts = PROFIL_FILTER.map(f => `<option value="${f}" ${el.filter===f?'selected':''}>${f||'kein Filter'}</option>`).join('');
        return `<div class="ce-attr-feld"><label>Bildfilter</label><select onchange="geAttr(${el.id},'filter',this.value)">${opts}</select></div>`;
    }
    function geTextViaPanel(id) { const el = geFindeEl(id); if (!el) return; const neu = prompt('Text:', el.text || ''); if (neu !== null) { el.text = neu; geAktualisiereElement(id); } }
    function geBaueAttr() {
        const box = document.getElementById('ge-attr'); if (!box) return;
        const el = geFindeEl(geSelektiert);
        if (!el) {
            box.innerHTML = `<div class="ce-attr-leer">Wähle ein Bild (Klick), um es frei zu formen: Position, Größe, Filter, Titel, Rahmen.<br><br>Neue Bilder: „＋ Bild laden" oben oder Klick auf die freie Bühne.</div>`;
            return;
        }
        let h = `<div class="ce-attr-titel">${GE_TITEL[el.typ] || 'Modul'}</div>`;
        h += `<div class="ce-attr-row">${geSchieber(el.id,'x','Position X',el.x,0,100,1,'%')}${geSchieber(el.id,'y','Position Y',el.y,0,100,1,'%')}</div>`;
        h += `<div class="ce-attr-row">${geSchieber(el.id,'w','Breite',el.w,3,100,1,'%')}${geSchieber(el.id,'h','Höhe',el.h,3,100,1,'%')}</div>`;
        if (el.typ === 'bild') {
            h += `<button class="ce-attr-btn" onclick="geBildWaehlen(${el.id})">🖼️ Bild wählen / ersetzen</button>`;
            h += geFilterSelect(el);
            h += `<div class="ce-attr-feld"><label>Titel (optional)</label>
                <input type="text" value="${escapeHtml(el.titel||'')}" oninput="geAttr(${el.id},'titel',this.value)" placeholder="Bildunterschrift …"></div>`;
            h += geFarbFeld(el.id,'farbe','Titelfarbe',el.farbe||'#ffffff',false);
            // Malermodus (Feature 3): Freistellen (transparente Box) + Bild-Passung (Füllen/Einpassen).
            h += `<div class="ce-attr-feld"><label>Freistellen (transparent)</label><div class="ce-attr-toggle">
                <button class="${!el.freistellen?'an':''}" onclick="geAttrToggle(${el.id},'freistellen',false)">Box sichtbar</button>
                <button class="${el.freistellen?'an':''}" onclick="geAttrToggle(${el.id},'freistellen',true)">Freigestellt</button></div></div>`;
            const gpas = el.bild_passung || 'cover';
            h += `<div class="ce-attr-feld"><label>Bild-Passung</label><div class="ce-attr-toggle">
                <button class="${gpas!=='contain'?'an':''}" onclick="geAttrToggle(${el.id},'bild_passung','cover')">Füllen</button>
                <button class="${gpas==='contain'?'an':''}" onclick="geAttrToggle(${el.id},'bild_passung','contain')">Einpassen</button></div></div>`;
        } else {
            h += geSchieber(el.id,'groesse','Schriftgröße',el.groesse,0.4,6,0.05,'rem');
            h += geFarbFeld(el.id,'farbe','Textfarbe',el.farbe||'#ffffff',false);
            const al = el.ausrichtung||'zentriert';
            h += `<div class="ce-attr-feld"><label>Ausrichtung</label><div class="ce-attr-toggle">
                <button class="${al==='links'?'an':''}" onclick="geAttrToggle(${el.id},'ausrichtung','links')">Links</button>
                <button class="${al==='zentriert'?'an':''}" onclick="geAttrToggle(${el.id},'ausrichtung','zentriert')">Mitte</button>
                <button class="${al==='rechts'?'an':''}" onclick="geAttrToggle(${el.id},'ausrichtung','rechts')">Rechts</button></div></div>`;
            h += `<button class="ce-attr-btn" onclick="geTextViaPanel(${el.id})">✎ Text bearbeiten</button>`;
        }
        // Malermodus (Feature 2): Z-Index + Ebenen-Buttons (für JEDES Galerie-Modul).
        h += geSchieber(el.id,'z','Ebene (Z-Index)',el.z||0,0,999,1,'');
        h += `<div class="ce-attr-row">
            <button class="ce-attr-btn" onclick="geElementNachHinten(${el.id})">⬇️ Nach hinten</button>
            <button class="ce-attr-btn" onclick="geElementNachVorne(${el.id})">⬆️ Nach vorne</button></div>`;
        // Malermodus (Feature 3): rahmenloser Kreis-Modus (hartes Viereck verschwindet).
        h += `<div class="ce-attr-feld"><label>Maske / Form</label><div class="ce-attr-toggle">
            <button class="${el.maske!=='kreis'?'an':''}" onclick="geAttrToggle(${el.id},'maske','')">Rechteck</button>
            <button class="${el.maske==='kreis'?'an':''}" onclick="geAttrToggle(${el.id},'maske','kreis')">Kreis</button></div></div>`;
        h += geSchieber(el.id,'radius','Rahmen-Radius',el.radius,0,200,1,'px');
        h += geSchieber(el.id,'polster','Innenabstand',el.polster,0,80,1,'px');
        h += geSchieber(el.id,'rahmen_breite','Rahmenstärke',el.rahmen_breite,0,40,1,'px');
        h += geFarbFeld(el.id,'rahmen_farbe','Rahmenfarbe',el.rahmen_farbe||'#ffd700',false);
        h += geFarbFeld(el.id,'bg_farbe','Box-Hintergrund',el.bg_farbe,true);
        h += `<button class="ce-attr-btn" style="background:var(--rot); border-color:var(--rot); color:#fff;" onclick="geElementLoeschen(${el.id})">Modul löschen</button>`;
        box.innerHTML = h;
    }

    // ---- Galerie: Module hinzufügen / laden / anordnen ----
    function geBildHinzufuegen(beiKlick) {
        const inp = document.createElement('input'); inp.type = 'file'; inp.accept = 'image/*'; inp.multiple = true;
        inp.onchange = () => {
            const files = Array.from(inp.files || []);
            files.forEach((f, k) => {
                const r = new FileReader();
                r.onload = e => {
                    const el = geStandard('bild'); el.bild = e.target.result;
                    if (beiKlick && geCtxNeuPos && k === 0) { el.x = Math.min(100 - el.w, geCtxNeuPos.x); el.y = Math.min(100 - el.h, geCtxNeuPos.y); }
                    else { el.x = Math.min(100 - el.w, 20 + (geElemente.length % 6) * 5); el.y = Math.min(100 - el.h, 14 + (geElemente.length % 6) * 5); }
                    geElemente.push(el); baueGalerieCanvas(); geSelect(el.id);
                };
                r.readAsDataURL(f);
            });
        };
        inp.click();
    }
    function geBildWaehlen(id) {
        const inp = document.createElement('input'); inp.type = 'file'; inp.accept = 'image/*';
        inp.onchange = () => { const f = inp.files[0]; if (!f) return; const r = new FileReader();
            r.onload = e => { const el = geFindeEl(id); if (!el) return; el.bild = e.target.result; baueGalerieCanvas(); geSelect(id); };
            r.readAsDataURL(f); };
        inp.click();
    }
    function geTextModulHinzufuegen(beiKlick) {
        const el = geStandard('text');
        if (beiKlick && geCtxNeuPos) { el.x = Math.min(100 - el.w, geCtxNeuPos.x); el.y = Math.min(100 - el.h, geCtxNeuPos.y); }
        geElemente.push(el); baueGalerieCanvas(); geSelect(el.id);
    }
    function geElementLoeschen(id) { geCtxSchliessen(); geElemente = geElemente.filter(e => e.id !== id); if (geSelektiert === id) geSelektiert = null; baueGalerieCanvas(); }
    function geElementDuplizieren(id) { const el = geFindeEl(id); if (!el) return; const k = geNorm(geSerialisiere(el)); k.x = Math.min(100 - k.w, (el.x||0) + 4); k.y = Math.min(100 - k.h, (el.y||0) + 4); geElemente.push(k); baueGalerieCanvas(); geSelect(k.id); }
    function geElementNachVorne(id) { const i = geElemente.findIndex(e => e.id === id); if (i < 0) return; const [el] = geElemente.splice(i, 1); geElemente.push(el); baueGalerieCanvas(); geSelect(id); }
    // Malermodus (Feature 2): ans Array-ANFANG -> liegt hinten (Bild-im-Bild-Tiefe in der Galerie).
    function geElementNachHinten(id) { const i = geElemente.findIndex(e => e.id === id); if (i < 0) return; const [el] = geElemente.splice(i, 1); geElemente.unshift(el); baueGalerieCanvas(); geSelect(id); }
    // Layout-Presets: ordnen die vorhandenen Bild-Module in ein Muster; 'raster' verteilt ALLE gleichmäßig.
    function geLayoutPreset(name) {
        if (name === 'raster') return geRasterAlle();
        const slots = GE_PRESETS[name]; if (!slots) return;
        const bilder = geElemente.filter(e => e.typ === 'bild');
        slots.forEach((s, i) => { const el = bilder[i]; if (el) Object.assign(el, s); });
        baueGalerieCanvas();
        const fehlend = slots.length - bilder.length;
        galerieMsg(`Layout „${name}" angewendet${fehlend > 0 ? ` – ${fehlend} Slot(s) frei (mehr Bilder laden).` : ''}.`, true);
    }
    function geRasterAlle() {
        const bilder = geElemente.filter(e => e.typ === 'bild'); const n = bilder.length; if (!n) return;
        const spalten = Math.ceil(Math.sqrt(n)), luecke = 3;
        const zellW = (100 - luecke * (spalten + 1)) / spalten;
        const zeilen = Math.ceil(n / spalten), zellH = Math.min(30, (100 - luecke * (zeilen + 1)) / zeilen);
        bilder.forEach((el, i) => { const c = i % spalten, r = Math.floor(i / spalten);
            el.x = luecke + c * (zellW + luecke); el.y = luecke + r * (zellH + luecke); el.w = zellW; el.h = zellH; });
        baueGalerieCanvas();
    }
    // Brücke Schritt 1 -> Schritt 2: migrierten Bild-Pool verlustfrei in Canvas-Module überführen.
    function geAusPoolAufbauen(pool) {
        const spalten = 3, luecke = 3, zellW = (100 - luecke * (spalten + 1)) / spalten, zellH = 26;
        return pool.slice(0, 60).map((b, i) => {
            const el = geStandard('bild'); const c = i % spalten, r = Math.floor(i / spalten);
            el.x = luecke + c * (zellW + luecke); el.y = luecke + r * (zellH + luecke); el.w = zellW; el.h = zellH;
            el.bild = b.url; el.filter = b.filter || ''; el.titel = b.titel || '';
            return el;
        });
    }

    // ---- Galerie-Bühne: Stil / Schema / Dock ----
    function geSchemaSelectBauen() {
        const sel = document.getElementById('ge-schema'); if (!sel) return;
        sel.innerHTML = Object.entries(PROFIL_SCHEMATA).map(([k,v]) => `<option value="${k}">${escapeHtml(v.label)}</option>`).join('');
        sel.value = geSchema;
    }
    function geSchemaWechsel(key) { geSchema = key; geCanvasStil(); }
    function geCanvasStil() {
        geBgUrl = (document.getElementById('ge-bg-url')||{}).value || '';
        geBgFarbe = (document.getElementById('ge-bg-farbe')||{}).value || '#0c1a2e';
        geRahmen = (document.getElementById('ge-rahmen')||{}).value || '';
        // Malermodus (Feature 1): Galerie-Hintergrund verschieben/skalieren aus den Reglern + Labels.
        geBgPosX = parseFloat((document.getElementById('ge-bg-posx')||{}).value); if (isNaN(geBgPosX)) geBgPosX = 50;
        geBgPosY = parseFloat((document.getElementById('ge-bg-posy')||{}).value); if (isNaN(geBgPosY)) geBgPosY = 50;
        geBgSkala = parseFloat((document.getElementById('ge-bg-skala')||{}).value); if (isNaN(geBgSkala)) geBgSkala = 100;
        const setLab = (id, v) => { const n = document.getElementById(id); if (n) n.textContent = Math.round(v) + '%'; };
        setLab('ge-bg-posx-lab', geBgPosX); setLab('ge-bg-posy-lab', geBgPosY); setLab('ge-bg-skala-lab', geBgSkala);
        const cv = document.getElementById('ge-canvas'); if (!cv) return;
        const schema = PROFIL_SCHEMATA[geSchema] || PROFIL_SCHEMATA.nachtblau;
        Object.assign(cv.style, ceHintergrund(geBgUrl, geBgFarbe, schema, geBgPosX, geBgPosY, geBgSkala));
        const rahmen = { gold: '3px solid #ffd700', doppelt: '6px double #ffd700', neon: '2px solid #00ffcc' };
        cv.style.border = rahmen[geRahmen] || `1px solid ${schema.rand}`;
        cv.style.boxShadow = geRahmen === 'neon' ? '0 0 22px rgba(0,255,204,0.55)' : (geRahmen === 'weich' ? '0 18px 50px rgba(0,0,0,0.6)' : 'none');
    }
    function geDockToggle() {
        const dock = document.getElementById('ge-dock'), btn = document.getElementById('ge-dock-btn'); if (!dock) return;
        const zu = dock.classList.toggle('eingeklappt'); if (btn) btn.textContent = zu ? '▼ Werkzeuge' : '▲ Werkzeuge';
    }
    function galerieMsg(text, ok) { const el = document.getElementById('galerie-msg'); if (el) { el.textContent = text || ''; el.classList.toggle('ok', !!ok); } }

    // ---- Galerie-Editor öffnen / speichern ----
    async function oeffneGalerieEditor() {
        galerieMsg(''); geElemente = []; geElementSeq = 1; geSelektiert = null; geAktion = null;
        galerieSeite = galerieStandardSeite();
        try {
            const res = await fetch(`/auth/profil-daten?email=${encodeURIComponent(userEmail)}`);
            const d = await res.json();
            if (d.success) {
                const gs = (d.galerie_seite && typeof d.galerie_seite === 'object') ? d.galerie_seite : {};
                galerieSeite = {
                    hintergrund_url: gs.hintergrund_url || '',
                    hintergrund_farbe: gs.hintergrund_farbe || '#0c1a2e',
                    // Malermodus (Feature 1): Hintergrund-Offset/Skalierung verlustsicher übernehmen.
                    hintergrund_pos_x: (typeof gs.hintergrund_pos_x === 'number') ? gs.hintergrund_pos_x : 50,
                    hintergrund_pos_y: (typeof gs.hintergrund_pos_y === 'number') ? gs.hintergrund_pos_y : 50,
                    hintergrund_skala: (typeof gs.hintergrund_skala === 'number') ? gs.hintergrund_skala : 100,
                    farbschema: (gs.farbschema && PROFIL_SCHEMATA[gs.farbschema]) ? gs.farbschema : 'nachtblau',
                    rahmen: gs.rahmen || '',
                    bilder: Array.isArray(gs.bilder) ? gs.bilder.map(ceGalerieBildNorm).filter(Boolean) : [],
                    elemente: Array.isArray(gs.elemente) ? gs.elemente.slice() : [],
                };
            }
        } catch (e) {}
        geBgUrl = galerieSeite.hintergrund_url; geBgFarbe = galerieSeite.hintergrund_farbe || '#0c1a2e';
        geRahmen = galerieSeite.rahmen || ''; geSchema = galerieSeite.farbschema || 'nachtblau';
        // Malermodus (Feature 1): Offset/Skalierung in den State + Regler übernehmen.
        geBgPosX = (typeof galerieSeite.hintergrund_pos_x === 'number') ? galerieSeite.hintergrund_pos_x : 50;
        geBgPosY = (typeof galerieSeite.hintergrund_pos_y === 'number') ? galerieSeite.hintergrund_pos_y : 50;
        geBgSkala = (typeof galerieSeite.hintergrund_skala === 'number') ? galerieSeite.hintergrund_skala : 100;
        geElemente = (galerieSeite.elemente || []).map(geNorm);
        // Verlustfreie Brücke: leerer Canvas, aber migrierter Pool -> Module aus dem Pool erzeugen.
        if (!geElemente.length && galerieSeite.bilder.length) geElemente = geAusPoolAufbauen(galerieSeite.bilder);
        geSchemaSelectBauen();
        document.getElementById('ge-bg-url').value = geBgUrl;
        document.getElementById('ge-bg-farbe').value = /^#/.test(geBgFarbe) ? geBgFarbe : '#0c1a2e';
        document.getElementById('ge-schema').value = geSchema;
        document.getElementById('ge-rahmen').value = geRahmen;
        // Malermodus (Feature 1): Regler-Positionen aus dem geladenen Zustand setzen.
        document.getElementById('ge-bg-posx').value = geBgPosX;
        document.getElementById('ge-bg-posy').value = geBgPosY;
        document.getElementById('ge-bg-skala').value = geBgSkala;
        geCanvasStil();
        baueGalerieCanvas();
        document.getElementById('galerie-overlay').classList.add('aktiv');
    }
    function schliesseGalerieEditor() { document.getElementById('galerie-overlay').classList.remove('aktiv'); }
    async function speichereGalerie() {
        galerieMsg('Speichere …', true);
        galerieSeite.hintergrund_url = geBgUrl; galerieSeite.hintergrund_farbe = geBgFarbe;
        // Malermodus (Feature 1): Hintergrund-Offset/Skalierung mitspeichern.
        galerieSeite.hintergrund_pos_x = geBgPosX; galerieSeite.hintergrund_pos_y = geBgPosY; galerieSeite.hintergrund_skala = geBgSkala;
        galerieSeite.farbschema = geSchema; galerieSeite.rahmen = geRahmen;
        galerieSeite.elemente = geElemente.map(geSerialisiere);
        // Bild-Pool aus den Bild-Modulen aktuell halten (Fallback-Grid + Quelle des Sichtbarkeits-Flags).
        galerieSeite.bilder = geElemente.filter(e => e.typ === 'bild' && e.bild).map(e => ({ url: e.bild, titel: e.titel || '', filter: e.filter || '' }));
        try {
            const res = await fetch('/auth/profil-update', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: userEmail, galerie_seite: galerieSeite }) });
            const d = await res.json();
            if (d.success) galerieMsg('Galerie gespeichert.', true);
            else galerieMsg(d.message || 'Speichern fehlgeschlagen.');
        } catch (e) { galerieMsg('Server-Verbindung fehlgeschlagen.'); }
    }

    // =====================================================================
    // ADMIN-PANEL (verstecktes Panel: Logo-Doppelklick)
    // =====================================================================
    let adminGewaehlterUser = null;
    let ethnoAktuellesKapitel = "";

    function versucheAdmin() { if (isAdmin) { oeffneAdmin(); } }
    function oeffneAdmin() {
        document.getElementById('admin-panel').classList.add('aktiv');
        ladeAdminStats(); ladeAdminUsers(); ladeAdminVideoConfig(); ladeEthnografie(); ladeSektorConfigAlle(); ladeAdminReservierungen(); ladeAdminLiveRegie();
    }
    function schliesseAdmin() { document.getElementById('admin-panel').classList.remove('aktiv'); }

    // SYSTEM 5: Echtzeit-Übersicht aller Reservierungen/Einladungen im Admin-Panel.
    async function ladeAdminReservierungen() {
        const box = document.getElementById('admin-res-liste');
        if (!box) return;
        try {
            const res = await fetch(`/admin/reservierungen?email=${encodeURIComponent(userEmail)}`);
            const d = await res.json();
            if (!d.success) { box.innerHTML = `<p style="color:#ff4d4d; padding:8px;">${escapeHtml(d.error||d.message||'Nicht autorisiert.')}</p>`; return; }
            document.getElementById('admin-res-gesamt').textContent = d.zusammenfassung.gesamt;
            document.getElementById('admin-res-live').textContent = d.zusammenfassung.live;
            document.getElementById('admin-res-geplant').textContent = d.zusammenfassung.geplant;
            if (!d.reservierungen.length) { box.innerHTML = `<p style="color:#666; padding:8px;">Noch keine Reservierungen.</p>`; return; }
            box.innerHTML = d.reservierungen.map(r => {
                const gaeste = (r.eingeladene||[]).map(g => `${g.online?'🟢':'⚪'} ${escapeHtml(g.name)} (${g.status})`).join(', ') || 'keine';
                const st = r.status === 'live' ? `<span class="live">● LIVE</span>` : r.status;
                return `<div class="admin-res-zeile"><b>Sektor ${r.sektor}</b> · ${escapeHtml(r.thema||'')} · ${st}<br>
                    Ersteller: ${escapeHtml(r.ersteller_name)}${r.zeitpunkt?(' · '+escapeHtml(r.zeitpunkt)):''} · ${r.angenommen}/${r.eingeladen_gesamt} zugesagt<br>
                    <span style="color:#9db8dd;">Gäste: ${gaeste}</span></div>`;
            }).join('');
        } catch (e) { box.innerHTML = `<p style="color:#ff4d4d; padding:8px;">Verbindungsfehler.</p>`; }
    }

    async function ladeAdminStats() {
        try { const r = await fetch('/admin/stats'); const d = await r.json(); if (d.success) document.getElementById('admin-zaehler').textContent = d.total_souls; } catch(e){}
    }

    async function ladeAdminUsers() {
        const box = document.getElementById('admin-user-tabelle');
        const suche = (document.getElementById('admin-user-suche').value || "").trim();
        box.innerHTML = `<p style="color:#666; padding:10px;">Lade …</p>`;
        try {
            const res = await fetch(`/admin/users?email=${encodeURIComponent(userEmail)}&suche=${encodeURIComponent(suche)}`);
            const data = await res.json();
            if (!data.success) { box.innerHTML = `<p style="color:#ff4d4d; padding:10px;">${data.error || "Nicht autorisiert."}</p>`; return; }
            if (!data.users.length) { box.innerHTML = `<p style="color:#666; padding:10px;">Keine Reisenden.</p>`; return; }
            let html = `<table><tr><th>E-Mail</th><th>Stufe</th><th>Sektor</th><th>Fertig</th><th></th></tr>`;
            data.users.forEach(u => {
                const safe = u.email.replace(/'/g, "\\'");
                const stufe = u.rolle || u.role || '';
                html += `<tr><td>${escapeHtml(u.email)}</td><td>${escapeHtml(stufe)}</td><td>${u.aktueller_sektor}</td><td>${(u.abgeschlossene_sektoren||[]).length}</td>
                    <td><button class="admin-btn" style="padding:3px 9px;" onclick="adminWaehleUser('${safe}','${u.aktueller_sektor}','${escapeHtml(stufe)}')">Wählen</button></td></tr>`;
            });
            box.innerHTML = html + `</table>`;
        } catch (e) { box.innerHTML = `<p style="color:#ff4d4d; padding:10px;">Verbindungsfehler.</p>`; }
    }

    function adminWaehleUser(email, sektor, stufe) {
        adminGewaehlterUser = email;
        document.getElementById('admin-ziel-user').textContent = email;
        document.getElementById('admin-ziel-sektor').value = sektor || "";
        document.getElementById('admin-zert-email').value = email;
        document.getElementById('admin-zert-sektor').value = sektor || "1";
        // Mitglieder-Stufen-Steuerung an denselben User koppeln.
        setText('admin-stufe-user', email);
        setText('admin-stufe-akt', stufe || '—');
    }

    async function adminSetzeStufe(stufe) {
        if (!adminGewaehlterUser) { alert("Bitte zuerst einen User in der Tabelle wählen."); return; }
        try {
            const res = await fetch('/admin/set-mitglied-stufe', { method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({ email: userEmail, ziel_email: adminGewaehlterUser, stufe }) });
            const d = await res.json();
            if (d.success) { setText('admin-stufe-akt', d.rolle || stufe); ladeAdminUsers(); }
            else alert("Fehler: " + (d.error || "?"));
        } catch (e) { alert("Verbindungsfehler."); }
    }

    async function adminSetzeUserProgress() {
        if (!adminGewaehlterUser) { alert("Bitte zuerst einen User wählen."); return; }
        try {
            const res = await fetch('/admin/set-user-progress', { method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({ email: userEmail, ziel_email: adminGewaehlterUser, aktueller_sektor: document.getElementById('admin-ziel-sektor').value }) });
            const d = await res.json();
            alert(d.success ? "Aktualisiert." : ("Fehler: " + (d.error || "?"))); if (d.success) ladeAdminUsers();
        } catch (e) { alert("Verbindungsfehler."); }
    }

    async function adminSendeZertifikat() {
        const ziel = (document.getElementById('admin-zert-email').value || "").trim();
        const sektor = document.getElementById('admin-zert-sektor').value;
        if (!ziel) { alert("Bitte Ziel-E-Mail angeben."); return; }
        try {
            const res = await fetch('/admin/send-certificate', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email: userEmail, ziel_email: ziel, sector_id: sektor }) });
            const d = await res.json();
            alert(d.success ? `Zertifikat an ${ziel} versendet.` : ("Fehlgeschlagen: " + (d.error || "?")));
        } catch (e) { alert("Verbindungsfehler."); }
    }

    async function ladeAdminVideoConfig() {
        try {
            const res = await fetch(`/admin/video-config?email=${encodeURIComponent(userEmail)}`);
            const d = await res.json();
            if (d.success) {
                document.getElementById('admin-video-teilnehmer').textContent = d.aktive_teilnehmer;
                document.getElementById('admin-video-tische').textContent = d.anzahl_tische;
                document.getElementById('admin-video-plaetze').value = d.plaetze_pro_tisch;
                const box = document.getElementById('admin-video-raeume');
                box.innerHTML = (d.raeume && d.raeume.length)
                    ? d.raeume.map(r => `Sektor ${r.raum} (${escapeHtml(r.thema)}): ${r.teilnehmer} Teiln. · ${r.tische} Tisch(e)`).join('<br>')
                    : "Keine aktiven Live-Räume.";
            }
        } catch (e) {}
    }

    async function adminSpeichereVideoConfig() {
        const plaetze = parseInt(document.getElementById('admin-video-plaetze').value) || 8;
        try {
            const res = await fetch('/admin/video-config', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email: userEmail, plaetze_pro_tisch: plaetze }) });
            const d = await res.json();
            alert(d.success ? `Gespeichert: ${d.plaetze_pro_tisch} Plätze/Tisch.` : "Speichern fehlgeschlagen."); ladeAdminVideoConfig();
        } catch (e) { alert("Verbindungsfehler."); }
    }

    // ---- LIVE-REGIE: Monitoring, Last-Regler/Not-Aus, manuelle Freigabe, Spontan-Slot ----
    let lrSessions = [];
    async function ladeAdminLiveRegie() {
        const box = document.getElementById('lr-sessions');
        if (!box) return;
        try {
            const res = await fetch(`/admin/live-regie?email=${encodeURIComponent(userEmail)}`);
            const d = await res.json();
            if (!d.success) { box.innerHTML = `<p style="color:#ff4d4d; padding:8px;">${escapeHtml(d.error||'Nicht autorisiert.')}</p>`; return; }
            lrSessions = d.sessions || [];
            document.getElementById('lr-pausiert').checked = !!(d.regie && d.regie.pausiert);
            document.getElementById('lr-maxtische').value = (d.regie && d.regie.max_tische) || 0;
            setText('lr-aktiv', d.aktive_teilnehmer || 0);
            if (!lrSessions.length) { box.innerHTML = `<p style="color:#666; padding:8px;">Für heute keine Zeitfenster.</p>`; return; }
            box.innerHTML = lrSessions.map(s => {
                const sid = (s.session_id||'').replace(/'/g, "\\'");
                const kopf = `<b>Sektor ${s.sektor}</b> · ${escapeHtml(s.thema||'')} · ${escapeHtml(s.slot||'')} · ${liveUhr(s.start)}–${liveUhr(s.ende)} · Status: ${escapeHtml(s.status||'')}${s.freigegeben?' · <span style="color:#00ff88;">Runde freigegeben</span>':''}`;
                const runde = s.freigegeben
                    ? `<button class="admin-btn grau" style="padding:2px 8px;" onclick="adminSessionFreigeben('${sid}',false)">Freigabe zurücknehmen</button>`
                    : `<button class="admin-btn gruen" style="padding:2px 8px;" onclick="adminSessionFreigeben('${sid}',true)">Ganze Runde freigeben</button>`;
                const anm = (s.anmeldungen||[]).map(a => {
                    const ae = (a.email||'').replace(/'/g, "\\'");
                    const tech = a.technik_ok ? '🟢 Technik' : '⚪ Technik';
                    return `<div style="display:flex; align-items:center; gap:6px; padding:3px 0; border-top:1px solid #1e2a3a; font-size:0.74rem;">
                        <span style="flex:1;">${escapeHtml(a.email||'')} · ${tech} · ${escapeHtml(a.status||'angemeldet')}</span>
                        <button class="admin-btn gruen" style="padding:1px 7px;" onclick="adminTeilnehmerFreigeben('${sid}','${ae}','freigeben')">Freigeben</button>
                        <button class="admin-btn grau" style="padding:1px 7px;" onclick="adminTeilnehmerFreigeben('${sid}','${ae}','entfernen')">Entfernen</button>
                    </div>`;
                }).join('') || `<div style="color:#666; font-size:0.74rem; padding:3px 0;">Noch keine Anmeldungen.</div>`;
                return `<div style="border:1px solid #1e3a5f; border-radius:6px; padding:8px 10px; margin-bottom:8px;">
                    <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap; color:#cfe0ff; font-size:0.78rem;">${kopf}<span style="margin-left:auto;">${runde}</span></div>
                    <div style="margin-top:6px;">${anm}</div></div>`;
            }).join('');
        } catch (e) { box.innerHTML = `<p style="color:#ff4d4d; padding:8px;">Verbindungsfehler.</p>`; }
    }

    async function adminSetLiveRegie() {
        const pausiert = document.getElementById('lr-pausiert').checked;
        const max_tische = parseInt(document.getElementById('lr-maxtische').value) || 0;
        try {
            const res = await fetch('/admin/live-regie/speichern', { method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({ email: userEmail, pausiert, max_tische }) });
            const d = await res.json();
            if (!d.success) alert("Fehler: " + (d.error || "?"));
            ladeAdminLiveRegie();
        } catch (e) { alert("Verbindungsfehler."); }
    }

    async function adminSessionFreigeben(sessionId, frei) {
        const s = lrSessions.find(x => x.session_id === sessionId);
        if (!s) return;
        try {
            const res = await fetch('/admin/live-session/speichern', { method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({ email: userEmail, session_id: sessionId, sektor: s.sektor, slot: s.slot,
                    start: s.start, dauer_min: 60, max_teilnehmer: s.max_teilnehmer, status: frei ? 'live' : 'offen', freigegeben: frei }) });
            const d = await res.json();
            if (!d.success) alert("Fehler: " + (d.error || "?"));
            ladeAdminLiveRegie();
        } catch (e) { alert("Verbindungsfehler."); }
    }

    async function adminTeilnehmerFreigeben(sessionId, zielEmail, aktion) {
        try {
            const res = await fetch('/admin/live-session/teilnehmer', { method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({ email: userEmail, session_id: sessionId, ziel_email: zielEmail, aktion }) });
            const d = await res.json();
            if (!d.success) alert("Fehler: " + (d.error || "?"));
            ladeAdminLiveRegie();
        } catch (e) { alert("Verbindungsfehler."); }
    }

    async function adminSpontanSlot() {
        const sektor = parseInt(document.getElementById('lr-slot-sektor').value) || 1;
        const dauer = parseInt(document.getElementById('lr-slot-dauer').value) || 60;
        // Startzeit = jetzt (lokale ISO ohne Zeitzone -> vom Server als naive datetime gelesen).
        const jetzt = new Date();
        const pad = n => String(n).padStart(2, '0');
        const startIso = `${jetzt.getFullYear()}-${pad(jetzt.getMonth()+1)}-${pad(jetzt.getDate())}T${pad(jetzt.getHours())}:${pad(jetzt.getMinutes())}:00`;
        const slot = jetzt.getHours() < 13 ? 'vormittag' : 'nachmittag';
        try {
            const res = await fetch('/admin/live-session/speichern', { method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({ email: userEmail, sektor, slot, start: startIso, dauer_min: dauer,
                    max_teilnehmer: 7, status: 'live', freigegeben: true }) });
            const d = await res.json();
            alert(d.success ? `Spontan-Slot für Sektor ${sektor} eröffnet und freigegeben.` : ("Fehler: " + (d.error || "?")));
            ladeAdminLiveRegie();
        } catch (e) { alert("Verbindungsfehler."); }
    }

    async function adminSpeichereSektorText() {
        const sektorIdx = document.getElementById('admin-sektor-auswahl').value;   // 0-basiert
        const headerText = document.getElementById('admin-sektor-text').value.trim();
        if (!headerText) return;
        try {
            await fetch('/admin/update-sector', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email: userEmail, sector_id: sektorIdx, header_text: headerText, status: 'update-text' }) });
            alert("Erfolgreich übertragen!");
        } catch (e) { alert("Verbindungsfehler."); }
    }

    // --- Ethnografische Studie ---
    async function ladeEthnografie(sektor) {
        try {
            const url = `/admin/ethnografie?email=${encodeURIComponent(userEmail)}` + (sektor ? `&sektor=${sektor}` : "");
            const res = await fetch(url);
            const d = await res.json();
            if (!d.success) { document.getElementById('ethno-kapitel').innerHTML = `<p style="color:#ff4d4d; padding:8px;">${d.error||"Nicht autorisiert."}</p>`; return; }
            document.getElementById('ethno-gesamt').textContent = d.gesamt || 0;
            const kap = document.getElementById('ethno-kapitel');
            kap.innerHTML = (d.kapitel || []).map(k =>
                `<div class="ethno-kapitel-zeile" onclick="ladeEthnografie(${k.sektor})"><span>${k.sektor}. ${escapeHtml(k.thema)}</span><span class="anzahl">${k.anzahl}</span></div>`
            ).join('');
            if (sektor) {
                ethnoAktuellesKapitel = String(sektor);
                document.getElementById('ethno-detail-titel').textContent = `Sektor ${sektor}`;
                const det = document.getElementById('ethno-detail');
                det.innerHTML = (d.detail && d.detail.length) ? d.detail.map(e => {
                    const mods = Object.entries(e.modul_brille || {}).filter(([k,v])=>v).map(([k,v])=>`<b>${k}:</b> ${escapeHtml(v)}`).join(' · ');
                    return `<div class="ethno-eintrag"><div class="roh">„${escapeHtml((e.roh_text||'').slice(0,160))}…"</div>${escapeHtml(e.sektor_brille||'')}${e.gefuehls_fundament?`<div style="color:#ffd; margin-top:3px;"><b>Gefühlsvorderung:</b> ${escapeHtml(e.gefuehls_fundament)}</div>`:''}${mods?`<div class="mods">${mods}</div>`:''}</div>`;
                }).join('') : `<p style="color:#666; padding:8px;">Noch keine Auswertungen in diesem Kapitel.</p>`;
            }
        } catch (e) {}
    }
    function adminEthnografiePDF(sektor) {
        const url = `/admin/ethnografie/pdf?email=${encodeURIComponent(userEmail)}` + (sektor ? `&sektor=${sektor}` : "");
        window.open(url, '_blank');
    }
    function adminEthnografiePDFKapitel() {
        if (!ethnoAktuellesKapitel) { alert("Bitte zuerst ein Kapitel öffnen."); return; }
        adminEthnografiePDF(ethnoAktuellesKapitel);
    }

    // --- Sektoren-Seelen · KI-Master-Switch · globale Sichtbarkeit ---
    let sektorConfigCache = [];
    async function ladeSektorConfigAlle() {
        try {
            const res = await fetch(`/admin/sektor-config?email=${encodeURIComponent(userEmail)}`);
            const d = await res.json();
            if (!d.success) return;
            sektorConfigCache = d.sektoren || [];
            const sel = document.getElementById('sk-sektor');
            if (sel && !sel.options.length) {
                sektorConfigCache.forEach(s => { sel.innerHTML += `<option value="${s.sektor}">Sektor ${s.sektor}: ${s.thema}</option>`; });
            }
            const g = document.getElementById('sk-global'); if (g) g.checked = (d.global_offen !== false);
            ladeSektorConfig();
        } catch (e) {}
    }
    function ladeSektorConfig() {
        const s = parseInt(document.getElementById('sk-sektor').value);
        const cfg = sektorConfigCache.find(x => x.sektor === s); if (!cfg) return;
        const kiEl = document.getElementById('sk-ki');
        kiEl.checked = !!cfg.ki_aktiv; kiEl.disabled = !cfg.ki_verfuegbar;
        document.getElementById('sk-sicht').checked = (cfg.sichtbarkeit === 'sichtbar');
        document.getElementById('sk-name').value = cfg.seele_name || "";
        document.getElementById('sk-wesen').value = cfg.seele_wesen || "";
    }
    async function speichereSektorConfig() {
        const s = parseInt(document.getElementById('sk-sektor').value);
        const payload = {
            email: userEmail, sektor: s,
            ki_aktiv: document.getElementById('sk-ki').checked,
            sichtbarkeit: document.getElementById('sk-sicht').checked ? 'sichtbar' : 'gesperrt',
            seele_name: document.getElementById('sk-name').value,
            seele_wesen: document.getElementById('sk-wesen').value,
        };
        try {
            const res = await fetch('/admin/sektor-config', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
            const d = await res.json();
            alert(d.success ? `Sektor ${s} gespeichert.` : ('Fehler: ' + (d.error || '?')));
            ladeSektorConfigAlle();
        } catch (e) { alert("Verbindungsfehler."); }
    }
    async function setzeGlobalOffen() {
        const offen = document.getElementById('sk-global').checked;
        try {
            await fetch('/admin/sektor-config', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email: userEmail, global_offen: offen }) });
        } catch (e) {}
    }

    // Admin-Sektor-Auswahl befüllen (0-basiert; Backend normalisiert +1).
    (function initAdminSelect() {
        const sel = document.getElementById('admin-sektor-auswahl');
        if (sel) themen.forEach((t, i) => { sel.innerHTML += `<option value="${i}">Sektor ${i+1}: ${t}</option>`; });
    })();

    // Enter-Tasten-Bedienung der Auth-Schleuse.
    document.addEventListener('keypress', function (e) {
        if (e.key !== 'Enter') return;
        const id = document.activeElement.id;
        if (id === 'login-email' || id === 'login-pass') authLogin();
        else if (id === 'reg-name' || id === 'reg-email' || id === 'reg-pass') authRegister();
        else if (id === 'verify-code') authVerify();
        else if (id === 'prof-vorname' || id === 'prof-nachname' || id === 'prof-handle') authProfil();
    });
   
