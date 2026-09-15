/* qBittorrent Enhanced Card v0.4.61 */

class QBittorrentEnhancedCard extends HTMLElement {
  static getConfigForm() {
    return {
      schema: [
        {
          name: "entry_id",
          required: true,
          selector: {
            config_entry: {
              integration: "qbittorrent_enhanced",
            },
          },
        },
        {
          name: "title",
          selector: {
            text: {},
          },
        },
        {
          name: "show_title",
          selector: {
            boolean: {},
          },
        },
        {
          name: "auto_marquee",
          selector: {
            boolean: {},
          },
        },
        {
          type: "grid",
          name: "",
          schema: [
            { name: "show_magnet", selector: { boolean: {} } },
            { name: "show_speeds", selector: { boolean: {} } },
            { name: "compact", selector: { boolean: {} } },
          ],
        },
        {
          name: "default_filter",
          selector: {
            select: {
              options: [
                "all",
                "downloading",
                "seeding",
                "paused",
                "error",
              ],
              mode: "dropdown",
            },
          },
        },
        {
          name: "sort",
          selector: {
            select: {
              options: ["name", "progress", "download_speed"],
              mode: "dropdown",
            },
          },
        },
        {
          name: "reverse",
          selector: {
            boolean: {},
          },
        },
        {
          name: "refresh_interval",
          selector: {
            number: {
              min: 5,
              max: 300,
              step: 1,
              mode: "slider",
            },
          },
        },
        {
          name: "max_torrents",
          selector: {
            number: {
              min: 0,
              max: 200,
              step: 1,
              mode: "box",
            },
          },
        },
      ],
      computeLabel: (schema) => ({
        entry_id: "qBittorrent",
        title: "Заголовок",
        show_title: "Показывать заголовок",
        auto_marquee: "Автопрокрутка названий",
        show_magnet: "Показывать Magnet",
        show_speeds: "Показывать скорости",
        compact: "Компактный режим",
        default_filter: "Фильтр по умолчанию",
        sort: "Сортировка",
        reverse: "Обратная сортировка",
        refresh_interval: "Обновление, секунд",
        max_torrents: "Максимум торрентов",
      })[schema.name] || schema.name,
      computeHelper: (schema) => {
        if (schema.name === "entry_id") {
          return "Выберите конкретное подключение qBittorrent";
        }
        return undefined;
      },
    };
  }

  static getStubConfig() {
    return {
      title: "qBittorrent",
      show_title: true,
      auto_marquee: true,
      show_magnet: true,
      show_speeds: true,
      compact: true,
      default_filter: "all",
      sort: "name",
      reverse: false,
      refresh_interval: 15,
      max_torrents: 0,
    };
  }
  constructor() {
    super();
    this._config = {};
    this._hass = null;
    this._entryId = null;
    this._uploadEntity = null;
    this._alternativeSpeedEntity = null;
    this._torrents = [];
    this._server = {};
    this._error = null;
    this._loading = false;
    this._filter = "all";
    this._sort = "name";
    this._reverse = false;
    this._timer = null;
    this._detailsHash = null;
    this._marqueeState = new Map();
  }

  setConfig(config) {
    if (!config || typeof config !== "object") {
      throw new Error("Invalid qBittorrent card configuration");
    }

    this._config = {
      entity: config.entity || null,
      entry_id: config.entry_id || null,
      title: config.title || "qBittorrent",
      show_title: config.show_title !== false,
      auto_marquee: config.auto_marquee !== false,
      show_magnet: config.show_magnet !== false,
      show_speeds: config.show_speeds !== false,
      compact: config.compact !== false,
      default_filter: config.default_filter || "all",
      sort: config.sort || "name",
      reverse: config.reverse === true,
      refresh_interval: Math.max(5, Number(config.refresh_interval || 15)),
      max_torrents: Math.max(0, Number(config.max_torrents || 0)),
      ...config,
    };

    this._entryId = this._config.entry_id || null;
    this._filter = this._config.default_filter || "all";
    this._sort = this._config.sort || "name";
    this._reverse = this._config.reverse === true;
    this._restartTimer();
    this._render();
    if (this._hass) this._start();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;

    if (first) {
      this._render();
    } else {
      // Do not rebuild the whole card on every HA state update.
      // This keeps marquee animations alive between state updates.
      this._updateLiveHeader();
      this._updateAlternativeButton();
    }

    this._start();
  }

  get hass() {
    return this._hass;
  }

  async _start() {
    if (!this._hass || this._starting) return;
    this._starting = true;
    try {
      if (!this._entryId && !this._config.entity) {
        throw new Error("Выберите подключение qBittorrent в настройках карточки");
      }
      if (!this._entryId) await this._resolveEntryId();
      if (this._entryId) {
        await this._resolveUploadEntity();
        await this._resolveAlternativeSpeedEntity();
        await this._load();
        this._restartTimer();
      }
    } finally {
      this._starting = false;
    }
  }

  _restartTimer() {
    if (this._timer) clearInterval(this._timer);
    this._timer = null;
    if (this._entryId && this._hass) {
      this._timer = setInterval(
        () => this._load(),
        this._config.refresh_interval * 1000
      );
    }
  }

  async _resolveEntryId() {
    if (this._entryId || !this._hass) return;

    if (!this._config.entity) {
      throw new Error("Укажите entity сенсора qBittorrent");
    }

    const reg = await this._hass.callWS({
      type: "config/entity_registry/get",
      entity_id: this._config.entity,
    });

    if (!reg?.config_entry_id) {
      throw new Error(`У entity ${this._config.entity} нет config_entry_id`);
    }

    this._entryId = reg.config_entry_id;
    this._error = null;
  }

  async _resolveUploadEntity() {
    if (!this._entryId || !this._hass) return;

    try {
      const reg = await this._hass.callWS({
        type: "config/entity_registry/list",
      });

      const entities = (reg?.entities || []).filter(
        (e) =>
          e.config_entry_id === this._entryId &&
          e.entity_id.startsWith("sensor.")
      );

      if (!this._config.entity) {
        const download = entities.find(
          (e) => /download.*speed|speed.*download/i.test(e.entity_id)
        );
        if (download) this._config.entity = download.entity_id;
      }

      const upload = entities.find(
        (e) => /upload.*speed|speed.*upload/i.test(e.entity_id)
      );

      if (upload) this._uploadEntity = upload.entity_id;
    } catch (_) {
      // Speeds can still be calculated from the torrent list.
    }
  }

