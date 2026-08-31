import { useLocation } from "react-router-dom";
import { useEffect } from "react";
import { Link } from "react-router-dom";

const NotFound = () => {
  const location = useLocation();

  useEffect(() => {
    console.error(
      "404 Error: User attempted to access non-existent route:",
      location.pathname,
    );
  }, [location.pathname]);

  return (
    <div className="flex min-h-screen items-center justify-center px-6 pt-16">
      <div className="panel max-w-md rounded-lg p-6 text-center">
        <p className="label-micro mb-3">Error 404</p>
        <h1 className="text-title font-semibold text-foreground mb-3">
          Signal lost
        </h1>
        <p className="text-body text-muted-foreground mb-8">
          This coordinate doesn&apos;t map to anything in the tracking
          network.
        </p>
        <Link
          to="/"
          className="text-body text-foreground border-b border-primary pb-0.5"
        >
          Return to Mission Control
        </Link>
      </div>
    </div>
  );
};

export default NotFound;
