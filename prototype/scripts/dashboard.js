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
  const tile = 168;
  const step = 168;
  const offset = 42;
  const tab = 25;
  const piecePalette = [
    "#ddc4b9",
    "#d6cba9",
    "#95ad9d",
    "#95c8cc",
    "#b1bcc9",
    "#8b92a7",
    "#b9a9b6",
    "#66788e",
    "#d7cfb0"
  ];
  const pieceHoverPalette = [
    "#e6cfc5",
    "#e0d4b2",
    "#a8bbaa",
    "#a8d2d5",
    "#c1cad5",
    "#9ba1b4",
    "#c8b8c4",
    "#76879c",
    "#e2dac0"
  ];
  const verticalEdges = [
    [1, -1],
    [-1, 1],
    [1, -1]
  ];
  const horizontalEdges = [
    [-1, 1, -1],
    [1, -1, 1]
  ];

  function getEdges(row, col) {
    return {
      top: row === 0 ? 0 : -horizontalEdges[row - 1][col],
      right: col === 2 ? 0 : verticalEdges[row][col],
      bottom: row === 2 ? 0 : horizontalEdges[row][col],
      left: col === 0 ? 0 : -verticalEdges[row][col - 1]
    };
  }

  function getLabelColor(hex) {
    const normalized = String(hex).replace("#", "");
    const r = Number.parseInt(normalized.slice(0, 2), 16);
    const g = Number.parseInt(normalized.slice(2, 4), 16);
    const b = Number.parseInt(normalized.slice(4, 6), 16);
    const luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
    return luminance < 0.54 ? "#f8f6f1" : "#253548";
  }

  function makePuzzlePath(x, y, size, edges) {
    const c1 = size * 0.34;
    const c2 = size * 0.39;
    const c3 = size * 0.50;
    const c4 = size * 0.61;
    const c5 = size * 0.66;
    const commands = [`M ${x} ${y}`];

    addHorizontalEdge(commands, x, y, size, edges.top, "top", c1, c2, c3, c4, c5);
    addVerticalEdge(commands, x, y, size, edges.right, "right", c1, c2, c3, c4, c5);
    addHorizontalEdge(commands, x, y, size, edges.bottom, "bottom", c1, c2, c3, c4, c5);
    addVerticalEdge(commands, x, y, size, edges.left, "left", c1, c2, c3, c4, c5);
    commands.push("Z");

    return commands.join(" ");
  }

  function addHorizontalEdge(commands, x, y, size, edge, side, c1, c2, c3, c4, c5) {
    const isTop = side === "top";
    const baseY = isTop ? y : y + size;
    const direction = isTop ? 1 : -1;
    const sign = edge === 1 ? (isTop ? -1 : 1) : (isTop ? 1 : -1);

    if (!edge) {
      commands.push(`L ${isTop ? x + size : x} ${baseY}`);
      return;
    }

    const points = isTop
      ? [x + c1, x + c2, x + c3, x + c4, x + c5, x + size]
      : [x + size - c1, x + size - c2, x + size - c3, x + size - c4, x + size - c5, x];

    commands.push(`L ${points[0]} ${baseY}`);
    commands.push(`C ${points[1]} ${baseY}, ${points[1]} ${baseY + sign * tab}, ${points[2]} ${baseY + sign * tab}`);
    commands.push(`C ${points[3]} ${baseY + sign * tab}, ${points[3]} ${baseY}, ${points[4]} ${baseY}`);
    commands.push(`L ${points[5]} ${baseY}`);

    if (!direction) {
      return;
    }
  }

  function addVerticalEdge(commands, x, y, size, edge, side, c1, c2, c3, c4, c5) {
    const isRight = side === "right";
    const baseX = isRight ? x + size : x;
    const sign = edge === 1 ? (isRight ? 1 : -1) : (isRight ? -1 : 1);

    if (!edge) {
      commands.push(`L ${baseX} ${isRight ? y + size : y}`);
      return;
    }

    const points = isRight
      ? [y + c1, y + c2, y + c3, y + c4, y + c5, y + size]
      : [y + size - c1, y + size - c2, y + size - c3, y + size - c4, y + size - c5, y];

    commands.push(`L ${baseX} ${points[0]}`);
    commands.push(`C ${baseX} ${points[1]}, ${baseX + sign * tab} ${points[1]}, ${baseX + sign * tab} ${points[2]}`);
    commands.push(`C ${baseX + sign * tab} ${points[3]}, ${baseX} ${points[3]}, ${baseX} ${points[4]}`);
    commands.push(`L ${baseX} ${points[5]}`);
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

  function addSparkles(group, x, y, index) {
    const sparklePositions = [
      [x + 34, y + 34],
      [x + tile - 34, y + 42],
      [x + tile - 48, y + tile - 34]
    ];

    sparklePositions.forEach(([cx, cy], sparkleIndex) => {
      const circle = document.createElementNS(ns, "circle");
      circle.setAttribute("class", `puzzle-sparkle sparkle-${(index + sparkleIndex) % 3}`);
      circle.setAttribute("cx", String(cx));
      circle.setAttribute("cy", String(cy));
      circle.setAttribute("r", sparkleIndex === 0 ? "3.4" : "2.4");
      group.appendChild(circle);
    });
  }

  boardOrder.forEach((key, index) => {
    const feature = features[key];

    if (!feature) {
      return;
    }

    const row = Math.floor(index / 3);
    const col = index % 3;
    const x = col * step + offset;
    const y = row * step + offset;
    const href = `./pages/${key}.html`;

    const link = document.createElementNS(ns, "a");
    link.setAttributeNS(linkNs, "xlink:href", href);
    link.setAttribute("href", href);
    link.setAttribute("class", "puzzle-piece-link");
    link.setAttribute("aria-label", feature.title);
    link.style.setProperty("--piece-delay", `${index * 70}ms`);

    const pieceColor = piecePalette[index % piecePalette.length];
    const pieceHover = pieceHoverPalette[index % pieceHoverPalette.length];
    link.style.setProperty("--piece-label", getLabelColor(pieceColor));
    link.style.setProperty("--piece-label-stroke", getLabelColor(pieceColor) === "#253548" ? "rgba(255, 255, 255, 0.42)" : "rgba(25, 42, 58, 0.22)");

    const piece = document.createElementNS(ns, "path");
    piece.setAttribute("class", "puzzle-piece-shape");
    piece.setAttribute("d", makePuzzlePath(x, y, tile, getEdges(row, col)));
    piece.style.setProperty("--piece-fill", pieceColor);
    piece.style.setProperty("--piece-hover", pieceHover);
    link.appendChild(piece);

    const shine = document.createElementNS(ns, "path");
    shine.setAttribute("class", "puzzle-piece-shine");
    shine.setAttribute("d", `M ${x + 36} ${y + 42} C ${x + 72} ${y + 20}, ${x + 118} ${y + 22}, ${x + tile - 34} ${y + 48}`);
    link.appendChild(shine);

    addSparkles(link, x, y, index);
    addLabel(link, feature.boardLines || [feature.title], x + tile / 2, y + tile / 2 + 5);

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
      }, 260);
    });

    svg.appendChild(link);
  });
})();
