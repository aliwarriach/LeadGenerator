import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import Chip from "../../components/ui/Chip";
import RadarScan from "./RadarScan";
import { DISCOVERY_SOURCES } from "../../constants/discovery";
import { scoreTone } from "../../constants/businesses";
import { useToastStore } from "../../store/useToastStore";
import { useViewStore } from "../../store/useViewStore";
import { useActiveRunStore } from "../../store/useActiveRunStore";
import { useDiscovery } from "../../hooks/useDiscovery";
import { useDiscoveryRunStats } from "../../hooks/useDiscoveryRunStats";
import {
  formatAvgDuration,
  formatAvgLeadsSaved,
  formatSuccessRate,
  formatTotalLeadsSaved,
} from "./formatRunStats";

function sourceLabel(sourceId) {
  return DISCOVERY_SOURCES.find((s) => s.id === sourceId)?.label ?? sourceId;
}

export default function RunEstimateCard({ payload, errors, onInvalidSubmit }) {
  const show = useToastStore((s) => s.show);
  const setView = useViewStore((s) => s.setView);
  const setActiveRunId = useActiveRunStore((s) => s.setActiveRunId);
  const { runDiscovery, running } = useDiscovery();
  const {
    data: stats,
    isLoading: statsLoading,
    isError: statsError,
    error: statsErrorObj,
    refetch: refetchStats,
  } = useDiscoveryRunStats();
  const hasSourceStats =
    !statsLoading && !statsError && stats?.leads_by_source?.length > 0;

  async function handleRun() {
    if (!payload) {
      onInvalidSubmit?.();
      show(`**Can't start discovery** — ${errors[0]}`);
      return;
    }

    try {
      const result = await runDiscovery(payload);
      const jobCount = result.jobs.length;
      setActiveRunId(result.run_id);
      show(
        `**Discovery started** — tracking ${jobCount} job${jobCount === 1 ? "" : "s"}`,
      );
      setView("run-monitoring", "Discovery", { runId: result.run_id });
    } catch (err) {
      show(`**Discovery failed** — ${err.message}`);
    }
  }

  return (
    <Card className="px-[22px] py-5 xl:sticky xl:top-6 xl:self-start">
      <h3 className="mb-1.5 text-sm font-semibold text-white">
        Past run performance
      </h3>
      <RadarScan />
      {statsLoading ? (
        <div className="my-3.5 space-y-2.5">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-3 animate-pulse rounded bg-line" />
          ))}
        </div>
      ) : statsError ? (
        <div className="my-3.5 text-center text-[12.5px]">
          <p className="mb-2 text-red">{statsErrorObj.message}</p>
          <Button variant="ghost" onClick={() => refetchStats()}>
            Retry
          </Button>
        </div>
      ) : !stats.completed_run_count ? (
        <p className="mb-3.5 text-[11.5px] leading-relaxed text-txt-mute">
          No completed runs yet — stats will appear here once a discovery run
          finishes successfully.
        </p>
      ) : (
        <>
          <p className="mb-3.5 text-[11.5px] leading-relaxed text-txt-mute">
            Based on your previous completed runs.
          </p>
          <dl className="divide-y divide-dashed divide-line">
            <div className="flex justify-between py-2.5 text-[13px] text-txt-dim">
              <dt>Avg. time to complete</dt>
              <dd className="font-mono text-txt-dim">
                {formatAvgDuration(stats.avg_duration_seconds) ?? "—"}
              </dd>
            </div>
            <div className="flex justify-between py-2.5 text-[13px] text-txt-dim">
              <dt>Avg. leads saved per run</dt>
              <dd className="font-mono text-txt-dim">
                {formatAvgLeadsSaved(stats.avg_leads_saved) ?? "—"}
              </dd>
            </div>
            <div className="flex justify-between py-2.5 text-[13px] text-txt-dim">
              <dt>Total leads saved</dt>
              <dd className="font-mono text-txt-dim">
                {formatTotalLeadsSaved(stats.total_leads_saved) ?? "—"}
              </dd>
            </div>
            <div className="flex items-center justify-between py-2.5 text-[13px] text-txt-dim">
              <dt>Success rate</dt>
              <dd>
                <Chip
                  tone={scoreTone(stats.success_rate * 100)}
                  className="font-mono"
                >
                  {formatSuccessRate(stats.success_rate)}
                </Chip>
              </dd>
            </div>
          </dl>
        </>
      )}
      <div className="pt-3 pb-6">
        <div className="mb-2 text-[11.5px] font-semibold uppercase tracking-wider text-txt-dim">
          {hasSourceStats
            ? "Best-performing source (avg. leads/job)"
            : "Sources fanned per city"}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {hasSourceStats
            ? stats.leads_by_source.map((s) => (
                <Chip key={s.source} tone="muted">
                  {sourceLabel(s.source)} ·{" "}
                  {formatAvgLeadsSaved(s.avg_leads_saved)}
                </Chip>
              ))
            : DISCOVERY_SOURCES.map((source) => (
                <Chip key={source.id} tone="muted">
                  {source.label}
                </Chip>
              ))}
        </div>
      </div>
      <Button
        className={`w-full justify-center ${running ? "cursor-not-allowed opacity-70" : ""}`}
        disabled={running}
        onClick={handleRun}
      >
        {running ? "Scanning neighborhoods…" : "Run discovery"}
      </Button>
    </Card>
  );
}
