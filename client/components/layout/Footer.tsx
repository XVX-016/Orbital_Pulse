import { Mail, Globe, ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";

function GithubIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      role="img"
      viewBox="0 0 24 24"
      fill="currentColor"
      {...props}
    >
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
    </svg>
  );
}

export default function Footer() {
  return (
    <footer className="relative z-10 border-t border-border bg-background px-6 py-12">
      <div className="mx-auto max-w-[1400px]">
        {/* Multi-column grid */}
        <div className="grid grid-cols-1 gap-10 sm:grid-cols-2 lg:grid-cols-4 lg:gap-12 pb-12">
          {/* Column 1: Brand */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <span className="text-lg font-bold tracking-wider text-foreground">SATQUERY AI</span>
            </div>
            <p className="text-body-sm text-muted-foreground leading-relaxed">
              An agentic multimodal remote-sensing VQA and change-analysis platform powered by 4-bit GeoChat-7B and Prithvi-EO. Designed and built for Smart India Hackathon 2026 under ISRO problem statement PS-26167.
            </p>
          </div>

          {/* Column 2: Navigation */}
          <div className="space-y-4">
            <h3 className="label-micro font-semibold text-foreground tracking-wider">Navigation</h3>
            <ul className="space-y-2.5 text-body-sm">
              <li>
                <Link to="/" className="text-muted-foreground hover:text-foreground transition-colors">
                  Home
                </Link>
              </li>
              <li>
                <Link to="/analyze" className="text-muted-foreground hover:text-foreground transition-colors">
                  SatQuery AI Console
                </Link>
              </li>
              <li>
                <Link to="/about" className="text-muted-foreground hover:text-foreground transition-colors">
                  Architecture &amp; Edge Roadmap
                </Link>
              </li>
            </ul>
          </div>

          {/* Column 3: Resources */}
          <div className="space-y-4">
            <h3 className="label-micro font-semibold text-foreground tracking-wider">Resources</h3>
            <ul className="space-y-2.5 text-body-sm">
              <li>
                <a
                  href="https://github.com/XVX-016/Orbital_Pulse"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors"
                >
                  GitHub Repository
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              </li>
              <li>
                <Link to="/about#architecture" className="text-muted-foreground hover:text-foreground transition-colors">
                  System Architecture &amp; Benchmark Report
                </Link>
              </li>
            </ul>
          </div>

          {/* Column 4: Connect */}
          <div className="space-y-4">
            <h3 className="label-micro font-semibold text-foreground tracking-wider">Connect &amp; Organization</h3>
            <div className="flex items-center gap-3">
              <a
                href="https://github.com/XVX-016/Orbital_Pulse"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="GitHub Repository"
                className="flex h-9 w-9 items-center justify-center rounded-md border border-border bg-[#121212] text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
              >
                <GithubIcon className="h-4 w-4" />
              </a>
              <a
                href="https://www.isro.gov.in"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="ISRO Website"
                className="flex h-9 w-9 items-center justify-center rounded-md border border-border bg-[#121212] text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
              >
                <Globe className="h-4 w-4" />
              </a>
              <a
                href="mailto:support@satquery.ai"
                aria-label="Email Support"
                className="flex h-9 w-9 items-center justify-center rounded-md border border-border bg-[#121212] text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
              >
                <Mail className="h-4 w-4" />
              </a>
            </div>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 border-t border-border/60 pt-8 text-caption text-muted-foreground">
          <p>&copy; 2026 SatQuery AI. All rights reserved.</p>
          <p className="text-center sm:text-right">
            Built for <span className="font-semibold text-foreground">Smart India Hackathon 2026</span> &mdash; ISRO / Space Applications Centre (SAC)
          </p>
        </div>
      </div>
    </footer>
  );
}
