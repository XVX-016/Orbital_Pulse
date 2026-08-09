export interface Mission {
  id: string;
  name: string;
  agency: string;
  launched: string;
  orbit: string;
  status: "active" | "en-route" | "completed";
  summary: string;
  altitude: number;
  velocity: number;
  inclination: number;
}

export const missions: Mission[] = [
  {
    id: "MSN-01",
    name: "Helios Solar Observer",
    agency: "Orbital Sciences Division",
    launched: "2023-03-14",
    orbit: "Heliosynchronous",
    status: "active",
    summary:
      "Continuous monitoring of solar wind activity and coronal mass ejections from a stable heliocentric vantage point.",
    altitude: 408.2,
    velocity: 7.66,
    inclination: 28.5,
  },
  {
    id: "MSN-02",
    name: "Meridian Deep Relay",
    agency: "Deep Space Network",
    launched: "2022-11-02",
    orbit: "Geostationary Transfer",
    status: "en-route",
    summary:
      "Communications relay currently transiting to geostationary insertion to extend deep-space downlink coverage.",
    altitude: 35786.0,
    velocity: 3.07,
    inclination: 0.1,
  },
  {
    id: "MSN-03",
    name: "Cygnus Watch",
    agency: "Near-Earth Object Program",
    launched: "2021-06-21",
    orbit: "Low Earth Orbit",
    status: "active",
    summary:
      "Wide-field survey platform tracking near-Earth asteroids and debris in low orbital altitudes.",
    altitude: 610.9,
    velocity: 7.51,
    inclination: 97.4,
  },
  {
    id: "MSN-04",
    name: "Polestar IV",
    agency: "Orbital Sciences Division",
    launched: "2019-09-08",
    orbit: "Geostationary",
    status: "completed",
    summary:
      "Decommissioned weather observation platform, retained in catalog for historical trajectory reference.",
    altitude: 35786.0,
    velocity: 3.07,
    inclination: 0.0,
  },
];
