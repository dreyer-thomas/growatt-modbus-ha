/*
 * Growatt SPH Card – Dashboard-Karte für die Integration "Growatt SPH (lokal)".
 *
 * Eine Karte zeigt genau eine Ansicht, gewählt mit `view` (im Karten-Editor auswählbar):
 *   overview – Haus-Grafik, Ladestand, Leistung (Standard)
 *   today    – Tagessummen, Monatsbalken aus der Langzeitstatistik
 *   control  – Entladestopp, Netzladen, Backup-Reserve
 *   device   – Temperaturen, Netz, Strings, Firmware
 * Für mehrere Ansichten einfach mehrere Karten anlegen.
 *
 * Die Entitäten werden über das Entitätsregister gefunden (Plattform
 * growatt_sph_local, translation_key) – die minimale Konfiguration ist
 *   type: custom:growatt-sph-card
 * Optional: view, title, capacity (nutzbare Batteriekapazität in kWh, Standard 7.5),
 *           device_id (bei mehreren Wechselrichtern).
 *
 * Gestaltung angelehnt an die Karten von BavarianData (Chris Krammer, MIT),
 * https://github.com/JustChr/BavarianData – eigener Code, keine Grafiken übernommen.
 * MIT-Lizenz, Nutzung auf eigene Verantwortung.
 */

const GSC_VERSION = "0.2.3";
const GSC_VIEWS = {
  overview: "Übersicht",
  today: "Heute & Verlauf",
  control: "Steuerung",
  device: "Gerät",
};
const GSC_PLATFORM = "growatt_sph_local";
const GSC_ACTIVE_W = 30; // darunter gilt die Batterie als ruhend

// translation_key -> Rolle in der Karte
const GSC_KEYS = [
  "status", "pv_power", "pv1_voltage", "pv1_current", "pv1_power", "pv2_voltage", "pv2_current",
  "pv2_power", "ac_power", "grid_frequency", "voltage_l1", "voltage_l2", "voltage_l3",
  "inverter_temperature", "battery_soc", "battery_charge_power", "battery_discharge_power",
  "battery_power", "battery_voltage", "battery_temperature", "grid_import_power", "grid_export_power",
  "grid_power", "load_power", "pv_energy_total", "grid_import_energy_total", "grid_export_energy_total",
  "battery_discharge_energy_total", "battery_charge_energy_total", "load_energy_total",
  "pv_energy_today", "grid_import_energy_today", "grid_export_energy_today", "load_energy_today",
  "grid_measurement", "battery_first_window", "meter_com_loss", "ac_charge", "battery_hold",
  "grid_charge", "backup_reserve", "grid_charge_soc", "grid_charge_rate",
];

const GSC_STATUS = {
  waiting: "Wartet", normal: "Normal", fault: "Störung", flash: "Firmware-Update",
  normal_hybrid: "Normal (Hybrid)", unknown: "Unbekannt",
};
const GSC_METER = { wired_ct: "CT-Klemme", wireless_ct: "Funk-CT", meter: "Zähler", unknown: "Unbekannt" };

// Material-Design-Icon-Pfade (Apache 2.0, Pictogrammers) – als Inline-SVG, damit die Karte
// nicht von ha-icon in Shadow-DOMs abhängt.
const GSC_ICONS = {
  sun: "M12,7A5,5 0 0,1 17,12A5,5 0 0,1 12,17A5,5 0 0,1 7,12A5,5 0 0,1 12,7M12,9A3,3 0 0,0 9,12A3,3 0 0,0 12,15A3,3 0 0,0 15,12A3,3 0 0,0 12,9M12,2L14.39,5.42C13.65,5.15 12.84,5 12,5C11.16,5 10.35,5.15 9.61,5.42L12,2M3.34,7L7.5,6.65C6.9,7.16 6.36,7.78 5.94,8.5C5.5,9.24 5.25,10 5.11,10.79L3.34,7M3.36,17L5.12,13.23C5.26,14 5.53,14.78 5.95,15.5C6.37,16.24 6.91,16.86 7.5,17.37L3.36,17M20.65,7L18.88,10.79C18.74,10 18.47,9.23 18.05,8.5C17.63,7.78 17.1,7.15 16.5,6.64L20.65,7M20.64,17L16.5,17.36C17.09,16.85 17.62,16.22 18.04,15.5C18.46,14.77 18.73,14 18.87,13.21L20.64,17M12,22L9.59,18.56C10.33,18.83 11.14,19 12,19C12.82,19 13.63,18.83 14.37,18.56L12,22Z",
  home: "M10,20V14H14V20H19V12H22L12,3L2,12H5V20H10Z",
  tower: "M8.28,5.45L6.5,4.55L7.76,2H16.23L17.5,4.55L15.72,5.44L15,4H9L8.28,5.45M18.62,8H14.09L13.3,5H10.7L9.91,8H5.38L4.1,10.55L5.89,11.44L6.62,10H17.38L18.1,11.45L19.89,10.56L18.62,8M17.77,22H15.7L15.46,21.1L12,15.9L8.53,21.1L8.3,22H6.23L9.12,11H11.19L10.83,12.35L12,14.1L13.16,12.35L12.81,11H14.88L17.77,22M11.4,15L10.5,13.65L9.32,18.13L11.4,15M14.68,18.12L13.5,13.64L12.6,15L14.68,18.12Z",
  battery: "M16,20H8V6H16M16.67,4H15V2H9V4H7.33A1.33,1.33 0 0,0 6,5.33V20.67C6,21.4 6.6,22 7.33,22H16.67A1.33,1.33 0 0,0 18,20.67V5.33C18,4.6 17.4,4 16.67,4Z",
  batteryCharging: "M16.67,4H15V2H9V4H7.33A1.33,1.33 0 0,0 6,5.33V20.67C6,21.4 6.6,22 7.33,22H16.67A1.33,1.33 0 0,0 18,20.67V5.33C18,4.6 17.4,4 16.67,4M11,20V14.5H9L13,7V12.5H15",
  lock: "M12,17A2,2 0 0,0 14,15C14,13.89 13.1,13 12,13A2,2 0 0,0 10,15A2,2 0 0,0 12,17M18,8A2,2 0 0,1 20,10V20A2,2 0 0,1 18,22H6A2,2 0 0,1 4,20V10C4,8.89 4.9,8 6,8H7V6A5,5 0 0,1 12,1A5,5 0 0,1 17,6V8H18M12,3A3,3 0 0,0 9,6V8H15V6A3,3 0 0,0 12,3Z",
  chart: "M22,21H2V3H4V19H6V10H10V19H12V6H16V19H18V14H22V21Z",
  tune: "M3,17V19H9V17H3M3,5V7H13V5H3M13,21V19H21V17H13V15H11V21H13M7,9V11H3V13H7V15H9V9H7M21,13V11H11V13H21M15,9H17V7H21V5H17V3H15V9Z",
  chip: "M6,4H18V5H21V7H18V9H21V11H18V13H21V15H18V17H21V19H18V20H6V19H3V17H6V15H3V13H6V11H3V9H6V7H3V5H6V4M11,15V18H12V15H11M13,15V18H14V15H13M15,15V18H16V15H15Z",
  chevron: "M8.59,16.58L13.17,12L8.59,7.41L10,6L16,12L10,18L8.59,16.58Z",
  back: "M15.41,16.58L10.83,12L15.41,7.41L14,6L8,12L14,18L15.41,16.58Z",
  thermo: "M15,13V5A3,3 0 0,0 9,5V13A5,5 0 1,0 15,13M12,4A1,1 0 0,1 13,5V8H11V5A1,1 0 0,1 12,4Z",
  wave: "M16,11.78L20.24,4.45L21.97,5.45L16.74,14.5L10.23,10.75L5.46,19H22V21H2V3H4V17.54L9.5,8L16,11.78Z",
  bolt: "M11,15H6L13,1V9H18L11,23V15Z",
  alert: "M13,14H11V9H13M13,18H11V16H13M1,21H23L12,2L1,21Z",
  check: "M21,7L9,19L3.5,13.5L4.91,12.09L9,16.17L19.59,5.59L21,7Z",
  leaf: "M17,8C8,10 5.9,16.17 3.82,21.34L5.71,22L6.66,19.7C7.14,19.87 7.64,20 8,20C19,20 22,3 22,3C21,5 14,5.25 9,6.25C4,7.25 2,11.5 2,13.5C2,15.5 3.75,17.25 3.75,17.25C7,8 17,8 17,8Z",
};

