export function downloadSvgMarkup(svg: string, filename: string) {
  const blob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function downloadSvgElement(svg: SVGSVGElement, filename: string) {
  if (!svg.getAttribute("xmlns")) {
    svg.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  }
  downloadSvgMarkup(svg.outerHTML, filename);
}

export function downloadSvgAsPng(svg: string | SVGSVGElement, filename: string) {
  const markup = typeof svg === "string" ? svg : svg.outerHTML;
  const width = svgSize(svg, "width", 640);
  const height = svgSize(svg, "height", 360);
  const blob = new Blob([markup], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const image = new Image();
  image.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      URL.revokeObjectURL(url);
      return;
    }
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, width, height);
    ctx.drawImage(image, 0, 0, width, height);
    URL.revokeObjectURL(url);
    canvas.toBlob((png) => {
      if (!png) return;
      const pngUrl = URL.createObjectURL(png);
      const link = document.createElement("a");
      link.href = pngUrl;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(pngUrl);
    }, "image/png");
  };
  image.src = url;
}

function svgSize(svg: string | SVGSVGElement, axis: "width" | "height", fallback: number): number {
  if (typeof svg !== "string") {
    const view = svg.viewBox.baseVal;
    const fromView = axis === "width" ? view.width : view.height;
    const fromAttr = Number(svg.getAttribute(axis));
    const fromClient = axis === "width" ? svg.clientWidth : svg.clientHeight;
    return Math.round(fromView || fromAttr || fromClient || fallback);
  }
  const match = svg.match(new RegExp(`${axis}="(\\d+(?:\\.\\d+)?)"`));
  return match ? Math.round(Number(match[1])) : fallback;
}
