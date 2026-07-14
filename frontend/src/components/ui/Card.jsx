export default function Card({ children, className = '', ...props }) {
  return (
    <div className={`rounded-2xl border border-line bg-ink-card ${className}`} {...props}>
      {children}
    </div>
  )
}
