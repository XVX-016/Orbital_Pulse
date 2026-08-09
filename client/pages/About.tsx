const ROADMAP = [
  {
    phase: "01",
    title: "Hackathon Build",
    detail: "Establish the mission-control interface and the first working Earth-observation workflows.",
  },
  {
    phase: "02",
    title: "Foundation Model Fine-tuning",
    detail: "Adapt multimodal models to recognize meaningful change across satellite imagery and telemetry.",
  },
  {
    phase: "03",
    title: "Edge Deployment",
    detail: "Move inference closer to the sensor so insights arrive with less latency and less data movement.",
  },
  {
    phase: "04",
    title: "Fleet Scaling",
    detail: "Expand from individual missions to a coordinated, continuously learning observation fleet.",
  },
];

const STACK = [
  "React + TypeScript",
  "Vite + Tailwind CSS",
  "CesiumJS globe layer",
  "Satellite imagery + telemetry APIs",
];

export default function About() {
  return (
    <div className="px-6 pb-24 pt-32">
      <div className="mx-auto max-w-[1000px]">
        <section className="max-w-2xl">
          <p className="label-micro mb-4">About Orbital</p>
          <h1 className="text-headline font-semibold leading-tight text-foreground">
            A clearer way to see our planet.
          </h1>
          <p className="mt-6 text-body text-muted-foreground">
            Orbital is an Earth-observation mission control for exploring what
            satellites see, finding change, and turning raw signals into useful
            decisions. It brings the globe, the data, and the next action into
            one focused workspace.
          </p>
        </section>

        <section className="mt-20 grid gap-12 border-y border-border py-12 md:grid-cols-[1fr_1.5fr] md:gap-20">
          <div>
            <p className="label-micro mb-4">The stack</p>
            <h2 className="text-subhead font-semibold text-foreground">
              Built for iteration
            </h2>
          </div>
          <ul className="divide-y divide-border border-y border-border">
            {STACK.map((item) => (
              <li key={item} className="py-4 text-body text-muted-foreground">
                {item}
              </li>
            ))}
          </ul>
        </section>

        <section className="mt-20">
          <div className="mb-10 flex items-end justify-between">
            <div>
              <p className="label-micro mb-4">Roadmap</p>
              <h2 className="text-headline font-semibold text-foreground">
                From prototype to fleet
              </h2>
            </div>
            <p className="label-micro hidden sm:block">Progress / 01—04</p>
          </div>

          <div className="relative ml-2 border-l border-border">
            {ROADMAP.map((item, index) => (
              <div key={item.phase} className="relative pl-8 sm:grid sm:grid-cols-[160px_1fr] sm:gap-8 sm:pl-10">
                <span className="absolute -left-[5px] top-1 h-2 w-2 rounded-full bg-accent" aria-hidden="true" />
                <div className="pb-10 sm:pb-12">
                  <p className="text-mono-value text-caption text-muted-foreground">
                    {item.phase} / {String(index + 1).padStart(2, "0")}
                  </p>
                </div>
                <div className="pb-10 sm:pb-12">
                  <h3 className="text-subhead font-medium text-foreground">
                    {item.title}
                  </h3>
                  <p className="mt-2 max-w-lg text-caption text-muted-foreground">
                    {item.detail}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
