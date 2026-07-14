const VARIANTS = {
  primary: 'bg-signal text-[#08110d] hover:brightness-110',
  ghost: 'border border-line-hi text-txt-dim hover:border-txt-mute hover:text-txt',
}

export default function Button({ variant = 'primary', className = '', children, ...props }) {
  return (
    <button
      className={`inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-[13px] font-semibold transition-colors duration-150 ${VARIANTS[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}
