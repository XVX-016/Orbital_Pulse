export default function Placeholder({ title }: { title: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center px-6 pt-16">
      <div className="panel max-w-lg rounded-lg p-6 text-center">
        <p className="label-micro mb-3">Module offline</p>
        <h1 className="text-title font-semibold text-foreground mb-3">
          {title}
        </h1>
        <p className="text-body text-muted-foreground">
          This module hasn&apos;t been built out yet. Keep prompting to fill
          in this page with the content you need.
        </p>
      </div>
    </div>
  );
}
