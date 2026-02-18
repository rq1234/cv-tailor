interface PipelineStep {
  step: string;
  status: "running" | "done" | "error";
  label: string;
  progress: number;
  total: number;
}

const PIPELINE_STAGES = [
  { key: "parsing_jd", label: "Parsing job description" },
  { key: "selecting_experiences", label: "Selecting best experiences" },
  { key: "analyzing_gaps", label: "Mapping experience to requirements" },
  { key: "tailoring_cv", label: "Tailoring bullet points" },
  { key: "checking_ats", label: "Checking ATS compliance" },
  { key: "saving", label: "Saving results" },
];

interface PipelineProgressProps {
  steps: PipelineStep[];
  error: string | null;
  onRetry: () => void;
}

export default function PipelineProgress({ steps, error, onRetry }: PipelineProgressProps) {
  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Tailoring in Progress</h2>

      <div className="space-y-3">
        {PIPELINE_STAGES.map((pipeStep) => {
          const stepEvents = steps.filter((s) => s.step === pipeStep.key);
          const latestStatus = stepEvents.length > 0
            ? stepEvents[stepEvents.length - 1].status
            : null;
          const completed = latestStatus === "done";
          const running = latestStatus === "running";
          const errored = latestStatus === "error";

          return (
            <div
              key={pipeStep.key}
              className={`flex items-center gap-3 rounded-md border p-3 ${
                completed ? "bg-green-50 border-green-200" :
                errored ? "bg-red-50 border-red-200" : ""
              }`}
            >
              {completed ? (
                <svg className="h-5 w-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              ) : errored ? (
                <svg className="h-5 w-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : running ? (
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              ) : (
                <div className="h-5 w-5 rounded-full border-2 border-muted" />
              )}
              <span
                className={`text-sm ${
                  completed ? "text-green-700 font-medium" :
                  errored ? "text-red-700 font-medium" :
                  running ? "text-primary font-medium" :
                  "text-muted-foreground"
                }`}
              >
                {pipeStep.label}
              </span>
            </div>
          );
        })}
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-700">{error}</p>
          <button onClick={onRetry} className="mt-2 text-sm text-red-600 underline">
            Try again
          </button>
        </div>
      )}
    </div>
  );
}
