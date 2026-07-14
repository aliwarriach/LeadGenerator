export default function PageHeader({ breadcrumb, title, titleExtra, subtitle, subtitleMono = false, actions }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <div className="mb-1.5 text-[11px] uppercase tracking-widest text-txt-mute">{breadcrumb}</div>
        <h1 className="font-display text-2xl font-semibold tracking-tight text-white">
          {title} {titleExtra}
        </h1>
        {subtitle && (
          <p className={`mt-1 text-txt-dim ${subtitleMono ? 'font-mono text-xs' : 'text-[13.5px]'}`}>{subtitle}</p>
        )}
      </div>
      {actions && <div className="flex gap-2.5">{actions}</div>}
    </div>
  )
}