const gscIcon = (name, cls = "") =>
  `<svg class="ic ${cls}" viewBox="0 0 24 24" aria-hidden="true"><path d="${GSC_ICONS[name]}"/></svg>`;
const gscEsc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

class GrowattSphCard extends HTMLElement {
  static getStubConfig() {
    return { view: "overview", capacity: 7.5 };
  }

  static getConfigElement() {
    return document.createElement("growatt-sph-card-editor");
  }

  setConfig(config) {
    this._config = { capacity: 7.5, ...(config || {}) };
    const view = this._config.view || "overview";
    if (!GSC_VIEWS[view]) {
      throw new Error(`Unbekannte Ansicht „${view}“ – erlaubt: ${Object.keys(GSC_VIEWS).join(", ")}`);
    }
    this._view = view;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
    }
    this._last = "";
    this._paint();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._map) this._discover();
    if (this._raf) return;
    this._raf = requestAnimationFrame(() => {
      this._raf = null;
      this._paint();
    });
  }

  getCardSize() {
    return 8;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6 };
  }

  // ---------- Entitäten ----------
  _discover() {
    const hass = this._hass;
    if (!hass || !hass.entities) return;
    const map = {};
    let device = this._config.device_id;
    for (const ent of Object.values(hass.entities)) {
      if (ent.platform !== GSC_PLATFORM || !ent.translation_key) continue;
      if (device && ent.device_id !== device) continue;
      if (!device) device = ent.device_id;
      if (!map[ent.translation_key]) map[ent.translation_key] = ent.entity_id;
    }
    if (!Object.keys(map).length) return;
    this._map = map;
    this._deviceId = device;
  }

  _id(key) {
    return this._map ? this._map[key] : undefined;
  }

  _st(key) {
    const id = this._id(key);
    return id ? this._hass.states[id] : undefined;
  }

  _num(key) {
    const s = this._st(key);
    if (!s) return null;
    const v = parseFloat(s.state);
    return Number.isFinite(v) ? v : null;
  }

  _on(key) {
    const s = this._st(key);
    return s ? s.state === "on" : null;
  }

  // ---------- Formatierung ----------
  get _lang() {
    return (this._hass && this._hass.locale && this._hass.locale.language) || this._hass?.language || "de";
  }

  _fmt(v, digits = 0) {
    if (v === null || v === undefined || !Number.isFinite(v)) return "–";
    return v.toLocaleString(this._lang, { minimumFractionDigits: digits, maximumFractionDigits: digits });
  }

  _power(w) {
    if (w === null || w === undefined) return "–";
    const a = Math.abs(w);
    return a >= 1000 ? `${this._fmt(w / 1000, 2)} kW` : `${this._fmt(w, 0)} W`;
  }

  _kwh(v, d = 1) {
    return v === null || v === undefined ? "–" : `${this._fmt(v, d)} kWh`;
  }

  _clock(date) {
    return date.toLocaleTimeString(this._lang, { hour: "2-digit", minute: "2-digit" });
  }

  _eta(hours) {
    if (!Number.isFinite(hours) || hours <= 0 || hours > 72) return null;
    const t = new Date(Date.now() + hours * 3600e3);
    const sameDay = t.toDateString() === new Date().toDateString();
    return sameDay ? this._clock(t) : `${t.toLocaleDateString(this._lang, { weekday: "short" })} ${this._clock(t)}`;
  }

  // Jüngster Zeitpunkt, zu dem irgendein Wert der Integration geschrieben wurde. Ein einzelner
  // Sensor taugt dafür nicht: bleibt sein Wert gleich (PV nachts 0 W), ändert sich last_updated nicht.
  _freshest() {
    let best = null;
    for (const id of Object.values(this._map || {})) {
      const st = this._hass.states[id];
      if (!st || st.state === "unavailable") continue;
      const t = Date.parse(st.last_reported || st.last_updated || "");
      if (Number.isFinite(t) && (best === null || t > best)) best = t;
    }
    return best;
  }

  _ago(ts) {
    if (ts === null || ts === undefined || ts === "") return "";
    const t = typeof ts === "number" ? ts : new Date(ts).getTime();
    const s = Math.max(0, Math.round((Date.now() - t) / 1000));
    if (s < 60) return `vor ${s} s`;
    const m = Math.round(s / 60);
    return m < 60 ? `vor ${m} min` : `vor ${Math.round(m / 60)} h`;
  }

  // ---------- Zustand ----------
  _model() {
    const soc = this._num("battery_soc");
    const charge = this._num("battery_charge_power") ?? 0;
    const discharge = this._num("battery_discharge_power") ?? 0;
    const pv = this._num("pv_power") ?? 0;
    const load = this._num("load_power") ?? 0;
    const imp = this._num("grid_import_power") ?? 0;
    const exp = this._num("grid_export_power") ?? 0;
    const reserve = this._num("backup_reserve") ?? 10;
    const gcSoc = this._num("grid_charge_soc") ?? 100;
    const cap = parseFloat(this._config.capacity) || 7.5;
    const gridCharge = this._on("grid_charge") === true;
    const hold = this._on("battery_hold") === true;
    const status = this._st("status")?.state;
    const fault = status === "fault" || this._on("meter_com_loss") === true;
    let mode = "idle";
    if (charge > GSC_ACTIVE_W) mode = "charge";
    else if (discharge > GSC_ACTIVE_W) mode = "discharge";
    const target = gridCharge ? gcSoc : 100;
    return { soc, charge, discharge, pv, load, imp, exp, reserve, gcSoc, cap, gridCharge, hold, status, fault, mode, target };
  }

  _headline(m) {
    if (m.soc === null) return { title: "Keine Daten", sub: "Wechselrichter nicht erreichbar" };
    if (m.fault) {
      return { title: "Störung", sub: this._on("meter_com_loss") ? "Zählerkommunikation gestört" : GSC_STATUS[m.status] || "" };
    }
    if (m.gridCharge) {
      if (m.mode === "charge" && m.soc < m.target) {
        const eta = this._eta(((m.target - m.soc) / 100) * m.cap / (m.charge / 1000));
        return { title: `Lädt aus dem Netz${eta ? ` · Ziel um ${eta}` : ""}`, sub: `Ziel ${m.target} % · ${this._power(m.charge)}` };
      }
      return { title: "Netzladen aktiv", sub: m.soc >= m.target ? `Ziel ${m.target} % erreicht – Batterie wird gehalten` : `Ziel ${m.target} %` };
    }
    if (m.mode === "charge") {
      const eta = this._eta(((100 - m.soc) / 100) * m.cap / (m.charge / 1000));
      return { title: `Batterie lädt${eta ? ` · voll um ${eta}` : ""}`, sub: `mit Solarstrom · ${this._power(m.charge)}` };
    }
    if (m.mode === "discharge") {
      const eta = this._eta(((m.soc - m.reserve) / 100) * m.cap / (m.discharge / 1000));
      return { title: `Haus läuft aus der Batterie${eta ? ` · reicht bis ~${eta}` : ""}`, sub: `${this._power(m.discharge)} · bis zur Reserve ${m.reserve} %` };
    }
    if (m.hold) return { title: "Entladestopp aktiv", sub: "Batterie wird gehalten, PV lädt weiter" };
    if (m.soc >= 99) return { title: "Batterie voll", sub: m.exp > GSC_ACTIVE_W ? `Überschuss geht ins Netz · ${this._power(m.exp)}` : "Bereit" };
    if (m.soc <= m.reserve + 1) return { title: "Batterie auf Reserve", sub: `Notstromreserve ${m.reserve} % bleibt erhalten` };
    if (m.imp > 100 && m.load < 500) return { title: "Batterie ruht", sub: `Kleine Last (${this._power(m.load)}) kommt aus dem Netz` };
    return { title: "Bereit", sub: GSC_STATUS[m.status] || "" };
  }

  // ---------- Darstellung ----------
  _paint() {
    if (!this.shadowRoot || !this._config) return;
    let body;
    if (!this._hass) body = "";
    else if (!this._map) body = `<div class="empty">Keine Entitäten der Integration „Growatt SPH (lokal)“ gefunden.</div>`;
    else if (this._view === "today") body = this._viewToday();
    else if (this._view === "control") body = this._viewControl();
    else if (this._view === "device") body = this._viewDevice();
    else body = this._viewOverview();
    const html = `<style>${GSC_STYLES}</style><ha-card>${body}</ha-card>`;
    if (html === this._last) return;
    this._last = html;
    this.shadowRoot.innerHTML = html;
  }

  _title() {
    if (this._config.title) return this._config.title;
    const dev = this._hass.devices?.[this._deviceId];
    return dev?.name_by_user || dev?.name || "Growatt SPH";
  }

  _hero(m) {
    const fresh = this._freshest();
    const stale = fresh !== null && Date.now() - fresh > 120000;
    const ok = !m.fault && m.soc !== null && !stale;
    const flow = (on, reverse) => `flow ${on ? "on" : ""} ${reverse ? "rev" : ""}`;
    const pvOn = m.pv > GSC_ACTIVE_W;
    const night = !pvOn;
    const batIn = m.mode === "charge";
    const batOut = m.mode === "discharge";
    const gridIn = m.imp > GSC_ACTIVE_W;
    const gridOut = m.exp > GSC_ACTIVE_W;
    const lvl = Math.max(0, Math.min(100, m.soc ?? 0));
    const batH = 56 * (lvl / 100);
    const batColor = m.mode === "charge" ? "#2fa864" : m.mode === "discharge" ? "#f0a030" : lvl <= m.reserve + 1 ? "#d9534f" : "#2fa864";
    return `
      <div class="hero ${night ? "night" : ""}">
        <div class="hero__top">
          <div class="hero__title">${gscEsc(this._title())}</div>
          <div class="pill" title="Letzte Daten vom Wechselrichter"><span class="dot ${ok ? "" : "bad"}"></span>${gscEsc(this._ago(fresh))}</div>
        </div>
        <svg class="scene" viewBox="0 0 400 200" role="img" aria-label="Energiefluss">
          ${night
            ? `<path class="moon" d="M332 30a18 18 0 1 0 14 30a15 15 0 0 1-14-30z"/>`
            : `<circle class="sunc" cx="340" cy="42" r="16"/>`}
          <!-- Netz -->
          <g class="mast"><path d="M48 176 L60 96 L72 176 M52 150 H68 M55 126 H65 M44 104 H76 M48 116 H72"/></g>
          <!-- Haus -->
          <path class="house" d="M140 176 V112 L205 66 L270 112 V176 Z"/>
          <path class="roof" d="M128 116 L205 58 L282 116"/>
          <g class="pv"><path d="M168 92 L205 64 L242 92 L232 99 L205 79 L178 99 Z"/></g>
          <rect class="door" x="194" y="140" width="22" height="36" rx="2"/>
          <rect class="win" x="156" y="126" width="22" height="18" rx="2"/>
          <rect class="win" x="232" y="126" width="22" height="18" rx="2"/>
          <!-- Batterie -->
          <rect class="bat" x="300" y="112" width="34" height="64" rx="5"/>
          <rect x="304" y="${172 - batH}" width="26" height="${batH}" rx="2" fill="${batColor}"/>
          <rect class="bat-cap" x="310" y="106" width="14" height="6" rx="2"/>
          <!-- Flüsse: Pfade laufen jeweils von der Quelle zum Ziel (Sonne→Dach, Netz→Haus, Batterie→Haus); .rev dreht um -->
          ${night ? "" : `<path class="${flow(pvOn)}" d="M326 52 L224 80" style="--c:#f0b429"/>`}
          <path class="${flow(gridIn || gridOut, gridOut)}" d="M72 150 C100 150 120 150 140 150" style="--c:#7f8fa6"/>
          <path class="${flow(batIn || batOut, batIn)}" d="M300 150 C290 150 280 150 270 150" style="--c:${batIn ? "#2fa864" : "#f0a030"}"/>
          <line class="ground" x1="20" y1="177" x2="380" y2="177"/>
        </svg>
      </div>`;
  }

  _bar(m) {
    const soc = Math.max(0, Math.min(100, m.soc ?? 0));
    const cls = m.mode === "charge" ? "charge" : m.mode === "discharge" ? "discharge" : soc <= m.reserve + 1 ? "low" : "idle";
    const target = m.gridCharge && m.target < 100
      ? `<span class="mark target" style="left:${m.target}%"></span>` : "";
    return `
      <div class="bar">
        <span class="fill ${cls}" style="width:${soc}%"></span>
        <span class="mark reserve" style="left:${m.reserve}%" title="Reserve"></span>
        ${target}
      </div>`;
  }

  _tile(icon, value, label, cls = "") {
    return `<div class="tile">${gscIcon(icon, cls)}<div><div class="tv">${value}</div><div class="tl">${gscEsc(label)}</div></div></div>`;
  }

  _viewOverview() {
    const m = this._model();
    const h = this._headline(m);
    const usable = m.soc === null ? null : Math.max(0, ((m.soc - m.reserve) / 100) * m.cap);
    const gridLabel = m.exp > GSC_ACTIVE_W ? "Einspeisung" : "Netzbezug";
    const gridVal = m.exp > GSC_ACTIVE_W ? m.exp : m.imp;
    const batLabel = m.mode === "charge" ? "Batterie lädt" : m.mode === "discharge" ? "Batterie entlädt" : "Batterie ruht";
    const batVal = m.mode === "charge" ? m.charge : m.mode === "discharge" ? m.discharge : 0;
    const left = m.mode === "charge" ? `Laden ${this._power(m.charge)}` : m.mode === "discharge" ? `Entladen ${this._power(m.discharge)}` : m.hold ? "Entladestopp" : "Ruht";
    const right = m.gridCharge && m.target < 100 ? `Ziel ${m.target} % · Reserve ${m.reserve} %` : `Reserve ${m.reserve} %`;
    const pvToday = this._num("pv_energy_today");
    const loadToday = this._num("load_energy_today");
    const impToday = this._num("grid_import_energy_today");
    const autark = loadToday ? Math.max(0, Math.min(100, (1 - (impToday ?? 0) / loadToday) * 100)) : null;
    const ctrlSub = [
      m.gridCharge ? `Netzladen bis ${m.gcSoc} %` : m.hold ? "Entladestopp an" : "Lastvorrang",
      `Reserve ${m.reserve} %`,
    ].join(" · ");
    const temp = this._num("inverter_temperature");
    const devSub = `${m.fault ? "Störung" : "Alles in Ordnung"} · ${this._fmt(temp, 0)} °C`;
    return `
      ${this._hero(m)}
      <div class="main">
        <div class="head">${gscEsc(h.title)}</div>
        <div class="sub">${gscEsc(h.sub)}</div>
        <div class="big">
          <div><span class="bn">${this._fmt(m.soc, 0)}</span><span class="bu">%</span><div class="bl">Ladestand</div></div>
          <div class="right"><span class="bn2">${this._kwh(usable, 1)}</span><div class="bl">nutzbar bis Reserve</div></div>
        </div>
        ${this._bar(m)}
        <div class="barlbl"><span>${gscEsc(left)}</span><span>${gscEsc(right)}</span></div>
        <div class="tiles">
          ${this._tile("sun", this._power(m.pv), "Solar jetzt", "amber")}
          ${this._tile("home", this._power(m.load), "Haus")}
          ${this._tile("tower", this._power(gridVal), gridLabel, m.exp > GSC_ACTIVE_W ? "green" : "")}
          ${this._tile(m.mode === "charge" ? "batteryCharging" : "battery", this._power(batVal), batLabel, m.mode === "charge" ? "green" : m.mode === "discharge" ? "amber" : "")}
        </div>
      </div>
      <div class="foot">
        <span>${gscIcon("chart")}Heute ${this._kwh(pvToday)} Solar · ${autark === null ? "–" : this._fmt(autark, 0)} % autark</span>
        <span>${gscIcon("tune")}${gscEsc(ctrlSub)}</span>
        <span>${gscIcon("chip")}${gscEsc(devSub)}</span>
      </div>`;
  }

  _subHead(title, sub, icon) {
    return `<div class="subhead"><span class="hi">${gscIcon(icon)}</span>
      <div><div class="sh">${gscEsc(this._config.title || title)}</div><div class="ss">${gscEsc(sub)}</div></div></div>`;
  }

  _stat(value, unit, label) {
    return `<div class="stat"><div class="sv">${value}${unit ? `<span class="su"> ${unit}</span>` : ""}</div><div class="sl">${gscEsc(label)}</div></div>`;
  }

  _split(title, a, b, la, lb, ca, cb, unit = "kWh") {
    const tot = (a ?? 0) + (b ?? 0);
    const pa = tot > 0 ? ((a ?? 0) / tot) * 100 : 0;
    return `<div class="block"><div class="bt">${gscEsc(title)}</div>
      <div class="split"><span style="width:${pa}%;background:${ca}"></span><span style="width:${100 - pa}%;background:${cb}"></span></div>
      <div class="legend"><span><i style="background:${ca}"></i>${gscEsc(la)} <b>${this._fmt(a, 1)}</b></span>
      <span><i style="background:${cb}"></i>${gscEsc(lb)} <b>${this._fmt(b, 1)}</b></span><span class="lu">${unit}</span></div></div>`;
  }

  _viewToday() {
    const pv = this._num("pv_energy_today");
    const load = this._num("load_energy_today");
    const imp = this._num("grid_import_energy_today");
    const exp = this._num("grid_export_energy_today");
    const autark = load ? Math.max(0, Math.min(100, (1 - (imp ?? 0) / load) * 100)) : null;
    const selfUse = pv ? Math.max(0, Math.min(100, (1 - (exp ?? 0) / pv) * 100)) : null;
    this._ensureMonth();
    return `
      ${this._subHead("Heute & Verlauf", new Date().toLocaleDateString(this._lang, { weekday: "long", day: "numeric", month: "long" }), "chart")}
      <div class="pad">
        <div class="stats3">
          ${this._stat(this._fmt(pv, 1), "kWh", "Solar")}
          ${this._stat(this._fmt(load, 1), "kWh", "Verbrauch")}
          ${this._stat(this._fmt(autark, 0), "%", "Autarkie")}
        </div>
        ${this._split("Woher kam der Strom", Math.max(0, (load ?? 0) - (imp ?? 0)), imp, "Eigen", "Netz", "#2fa864", "#9aa3ad")}
        ${this._split("Wohin ging der Solarstrom", Math.max(0, (pv ?? 0) - (exp ?? 0)), exp, "Selbst genutzt", "Eingespeist", "#f0b429", "#4a90d9")}
        <div class="note">Eigenverbrauchsquote ${this._fmt(selfUse, 0)} %</div>
      </div>
      <div class="divider"></div>
      ${this._monthBlock()}`;
  }

  // ---------- Monatsverlauf (Langzeitstatistik) ----------
  _monthKey() {
    const d = this._month || new Date();
    return `${d.getFullYear()}-${d.getMonth()}`;
  }

  _ensureMonth() {
    if (!this._month) {
      const n = new Date();
      this._month = new Date(n.getFullYear(), n.getMonth(), 1);
    }
    const key = this._monthKey();
    this._stats = this._stats || {};
    if (this._stats[key] || this._loading === key) return;
    if (this._failedAt && Date.now() - this._failedAt < 30000) return;
    this._loading = key;
    const ids = ["pv_energy_total", "load_energy_total", "grid_import_energy_total", "grid_export_energy_total"]
      .map((k) => this._id(k)).filter(Boolean);
    const start = new Date(this._month);
    const end = new Date(start.getFullYear(), start.getMonth() + 1, 1);
    this._hass.callWS({
      type: "recorder/statistics_during_period",
      start_time: start.toISOString(),
      end_time: end.toISOString(),
      statistic_ids: ids,
      period: "day",
      types: ["change"],
    }).then((res) => {
      const days = new Date(start.getFullYear(), start.getMonth() + 1, 0).getDate();
      const series = {};
      for (const k of ["pv_energy_total", "load_energy_total", "grid_import_energy_total", "grid_export_energy_total"]) {
        const arr = new Array(days).fill(null);
        for (const row of res[this._id(k)] || []) {
          const d = new Date(typeof row.start === "number" ? row.start : Date.parse(row.start)).getDate();
          if (row.change !== null && row.change !== undefined) arr[d - 1] = (arr[d - 1] ?? 0) + Math.max(0, row.change);
        }
        series[k] = arr;
      }
      this._stats[key] = series;
      this._loading = null;
      this._last = "";
      this._paint();
    }).catch(() => {
      this._loading = null;
      this._failedAt = Date.now();
    });
  }

  _monthBlock() {
    const key = this._monthKey();
    const s = this._stats?.[key];
    const label = this._month.toLocaleDateString(this._lang, { month: "long", year: "numeric" });
    const now = new Date();
    const isCurrent = this._month.getFullYear() === now.getFullYear() && this._month.getMonth() === now.getMonth();
    const nav = `<div class="mnav"><button class="nb" data-month="-1" aria-label="Vorheriger Monat">${gscIcon("back")}</button>
      <span>${gscEsc(label)}</span><button class="nb" data-month="1" ${isCurrent ? "disabled" : ""} aria-label="Nächster Monat">${gscIcon("chevron")}</button></div>`;
    if (!s) return `<div class="pad">${nav}<div class="note">Lade Statistik …</div></div>`;
    const sum = (a) => a.reduce((x, y) => x + (y ?? 0), 0);
    const pv = sum(s.pv_energy_total), load = sum(s.load_energy_total), imp = sum(s.grid_import_energy_total);
    const autark = load ? Math.max(0, Math.min(100, (1 - imp / load) * 100)) : null;
    const max = Math.max(1, ...s.pv_energy_total.map((v) => v ?? 0), ...s.load_energy_total.map((v) => v ?? 0));
    const today = isCurrent ? now.getDate() : 99;
    const bars = s.pv_energy_total.map((v, i) => {
      const l = s.load_energy_total[i];
      const future = i + 1 > today;
      return `<div class="day ${future ? "future" : ""}" title="${i + 1}.: Solar ${this._fmt(v, 1)} kWh, Verbrauch ${this._fmt(l, 1)} kWh">
        <span class="b load" style="height:${((l ?? 0) / max) * 100}%"></span>
        <span class="b pv" style="height:${((v ?? 0) / max) * 100}%"></span></div>`;
    }).join("");
    const n = s.pv_energy_total.length;
    return `<div class="pad">${nav}
      <div class="stats3">
        ${this._stat(this._fmt(pv, 0), "kWh", "Solar")}
        ${this._stat(this._fmt(load, 0), "kWh", "Verbrauch")}
        ${this._stat(this._fmt(autark, 0), "%", "Autarkie")}
      </div>
      <div class="bt row2"><span>Pro Tag</span><span class="legend small"><span><i style="background:#f0b429"></i>Solar</span><span><i style="background:var(--gsc-track)"></i>Verbrauch</span><span class="lu">kWh</span></span></div>
      <div class="chart">${bars}</div>
      <div class="axis"><span>1</span><span>${Math.ceil(n / 2)}</span><span>${n}</span></div>
    </div>`;
  }

  // ---------- Steuerung ----------
  _toggle(key, title, sub, icon) {
    const on = this._on(key);
    return `<div class="ctl">
      <span class="ri">${gscIcon(icon)}</span>
      <span class="rt"><span class="rh">${gscEsc(title)}</span><span class="rs">${gscEsc(sub)}</span></span>
      <button class="sw ${on ? "on" : ""}" data-toggle="${key}" role="switch" aria-checked="${on ? "true" : "false"}" aria-label="${gscEsc(title)}"><span></span></button></div>`;
  }

  _stepper(key, title, sub) {
    const v = this._num(key);
    return `<div class="ctl">
      <span class="rt"><span class="rh">${gscEsc(title)}</span><span class="rs">${gscEsc(sub)}</span></span>
      <span class="step"><button data-step="${key}" data-delta="-5" aria-label="${gscEsc(title)} minus">−</button>
      <b>${this._fmt(v, 0)} %</b>
      <button data-step="${key}" data-delta="5" aria-label="${gscEsc(title)} plus">+</button></span></div>`;
  }

  _viewControl() {
    const m = this._model();
    const mode = m.gridCharge ? "Netzladen" : m.hold ? "Entladestopp" : "Lastvorrang (normal)";
    return `
      ${this._subHead("Steuerung", `Betrieb: ${mode}`, "tune")}
      <div class="pad">
        ${this._toggle("battery_hold", "Entladestopp", "Batterie entlädt nicht, PV lädt weiter", "lock")}
        ${this._toggle("grid_charge", "Netzladen", `lädt aus dem Netz bis ${m.gcSoc} %`, "tower")}
        <div class="group">
          ${this._stepper("grid_charge_soc", "Netzladen bis", "Ziel-Ladestand")}
          ${this._stepper("grid_charge_rate", "Netzladeleistung", "Anteil der Nennleistung")}
        </div>
        <div class="group">
          ${this._stepper("backup_reserve", "Backup-Reserve", "bleibt für Notstrom in der Batterie")}
        </div>
        <div class="note">Entladestopp und Netzladen schließen sich aus. Schreibzugriff muss in der Integration erlaubt sein.</div>
      </div>`;
  }

  // ---------- Gerät ----------
  _kv(label, value, cls = "") {
    return `<div class="kv"><span>${gscEsc(label)}</span><b class="${cls}">${value}</b></div>`;
  }

  _viewDevice() {
    const m = this._model();
    const dev = this._hass.devices?.[this._deviceId] || {};
    const discharged = this._num("battery_discharge_energy_total");
    const cycles = discharged !== null ? discharged / m.cap : null;
    const meterLoss = this._on("meter_com_loss");
    return `
      ${this._subHead("Gerät", [dev.model, dev.serial_number].filter(Boolean).join(" · ") || "Growatt SPH", "chip")}
      <div class="pad">
        <div class="tiles">
          ${this._tile("thermo", `${this._fmt(this._num("inverter_temperature"), 1)} °C`, "Wechselrichter")}
          ${this._tile("thermo", `${this._fmt(this._num("battery_temperature"), 1)} °C`, "Batterie")}
          ${this._tile("bolt", `${this._fmt(this._num("battery_voltage"), 1)} V`, "Batteriespannung")}
          ${this._tile("wave", `${this._fmt(this._num("grid_frequency"), 2)} Hz`, "Netzfrequenz")}
        </div>
        <div class="kvs">
          ${this._kv("Status", gscEsc(GSC_STATUS[m.status] || m.status || "–"), m.fault ? "bad" : "")}
          ${this._kv("Zählerkommunikation", meterLoss ? "gestört" : "in Ordnung", meterLoss ? "bad" : "good")}
          ${this._kv("Netzmessung", gscEsc(GSC_METER[this._st("grid_measurement")?.state] || "–"))}
          ${this._kv("Netzspannung (L-L)", `${this._fmt(this._num("voltage_l1"), 0)} / ${this._fmt(this._num("voltage_l2"), 0)} / ${this._fmt(this._num("voltage_l3"), 0)} V`)}
          ${this._kv("String 1", `${this._power(this._num("pv1_power"))} · ${this._fmt(this._num("pv1_voltage"), 0)} V`)}
          ${this._kv("String 2", `${this._power(this._num("pv2_power"))} · ${this._fmt(this._num("pv2_voltage"), 0)} V`)}
          ${this._kv("Battery-First-Fenster", gscEsc(this._window()))}
          ${this._kv("Vollzyklen (≈)", `${this._fmt(cycles, 0)} bei ${this._fmt(m.cap, 1)} kWh`)}
          ${this._kv("PV gesamt", this._kwh(this._num("pv_energy_total"), 0))}
          ${this._kv("Firmware", gscEsc(dev.sw_version || "–"))}
        </div>
      </div>`;
  }

  _window() {
    const s = this._st("battery_first_window")?.state;
    if (!s || s === "unknown" || s === "unavailable") return "–";
    return /^00:00.00:00$/.test(s) ? "aus" : s;
  }

  // ---------- Bedienung ----------
  _onClick(ev) {
    const el = ev.composedPath().find((n) => n.dataset && (n.dataset.toggle || n.dataset.step || n.dataset.month));
    if (!el) return;
    if (el.dataset.month) {
      const d = this._month;
      this._month = new Date(d.getFullYear(), d.getMonth() + parseInt(el.dataset.month, 10), 1);
      this._last = "";
      this._paint();
      return;
    }
    if (el.dataset.toggle) {
      const id = this._id(el.dataset.toggle);
      if (id) this._call("switch", this._on(el.dataset.toggle) ? "turn_off" : "turn_on", { entity_id: id });
      return;
    }
    if (el.dataset.step) {
      const key = el.dataset.step;
      const id = this._id(key);
      const st = this._st(key);
      if (!id || !st) return;
      const cur = parseFloat(st.state);
      const min = st.attributes.min ?? 0;
      const max = st.attributes.max ?? 100;
      const delta = parseFloat(el.dataset.delta);
      // auf das 5er-Raster springen, dann begrenzen
      let next = delta > 0 ? Math.floor(cur / 5) * 5 + 5 : Math.ceil(cur / 5) * 5 - 5;
      next = Math.max(min, Math.min(max, next));
      if (next !== cur) this._call("number", "set_value", { entity_id: id, value: next });
    }
  }

  _call(domain, service, data) {
    this._hass.callService(domain, service, data).catch((err) => {
      this.dispatchEvent(new CustomEvent("hass-notification", {
        detail: { message: err?.message || String(err) }, bubbles: true, composed: true,
      }));
    });
  }
}

