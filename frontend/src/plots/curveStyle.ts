export type CurveStyle = {
  color: string;
  dash: "solid" | "dashed" | "dotted";
};

const colors = [
  "#167d9a",
  "#b05e20",
  "#8560b4",
  "#337c45",
  "#b63850",
  "#806329",
  "#566476",
  "#ac4d91",
];
export function curveStyle(index: number): CurveStyle {
  return {
    color: colors[index % colors.length],
    dash: (["solid", "dashed", "dotted"] as const)[
      Math.floor(index / colors.length) % 3
    ],
  };
}

export type LegendEntry = CurveStyle & { id: string; label: string };

export async function imageWithLegend(href: string, entries: LegendEntry[]) {
  const image = new Image();
  image.src = href;
  await image.decode();
  const canvas = document.createElement("canvas");
  canvas.width = image.width;
  const context = canvas.getContext("2d")!;
  const padding = 24,
    swatch = 36,
    lineHeight = 34;
  const font = "24px system-ui, sans-serif";
  context.font = font;
  const lines: { entry: LegendEntry; text: string; first: boolean }[] = [];
  const maxWidth = canvas.width - padding * 2 - swatch - 12;
  for (const entry of entries) {
    let text = "",
      first = true;
    for (const word of entry.label.split(" ")) {
      const next = text ? `${text} ${word}` : word;
      if (text && context.measureText(next).width > maxWidth) {
        lines.push({ entry, text, first });
        first = false;
        text = word;
      } else text = next;
    }
    lines.push({ entry, text, first });
  }
  const legendHeight = padding * 2 + lines.length * lineHeight;
  canvas.height = image.height + legendHeight;
  context.fillStyle = "white";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(image, 0, legendHeight);
  context.font = font;
  context.textBaseline = "middle";
  lines.forEach(({ entry, text, first }, index) => {
    const y = padding + (index + 0.5) * lineHeight;
    if (first) {
      context.strokeStyle = entry.color;
      context.lineWidth = 4;
      context.setLineDash(
        entry.dash === "dashed"
          ? [10, 6]
          : entry.dash === "dotted"
            ? [3, 5]
            : [],
      );
      context.beginPath();
      context.moveTo(padding, y);
      context.lineTo(padding + swatch, y);
      context.stroke();
    }
    context.fillStyle = "#203744";
    context.fillText(text, padding + swatch + 12, y);
  });
  return canvas.toDataURL("image/png");
}
