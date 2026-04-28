(function () {
  const svg = document.getElementById("puzzle-board");
  const features = window.MDPieceFeatures || {};
  const moodButtons = Array.from(document.querySelectorAll(".dashboard-mood-chip"));
  const boardOrder = [
    "symptoms",
    "medications",
    "previsit",
    "education",
    "condition-education",
    "symptom-analysis",
    "memo",
    "labs",
    "ai-bot"
  ];

  if (!svg) {
    return;
  }

  function setMood(nextMood) {
    moodButtons.forEach((button) => {
      const isSelected = button.dataset.mood === nextMood;
      button.classList.toggle("is-selected", isSelected);
      button.setAttribute("aria-pressed", isSelected ? "true" : "false");
    });

    try {
      if (nextMood) {
        window.localStorage.setItem("md-piece-daily-mood", nextMood);
      } else {
        window.localStorage.removeItem("md-piece-daily-mood");
      }
    } catch (error) {
      console.warn("Mood state unavailable.", error);
    }
  }

  moodButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const nextMood = button.classList.contains("is-selected") ? "" : button.dataset.mood;
      setMood(nextMood);
    });
  });

  try {
    const storedMood = window.localStorage.getItem("md-piece-daily-mood");
    if (storedMood) {
      setMood(storedMood);
    }
  } catch (error) {
    console.warn("Mood state unavailable.", error);
  }

  const ns = "http://www.w3.org/2000/svg";
  const linkNs = "http://www.w3.org/1999/xlink";
  const size = 200;
  const half = size / 2;
  const neck = 42;
  const tab = 34;
  const edgeMap = [
    { top: 0, right: -1, bottom: 1, left: 0 },
    { top: 0, right: -1, bottom: 1, left: 1 },
    { top: 0, right: 0, bottom: -1, left: 1 },
    { top: -1, right: 1, bottom: -1, left: 0 },
    { top: -1, right: -1, bottom: -1, left: -1 },
    { top: 1, right: 0, bottom: 1, left: 1 },
    { top: 1, right: -1, bottom: 0, left: 0 },
    { top: 1, right: 1, bottom: 0, left: 1 },
    { top: -1, right: 0, bottom: 0, left: -1 }
  ];

  function buildPath(x, y, edges) {
    let d = `M ${x} ${y}`;

    if (edges.top === 0) {
      d += ` H ${x + size}`;
    } else {
      d += ` H ${x + half - neck}`;
      d += ` C ${x + half - neck / 2} ${y}, ${x + half - neck / 2} ${y - edges.top * tab}, ${x + half} ${y - edges.top * tab}`;
      d += ` C ${x + half + neck / 2} ${y - edges.top * tab}, ${x + half + neck / 2} ${y}, ${x + half + neck} ${y}`;
      d += ` H ${x + size}`;
    }

    if (edges.right === 0) {
      d += ` V ${y + size}`;
    } else {
      d += ` V ${y + half - neck}`;
      d += ` C ${x + size} ${y + half - neck / 2}, ${x + size + edges.right * tab} ${y + half - neck / 2}, ${x + size + edges.right * tab} ${y + half}`;
      d += ` C ${x + size + edges.right * tab} ${y + half + neck / 2}, ${x + size} ${y + half + neck / 2}, ${x + size} ${y + half + neck}`;
      d += ` V ${y + size}`;
    }

    if (edges.bottom === 0) {
      d += ` H ${x}`;
    } else {
      d += ` H ${x + half + neck}`;
      d += ` C ${x + half + neck / 2} ${y + size}, ${x + half + neck / 2} ${y + size + edges.bottom * tab}, ${x + half} ${y + size + edges.bottom * tab}`;
      d += ` C ${x + half - neck / 2} ${y + size + edges.bottom * tab}, ${x + half - neck / 2} ${y + size}, ${x + half - neck} ${y + size}`;
      d += ` H ${x}`;
    }

    if (edges.left === 0) {
      d += ` V ${y}`;
    } else {
      d += ` V ${y + half + neck}`;
      d += ` C ${x} ${y + half + neck / 2}, ${x - edges.left * tab} ${y + half + neck / 2}, ${x - edges.left * tab} ${y + half}`;
      d += ` C ${x - edges.left * tab} ${y + half - neck / 2}, ${x} ${y + half - neck / 2}, ${x} ${y + half - neck}`;
      d += ` V ${y}`;
    }

    return `${d} Z`;
  }

  function addLabel(group, lines, cx, cy) {
    const text = document.createElementNS(ns, "text");
    text.setAttribute("class", "puzzle-piece-label");
    text.setAttribute("x", String(cx));
    text.setAttribute("y", String(cy - ((lines.length - 1) * 11)));

    lines.forEach((line, index) => {
      const tspan = document.createElementNS(ns, "tspan");
      tspan.setAttribute("x", String(cx));
      tspan.setAttribute("dy", index === 0 ? "0" : "22");
      tspan.textContent = line;
      text.appendChild(tspan);
    });

    group.appendChild(text);
  }

  boardOrder.forEach((key, index) => {
    const feature = features[key];

    if (!feature) {
      return;
    }

    const row = Math.floor(index / 3);
    const col = index % 3;
    const x = col * size;
    const y = row * size;
    const href = `./pages/${key}.html`;

    const link = document.createElementNS(ns, "a");
    link.setAttributeNS(linkNs, "xlink:href", href);
    link.setAttribute("href", href);
    link.setAttribute("class", "puzzle-piece-link");
    link.setAttribute("aria-label", feature.title);

    const path = document.createElementNS(ns, "path");
    path.setAttribute("class", "puzzle-piece-shape");
    path.setAttribute("d", buildPath(x, y, edgeMap[index]));
    if (feature.color) {
      path.style.setProperty("--piece-fill", feature.color);
    }
    if (feature.hoverColor) {
      path.style.setProperty("--piece-hover", feature.hoverColor);
    }
    link.appendChild(path);

    addLabel(link, feature.boardLines || [feature.title], x + half, y + half);

    link.addEventListener("click", (event) => {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
        return;
      }

      event.preventDefault();
      link.classList.remove("is-launching");
      void link.getBBox();
      link.classList.add("is-launching");

      window.setTimeout(() => {
        window.location.href = href;
      }, 300);
    });

    svg.appendChild(link);
  });
})();