  async _resolveAlternativeSpeedEntity() {
    if (!this._entryId || !this._hass) return;

    try {
      const reg = await this._hass.callWS({ type: "config/entity_registry/list" });
      // HA returns config/entity_registry/list as the result array directly.
      const entities = (Array.isArray(reg) ? reg : (reg?.entities || [])).filter(
        (e) => e.config_entry_id === this._entryId && e.entity_id.startsWith("switch.")
      );

      // Backend creates this switch with a stable unique_id:
      // <entry_id>_alternative_speed. Resolve by unique_id first so the
      // card can never accidentally control another switch from the same
      // qBittorrent config entry.
      const uniqueId = `${this._entryId}_alternative_speed`;
      const exact = entities.find((e) => e.unique_id === uniqueId);

      if (exact?.entity_id) {
        this._alternativeSpeedEntity = exact.entity_id;
        return;
      }

      // Compatibility fallback for older backend versions.
      const candidates = entities.filter((e) => {
        const id = String(e.entity_id || "").toLowerCase();
        const name = String(e.original_name || e.name || "").toLowerCase();
        return /alternative|alternate|turtle/.test(id) ||
          /alternative|alternate|turtle/.test(name);
      });

      const preferred = candidates.find((e) => /alternative|turtle/.test(
        `${e.entity_id} ${e.original_name || ""}`.toLowerCase()
      ));

      this._alternativeSpeedEntity = preferred?.entity_id || null;
    } catch (_) {
      this._alternativeSpeedEntity = null;
    }
  }

  _alternativeSpeedState() {
    const state = this._alternativeSpeedEntity
      ? this._hass?.states?.[this._alternativeSpeedEntity]
      : null;
    if (!state) return null;
    if (state.state === "on") return true;
    if (state.state === "off") return false;
    return null;
  }

  async _toggleAlternativeSpeed() {
    if (!this._hass || !this._alternativeSpeedEntity) return;

    const enabled = this._alternativeSpeedState() === true;
    try {
      await this._hass.callService(
        "switch",
        enabled ? "turn_off" : "turn_on",
        { entity_id: this._alternativeSpeedEntity }
      );
      await new Promise((resolve) => setTimeout(resolve, 250));
      await this._resolveAlternativeSpeedEntity();
      this._render();
    } catch (error) {
      this._error = error?.message || "Не удалось переключить альтернативную скорость";
      this._render();
    }
  }

  async _load() {
    if (!this._hass || !this._entryId || this._loading) return;

    this._loading = true;
    if (!this.querySelector(".torrent-list")) {
      this._render();
    }

    try {
      const resultRaw = await this._hass.callWS({
        type: "call_service",
        domain: "qbittorrent_enhanced",
        service: "get_torrents",
        service_data: { entry_id: this._entryId },
        return_response: true,
      });

      const result = resultRaw?.response ?? resultRaw ?? {};
      this._torrents = Array.isArray(result.torrents) ? result.torrents : [];
      this._server = result.server || {};
      this._error = null;
    } catch (error) {
      console.error("[qBittorrent Enhanced Card v0.4.61]", error);
      this._error = error?.message || "Не удалось получить список торрентов";
    } finally {
      this._loading = false;

      // Preserve the existing DOM during refreshes. Only update the parts
      // that actually depend on refreshed torrent data.
      if (this.querySelector(".torrent-list")) {
        this._updateTorrentDom();
        this._updateLiveHeader();
        this._updateAlternativeButton();
      } else {
        this._render();
      }
    }
  }

  async _service(service, data = {}) {
    if (!this._hass || !this._entryId) return;

    try {
      await this._hass.callService("qbittorrent_enhanced", service, {
        entry_id: this._entryId,
        ...data,
      });
      await new Promise((resolve) => setTimeout(resolve, 350));
      await this._load();
    } catch (error) {
      console.error("[qBittorrent Enhanced Card v0.4.61]", error);
      this._error = error?.message || `Ошибка: ${service}`;
      this._render();
    }
  }

  _state(t) {
    const s = String(t.state || "").toLowerCase();

    if (["downloading", "metadl", "forceddl", "stalleddl"].includes(s))
      return ["downloading", "Загрузка", "↓"];
    if (["uploading", "stalledup", "forcedup"].includes(s))
      return ["seeding", "Раздача", "↑"];
    if (["pausedl", "pausedup", "stoppeddl", "stoppedup"].includes(s))
      return ["paused", "Пауза", "Ⅱ"];
    if (["error", "missingfiles"].includes(s))
      return ["error", "Ошибка", "⚠"];
    if (["queuedl", "queueup"].includes(s))
      return ["queued", "В очереди", "⋯"];
    if (["checkingdl", "checkingup", "checkingresumedata"].includes(s))
      return ["checking", "Проверка", "✓"];
    return ["other", t.state || "Неизвестно", "•"];
  }

  _filtered() {
    let list = [...this._torrents];

    if (this._filter === "downloading") {
      list = list.filter((t) => this._state(t)[0] === "downloading");
    } else if (this._filter === "seeding") {
      list = list.filter((t) => this._state(t)[0] === "seeding");
    } else if (this._filter === "paused") {
      list = list.filter((t) => this._state(t)[0] === "paused");
    } else if (this._filter === "error") {
      list = list.filter((t) => this._state(t)[0] === "error");
    }

    const key = this._sort;
    list.sort((a, b) => {
      let av = a[key];
      let bv = b[key];

      if (key === "name") {
        av = String(av || "").toLowerCase();
        bv = String(bv || "").toLowerCase();
      } else {
        av = Number(av ?? 0);
        bv = Number(bv ?? 0);
      }

      if (av < bv) return -1;
      if (av > bv) return 1;
      return 0;
    });

    if (this._reverse) list.reverse();
    if (this._config.max_torrents > 0) {
      list = list.slice(0, this._config.max_torrents);
    }

    return list;
  }

  _formatBytes(value) {
    let n = Number(value || 0);
    if (!Number.isFinite(n) || n <= 0) return "0 B";

    const units = ["B", "KB", "MB", "GB", "TB"];
    let i = 0;
    while (n >= 1024 && i < units.length - 1) {
      n /= 1024;
      i++;
    }

    const digits = n >= 100 ? 0 : n >= 10 ? 1 : 2;
    return `${n.toFixed(digits)} ${units[i]}`;
  }