const GSC_STYLES = `
  :host { --gsc-tile: color-mix(in srgb, var(--primary-text-color, #1c2b4a) 7%, transparent);
          --gsc-track: color-mix(in srgb, var(--primary-text-color, #1c2b4a) 14%, transparent);
          --gsc-fg: var(--primary-text-color, #14213d); --gsc-fg2: var(--secondary-text-color, #5b6b82);
          --gsc-blue: #2f7fe0; --gsc-green: #2fa864; --gsc-amber: #e8a317; --gsc-red: #d9534f; }
  ha-card { display: block; overflow: hidden; color: var(--gsc-fg); background: var(--ha-card-background, var(--card-background-color, #fff));
            border-radius: var(--ha-card-border-radius, 12px); }
  button { font: inherit; color: inherit; background: none; border: 0; cursor: pointer; padding: 0; }
  .ic { width: 24px; height: 24px; fill: currentColor; flex: none; }
  .ic.amber { fill: var(--gsc-amber); } .ic.green { fill: var(--gsc-green); }
  .empty { padding: 24px; color: var(--gsc-fg2); }

  .hero { position: relative; background: linear-gradient(180deg, #8fa3bd 0%, #dbe5f2 38%, #e9eff7 100%); }
  .hero.night { background: linear-gradient(180deg, #1f2b45 0%, #34476a 45%, #4c5f80 100%); }
  .hero__top { position: absolute; inset: 14px 16px auto 16px; display: flex; justify-content: space-between; align-items: center; z-index: 1; }
  .hero__title { color: #fff; font-size: 22px; font-weight: 700; text-shadow: 0 1px 3px rgba(0,0,0,.35); }
  .pill { display: inline-flex; align-items: center; gap: 8px; background: rgba(40,45,55,.55); color: #fff; font-size: 13px; font-weight: 600; padding: 6px 12px; border-radius: 999px; }
  .dot { width: 9px; height: 9px; border-radius: 50%; background: #3ddc84; } .dot.bad { background: #ff5f57; }
  .scene { display: block; width: 100%; height: auto; padding-top: 40px; }
  .scene .house { fill: #f4f6fa; stroke: #b7c2d3; stroke-width: 1.5; }
  .scene .roof { fill: none; stroke: #5a6577; stroke-width: 6; stroke-linecap: round; stroke-linejoin: round; }
  .scene .pv path { fill: #2d4f8f; stroke: #8fb0e6; stroke-width: 1; }
  .scene .door { fill: #8a6a4f; } .scene .win { fill: #bcd3ee; stroke: #8ea6c4; }
  .night .scene .win { fill: #ffd97a; } .night .scene .house { fill: #c9d2e0; }
  .scene .bat { fill: #e9edf3; stroke: #8a96a8; stroke-width: 2; } .scene .bat-cap { fill: #8a96a8; }
  .scene .mast path { fill: none; stroke: #6f7d92; stroke-width: 3; stroke-linecap: round; }
  .scene .sunc { fill: #ffcf3f; filter: drop-shadow(0 0 8px rgba(255,200,40,.8)); }
  .scene .moon { fill: #f1f3f8; }
  .scene .ground { stroke: #9fb0c6; stroke-width: 2; }
  .scene .flow { fill: none; stroke: var(--c); stroke-width: 4; stroke-linecap: round; stroke-dasharray: 2 12; opacity: .18; }
  .scene .flow.on { opacity: 1; animation: gsc-flow 1.1s linear infinite; }
  .scene .flow.on.rev { animation-direction: reverse; }
  @keyframes gsc-flow { to { stroke-dashoffset: -28; } }
  @media (prefers-reduced-motion: reduce) { .scene .flow.on { animation: none; stroke-dasharray: none; } }

  .main { padding: 18px 20px 6px; }
  .head { font-size: 22px; font-weight: 700; line-height: 1.25; }
  .sub { color: var(--gsc-fg2); margin-top: 4px; }
  .big { display: flex; justify-content: space-between; align-items: flex-end; margin: 18px 0 12px; }
  .big .right { text-align: right; }
  .bn { font-size: 52px; font-weight: 800; line-height: 1; } .bu { font-size: 20px; color: var(--gsc-fg2); margin-left: 3px; }
  .bn2 { font-size: 28px; font-weight: 800; } .bl { color: var(--gsc-fg2); margin-top: 6px; }
  .bar { position: relative; height: 14px; background: var(--gsc-track); border-radius: 999px; }
  .fill { position: absolute; inset: 0 auto 0 0; border-radius: 999px; transition: width .6s; }
  .fill.idle { background: var(--gsc-green); } .fill.low { background: var(--gsc-red); }
  .fill.discharge { background: var(--gsc-amber); }
  .fill.charge { background: repeating-linear-gradient(-45deg, var(--gsc-blue) 0 8px, #6aa8f0 8px 14px); background-size: 200% 100%; animation: gsc-stripes 1.4s linear infinite; }
  @keyframes gsc-stripes { to { background-position: -40px 0; } }
  .mark { position: absolute; top: -5px; bottom: -5px; width: 3px; margin-left: -1px; border-radius: 2px; background: var(--gsc-fg); }
  .mark.target { background: var(--gsc-blue); }
  .barlbl { display: flex; justify-content: space-between; color: var(--gsc-fg2); font-size: 14px; margin-top: 10px; }
  .tiles { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 18px 0 12px; }
  .tile { display: flex; align-items: center; gap: 14px; background: var(--gsc-tile); border-radius: 16px; padding: 14px 16px; }
  .tile .ic { fill: var(--gsc-fg2); } .tile .ic.amber { fill: var(--gsc-amber); } .tile .ic.green { fill: var(--gsc-green); }
  .tv { font-size: 18px; font-weight: 700; } .tl { color: var(--gsc-fg2); font-size: 14px; }

  .ri { display: grid; place-items: center; width: 44px; height: 44px; border-radius: 12px; background: var(--gsc-tile); }
  .ri .ic { fill: var(--gsc-fg2); }
  .rt { flex: 1; display: flex; flex-direction: column; min-width: 0; }
  .rh { font-weight: 700; font-size: 16px; } .rs { color: var(--gsc-fg2); font-size: 14px; }
  .chev { fill: var(--gsc-fg2); }

  .subhead { display: flex; align-items: center; gap: 12px; padding: 16px 16px 12px; border-bottom: 1px solid var(--divider-color, #e1e6ee); }
  .hi { display: grid; place-items: center; width: 44px; height: 44px; border-radius: 12px; background: var(--gsc-tile); flex: none; }
  .hi .ic { fill: var(--gsc-fg2); }
  .foot { display: flex; flex-direction: column; gap: 8px; border-top: 1px solid var(--divider-color, #e1e6ee); padding: 14px 20px 16px; color: var(--gsc-fg2); font-size: 14px; }
  .foot span { display: flex; align-items: center; gap: 10px; }
  .foot .ic { width: 18px; height: 18px; fill: var(--gsc-fg2); }
  .sh { font-size: 20px; font-weight: 700; } .ss { color: var(--gsc-fg2); font-size: 14px; }
  .pad { padding: 14px 16px; }
  .divider { border-top: 1px solid var(--divider-color, #e1e6ee); }
  .stats3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 16px; }
  .stat { background: var(--gsc-tile); border-radius: 16px; padding: 12px 14px; }
  .sv { font-size: 22px; font-weight: 800; } .su { font-size: 14px; font-weight: 600; color: var(--gsc-fg2); }
  .sl { color: var(--gsc-fg2); font-size: 14px; margin-top: 4px; }
  .block { margin: 6px 0 16px; } .bt { font-weight: 700; margin-bottom: 8px; }
  .bt.row2 { display: flex; justify-content: space-between; align-items: center; }
  .split { display: flex; height: 12px; border-radius: 999px; overflow: hidden; background: var(--gsc-track); gap: 2px; }
  .split span { display: block; height: 100%; }
  .legend { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 8px; color: var(--gsc-fg2); font-size: 14px; }
  .legend.small { margin-top: 0; font-weight: 400; font-size: 13px; }
  .legend i { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
  .legend b { color: var(--gsc-fg); } .legend .lu { margin-left: auto; }
  .note { color: var(--gsc-fg2); font-size: 13px; margin-top: 6px; }
  .mnav { display: flex; align-items: center; justify-content: center; gap: 12px; font-weight: 700; margin: 2px 0 14px; }
  .nb { display: grid; place-items: center; width: 36px; height: 36px; border-radius: 50%; border: 1px solid var(--divider-color, #d6dde8); }
  .nb .ic { width: 20px; height: 20px; fill: var(--gsc-fg); } .nb[disabled] { opacity: .35; cursor: default; }
  .chart { display: flex; align-items: flex-end; gap: 3px; height: 110px; }
  .day { position: relative; flex: 1; height: 100%; }
  .day .b { position: absolute; left: 0; right: 0; bottom: 0; border-radius: 3px 3px 1px 1px; min-height: 3px; }
  .day .b.load { background: var(--gsc-track); } .day .b.pv { left: 22%; right: 22%; background: #f0b429; }
  .day.future .b { opacity: .35; }
  .axis { display: flex; justify-content: space-between; color: var(--gsc-fg2); font-size: 13px; margin-top: 6px; }

  .ctl { display: flex; align-items: center; gap: 14px; padding: 10px 4px; }
  .group { background: var(--gsc-tile); border-radius: 16px; padding: 4px 12px; margin: 10px 0; }
  .sw { position: relative; width: 52px; height: 30px; border-radius: 999px; background: var(--gsc-track); transition: background .2s; flex: none; }
  .sw span { position: absolute; top: 3px; left: 3px; width: 24px; height: 24px; border-radius: 50%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.3); transition: left .2s; }
  .sw.on { background: var(--gsc-blue); } .sw.on span { left: 25px; }
  .step { display: inline-flex; align-items: center; gap: 10px; }
  .step b { min-width: 52px; text-align: center; font-size: 17px; }
  .step button { width: 38px; height: 38px; border-radius: 50%; background: var(--card-background-color, #fff); border: 1px solid var(--divider-color, #d6dde8); font-size: 22px; line-height: 1; }
  .kvs { margin-top: 6px; }
  .kv { display: flex; justify-content: space-between; gap: 12px; padding: 10px 2px; border-bottom: 1px solid var(--divider-color, #e8ecf2); }
  .kv span { color: var(--gsc-fg2); } .kv b { text-align: right; }
  .kv b.good { color: var(--gsc-green); } .kv b.bad, .kv b.bad { color: var(--gsc-red); }
`;

