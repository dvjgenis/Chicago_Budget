(function () {
  "use strict";

  let YEAR = "";
  let GROSS = 0;
  let NET = 0;
  let TRANSFERS = 0;
  let LOCAL = 0;
  let GRANT = 0;
  let FUNDS = [];
  let SERVICES = [];
  let FLOWS = [];
  let DEPARTMENTS = {};
  let YOY = [];
  let INSIGHTS = [];
  let FILTERS = [{ id: "all", label: "Everything" }];
  let HINTS = {};
  let ready = false;

  const state = { selected: null, hover: null, drawn: false, filter: "all" };

  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text || "";
  }

  function applyPayload(g) {
    if (!g) return false;
    YEAR = g.year || "";
    GROSS = Number(g.gross) || 0;
    NET = Number(g.net) || 0;
    TRANSFERS = Number(g.transfers) || 0;
    LOCAL = Number(g.local) || 0;
    GRANT = Number(g.grant) || 0;
    FUNDS = g.funds || [];
    SERVICES = g.services || [];
    FLOWS = g.flows || [];
    DEPARTMENTS = g.departments || {};
    YOY = g.yoy || [];
    INSIGHTS = g.takes || [];
    FILTERS = (g.filters && g.filters.length) ? g.filters : [{ id: "all", label: "Everything" }];
    HINTS = g.hints || {};
    setText("glance-headline", g.headline);
    setText("glance-lede", g.lede);
    setText("glance-caption", g.caption);
    setText("glance-yoy-kicker", g.yoy_kicker);
    setText("glance-yoy-title", g.yoy_title);
    setText("glance-yoy-caption", g.yoy_caption);
    const yoyPanel = document.getElementById("glance-yoy-panel");
    if (yoyPanel) yoyPanel.hidden = !YOY.length;
    ready = true;
    return true;
  }

  function loadFromPage() {
    if (ready) return true;
    const dataEl = document.getElementById("budget-data");
    if (!dataEl) return false;
    try {
      const data = JSON.parse(dataEl.textContent);
      return applyPayload(data.glance);
    } catch (err) {
      return false;
    }
  }

  function money(n) {
    const abs = Math.abs(n);
    if (abs >= 1e9) return (n < 0 ? "-" : "") + "$" + (abs / 1e9).toFixed(2) + "B";
    if (abs >= 1e6) {
      const m = abs / 1e6;
      const digits = m >= 100 ? 0 : 1;
      return (n < 0 ? "-" : "") + "$" + m.toFixed(digits).replace(/\.0$/, "") + "M";
    }
    return (n < 0 ? "-" : "") + "$" + Math.round(abs).toLocaleString("en-US");
  }

  function pct(part, whole) {
    return ((part / whole) * 100).toFixed(1) + "%";
  }

  function byId(id) {
    return FUNDS.find(function (d) { return d.id === id; }) || SERVICES.find(function (d) { return d.id === id; });
  }

  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;");
  }

  function connectedIds(id) {
    const set = new Set([id, "all", "local", "grantTop"]);
    if (id === "all") {
      FUNDS.forEach(function (f) { set.add(f.id); });
      SERVICES.forEach(function (s) { set.add(s.id); });
      return set;
    }
    if (id === "local") {
      FUNDS.filter(function (f) { return f.group === "local"; }).forEach(function (f) { set.add(f.id); });
      FLOWS.forEach(function (row) {
        if (byId(row[0]).group === "local") set.add(row[1]);
      });
      return set;
    }
    if (id === "grantTop" || id === "grant") {
      set.add("grant");
      set.add("grantTop");
      FLOWS.forEach(function (row) {
        if (row[0] === "grant") set.add(row[1]);
      });
      return set;
    }
    FLOWS.forEach(function (row) {
      if (row[0] === id) set.add(row[1]);
      if (row[1] === id) set.add(row[0]);
    });
    const item = byId(id);
    if (item && item.group === "local") set.add("local");
    if (item && (item.group === "grant" || id === "grant")) {
      set.add("grantTop");
      set.add("grant");
    }
    if (SERVICES.some(function (s) { return s.id === id; })) {
      FLOWS.forEach(function (row) {
        if (row[1] === id && byId(row[0]).group === "local") set.add("local");
        if (row[1] === id && row[0] === "grant") set.add("grantTop");
      });
    }
    return set;
  }

  function layoutNodes(items, x, width, height, y0) {
    const gap = 8;
    const minH = 18;
    const usable = height - gap * (items.length - 1);
    const total = items.reduce(function (s, d) { return s + d.value; }, 0);
    let heights = items.map(function (d) { return (d.value / total) * usable; });
    heights = heights.map(function (h) { return Math.max(h, minH); });
    const extra = heights.reduce(function (s, h) { return s + h; }, 0) - usable;
    if (extra > 0) {
      const shrinkable = heights.map(function (h, i) { return h > minH ? i : -1; }).filter(function (i) { return i >= 0; });
      const shrinkSum = shrinkable.reduce(function (s, i) { return s + (heights[i] - minH); }, 0);
      shrinkable.forEach(function (i) {
        heights[i] -= extra * ((heights[i] - minH) / shrinkSum);
      });
    }
    let y = y0;
    return items.map(function (d, i) {
      const node = Object.assign({}, d, { x: x, y: y, w: width, h: heights[i] });
      y += heights[i] + gap;
      return node;
    });
  }

  function flowPath(x0, y0, x1, y1, h) {
    const mx = (x0 + x1) / 2;
    return ["M", x0, y0, "C", mx, y0, mx, y1, x1, y1, "L", x1, y1 + h, "C", mx, y1 + h, mx, y0 + h, x0, y0 + h, "Z"].join(" ");
  }

  function renderSankey() {
    const host = document.getElementById("sankey");
    if (!host || host.offsetParent === null && host.clientWidth === 0) return;
    const width = Math.max(host.clientWidth || 1100, 640);
    const height = 640;
    const padTop = 28;
    const colW = Math.min(168, Math.max(118, width * 0.13));
    const innerH = height - padTop - 8;
    const x0 = 8;
    const x1 = width * 0.28 - colW / 2;
    const x2 = width * 0.54 - colW / 2;
    const x3 = width - colW - 8;

    const allNode = layoutNodes([{ id: "all", name: "All funds", value: GROSS, short: "All funds" }], x0, colW, innerH, padTop)[0];
    const mid = layoutNodes([
      { id: "local", name: "Local Funds", short: "Local funds", value: LOCAL },
      { id: "grantTop", name: "Grant Funds", short: "Grant funds", value: GRANT }
    ], x1, colW, innerH, padTop);
    const fundNodes = layoutNodes(FUNDS, x2, colW, innerH, padTop);
    const serviceNodes = layoutNodes(SERVICES, x3, colW, innerH, padTop);
    const nodes = [allNode].concat(mid, fundNodes, serviceNodes);

    const fundY = {};
    const fundHLeft = {};
    const fundScale = {};
    fundNodes.forEach(function (n) {
      fundY[n.id] = n.y;
      fundHLeft[n.id] = 0;
      fundScale[n.id] = n.h / n.value;
    });
    const serviceY = {};
    const serviceHLeft = {};
    const serviceScale = {};
    serviceNodes.forEach(function (n) {
      serviceY[n.id] = n.y;
      serviceHLeft[n.id] = 0;
      serviceScale[n.id] = n.h / n.value;
    });

    const ribbons = FLOWS.map(function (row) {
      const fid = row[0];
      const sid = row[1];
      const value = row[2];
      const h = Math.max(1.2, value * fundScale[fid]);
      const yL = fundY[fid] + fundHLeft[fid];
      const yR = serviceY[sid] + serviceHLeft[sid];
      fundHLeft[fid] += h;
      serviceHLeft[sid] += value * serviceScale[sid];
      const src = fundNodes.find(function (n) { return n.id === fid; });
      return { fid: fid, sid: sid, value: value, d: flowPath(src.x + src.w, yL, serviceNodes[0].x, yR, h) };
    });

    const localNode = mid[0];
    const grantNode = mid[1];
    const leftRibbons = [
      { fid: "all", sid: "local", value: LOCAL, d: flowPath(allNode.x + allNode.w, allNode.y, localNode.x, localNode.y, localNode.h) },
      { fid: "all", sid: "grantTop", value: GRANT, d: flowPath(allNode.x + allNode.w, allNode.y + localNode.h + 8, grantNode.x, grantNode.y, grantNode.h) }
    ];

    const localFunds = fundNodes.filter(function (n) { return n.group === "local"; });
    const localTotalH = localFunds.reduce(function (s, n) { return s + n.h; }, 0);
    let localCursor = localNode.y;
    const midRibbons = localFunds.map(function (n) {
      const h = n.h * (localNode.h / localTotalH);
      const ribbon = { fid: "local", sid: n.id, value: n.value, d: flowPath(localNode.x + localNode.w, localCursor, n.x, n.y, n.h) };
      localCursor += h;
      return ribbon;
    });
    const grantFund = fundNodes.find(function (n) { return n.id === "grant"; });
    midRibbons.push({
      fid: "grantTop",
      sid: "grant",
      value: GRANT,
      d: flowPath(grantNode.x + grantNode.w, grantNode.y, grantFund.x, grantFund.y, grantNode.h)
    });

    const allRibbons = leftRibbons.concat(midRibbons, ribbons);
    const svg = ['<svg viewBox="0 0 ' + width + " " + height + '" role="img" aria-label="Sankey diagram of the 2026 Chicago budget">'];
    ["All funds", "Source", "Fund type", "City function"].forEach(function (label, i) {
      svg.push('<text class="col-label" x="' + [x0, x1, x2, x3][i] + '" y="16">' + label + "</text>");
    });
    allRibbons.forEach(function (r) {
      svg.push('<path class="flow" data-fid="' + r.fid + '" data-sid="' + r.sid + '" data-value="' + r.value + '" d="' + r.d + '"></path>');
    });
    nodes.forEach(function (n) {
      const fill = n.id === "gfr" ? "#082f5b" : (n.id === "grant" || n.id === "grantTop" ? "#3d8fd9" : "#0b5cab");
      const showInside = n.h >= 34;
      const name = n.short || n.name;
      svg.push('<g class="node" data-id="' + n.id + '">');
      svg.push('<rect x="' + n.x + '" y="' + n.y + '" width="' + n.w + '" height="' + n.h + '" rx="3" fill="' + fill + '"></rect>');
      if (showInside) {
        svg.push('<text class="name" x="' + (n.x + 8) + '" y="' + (n.y + 16) + '">' + escapeHtml(name) + "</text>");
        svg.push('<text class="amt" x="' + (n.x + 8) + '" y="' + (n.y + 30) + '">' + money(n.value) + "</text>");
      } else {
        svg.push('<text class="name" x="' + (n.x + 8) + '" y="' + (n.y + Math.max(12, n.h - 4)) + '" font-size="10">' + escapeHtml(name) + "</text>");
      }
      svg.push("</g>");
    });
    svg.push("</svg>");
    host.innerHTML = svg.join("");
    bindChart(host);
    applyFocus();
    state.drawn = true;
  }

  function applyFocus() {
    const host = document.getElementById("sankey");
    if (!host) return;
    const active = state.selected || state.hover || (state.filter !== "all" ? state.filter : null);
    const keep = active ? connectedIds(active) : null;
    host.querySelectorAll(".node").forEach(function (el) {
      const id = el.getAttribute("data-id");
      el.classList.toggle("dim", !!(keep && !keep.has(id) && id !== "all"));
      el.classList.toggle("active", state.selected === id);
    });
    host.querySelectorAll(".flow").forEach(function (el) {
      const fid = el.getAttribute("data-fid");
      const sid = el.getAttribute("data-sid");
      const on = !keep || (keep.has(fid) && keep.has(sid));
      el.classList.toggle("dim", !on);
      el.classList.toggle("hot", !!(keep && on));
    });
  }

  function labelOf(id) {
    if (id === "all") return "All funds";
    if (id === "local") return "Local funds";
    if (id === "grantTop") return "Grant funds";
    const item = byId(id);
    return item ? item.name : id;
  }

  function nodeTip(id) {
    if (id === "all") {
      const extra = TRANSFERS
        ? "<br>" + money(NET) + " after removing " + money(TRANSFERS) + " of transfers and debt proceeds"
        : "";
      return "<strong>All funds</strong>" + money(GROSS) + " appropriated" + extra;
    }
    if (id === "local") {
      const extra = HINTS.local ? "<br>" + escapeHtml(HINTS.local) : "";
      return "<strong>Local funds</strong>" + money(LOCAL) + " · " + pct(LOCAL, GROSS) + " of the appropriation" + extra;
    }
    if (id === "grantTop") return "<strong>Grant funds</strong>" + money(GRANT) + " · " + pct(GRANT, GROSS);
    const item = byId(id);
    return "<strong>" + escapeHtml(item.name) + "</strong>" + money(item.value) + " · " + pct(item.value, GROSS) + " of the appropriation<br>" + escapeHtml(item.blurb);
  }

  function showTip(ev, html) {
    const tip = document.getElementById("glance-tooltip");
    const host = document.getElementById("sankey");
    if (!tip || !host) return;
    const frame = host.getBoundingClientRect();
    tip.innerHTML = html;
    tip.classList.add("show");
    tip.style.left = ev.clientX - frame.left + 14 + "px";
    tip.style.top = ev.clientY - frame.top - 8 + "px";
  }

  function hideTip() {
    const tip = document.getElementById("glance-tooltip");
    if (tip) tip.classList.remove("show");
  }

  function bindChart(host) {
    host.querySelectorAll(".node").forEach(function (el) {
      el.addEventListener("mouseenter", function (ev) {
        const id = el.getAttribute("data-id");
        state.hover = id;
        showTip(ev, nodeTip(id));
        applyFocus();
      });
      el.addEventListener("mousemove", function (ev) {
        showTip(ev, nodeTip(el.getAttribute("data-id")));
      });
      el.addEventListener("mouseleave", function () {
        state.hover = null;
        hideTip();
        applyFocus();
      });
      el.addEventListener("click", function () {
        selectNode(el.getAttribute("data-id"));
      });
    });
    host.querySelectorAll(".flow").forEach(function (el) {
      function tipHtml() {
        const fid = el.getAttribute("data-fid");
        const sid = el.getAttribute("data-sid");
        const value = Number(el.getAttribute("data-value"));
        return "<strong>" + escapeHtml(labelOf(fid)) + " → " + escapeHtml(labelOf(sid)) + "</strong>" + money(value) + " · " + pct(value, GROSS) + " of the appropriation";
      }
      el.addEventListener("mouseenter", function (ev) {
        state.hover = el.getAttribute("data-sid");
        applyFocus();
        showTip(ev, tipHtml());
      });
      el.addEventListener("mousemove", function (ev) { showTip(ev, tipHtml()); });
      el.addEventListener("mouseleave", function () {
        state.hover = null;
        hideTip();
        applyFocus();
      });
      el.addEventListener("click", function () {
        selectNode(el.getAttribute("data-sid"));
      });
    });
  }

  function syncChrome() {
    const reset = document.getElementById("glance-reset");
    if (reset) reset.hidden = !state.selected;
    applyFocus();
    renderDetail();
    renderTakeaway();
    renderFilters();
    renderInsights();
  }

  function filterFor(id) {
    if (!id) return "all";
    if (id === "grant" || id === "grantTop") return "grantTop";
    if (FILTERS.some(function (f) { return f.id === id; })) return id;
    return "all";
  }

  function canonicalId(id) {
    return id === "grantTop" ? "grant" : id;
  }

  function selectNode(id) {
    const next = canonicalId(id);
    state.selected = state.selected === next ? null : next;
    state.filter = filterFor(state.selected);
    syncChrome();
    if (state.selected) {
      const box = document.getElementById("glance-detail");
      if (box) box.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }

  function setFilter(id) {
    const next = canonicalId(id);
    if (!next || next === "all" || next === state.selected) {
      state.filter = "all";
      state.selected = null;
    } else {
      state.selected = next;
      state.filter = filterFor(next);
    }
    syncChrome();
  }

  function renderInsights() {
    const host = document.getElementById("glance-insights");
    if (!host) return;
    host.innerHTML = INSIGHTS.map(function (card) {
      const on = state.selected === card.id;
      return '<button type="button" class="insight' + (on ? " on" : "") + '" data-insight="' + card.id + '">' +
        '<p class="insight-kicker">' + escapeHtml(card.kicker) + "</p>" +
        "<h3>" + escapeHtml(card.title) + "</h3>" +
        "<p>" + escapeHtml(card.body) + "</p></button>";
    }).join("");
    host.querySelectorAll("[data-insight]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        setFilter(btn.getAttribute("data-insight"));
      });
    });
  }

  function renderFilters() {
    const host = document.getElementById("glance-filters");
    if (!host) return;
    host.innerHTML = FILTERS.map(function (chip) {
      const on = state.filter === chip.id;
      return '<button type="button" class="chip' + (on ? " on" : "") + '" data-filter="' + chip.id + '"' +
        (on ? ' aria-pressed="true"' : ' aria-pressed="false"') + ">" + escapeHtml(chip.label) + "</button>";
    }).join("");
    host.querySelectorAll("[data-filter]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        setFilter(btn.getAttribute("data-filter"));
      });
    });
  }

  function renderTakeaway() {
    const el = document.getElementById("glance-takeaway");
    if (!el) return;
    const id = state.selected;
    if (!id || id === "all") {
      el.textContent = "Click a takeaway or a bar. Esc clears the focus. 1 and 2 switch pages.";
      return;
    }
    if (HINTS[id]) {
      el.textContent = HINTS[id];
      return;
    }
    const item = byId(id === "grantTop" ? "grant" : id);
    if (item) {
      el.textContent = item.name + " is " + money(item.value) + " — " + pct(item.value, GROSS) + " of the appropriation. " + item.blurb;
      return;
    }
    el.textContent = labelOf(id);
  }

  function openExplore(fund, department) {
    if (window.ChicagoExplore) {
      window.ChicagoExplore.open(fund || "All funds", department || "All departments");
    } else {
      location.hash = "explore";
    }
  }

  function renderDetail() {
    const box = document.getElementById("glance-detail");
    if (!box) return;
    const id = state.selected;
    if (!id || id === "all") {
      box.className = "glance-detail";
      box.innerHTML = "";
      return;
    }
    const resolved = id === "grantTop" ? "grant" : id;
    const item = byId(resolved) || {
      name: labelOf(id),
      value: id === "local" ? LOCAL : GRANT,
      blurb: id === "local" ? "Every non-grant city fund, before the transfer deduction." : "Federal, state, and private awards."
    };
    let html = "<p class='ui-caps'>Selected</p><h3>" + escapeHtml(item.name) + "</h3>";
    html += "<p>" + money(item.value) + " · " + pct(item.value, GROSS) + " of the " + money(GROSS) + " appropriation. " + escapeHtml(item.blurb || "") + "</p>";

    if (DEPARTMENTS[resolved]) {
      const rows = DEPARTMENTS[resolved];
      const max = rows[0][1];
      html += "<table class='dept-table'><thead><tr><th>Department</th><th class='num'>" + escapeHtml(YEAR || "This year") + "</th><th class='num'>Share</th><th></th></tr></thead><tbody>";
      rows.forEach(function (row) {
        const name = row[0];
        const amt = row[1];
        const canExplore = row[2] !== false;
        html += "<tr><td>" + escapeHtml(name) + "<span class='bar'><i style='width:" + (amt / max * 100) + "%'></i></span></td>";
        html += "<td class='num'>" + money(amt) + "</td><td class='num'>" + pct(amt, item.value) + "</td>";
        html += "<td class='num'>" + (canExplore ? "<button type='button' class='text-link' data-explore-dept='" + escapeHtml(name) + "'>Ordinance lines</button>" : "") + "</td></tr>";
      });
      html += "</tbody></table>";
    } else if (FUNDS.some(function (f) { return f.id === resolved; })) {
      const outs = FLOWS.filter(function (row) { return row[0] === resolved; }).sort(function (a, b) { return b[2] - a[2]; });
      html += "<table class='dept-table'><thead><tr><th>Pays for</th><th class='num'>Estimated</th><th class='num'>Share</th></tr></thead><tbody>";
      outs.forEach(function (row) {
        html += "<tr><td>" + escapeHtml(byId(row[1]).name) + "</td><td class='num'>" + money(row[2]) + "</td><td class='num'>" + pct(row[2], item.value) + "</td></tr>";
      });
      html += "</tbody></table>";
      if (item.exploreFund) {
        html += "<p class='note'><button type='button' class='text-link' data-explore-fund='" + escapeHtml(item.exploreFund) + "'>Open this pot on the ordinance page</button></p>";
      }
    }

    box.className = "glance-detail open";
    box.innerHTML = html;
    box.querySelectorAll("[data-explore-dept]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        openExplore("All funds", btn.getAttribute("data-explore-dept"));
      });
    });
    box.querySelectorAll("[data-explore-fund]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        openExplore(btn.getAttribute("data-explore-fund"), "All departments");
      });
    });
  }

  function yoyRow(row, max, mark) {
    const a = row.prior;
    const b = row.current;
    const delta = b - a;
    const cls = delta > 0 ? "up" : (delta < 0 ? "down" : "");
    return '<div class="compare-row' + (mark ? " mark" : "") + '"><div>' + escapeHtml(row.name) +
      (mark ? '<span class="mark-tag">' + mark + "</span>" : "") +
      '<div class="twin"><span class="y25" style="width:' + (a / max * 100) + '%"></span><span class="y26" style="width:' + (b / max * 100) + '%"></span></div></div>' +
      '<div class="num">' + money(a) + " → " + money(b) + "</div>" +
      '<div class="num delta ' + cls + '">' + (delta > 0 ? "+" : "") + money(delta) + "</div></div>";
  }

  function renderYoy() {
    const yoy = document.getElementById("glance-yoy");
    if (!yoy || !YOY.length) return;
    const max = Math.max.apply(null, YOY.map(function (r) { return Math.max(r.prior, r.current); }));
    const biggestUp = YOY.reduce(function (a, b) { return (b.current - b.prior) > (a.current - a.prior) ? b : a; });
    const biggestDown = YOY.reduce(function (a, b) { return (b.current - b.prior) < (a.current - a.prior) ? b : a; });
    function markFor(row) {
      if (row.id === biggestUp.id && biggestUp.current - biggestUp.prior > 0) return "Biggest rise";
      if (row.id === biggestDown.id && biggestDown.current - biggestDown.prior < 0) return "Biggest drop";
      return "";
    }
    const funds = YOY.filter(function (r) { return r.kind === "fund"; });
    const services = YOY.filter(function (r) { return r.kind !== "fund"; });
    let html = "";
    if (funds.length) html += "<p class='ui-caps'>Funds</p>" + funds.map(function (r) { return yoyRow(r, max, markFor(r)); }).join("");
    if (services.length) html += "<p class='ui-caps yoy-sub'>Functions</p>" + services.map(function (r) { return yoyRow(r, max, markFor(r)); }).join("");
    yoy.innerHTML = html;
  }

  function renderMobile() {
    const box = document.getElementById("glance-mobile");
    if (!box) return;
    box.innerHTML = "<p class='note'>On a phone the river becomes this list. Rotate or use a wider screen for the diagram.</p>" +
      SERVICES.map(function (s) {
        return '<button type="button" class="stack-row" data-id="' + s.id + '">' +
          '<div class="stack-name">' + escapeHtml(s.name) + "</div>" +
          '<div class="num">' + money(s.value) + "</div>" +
          '<div class="num">' + pct(s.value, GROSS) + "</div>" +
          '<div class="stack-track"><i style="width:' + (s.value / GROSS * 100) + '%"></i></div></button>';
      }).join("");
    box.querySelectorAll("[data-id]").forEach(function (el) {
      el.addEventListener("click", function () { selectNode(el.getAttribute("data-id")); });
    });
  }

  function bindChrome() {
    const reset = document.getElementById("glance-reset");
    if (reset && !reset.dataset.bound) {
      reset.dataset.bound = "1";
      reset.addEventListener("click", function () { setFilter("all"); });
    }
    if (!document.body.dataset.glanceKeys) {
      document.body.dataset.glanceKeys = "1";
      document.addEventListener("keydown", function (ev) {
        if (ev.target && (ev.target.tagName === "INPUT" || ev.target.tagName === "SELECT" || ev.target.tagName === "TEXTAREA")) return;
        if (ev.key === "Escape") setFilter("all");
      });
    }
  }

  function show() {
    if (!loadFromPage()) return;
    bindChrome();
    renderInsights();
    renderFilters();
    renderTakeaway();
    renderYoy();
    renderMobile();
    requestAnimationFrame(function () {
      renderSankey();
    });
  }

  window.ChicagoGlance = {
    load: applyPayload,
    show: show,
    resize: function () {
      if (document.body.getAttribute("data-page") === "glance") renderSankey();
    }
  };
})();
