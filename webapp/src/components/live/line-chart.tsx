export interface Series {
  label: string;
  values: (number | null)[];
  /** A Tailwind text-color class; the line uses currentColor. */
  className: string;
}

/**
 * A small multi-series line chart in SVG over a shared x axis (sample index,
 * labelled with simulated seconds). Series and their latest values are also
 * listed as text, so nothing is conveyed by colour alone.
 */
export function LineChart({
  title,
  unit,
  x,
  series,
}: {
  title: string;
  unit: string;
  x: number[];
  series: Series[];
}) {
  const w = 640;
  const h = 180;
  const pad = { l: 44, r: 8, t: 8, b: 22 };
  const all = series.flatMap((s) => s.values.filter((v): v is number => v !== null));
  if (x.length < 2 || all.length < 2) {
    return <p className="text-muted-foreground text-sm">Waiting for at least two samples.</p>;
  }
  const max = Math.max(...all) || 1;
  const sx = (i: number) => pad.l + (i / (x.length - 1)) * (w - pad.l - pad.r);
  const sy = (v: number) => h - pad.b - (v / max) * (h - pad.t - pad.b);
  const ticks = [0, max / 2, max];
  return (
    <figure className="space-y-2">
      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="h-auto w-full"
        role="img"
        aria-label={`${title}, ${unit}, over simulated time`}
      >
        {ticks.map((t) => (
          <g key={t} className="text-muted-foreground">
            <line
              x1={pad.l}
              x2={w - pad.r}
              y1={sy(t)}
              y2={sy(t)}
              stroke="currentColor"
              strokeOpacity={0.15}
            />
            <text x={pad.l - 6} y={sy(t) + 4} textAnchor="end" fontSize={11} fill="currentColor">
              {t >= 100 ? t.toFixed(0) : t.toFixed(1)}
            </text>
          </g>
        ))}
        <text
          x={w - pad.r}
          y={h - 4}
          textAnchor="end"
          fontSize={11}
          className="text-muted-foreground"
          fill="currentColor"
        >
          simulated {(x.at(-1) ?? 0).toFixed(0)} s
        </text>
        {series.map((s) => {
          const pts = s.values
            .map((v, i) => (v === null ? null : `${sx(i).toFixed(1)},${sy(v).toFixed(1)}`))
            .filter(Boolean)
            .join(" ");
          return (
            <polyline
              key={s.label}
              points={pts}
              fill="none"
              stroke="currentColor"
              strokeWidth={1.75}
              className={s.className}
            />
          );
        })}
      </svg>
      <figcaption className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {series.map((s) => {
          const last = [...s.values].reverse().find((v) => v !== null);
          return (
            <span key={s.label} className="flex items-center gap-1.5">
              <span className={`${s.className} inline-block h-0.5 w-4 bg-current`} aria-hidden />
              {s.label}:{" "}
              <span className="tabular font-medium">
                {last === undefined || last === null ? "n/a" : `${last.toFixed(1)} ${unit}`}
              </span>
            </span>
          );
        })}
      </figcaption>
    </figure>
  );
}
