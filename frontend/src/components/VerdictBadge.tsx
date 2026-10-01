import type { Verdict } from "@/types";

export default function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const isOk = verdict === "OK";
  return (
    <span
      className={`inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-semibold ${
        isOk ? "bg-ok/20 text-ok border border-ok" : "bg-nok/20 text-nok border border-nok"
      }`}
    >
      <span className={`w-2 h-2 rounded-full ${isOk ? "bg-ok" : "bg-nok"}`} />
      {isOk ? "YAROQLI ✅" : "YAROQSIZ ⚠️"}
    </span>
  );
}
