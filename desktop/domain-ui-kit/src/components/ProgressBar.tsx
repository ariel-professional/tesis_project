export type ProgressBarProps = {
  value?: number;
  label: string;
  valueText?: string;
  indeterminate?: boolean;
  paused?: boolean;
  className?: string;
};

export function ProgressBar({
  value = 0,
  label,
  valueText,
  indeterminate = false,
  paused = false,
  className = "",
}: ProgressBarProps) {
  const bounded = Math.max(0, Math.min(100, value));
  return (
    <div className={`ui-progress ${paused ? "is-paused" : ""} ${className}`.trim()}>
      <div className="ui-progress__heading">
        <span>{label}</span>
        {valueText !== undefined && <strong>{valueText}</strong>}
      </div>
      <div
        className={`ui-progress__track ${indeterminate ? "is-indeterminate" : ""}`}
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={indeterminate ? undefined : 100}
        aria-valuenow={indeterminate ? undefined : bounded}
        aria-valuetext={valueText}
      >
        <span className="ui-progress__fill" style={indeterminate ? undefined : { width: `${bounded}%` }} />
      </div>
    </div>
  );
}
