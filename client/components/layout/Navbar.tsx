import { useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";

const NAV_LINKS = [
  { to: "/globe", label: "Globe" },
  { to: "/change-detection", label: "Change Detection" },
  { to: "/about", label: "About" },
];

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={cn(
        "pointer-events-none fixed top-0 left-0 right-0 z-50 h-16 transition-all duration-200 bg-[#0A0A0A]/90 backdrop-blur-md border-b",
        scrolled ? "border-border shadow-md" : "border-white/10"
      )}
    >
      <div className="pointer-events-auto mx-auto flex h-full max-w-[1400px] items-center justify-between px-6">
        <Link
          to="/"
          className="text-body font-semibold tracking-[0.02em] text-foreground"
        >
          ORBITAL PULSE
        </Link>

        <nav className="flex items-center gap-8">
          {NAV_LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                cn(
                  "text-body text-secondary-foreground/0 pb-1 border-b border-transparent transition-colors",
                  isActive
                    ? "text-foreground border-primary"
                    : "text-muted-foreground hover:text-foreground",
                )
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  );
}