// ---------- Editor ----------
class GrowattSphCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
  }

  _render() {
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const c = this._config || {};
    this.shadowRoot.innerHTML = `
      <style>label{display:block;margin:10px 0 4px;font-weight:600}input,select{width:100%;box-sizing:border-box;padding:8px;font:inherit}
      .hint{color:var(--secondary-text-color);font-size:13px;margin-top:4px}</style>
      <label for="v">Ansicht</label>
      <select id="v">${Object.entries(GSC_VIEWS).map(([k, n]) =>
        `<option value="${k}" ${(c.view || "overview") === k ? "selected" : ""}>${gscEsc(n)}</option>`).join("")}</select>
      <label for="t">Titel</label><input id="t" value="${gscEsc(c.title || "")}" placeholder="Standard je nach Ansicht">
      <label for="c">Nutzbare Batteriekapazität (kWh)</label><input id="c" type="number" step="0.1" min="1" value="${gscEsc(c.capacity ?? 7.5)}">
      <div class="hint">Für Restlaufzeit, „nutzbar bis Reserve“ und Vollzyklen.</div>`;
    const fire = () => {
      const cfg = { ...this._config };
      cfg.view = this.shadowRoot.getElementById("v").value;
      const t = this.shadowRoot.getElementById("t").value.trim();
      const cap = parseFloat(this.shadowRoot.getElementById("c").value);
      if (t) cfg.title = t; else delete cfg.title;
      if (Number.isFinite(cap)) cfg.capacity = cap;
      this._config = cfg;
      this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: cfg }, bubbles: true, composed: true }));
    };
    this.shadowRoot.getElementById("t").addEventListener("change", fire);
    this.shadowRoot.getElementById("v").addEventListener("change", fire);
    this.shadowRoot.getElementById("c").addEventListener("change", fire);
  }
}

if (!customElements.get("growatt-sph-card")) customElements.define("growatt-sph-card", GrowattSphCard);
if (!customElements.get("growatt-sph-card-editor")) customElements.define("growatt-sph-card-editor", GrowattSphCardEditor);
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "growatt-sph-card")) {
  window.customCards.push({
    type: "growatt-sph-card",
    name: "Growatt SPH Karte",
    description: "Wechselrichter der Integration Growatt SPH (lokal) – Ansicht wählbar: Übersicht, Heute & Verlauf, Steuerung oder Gerät.",
    preview: true,
  });
}
console.info(`%c GROWATT-SPH-CARD %c ${GSC_VERSION} `, "background:#2f7fe0;color:#fff;border-radius:3px 0 0 3px", "background:#14213d;color:#fff;border-radius:0 3px 3px 0");
