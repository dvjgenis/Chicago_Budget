(function () {
  "use strict";

  const CHART_IDS = ["left-chart", "purpose-chart", "change-chart", "revenue-chart"];

  function readData() {
    const dataEl = document.getElementById("budget-data");
    if (!dataEl) {
      throw new Error("Missing embedded budget data.");
    }
    return JSON.parse(dataEl.textContent);
  }

  function viewKey(fund, department) {
    return fund + "|" + department;
  }

  function formatMoney(value) {
    const n = Number(value) || 0;
    return Math.abs(n).toLocaleString("en-US", { maximumFractionDigits: 0 });
  }

  function formatSignedMoney(value) {
    const n = Number(value) || 0;
    if (n > 0) return "+" + formatMoney(n);
    if (n < 0) return "-" + formatMoney(n);
    return "0";
  }

  function fillSelect(select, options, selected) {
    select.innerHTML = "";
    options.forEach(function (opt) {
      const node = document.createElement("option");
      node.value = opt;
      node.textContent = opt;
      if (opt === selected) node.selected = true;
      select.appendChild(node);
    });
  }

  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text || "";
  }

  function renderChart(containerId, figure, plotConfig) {
    const node = document.getElementById(containerId);
    if (!node || !window.Plotly) return;
    Plotly.react(node, figure.data, figure.layout, plotConfig);
  }

  function renderTable(tableBody, rows, tableFilter) {
    const query = (tableFilter.value || "").trim().toLowerCase();
    const filtered = query
      ? rows.filter(function (row) {
          return (
            String(row.Fund).toLowerCase().includes(query) ||
            String(row.Department).toLowerCase().includes(query) ||
            String(row.Account).toLowerCase().includes(query)
          );
        })
      : rows;

    tableBody.innerHTML = "";
    const shown = filtered.slice(0, 200);
    shown.forEach(function (row) {
      const tr = document.createElement("tr");
      const change = Number(row.change) || 0;
      if (change > 0) tr.classList.add("change-up");
      if (change < 0) tr.classList.add("change-down");

      [
        row.Fund,
        row.Department,
        row.Account,
        formatMoney(row.Recommended),
        formatMoney(row.Adopted),
        formatSignedMoney(change),
      ].forEach(function (cell, index) {
        const td = document.createElement("td");
        td.textContent = cell;
        if (index >= 3) td.classList.add("num");
        tr.appendChild(td);
      });
      tableBody.appendChild(tr);
    });

    const foot = document.getElementById("table-footnote");
    if (!foot) return;
    if (query && filtered.length !== rows.length) {
      foot.textContent =
        "Showing " +
        shown.length +
        " of " +
        filtered.length +
        " matching lines (filtered from " +
        rows.length +
        ").";
    } else if (filtered.length > 200) {
      foot.textContent = "Showing the first 200 of " + filtered.length + " lines. Filter to narrow further.";
    } else {
      foot.textContent = "";
    }
  }

  function applyView(data, plotConfig, fund, department, tableBody, tableFilter) {
    const view = data.views[viewKey(fund, department)];
    if (!view) {
      setText("scope-line", "No data for this combination.");
      return;
    }

    setText("scope-line", view.scope_line);
    setText("story", view.story);
    setText("scope-note", view.scope_note);
    setText("adopted-label", view.adopted_label);
    setText("recommended-label", view.recommended_label);
    setText("delta-label", view.delta_label);
    setText("delta-hint", view.delta_hint);
    setText("revenue-label", view.revenue_label);
    setText("revenue-hint", view.revenue_hint);

    const deltaLabel = document.getElementById("delta-label");
    if (deltaLabel) {
      deltaLabel.classList.remove("up", "down");
      if (view.delta_trend === "up") deltaLabel.classList.add("up");
      if (view.delta_trend === "down") deltaLabel.classList.add("down");
    }

    setText("left-title", view.left_title);
    setText("left-caption", view.left_caption);
    setText("purpose-title", view.purpose_title);
    setText("purpose-caption", view.purpose_caption);
    setText("change-title", view.change_title);
    setText("change-caption", view.change_caption);
    setText("revenue-title", view.revenue_title);
    setText("revenue-caption", view.revenue_caption);
    setText("table-title", view.table_title);
    setText("table-caption", view.table_caption);

    const financeNote = document.getElementById("finance-note");
    if (financeNote) {
      if (view.show_finance_note) {
        financeNote.textContent = view.finance_note;
        financeNote.classList.remove("hidden");
      } else {
        financeNote.classList.add("hidden");
      }
    }

    renderChart("left-chart", view.left_figure, plotConfig);
    renderChart("purpose-chart", view.purpose_figure, plotConfig);
    renderChart("change-chart", view.change_figure, plotConfig);
    renderChart("revenue-chart", view.revenue_figure, plotConfig);
    tableFilter.value = "";
    renderTable(tableBody, view.line_items, tableFilter);
  }

  function whenPlotlyReady(callback) {
    if (window.Plotly) {
      callback();
      return;
    }
    window.addEventListener("load", callback);
  }

  function showFatal(message) {
    const scope = document.getElementById("scope-line");
    if (scope) {
      scope.textContent = message;
      scope.style.color = "#e4002b";
    }
  }

  function pageFromHash() {
    const raw = (location.hash || "#glance").replace(/^#/, "").split("?")[0];
    return raw === "explore" ? "explore" : "glance";
  }

  function dismissBoot() {
    const boot = document.getElementById("boot");
    document.body.removeAttribute("data-booting");
    if (!boot) return;
    boot.classList.add("out");
    window.setTimeout(function () {
      if (boot.parentNode) boot.parentNode.removeChild(boot);
    }, 480);
  }

  function typingInField(el) {
    if (!el) return false;
    const tag = (el.tagName || "").toUpperCase();
    return tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA" || el.isContentEditable;
  }

  function yearPayload(envelope, year) {
    if (envelope.by_year && envelope.by_year[year]) return envelope.by_year[year];
    return envelope;
  }

  function collectDepartments(data) {
    const seen = {};
    const out = [];
    Object.keys(data.departments_by_fund || {}).forEach(function (fund) {
      (data.departments_by_fund[fund] || []).forEach(function (name) {
        if (!name || name === "All departments" || seen[name]) return;
        seen[name] = true;
        out.push(name);
      });
    });
    return out;
  }

  function init() {
    let envelope;
    try {
      envelope = readData();
    } catch (err) {
      showFatal("Could not load budget data. Rebuild with: python3 run.py");
      dismissBoot();
      return;
    }

    const years = envelope.years && envelope.years.length
      ? envelope.years
      : [envelope.budget_year || (envelope.glance && envelope.glance.year) || ""];
    let data = yearPayload(envelope, envelope.default_year || years[years.length - 1]);
    let glance = data.glance || {};
    if (window.ChicagoGlance && glance.year) window.ChicagoGlance.load(glance);

    function applyChrome() {
      const year = data.budget_year || glance.year || "";
      setText("boot-title", glance.boot_title || (year ? "Opening the " + year + " budget" : "Opening the budget"));
      setText("boot-hint", glance.boot_hint || "The ordinance file is large. Hang on a moment.");
      setText("mast-kicker", glance.kicker || (year ? "Chicago budget · " + year : "Chicago budget"));
      const page = document.body.getAttribute("data-page") || "glance";
      const aside = document.getElementById("mast-aside");
      if (aside) {
        aside.textContent = page === "glance"
          ? (glance.aside_glance || "All-funds map")
          : (glance.aside_explore || "The version City Council passed");
      }
      setText("colophon-text", glance.colophon);
      const sources = document.getElementById("colophon-sources");
      if (sources && glance.source_links && glance.source_links.length) {
        sources.innerHTML = "Source: " + glance.source_links.map(function (link, i) {
          const label = String(link.label || "").replace(/</g, "&lt;");
          const href = String(link.href || "#").replace(/"/g, "&quot;");
          const prefix = i === 0 ? "" : (i === glance.source_links.length - 1 ? ", and " : ", ");
          return prefix + '<a href="' + href + '">' + label + "</a>";
        }).join("") + ".";
      }
    }
    applyChrome();

    const plotConfig = Object.assign({ responsive: true, displayModeBar: false }, data.plot_config || {});
    const fundSelect = document.getElementById("fund-select");
    const departmentSelect = document.getElementById("department-select");
    const tableFilter = document.getElementById("table-filter");
    const tableBody = document.getElementById("line-table-body");
    const pageGlance = document.getElementById("page-glance");
    const pageExplore = document.getElementById("page-explore");

    if (!fundSelect || !departmentSelect || !tableBody || !tableFilter) {
      dismissBoot();
      return;
    }

    let currentRows = [];
    let exploreReady = false;
    let pendingExplore = null;

    function refreshView(fund, department) {
      const view = data.views[viewKey(fund, department)];
      currentRows = view ? view.line_items : [];
      applyView(data, plotConfig, fund, department, tableBody, tableFilter);
    }

    function onFundChange() {
      const fund = fundSelect.value;
      const departments = data.departments_by_fund[fund] || [data.default_department];
      const department = departments.includes(departmentSelect.value)
        ? departmentSelect.value
        : data.default_department;
      fillSelect(departmentSelect, departments, department);
      refreshView(fund, department);
    }

    function applyExploreSelection(fund, department) {
      const funds = data.fund_options || [];
      const nextFund = funds.indexOf(fund) >= 0 ? fund : data.default_fund;
      const departments = data.departments_by_fund[nextFund] || [data.default_department];
      const nextDept = departments.indexOf(department) >= 0 ? department : data.default_department;
      fillSelect(fundSelect, funds, nextFund);
      fillSelect(departmentSelect, departments, nextDept);
      refreshView(nextFund, nextDept);
    }

    function paintPage(page) {
      document.body.setAttribute("data-page", page);
      const aside = document.getElementById("mast-aside");
      if (aside) {
        aside.textContent = page === "glance"
          ? (glance.aside_glance || "All-funds map")
          : (glance.aside_explore || "The version City Council passed");
      }
      if (pageGlance) {
        pageGlance.hidden = page !== "glance";
        pageGlance.classList.toggle("page-enter", page === "glance");
      }
      if (pageExplore) {
        pageExplore.hidden = page !== "explore";
        pageExplore.classList.toggle("page-enter", page === "explore");
      }
      document.querySelectorAll("[data-page-link]").forEach(function (link) {
        const on = link.getAttribute("data-page-link") === page;
        link.setAttribute("aria-current", on ? "page" : "false");
      });
      if (page === "glance" && window.ChicagoGlance) {
        window.ChicagoGlance.show();
      }
      if (page === "explore") {
        if (pendingExplore) {
          const next = pendingExplore;
          pendingExplore = null;
          applyExploreSelection(next.fund, next.department);
        } else if (!exploreReady) {
          applyExploreSelection(data.default_fund, data.default_department);
        }
        exploreReady = true;
        requestAnimationFrame(function () {
          CHART_IDS.forEach(function (id) {
            const node = document.getElementById(id);
            if (node && window.Plotly && node.data) Plotly.Plots.resize(node);
          });
        });
      }
    }

    function showPage(page) {
      const apply = function () { paintPage(page); };
      if (document.startViewTransition) {
        document.startViewTransition(apply);
      } else {
        apply();
      }
    }

    fillSelect(fundSelect, data.fund_options, data.default_fund);
    fillSelect(
      departmentSelect,
      data.departments_by_fund[data.default_fund],
      data.default_department
    );

    fundSelect.addEventListener("change", onFundChange);
    departmentSelect.addEventListener("change", function () {
      refreshView(fundSelect.value, departmentSelect.value);
    });
    tableFilter.addEventListener("input", function () {
      renderTable(tableBody, currentRows, tableFilter);
    });

    function goTo(page) {
      const next = page === "explore" ? "explore" : "glance";
      if (pageFromHash() !== next) {
        location.hash = next;
        return;
      }
      showPage(next);
    }

    window.ChicagoExplore = {
      open: function (fund, department) {
        pendingExplore = {
          fund: fund || data.default_fund,
          department: department || data.default_department,
        };
        goTo("explore");
      },
    };

    const jump = document.getElementById("jump");
    const jumpOpen = document.getElementById("jump-open");
    const jumpInput = document.getElementById("jump-input");
    const jumpList = document.getElementById("jump-list");
    let FEATURED = glance.featured_departments || [];
    let ALIASES = glance.aliases || {};
    let departments = collectDepartments(data);

    const yearSwitch = document.getElementById("year-switch");
    function markYear() {
      if (!yearSwitch) return;
      yearSwitch.querySelectorAll("[data-year]").forEach(function (btn) {
        const on = btn.getAttribute("data-year") === String(data.budget_year);
        btn.setAttribute("aria-selected", on ? "true" : "false");
      });
    }
    function activateYear(nextYear) {
      if (!envelope.by_year || !envelope.by_year[nextYear]) return;
      if (String(data.budget_year) === String(nextYear)) return;
      data = envelope.by_year[nextYear];
      glance = data.glance || {};
      FEATURED = glance.featured_departments || [];
      ALIASES = glance.aliases || {};
      departments = collectDepartments(data);
      if (window.ChicagoGlance) window.ChicagoGlance.load(glance);
      applyChrome();
      markYear();
      document.title = "Chicago Budget " + (data.budget_year || nextYear);
      const page = document.body.getAttribute("data-page") || "glance";
      if (page === "glance" && window.ChicagoGlance) window.ChicagoGlance.show();
      if (page === "explore") {
        applyExploreSelection(data.default_fund, data.default_department);
      } else {
        exploreReady = false;
      }
    }
    if (yearSwitch && years.filter(Boolean).length > 1) {
      yearSwitch.innerHTML = years.map(function (year) {
        return '<button type="button" role="tab" data-year="' + year + '">FY ' + year + "</button>";
      }).join("");
      yearSwitch.querySelectorAll("[data-year]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          activateYear(btn.getAttribute("data-year"));
        });
      });
      markYear();
    } else if (yearSwitch) {
      yearSwitch.hidden = true;
    }

    function closeJump() {
      if (!jump) return;
      jump.hidden = true;
    }

    function rankDept(name, query) {
      const n = name.toLowerCase();
      const q = (query || "").trim().toLowerCase();
      if (!q) {
        const featured = FEATURED.indexOf(name);
        return featured >= 0 ? featured : 50 + n.charCodeAt(0);
      }
      if (ALIASES[q] === name) return 0;
      if (n === q) return 1;
      if (n.startsWith(q)) return 2;
      const words = n.split(/[^a-z0-9]+/);
      if (words.indexOf(q) >= 0) return name.indexOf("Department") >= 0 ? 3 : 4;
      if (words.some(function (w) { return w.indexOf(q) === 0; })) return 5;
      if (n.indexOf(q) >= 0) return 6;
      return 99;
    }

    function matches(name, query) {
      return rankDept(name, query) < 99;
    }

    function renderJump(query, activeIndex) {
      if (!jumpList) return 0;
      const hits = departments
        .filter(function (name) { return matches(name, query); })
        .sort(function (a, b) {
          const ra = rankDept(a, query);
          const rb = rankDept(b, query);
          return ra === rb ? a.localeCompare(b) : ra - rb;
        })
        .slice(0, 12);
      jumpList.innerHTML = hits.map(function (name, i) {
        return '<li><button type="button" data-dept="' + name.replace(/"/g, "&quot;") + '"' +
          (i === activeIndex ? ' class="active"' : "") + ">" + name + "</button></li>";
      }).join("");
      jumpList.querySelectorAll("[data-dept]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          closeJump();
          window.ChicagoExplore.open("All funds", btn.getAttribute("data-dept"));
        });
      });
      return hits.length;
    }

    function openJump() {
      if (!jump || !jumpInput) return;
      jump.hidden = false;
      jumpInput.value = "";
      renderJump("", 0);
      jumpInput.focus();
    }

    if (jumpOpen) jumpOpen.addEventListener("click", openJump);
    if (jump) {
      jump.addEventListener("click", function (ev) {
        if (ev.target === jump) closeJump();
      });
    }
    if (jumpInput) {
      jumpInput.addEventListener("input", function () {
        renderJump(jumpInput.value, 0);
      });
      jumpInput.addEventListener("keydown", function (ev) {
        const buttons = jumpList ? jumpList.querySelectorAll("[data-dept]") : [];
        let idx = Array.prototype.findIndex.call(buttons, function (btn) {
          return btn.classList.contains("active");
        });
        if (ev.key === "ArrowDown") {
          ev.preventDefault();
          idx = Math.min(buttons.length - 1, idx + 1);
          buttons.forEach(function (btn, i) { btn.classList.toggle("active", i === idx); });
          if (buttons[idx]) buttons[idx].scrollIntoView({ block: "nearest" });
        } else if (ev.key === "ArrowUp") {
          ev.preventDefault();
          idx = Math.max(0, idx - 1);
          buttons.forEach(function (btn, i) { btn.classList.toggle("active", i === idx); });
        } else if (ev.key === "Enter") {
          ev.preventDefault();
          const pick = buttons[idx] || buttons[0];
          if (pick) pick.click();
        } else if (ev.key === "Escape") {
          ev.preventDefault();
          closeJump();
        }
      });
    }

    document.addEventListener("keydown", function (ev) {
      if (typingInField(ev.target) && ev.key !== "Escape") return;
      if (ev.key === "1") {
        ev.preventDefault();
        closeJump();
        goTo("glance");
      } else if (ev.key === "2") {
        ev.preventDefault();
        closeJump();
        goTo("explore");
      } else if (ev.key === "j" || ev.key === "J" || ev.key === "/") {
        ev.preventDefault();
        if (jump && !jump.hidden) closeJump();
        else openJump();
      } else if (ev.key === "Escape") {
        if (jump && !jump.hidden) closeJump();
      }
    });

    document.querySelectorAll("[data-page-link]").forEach(function (link) {
      link.addEventListener("click", function (ev) {
        ev.preventDefault();
        goTo(link.getAttribute("data-page-link"));
      });
    });

    window.addEventListener("hashchange", function () {
      showPage(pageFromHash());
    });

    whenPlotlyReady(function () {
      showPage(pageFromHash());
      window.setTimeout(dismissBoot, 280);
    });
    window.setTimeout(dismissBoot, 4000);

    window.addEventListener("resize", function () {
      if (document.body.getAttribute("data-page") === "glance" && window.ChicagoGlance) {
        window.ChicagoGlance.resize();
        return;
      }
      CHART_IDS.forEach(function (id) {
        const node = document.getElementById(id);
        if (node && node.data) Plotly.Plots.resize(node);
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
