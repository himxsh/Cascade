export function Mark({
  className,
  animate = false,
}: {
  className?: string
  animate?: boolean
}) {
  const stroke = animate ? 'mark-stroke' : undefined
  return (
    <svg
      className={className}
      viewBox="0 0 200 160"
      fill="none"
      aria-hidden="true"
    >
      <path
        className={stroke}
        pathLength={1}
        d="M22 142 L100 28 L178 142"
        stroke="#e4e8f0"
        strokeWidth="16"
      />
      <path
        className={stroke ? `${stroke} inner` : undefined}
        pathLength={1}
        d="M54 142 L100 72 L146 142"
        stroke="#fc3010"
        strokeWidth="16"
      />
    </svg>
  )
}
