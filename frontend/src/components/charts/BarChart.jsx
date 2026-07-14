export default function BarChart({ data }) {
  const maxTotal = Math.max(...data.map((d) => d.hasWebsite + d.noWebsite))

  return (
    <div className="flex h-[150px] items-end gap-2.5 px-5 pb-2 pt-[18px]">
      {data.map((d) => (
        <div key={d.day} className="flex h-full flex-1 flex-col items-center justify-end gap-1.5">
          <div className="flex w-full flex-1 items-end gap-[3px]">
            <div
              className="min-h-[4px] flex-1 rounded-b-[2px] rounded-t-[4px] bg-signal"
              style={{ height: `${(d.hasWebsite / maxTotal) * 100}%` }}
            />
            <div
              className="min-h-[4px] flex-1 rounded-b-[2px] rounded-t-[4px] bg-[#1f5e45]"
              style={{ height: `${(d.noWebsite / maxTotal) * 100}%` }}
            />
          </div>
          <span className="text-[10.5px] text-txt-mute">{d.day}</span>
        </div>
      ))}
    </div>
  )
}
