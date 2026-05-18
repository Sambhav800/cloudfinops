"use client";

const ROW_ONE = [
    "AWS",
    "Azure",
    "Google Cloud",
    "Kubernetes",
    "Terraform",
    "Pulumi",
    "GitHub Actions",
    "GitLab CI",
    "CircleCI",
    "ArgoCD",
];

const ROW_TWO = [
    "Datadog",
    "Grafana",
    "Prometheus",
    "Slack",
    "PagerDuty",
    "Jira",
    "Linear",
    "Notion",
    "Confluence",
    "OpsGenie",
];

export function IntegrationsMarquee() {
    return (
        <section className="overflow-hidden py-24">
            <div className="mb-12 px-6 text-center">
                <p className="mb-4 text-[11px] font-medium uppercase tracking-[0.2em] text-indigo-400">
                    Works with your stack
                </p>
                <h2 className="mx-auto max-w-2xl text-[32px] font-medium tracking-tight text-white">
                    Plugs into the tools you already use.
                </h2>
            </div>

            <div
                className="group space-y-6 overflow-hidden"
                style={{
                    maskImage:
                        "linear-gradient(to right, transparent, black 10%, black 90%, transparent)",
                    WebkitMaskImage:
                        "linear-gradient(to right, transparent, black 10%, black 90%, transparent)",
                }}
            >
                <MarqueeRow items={ROW_ONE} animation="animate-[marquee_40s_linear_infinite]" />
                <MarqueeRow
                    items={ROW_TWO}
                    animation="animate-[marquee-reverse_60s_linear_infinite]"
                />
            </div>
        </section>
    );
}

function MarqueeRow({
    items,
    animation,
}: {
    items: string[];
    animation: string;
}) {
    const repeated = [...items, ...items];

    return (
        <div className="flex w-max gap-16">
            <div
                className={`marquee-track flex min-w-max items-center gap-16 ${animation} group-hover:[animation-play-state:paused]`}
            >
                {repeated.map((item, index) => (
                    <div
                        key={`${item}-${index}`}
                        className="flex items-center gap-3 text-[14px] font-medium text-zinc-500 transition-colors hover:text-zinc-300"
                    >
                        <span className="h-1.5 w-1.5 rounded-full bg-indigo-400/80" />
                        <span className="tracking-[0.12em] uppercase">{item}</span>
                    </div>
                ))}
            </div>
        </div>
    );
}
