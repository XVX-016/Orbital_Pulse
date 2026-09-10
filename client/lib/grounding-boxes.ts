export type GroundingBoxPercent = [number, number, number, number];

/**
 * Convert an explicitly-declared model coordinate system to a clipped CSS box.
 * Callers must not guess `pixels` from a small numeric value: 80 can be 80px
 * or 80% depending on the model contract.
 */
export function normalizeGroundingBox(
  box: readonly number[],
  space: "percent" | "grid_1000" | "pixels" = "percent",
  imageSize?: { width: number; height: number },
): GroundingBoxPercent | null {
  if (box.length !== 4 || box.some((value) => !Number.isFinite(value))) return null;
  const [x1, y1, x2, y2] = box;
  const xScale = space === "pixels" ? imageSize?.width : space === "grid_1000" ? 1000 : 100;
  const yScale = space === "pixels" ? imageSize?.height : space === "grid_1000" ? 1000 : 100;
  if (!xScale || !yScale || xScale <= 0 || yScale <= 0) return null;
  const clamp = (value: number, maximum: number) => Math.min(maximum, Math.max(0, value));
  const left = clamp(x1, xScale) / xScale * 100;
  const right = clamp(x2, xScale) / xScale * 100;
  const top = clamp(y1, yScale) / yScale * 100;
  const bottom = clamp(y2, yScale) / yScale * 100;
  return [Math.min(left, right), Math.min(top, bottom), Math.max(left, right), Math.max(top, bottom)];
}