  _formatRate(value) {
    return `${this._formatBytes(value)}/s`;
  }

  _formatMBps(value, unit = "") {
    let n = Number(value);
    if (!Number.isFinite(n) || n < 0) n = 0;

    const u = String(unit || "").toLowerCase().replace(/\s+/g, "");
    if (u.includes("mb/s") || u.includes("mib/s")) {
      return `${n.toFixed(n >= 100 ? 0 : n >= 10 ? 1 : 2)} MB/s`;
    }
    if (u.includes("kb/s") || u.includes("kib/s")) n *= 1024;
    else if (u === "b/s" || u === "bps" || u.includes("byte/s")) {
      // Already bytes per second.
    } else if (!u) {
      // Backend values are bytes per second.
    }

    const mb = n / (1024 * 1024);
    return `${mb.toFixed(mb >= 100 ? 0 : mb >= 10 ? 1 : 2)} MB/s`;
  }

  _formatEta(value) {
    const n = Number(value);
    if (!Number.isFinite(n) || n < 0 || n >= 8640000) return "—";
    if (n < 60) return `${Math.round(n)}с`;
    if (n < 3600) return `${Math.floor(n / 60)}м`;
    if (n < 86400)
      return `${Math.floor(n / 3600)}ч ${Math.floor((n % 3600) / 60)}м`;
    return `${Math.floor(n / 86400)}д ${Math.floor((n % 86400) / 3600)}ч`;
  }

