import { describe, it, expect } from "vitest";
import {
  parseTLECatalog,
  propagateSatellite,
  HARDCODED_TLE_STRING,
  fetchSatelliteCatalog,
} from "./satellite-service";

describe("satellite-service", () => {
  it("parses hardcoded TLE string into satellite entries", () => {
    const satellites = parseTLECatalog(HARDCODED_TLE_STRING);
    expect(satellites.length).toBeGreaterThanOrEqual(18);

    const iss = satellites.find((s) => s.noradId === "25544");
    expect(iss).toBeDefined();
    expect(iss?.name).toContain("ISS");
  });

  it("propagates satellite coordinates and velocity accurately", () => {
    const satellites = parseTLECatalog(HARDCODED_TLE_STRING);
    const iss = satellites.find((s) => s.noradId === "25544");
    expect(iss).toBeDefined();

    if (iss) {
      const pos = propagateSatellite(iss.satrec, new Date());
      expect(pos).not.toBeNull();
      if (pos) {
        expect(pos.latitude).toBeGreaterThanOrEqual(-90);
        expect(pos.latitude).toBeLessThanOrEqual(90);
        expect(pos.longitude).toBeGreaterThanOrEqual(-180);
        expect(pos.longitude).toBeLessThanOrEqual(180);
        expect(pos.altitude).toBeGreaterThan(150);
        expect(pos.altitude).toBeLessThan(1000);
        expect(pos.velocity).toBeGreaterThan(5.0);
        expect(pos.velocity).toBeLessThan(10.0);
      }
    }
  });

  it("fetches satellite catalog and utilizes fallback/cache", async () => {
    const result = await fetchSatelliteCatalog();
    expect(result.satellites.length).toBeGreaterThan(0);
    expect(["live", "fallback"]).toContain(result.source);
  }, 10000);
});
