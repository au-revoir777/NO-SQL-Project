/** A tiny trend line; `values` are plotted left to right, scaled to their own range. */
export function Sparkline({
  values,
  label,
  className = "text-primary",
}: {
  values: number[];
  label: string;
  className?: string;
}) {
  const w = 120;
  const h = 32;
  if (values.length < 2) {
    return <svg width={w} height={h} role="img" aria-label={`${label}: not enough data yet`} />;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const points = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * (w - 2) + 1;
      const y = h - 1 - ((v - min) / span) * (h - 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      role="img"
      aria-label={`${label}: trend over the last ${values.length} samples`}
      className={className}
    >
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth={1.5} />
    </svg>
  );
}