  _esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[c]));
  }

  _globalSpeedValue(entityId, fallbackKey) {
    const state = entityId ? this._hass?.states?.[entityId] : null;
    if (state && state.state !== "unknown" && state.state !== "unavailable") {
      let n = Number(state.state);
      if (!Number.isFinite(n) || n < 0) n = 0;
      const u = String(state.attributes?.unit_of_measurement || "").toLowerCase().replace(/\s+/g, "");
      if (u.includes("mb/s") || u.includes("mib/s")) return n * 1024 * 1024;
      if (u.includes("kb/s") || u.includes("kib/s")) return n * 1024;
      return n;
    }

    return this._torrents.reduce(
      (sum, t) => sum + Number(t[fallbackKey] || 0),
      0
    );
  }

  _counts() {
    const c = { downloading: 0, seeding: 0, paused: 0, error: 0 };
    for (const t of this._torrents) {
      const s = this._state(t)[0];
      if (c[s] !== undefined) c[s]++;
    }
    return c;
  }

  _render() {
    if (!this.isConnected) return;

    const counts = this._counts();
    const list = this._filtered();
    const downValue = this._globalSpeedValue(this._config.entity, "download_speed");
    const upValue = this._globalSpeedValue(this._uploadEntity, "upload_speed");
    const down = downValue > 0 ? this._formatMBps(downValue, "B/s") : "";
    const up = upValue > 0 ? this._formatMBps(upValue, "B/s") : "";
    const connected = !this._error && !!this._entryId;

    this.innerHTML = `
      <style>
        :host { display:block; }
        ha-card { overflow:hidden; }
        .card { padding: 14px; }
        .header { display:flex; align-items:center; justify-content:space-between; gap:12px; }
        .title { font-size:20px; font-weight:600; line-height:1.2; }
        .subtitle { margin-top:3px; font-size:12px; opacity:.65; }
        .status { display:flex; align-items:center; gap:9px; font-size:12px; }
        .header-speeds { display:flex; align-items:center; gap:6px; white-space:nowrap; }
        .header-speed { display:flex; align-items:center; gap:2px; min-width:20px; }
        .header-speed.down { color:var(--warning-color,#ff9800); }
        .header-speed.up { color:var(--info-color,#03a9f4); }
        .speed-icon { width:15px; height:15px; display:block; flex:none; }
        .speed-value { font-size:12px; line-height:1; font-weight:600; opacity:.9; }
        .header-error { color:var(--error-color,#e53935); font-size:12px; }
        button, select, input {
          font: inherit;
          color: inherit;
        }
        button {
          border:0;
          border-radius:9px;
          background:var(--secondary-background-color);
          cursor:pointer;
        }
        button:hover { filter:brightness(1.12); }
        .icon { width:34px; height:34px; font-size:18px; }
        .magnet-bottom { margin-top:8px; }
        .magnet { display:flex; gap:7px; margin:10px 0; }
        .magnet input {
          flex:1;
          min-width:0;
          border:1px solid var(--divider-color);
          border-radius:9px;
          padding:9px 10px;
          background:var(--primary-background-color);
          outline:none;
        }
        .magnet input:focus { border-color:var(--primary-color); }
        .send { width:40px; font-size:18px; }
        .toolbar { display:flex; margin:7px 0; }
        .view-sort-block {
          display:flex; align-items:center; gap:4px; width:100%; min-width:0;
          padding:2px; border:1px solid var(--divider-color);
          border-radius:11px; background:var(--secondary-background-color);
          overflow:hidden;
        }
        .filters { display:flex; align-items:center; gap:1px; min-width:0; flex:1; overflow-x:auto; scrollbar-width:none; }
        .filters::-webkit-scrollbar { display:none; }
        .filter-btn {
          width:28px; height:28px; flex:0 0 28px; padding:0;
          display:flex; align-items:center; justify-content:center;
          border-radius:8px; background:transparent; opacity:.72;
        }
        .filter-btn:hover { opacity:1; }
        .filter-btn.active { background:var(--primary-color); color:var(--text-primary-color,#fff); opacity:1; }
        .filter-icon { width:15px; height:15px; display:block; }
        .sort { display:flex; align-items:center; gap:2px; flex:0 0 132px; }
        .sort select {
          width:100%; min-width:0; padding:5px 7px;
          border:1px solid var(--divider-color); border-radius:7px;
          background:var(--primary-background-color);
        }
        .sort button { width:28px; height:28px; flex:0 0 28px; font-size:17px; }
        .bottom-controls {
          display:flex; margin-top:5px; padding-top:4px;
          border-top:1px solid var(--divider-color);
        }
        .global-actions {
          display:flex; align-items:center; gap:4px; width:100%;
          padding:2px; border:1px solid var(--divider-color);
          border-radius:11px; background:var(--secondary-background-color);
        }
        .global-actions button {
          width:34px; height:30px; flex:1; padding:0;
          display:flex; align-items:center; justify-content:center;
          border-radius:7px; background:transparent;
        }
        .control-icon { width:18px; height:18px; display:block; }
        .turtle-btn { width:34px; height:30px; display:flex; align-items:center; justify-content:center; padding:0; color:var(--primary-text-color); opacity:.72; }
        .turtle-btn.active { color:#ff9800; opacity:1; background:color-mix(in srgb, #ff9800 18%, var(--secondary-background-color)); }
        .turtle-btn.unavailable { opacity:.35; cursor:not-allowed; }
        .turtle-icon { width:18px; height:18px; display:block; }
        .torrent-list { display:flex; flex-direction:column; gap:6px; }
        .torrent { display:block;
          position:relative;
          padding:10px 10px 9px 10px;
          border-radius:10px;
          background:var(--secondary-background-color);
          border-left:3px solid var(--divider-color);
         align-items:center; width:100%; box-sizing:border-box; min-width:0;}
        .torrent.downloading { border-left-color:var(--info-color,#42a5f5); }
        .torrent.seeding { border-left-color:var(--success-color,#66bb6a); }
        .torrent.paused { border-left-color:var(--disabled-text-color,#888); }
        .torrent.error { border-left-color:var(--error-color,#e53935); }
        .name {
          display:block;
          width:100%;
          box-sizing:border-box;
          font-size:14px;
          font-weight:500;
          white-space:nowrap;
          overflow:hidden;
          text-overflow:clip;
          padding-bottom:2px; max-width:100%; min-width:0;}
        .name-track {
          display:inline-flex;
          white-space:nowrap;
          width:max-content;
          will-change:transform;
          transform:translate3d(0,0,0); max-width:none;}
        .name-copy {
          display:inline-block;
          white-space:nowrap;
          flex:none;
        }
        .name-gap {
          display:inline-block;
          width:56px;
          flex:none;
        }
        .name.marquee .name-track {
          animation-name:qb-name-marquee-loop;
          animation-timing-function:linear;
          animation-iteration-count:infinite;
        }
        @keyframes qb-name-marquee-loop {
          0%, 25% {
            transform:translate3d(0,0,0);
          }
          100% {
            transform:translate3d(var(--qb-marquee-distance),0,0);
          }
        }
        @media (prefers-reduced-motion: reduce) {
          .name.marquee .name-track {
            animation-play-state:paused;
          }
        }
        .meta { display:flex; align-items:center; gap:7px; margin-top:5px; font-size:11px; opacity:.72; }
        .meta .stats { margin-left:0; display:flex; align-items:center; gap:7px; }
        .bar { height:4px; margin-top:8px; border-radius:3px; background:var(--divider-color); overflow:hidden; }
        .bar > div { height:100%; background:var(--primary-color); border-radius:3px; }
        .state { margin-left:8px; flex:0 0 auto; }
        .torrent { cursor:pointer; min-width:0; width:100%; box-sizing:border-box; } .torrent:active { opacity:.86; } .torrent:focus-visible { outline:2px solid var(--primary-color); outline-offset:-2px; }
        .empty { padding:25px 8px; text-align:center; opacity:.55; }
        .errorbox { margin:8px 0; padding:9px 10px; border-radius:8px; background:var(--error-color,#e53935); color:#fff; font-size:12px; word-break:break-word; }
        .overlay {
          position:fixed; inset:0; z-index:1000;
          background:rgba(0,0,0,.55);
          display:flex; align-items:center; justify-content:center;
          padding:16px;
        }
        .dialog {
          width:min(620px,100%);
          max-height:90vh; overflow:auto;
          background:var(--card-background-color,var(--primary-background-color));
          color:var(--primary-text-color);
          border-radius:14px;
          box-shadow:0 10px 40px rgba(0,0,0,.35);
          padding:16px;
        }
        .dialog-head { display:flex; align-items:flex-start; gap:10px; }
        .dialog-title { flex:1; font-size:18px; font-weight:600; }
        .detail-grid { display:grid; grid-template-columns:1fr 1.5fr; gap:8px 14px; margin:15px 0; font-size:13px; }
        .detail-grid span { opacity:.65; }
        .detail-grid b { font-weight:500; word-break:break-word; }
        .dialog-actions { display:flex; flex-wrap:wrap; gap:7px; }
        .dialog-actions button { padding:8px; min-width:46px; min-height:42px; font-size:20px; line-height:1; }
        .danger { color:var(--error-color,#e53935); }
        @media (max-width: 500px) {
          .card { padding:10px; }
          .title { font-size:18px; }
          .torrent { padding-top:9px; }
          .meta { gap:5px; }
        }
      
    
        /* v0.4.61 compact mode: single-line pill torrent rows */
        .card.compact .torrent {
      font-weight: 300;
          display:flex;
          align-items:center;
          gap:10px;
          min-height: 24px;
          height: 24px;
          padding:0 10px;
          margin:0;
          border:0;
          border-radius:8px;
          background:var(--secondary-background-color);
          box-sizing:border-box;
        }
        .card.compact .torrent.downloading {
          background:color-mix(in srgb, var(--secondary-background-color) 88%, var(--info-color,#42a5f5));
        }
        .card.compact .torrent.seeding {
          background:color-mix(in srgb, var(--secondary-background-color) 25%, var(--info-color,#42a5f5));
        }
        .card.compact .torrent.paused {
          background:color-mix(in srgb, var(--secondary-background-color) 82%, var(--disabled-text-color,#888));
        }
        .card.compact .torrent.error {
          background:color-mix(in srgb, var(--secondary-background-color) 78%, var(--error-color,#e53935));
        }
        .card.compact .torrent.queued,
        .card.compact .torrent.checking,
        .card.compact .torrent.other {
          background:var(--secondary-background-color);
        }
        .card.compact .torrent .name {
          flex:1 1 auto;
          width:auto;
          min-width:0;
          max-width:none;
          padding:0;
          font-size:16px;
          line-height:38px;
          font-weight:500;
        }
        .card.compact .torrent .meta {
          flex:0 0 auto;
          display:flex;
          align-items:center;
          margin:0;
          padding:0;
          font-size:16px;
          line-height:1;
          opacity:.95;
        }
        .card.compact .torrent .stats {
          display:none;
        }
        .card.compact .torrent .progress-value {
          margin-left:0 !important;
          white-space:nowrap;
          font-size:16px;
          font-weight:500;
        }
        .card.compact .torrent .bar {
          display:none;
        }
        .card.compact .torrent-list {
          gap:5px;
        }

    .card.compact .magnet input {
      height: 24px;
      min-height: 24px;
      box-sizing: border-box;
    }
    .card.compact .magnet button {
      height: 24px;
      min-height: 24px;
      padding-top: 0;
      padding-bottom: 0;
    }
    
    .card.compact .controls button,
    .card.compact .controls select,
    .card.compact .sort select,
    .card.compact .sort button,
    .card.compact .sort-control {
      height: 24px;
      min-height: 24px;
      box-sizing: border-box;
    }
    .card.compact .controls button {
      padding-top: 0;
      padding-bottom: 0;
    }
    
    /* v0.4.61 compact controls */
    .card.compact .torrent {
      height: 24px !important;
      min-height: 24px !important;
      max-height: 24px !important;
      box-sizing: border-box;
      padding-top: 0 !important;
      padding-bottom: 0 !important;
      font-weight: 300 !important;
    }

    .card.compact .torrent .name,
    .card.compact .torrent .name-copy {
      font-weight: 300 !important;
      line-height: 24px !important;
    }

    .card.compact .controls {
      height: 24px !important;
      min-height: 24px !important;
      box-sizing: border-box;
    }

    .card.compact .controls button,
    .card.compact .controls input,
    .card.compact .controls select {
      height: 24px !important;
      min-height: 24px !important;
      max-height: 24px !important;
      box-sizing: border-box;
      padding-top: 0 !important;
      padding-bottom: 0 !important;
      line-height: 22px !important;
    }

    .card.compact .sort,
    .card.compact .sort-control {
      height: 24px !important;
      min-height: 24px !important;
      box-sizing: border-box;
    }

    .card.compact .sort button,
    .card.compact .sort input,
    .card.compact .sort select,
    .card.compact .sort-control button,
    .card.compact .sort-control input,
    .card.compact .sort-control select {
      height: 24px !important;
      min-height: 24px !important;
      max-height: 24px !important;
      box-sizing: border-box;
      padding-top: 0 !important;
      padding-bottom: 0 !important;
      line-height: 22px !important;
    }

    /* Magnet area stays deliberately larger than the compact 24px controls. */
    .card.compact .magnet {
      min-height: 34px !important;
      height: 34px !important;
      box-sizing: border-box;
    }

    .card.compact .magnet input,
    .card.compact .magnet button {
      height: 34px !important;
      min-height: 34px !important;
      max-height: 34px !important;
      box-sizing: border-box;
      padding-top: 0 !important;
      padding-bottom: 0 !important;
      line-height: 32px !important;
    }
    
    /* v0.4.61 compact empty torrent list */
    .card.compact .torrent-list:has(.empty) {
      height: 24px !important;
      min-height: 24px !important;
      max-height: 24px !important;
      box-sizing: border-box;
    }
    .card.compact .torrent-list .empty {
      height: 24px !important;
      min-height: 24px !important;
      max-height: 24px !important;
      box-sizing: border-box;
      display: flex !important;
      align-items: center !important;
      padding: 0 !important;
      margin: 0 !important;
      line-height: 24px !important;
    }
    
    /* v0.4.61 compact empty state: center the message horizontally */
    .card.compact .torrent-list:has(.empty) {
      display: flex !important;
      justify-content: center !important;
      align-items: center !important;
    }
    .card.compact .torrent-list .empty {
      width: 100% !important;
      justify-content: center !important;
      text-align: center !important;
    }
    
    /* v0.4.61 compact spacing and equal control heights */
    .card.compact .torrent-list {
      margin-bottom: 8px !important;
    }

    .card.compact .divider {
      margin-top: 6px !important;
      margin-bottom: 6px !important;
    }

    .card.compact .controls,
    .card.compact .sort,
    .card.compact .sort-control {
      height: 24px !important;
      min-height: 24px !important;
      max-height: 24px !important;
      box-sizing: border-box !important;
      align-items: center !important;
    }

    .card.compact .controls > *,
    .card.compact .sort > *,
    .card.compact .sort-control > * {
      height: 24px !important;
      min-height: 24px !important;
      max-height: 24px !important;
      box-sizing: border-box !important;
    }
    
/* v0.4.61 compact control spacing */
.card.compact .controls {
  height: 20px !important;
  min-height: 20px !important;
  max-height: 20px !important;
  box-sizing: border-box !important;
}
.card.compact .controls > * {
  height: 20px !important;
  min-height: 20px !important;
  max-height: 20px !important;
  box-sizing: border-box !important;
}
.card.compact .divider {
  margin-bottom: 10px !important;
}

    /* v0.4.61 compact controls: 16px */
    .card.compact .controls {
      height: 16px !important;
      min-height: 16px !important;
      max-height: 16px !important;
      padding: 0 !important;
      margin: 0 !important;
      gap: 0 !important;
      box-sizing: border-box !important;
    }

    .card.compact .controls > * {
      height: 16px !important;
      min-height: 16px !important;
      max-height: 16px !important;
      padding: 0 !important;
      margin: 0 !important;
      box-sizing: border-box !important;
      line-height: 16px !important;
    }
    
    /* v0.4.61 compact global actions */
    .card.compact .global-actions {
      padding: 1px !important;
      box-sizing: border-box !important;
      margin-top: 8px !important;
    }

    .card.compact .global-actions button {
      height: 28px !important;
      min-height: 28px !important;
      max-height: 28px !important;
      padding-top: 0 !important;
      padding-bottom: 0 !important;
      box-sizing: border-box !important;
    }
    
/* v0.4.61 align all compact global action icons */
.card.compact .global-actions button > svg {
  width: 18px !important;
  height: 18px !important;
  display: block !important;
  flex: 0 0 18px !important;
}

    /* v0.4.61 desktop popup: keep popup inside the card, avoid clipping */
    .overlay {
      position: fixed !important;
      inset: 0 !important;
      z-index: 2147483647 !important;
    }
    </style>

      <ha-card>
        <div class="card${this._config.compact ? " compact" : ""}">
          <div class="header">
            <div>
              ${this._config.show_title !== false ? `<div class="title">${this._esc(this._config.title)}</div>` : ""}
              <div class="subtitle">
                ${this._server.version ? `qBittorrent ${this._esc(this._server.version)}` : "qBittorrent Enhanced"}
              </div>
            </div>
            <div class="status">
              ${connected && this._config.show_speeds ? `
                <div class="header-speeds">
                  <div class="header-speed down" title="Загрузка">
                    <svg class="speed-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M5 19h14v2H5zM11 3h2v10.17l3.59-3.58L18 11l-6 6-6-6 1.41-1.41L11 13.17z"/></svg>
                    ${down ? `<span class="speed-value">${this._esc(down)}</span>` : ""}
                  </div>
                  <div class="header-speed up" title="Отдача">
                    <svg class="speed-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M5 3h14v2H5zM13 21h-2V10.83L7.41 14.41 6 13l6-6 6 6-1.41 1.41L13 10.83z"/></svg>
                    ${up ? `<span class="speed-value">${this._esc(up)}</span>` : ""}
                  </div>
                </div>
              ` : connected ? "" : `<span class="header-error">Ошибка</span>`}
            </div>
          </div>

          <div class="toolbar">
            <div class="view-sort-block">
              <div class="filters">
                ${[
                  ["all", "Все", `<svg class="filter-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M4 5h2v2H4zm4 0h12v2H8zM4 11h2v2H4zm4 0h12v2H8zM4 17h2v2H4zm4 0h12v2H8z"/></svg>`],
                  ["downloading", "Скачивается", `<svg class="filter-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M11 3h2v11.17l3.59-3.58L18 12l-6 6-6-6 1.41-1.41L11 14.17zM5 19h14v2H5z"/></svg>`],
                  ["seeding", "Раздается", `<svg class="filter-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M11 21h2V9.83l3.59 3.58L18 12l-6-6-6 6 1.41 1.41L11 9.83zM5 3h14v2H5z"/></svg>`],
                  ["paused", "Пауза", `<svg class="filter-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M6 4h4v16H6zm8 0h4v16h-4z"/></svg>`],
                  ["error", "Ошибка", `<svg class="filter-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 3 2.5 20h19zM11 9h2v5h-2zm0 7h2v2h-2z"/></svg>`],
                ].map(([key,label,icon]) =>
                  `<button class="filter-btn ${this._filter === key ? "active" : ""}" data-filter="${key}" title="${label}" aria-label="${label}">${icon}</button>`
                ).join("")}
              </div>
              <div class="sort">
                <select id="sort" aria-label="Сортировка">
                  <option value="name">Имя</option>
                  <option value="progress">Прогресс</option>
                  <option value="download_speed">Скорость</option>
                </select>
                <button data-action="reverse" title="Обратный порядок" aria-label="Обратный порядок">⇅</button>
              </div>
            </div>
          </div>

          ${this._error ? `<div class="errorbox">${this._esc(this._error)}</div>` : ""}

          <div class="torrent-list">
            ${this._loading && !this._torrents.length
              ? `<div class="empty">Загрузка…</div>`
              : list.length
                ? list.map((t) => this._torrent(t)).join("")
                : `<div class="empty">Нет торрентов</div>`
            }
          </div>

          <div class="bottom-controls">
            <div class="global-actions">
              <button data-action="start-all" title="Возобновить все" aria-label="Возобновить все"><svg class="control-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M8 5v14l11-7z"/></svg></button>
              <button data-action="stop-all" title="Пауза всех" aria-label="Пауза всех"><svg class="control-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M6 5h4v14H6zm8 0h4v14h-4z"/></svg></button>
              <button data-action="recheck-all" title="Проверить все" aria-label="Проверить все"><svg class="control-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="m9 16.17-3.88-3.88L3.71 13.7 9 19l12-12-1.41-1.41z"/></svg></button>
              <button data-action="reannounce-all" title="Обновить трекеры" aria-label="Обновить трекеры"><svg class="control-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M17.65 6.35A7.95 7.95 0 0 0 12 4V1L7 6l5 5V7a5 5 0 1 1-4.9 6H5.02A7 7 0 1 0 17.65 6.35z"/></svg></button>
              <button class="turtle-btn ${this._alternativeSpeedState() === true ? "active" : ""} ${this._alternativeSpeedEntity ? "" : "unavailable"}" data-action="alternative-speed" title="${this._alternativeSpeedState() === true ? "Альтернативная скорость: включена" : this._alternativeSpeedEntity ? "Альтернативная скорость: выключена" : "Альтернативная скорость: переключатель не найден"}" aria-label="Альтернативная скорость" ${this._alternativeSpeedEntity ? "" : "disabled"}>
                <svg class="turtle-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M7.2 16.8c-2.1 0-3.7-1.4-3.7-3.3 0-1.8 1.3-3.1 3.1-3.3.5-2.8 2.9-4.8 5.8-4.8 3.3 0 6 2.4 6.2 5.6 1.4.3 2.4 1.4 2.4 2.8 0 1.7-1.4 3-3.2 3H7.2zm3.4-7.1c-.6 0-1.1.5-1.1 1.1s.5 1.1 1.1 1.1 1.1-.5 1.1-1.1-.5-1.1-1.1-1.1zm4.4 0c-.6 0-1.1.5-1.1 1.1s.5 1.1 1.1 1.1 1.1-.5 1.1-1.1-.5-1.1-1.1-1.1zM5.8 7.4 4.3 5.9l1.4-1.4 1.5 1.5-1.4 1.4zm11.9 0-1.4-1.4 1.5-1.5 1.4 1.4-1.5 1.5zM12 4.6h-2V2h2v2.6z"/></svg>
              </button>
            </div>
          </div>

          ${this._config.show_magnet ? `
            <div class="magnet magnet-bottom">
              <input id="magnet" type="text" placeholder="Вставьте Magnet-ссылку">
              <button class="send" data-action="magnet" title="Добавить торрент">➤</button>
            </div>
          ` : ""}
        </div>
      </ha-card>
    `;

    this._bind();
    if (this._detailsHash) this._openDetails(this._detailsHash);
  }

  _torrent(t) {
    const progress = Math.max(
      0,
      Math.min(100, Number(t.progress || 0) * 100)
    );
    const [stateClass] = this._state(t);

    return `
      <div class="torrent ${stateClass}" data-hash="${this._esc(t.hash)}" data-name="${this._esc(t.name)}" role="button" tabindex="0" aria-label="Подробнее: ${this._esc(t.name)}">
        <div class="name" title="${this._esc(t.name)}">
          <span class="name-track">
            <span class="name-copy">${this._esc(t.name)}</span>
            <span class="name-gap" aria-hidden="true"></span>
            <span class="name-copy" aria-hidden="true">${this._esc(t.name)}</span>
            <span class="name-gap" aria-hidden="true"></span>
          </span>
        </div>
        <div class="meta">
          <span class="stats">
            ${this._config.show_speeds ? `<span>${this._formatRate(t.download_speed)} ↓</span>` : ""}
            ${this._config.show_speeds ? `<span>${this._formatRate(t.upload_speed)} ↑</span>` : ""}
            ${stateClass === "downloading" && Number(t.eta) >= 0 ? `<span>ETA ${this._formatEta(t.eta)}</span>` : ""}
          </span>
          <span class="progress-value" style="margin-left:auto">${progress.toFixed(0)}%</span>
        </div>
        <div class="bar"><div style="width:${progress}%"></div></div>
      </div>
    `;
  }

  _updateLiveHeader() {
    if (!this._hass) return;

    const downValue = this._globalSpeedValue(this._config.entity, "download_speed");
    const upValue = this._globalSpeedValue(this._uploadEntity, "upload_speed");
    const down = downValue > 0 ? this._formatMBps(downValue, "B/s") : "";
    const up = upValue > 0 ? this._formatMBps(upValue, "B/s") : "";

    const downEl = this.querySelector(".header-speed.down .speed-value");
    const upEl = this.querySelector(".header-speed.up .speed-value");

    if (downEl) downEl.textContent = down;
    if (upEl) upEl.textContent = up;
  }

  _updateTorrentDom() {
    const list = this.querySelector(".torrent-list");
    if (!list) return;

    const visible = this._filtered();
    const existing = new Map(
      [...list.querySelectorAll(".torrent")].map((el) => [el.dataset.hash, el])
    );

    // If the visible set/order changed, rebuild only the torrent list.
    const hashes = visible.map((t) => t.hash);
    const currentHashes = [...list.querySelectorAll(".torrent")].map(
      (el) => el.dataset.hash
    );

    const same =
      hashes.length === currentHashes.length &&
      hashes.every((hash, i) => hash === currentHashes[i]);

    if (!same) {
      list.innerHTML = visible.length
        ? visible.map((t) => this._torrent(t)).join("")
        : `<div class="empty">Нет торрентов</div>`;
      this._bindTorrentListOnly();
      return;
    }

    // Empty -> empty is a special case: the row list itself did not change,
    // but the placeholder must change from "Загрузка…" to "Нет торрентов"
    // after the request has completed.
    if (!visible.length) {
      const empty = list.querySelector(".empty");
      if (empty) empty.textContent = "Нет торрентов";
      return;
    }

    // Same rows: update only changing values, leaving .name-track untouched.
    visible.forEach((t) => {
      const row = existing.get(t.hash);
      if (!row) return;

      const progress = Math.max(0, Math.min(100, Number(t.progress || 0) * 100));
      const [stateClass] = this._state(t);

      row.classList.remove("downloading", "seeding", "paused", "error", "queued", "checking", "other");
      row.classList.add(stateClass);

      const meta = row.querySelector(".meta");
      if (meta) {
        meta.innerHTML = `
          <span class="stats">
            ${this._config.show_speeds ? `<span>${this._formatRate(t.download_speed)} ↓</span>` : ""}
            ${this._config.show_speeds ? `<span>${this._formatRate(t.upload_speed)} ↑</span>` : ""}
            ${stateClass === "downloading" && Number(t.eta) >= 0 ? `<span>ETA ${this._formatEta(t.eta)}</span>` : ""}
          </span>
          <span class="progress-value" style="margin-left:auto">${progress.toFixed(0)}%</span>
        `;
      }

      const bar = row.querySelector(".bar > div");
      if (bar) bar.style.width = `${progress}%`;
    });
  }

  _bindTorrentListOnly() {
    this.querySelectorAll(".torrent").forEach((row) => {
      const open = () => this._openDetails(row.dataset.hash);

      row.onclick = (event) => {
        // Ignore clicks on actual interactive controls if any are added later.
        if (event.target.closest("button, input, select, textarea, a")) return;
        open();
      };

      row.onkeydown = (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          open();
        }
      };
    });
  }

  _updateAlternativeButton() {
    const button = this.querySelector('[data-action="alternative-speed"]');
    if (!button) return;

    const state = this._alternativeSpeedState();
    button.classList.toggle("active", state === true);
    button.classList.toggle("unavailable", !this._alternativeSpeedEntity);
    button.disabled = !this._alternativeSpeedEntity;
    button.title = state === true
      ? "Альтернативная скорость: включена"
      : this._alternativeSpeedEntity
        ? "Альтернативная скорость: выключена"
        : "Альтернативная скорость: переключатель не найден";
  }

  _initMarquees() {
    if (this._config.auto_marquee === false) return;

    // Wait for layout so clientWidth/scrollWidth are real values.
    requestAnimationFrame(() => {
      this.querySelectorAll(".name").forEach((name) => {
        const track = name.querySelector(".name-track");
        const firstCopy = name.querySelector(".name-copy");
        const gap = name.querySelector(".name-gap");
        if (!track || !firstCopy || !gap) return;

        const overflow = Math.max(0, firstCopy.scrollWidth - name.clientWidth);
        if (overflow <= 6) {
          track.style.animation = "none";
          track.style.transform = "translate3d(0,0,0)";
          return;
        }

        // The animation moves exactly one copy + one gap. The second copy
        // is already in place, so when the animation loops there is no jump.
        const loopDistance = firstCopy.scrollWidth + gap.getBoundingClientRect().width;
        name.classList.add("marquee");
        name.style.setProperty("--qb-marquee-distance", `${-loopDistance}px`);

        // Constant, calm speed. Long names naturally take longer to loop.
        const moveDuration = Math.max(8, loopDistance / 28);
        const pauseDuration = 10;
        const totalDuration = pauseDuration + moveDuration;
        track.style.animationDuration = `${totalDuration}s`;
      });
    });
  }


  _bind() {
    this.querySelectorAll("[data-filter]").forEach((button) => {
      button.onclick = () => {
        this._filter = button.dataset.filter;
        this._render();
      };
    });

    const sort = this.querySelector("#sort");
    if (sort) {
      sort.value = this._sort;
      sort.onchange = () => {
        this._sort = sort.value;
        this._render();
      };
    }

    this.querySelectorAll("[data-action]").forEach((button) => {
      button.onclick = () =>
        this._handle(button.dataset.action, button.dataset.hash);
    });

    this._initMarquees();

    const magnet = this.querySelector("#magnet");
    if (magnet) {
      magnet.addEventListener("keydown", (event) => {
        if (event.key === "Enter") this._handle("magnet");
      });
    }
  }

  async _handle(action, hash) {
    if (action === "refresh") return this._load();

    if (action === "alternative-speed") return this._toggleAlternativeSpeed();

    if (action === "reverse") {
      this._reverse = !this._reverse;
      return this._render();
    }

    if (action === "magnet") {
      const input = this.querySelector("#magnet");
      const value = input?.value.trim();

      if (!value) return;
      if (!value.toLowerCase().startsWith("magnet:?")) {
        this._error = "Нужна magnet-ссылка, начинающаяся с magnet:?";
        return this._render();
      }

      if (input) input.value = "";
      await this._service("add_magnet", { magnet_url: value });
      return;
    }

    if (action === "details") {
      return this._openDetails(hash);
    }

    const serviceMap = {
      "start-all": "start_torrent",
      "stop-all": "stop_torrent",
      "recheck-all": "recheck_torrent",
      "reannounce-all": "reannounce_torrent",
    };

    if (serviceMap[action]) {
      const hashes = this._torrents.map((t) => t.hash).filter(Boolean);
      if (!hashes.length) return;
      return this._service(serviceMap[action], { hashes });
    }
  }

  _openDetails(hash) {
    const torrent = this._torrents.find((t) => t.hash === hash);
    if (!torrent) return;

    this._detailsHash = hash;
    const old = document.querySelector(
      'qbittorrent-enhanced-card .overlay'
    );
    if (old) old.remove();

    const [stateClass, stateText] = this._state(torrent);
    const progress = (Number(torrent.progress || 0) * 100).toFixed(1);
    const paused = stateClass === "paused";

    const overlay = document.createElement("div");
    overlay.className = "overlay";
    overlay.innerHTML = `
      <div class="dialog">
        <div class="dialog-head">
          <div class="dialog-title">${this._esc(torrent.name)}</div>
          <button class="icon close" title="Закрыть">×</button>
        </div>

        <div class="detail-grid">
          <span>Состояние</span><b>${this._esc(stateText)}</b>
          <span>Прогресс</span><b>${progress}%</b>
          <span>Размер</span><b>${this._formatBytes(torrent.total_size || torrent.size)}</b>
          <span>Осталось</span><b>${this._formatBytes(torrent.amount_left)}</b>
          <span>Загрузка</span><b>${this._formatRate(torrent.download_speed)}</b>
          <span>Отдача</span><b>${this._formatRate(torrent.upload_speed)}</b>
          <span>ETA</span><b>${this._formatEta(torrent.eta)}</b>
          <span>Ratio</span><b>${Number(torrent.ratio || 0).toFixed(2)}</b>
          <span>Seeds / Peers</span><b>${Number(torrent.num_seeds || 0)} / ${Number(torrent.num_leechs || 0)}</b>
          <span>Категория</span><b>${this._esc(torrent.category || "—")}</b>
          <span>Теги</span><b>${this._esc((torrent.tags || []).join(", ") || "—")}</b>
          <span>Путь</span><b>${this._esc(torrent.save_path || "—")}</b>
          <span>Hash</span><b>${this._esc(torrent.hash)}</b>
        </div>

        <div class="dialog-actions">
          <button
            data-dlg="${paused ? "start" : "stop"}"
            title="${paused ? "Возобновить" : "Пауза"}"
            aria-label="${paused ? "Возобновить" : "Пауза"}"
          >${paused ? "▶️" : "⏸️"}</button>
          <button data-dlg="recheck" title="Проверить" aria-label="Проверить">✔️</button>
          <button data-dlg="reannounce" title="Обновить трекеры" aria-label="Обновить трекеры">🔄</button>
          <button class="danger" data-dlg="delete" title="Удалить торрент" aria-label="Удалить торрент">🗑️</button>
          <button class="danger" data-dlg="delete-files" title="Удалить торрент и файлы" aria-label="Удалить торрент и файлы">🔥</button>
        </div>
      </div>
    `;

    this.appendChild(overlay);

    overlay.querySelector(".close").onclick = () => {
      this._detailsHash = null;
      overlay.remove();
    };

    overlay.onclick = (event) => {
      if (event.target === overlay) {
        this._detailsHash = null;
        overlay.remove();
      }
    };

    overlay.querySelectorAll("[data-dlg]").forEach((button) => {
      button.onclick = async () => {
        const action = button.dataset.dlg;

        if (action === "delete" || action === "delete-files") {
          const text =
            action === "delete-files"
              ? "Удалить торрент вместе со всеми файлами?"
              : "Удалить торрент?";
          if (!confirm(text)) return;
        }

        const map = {
          start: "start_torrent",
          stop: "stop_torrent",
          recheck: "recheck_torrent",
          reannounce: "reannounce_torrent",
          delete: "delete_torrent",
          "delete-files": "delete_torrent",
        };

        const data = { hash: torrent.hash };
        if (action === "delete-files") data.delete_files = true;

        this._detailsHash = null;
        overlay.remove();
        await this._service(map[action], data);
      };
    });
  }

  disconnectedCallback() {
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
  }

  getCardSize() {
    return Math.max(3, Math.ceil((this._torrents.length || 1) / 2) + 3);
  }
}

if (!customElements.get("qbittorrent-enhanced-card")) {
  customElements.define("qbittorrent-enhanced-card", QBittorrentEnhancedCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "qbittorrent-enhanced-card")) {
  window.customCards.push({
    type: "qbittorrent-enhanced-card",
    name: "qBittorrent Enhanced Card",
    description: "Torrent management card for qBittorrent Enhanced",
    preview: false,
  });
}
