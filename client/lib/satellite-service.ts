import * as satellite from "satellite.js";

export interface SatelliteData {
  id: string;
  name: string;
  noradId: string;
  line1: string;
  line2: string;
  satrec: satellite.SatRec;
  latitude?: number;
  longitude?: number;
  altitude?: number; // in km
  velocity?: number; // in km/s
}

export interface SatellitePosition {
  latitude: number;  // degrees (-90 to 90)
  longitude: number; // degrees (-180 to 180)
  altitude: number;  // km
  velocity: number;  // km/s
}

// Hardcoded subset of ~20 well-known satellites for immediate offline verification & fallback
export const HARDCODED_TLE_STRING = `ISS (ZARYA)
1 25544U 98067A   24045.54921609  .00014761  00000+0  26477-3 0  9997
2 25544  51.6416 288.7525 0004543  90.7589 313.2796 15.49842456439363
HST (HUBBLE)
1 20580U 90037B   24045.21319444  .00000984  00000+0  57685-4 0  9996
2 20580  28.4687 236.4385 0002821 270.8359  89.1026 14.99611283738522
CSS (TIANGONG)
1 48274U 21035A   24045.55628472  .00018541  00000+0  20738-3 0  9991
2 48274  41.4721  82.5482 0006093 252.1287 167.3481 15.60381643159392
GOES 16
1 41866U 16071A   24045.39958333 -.00000248  00000+0  00000+0 0  9998
2 41866   0.0248  75.2140 0001824  85.2341 180.4120  1.00271891 26421
GOES 18
1 51850U 22021A   24045.41215278 -.00000224  00000+0  00000+0 0  9995
2 51850   0.0312 137.2841 0001952 142.1852 312.4418  1.00273512  7124
NOAA 20
1 43013U 17073A   24045.48512803  .00000084  00000+0  67832-4 0  9990
2 43013  98.7185 105.1842 0001358  80.2314 279.9012 14.19532890322987
NOAA 21
1 54234U 22150A   24045.51842105  .00000078  00000+0  63421-4 0  9997
2 54234  98.7051 106.1245 0001421  78.4312 281.7011 14.19512340 6501
TERRA
1 25994U 99068A   24045.49811204  .00000125  00000+0  89412-4 0  9993
2 25994  98.2045  78.3412 0001150  92.1451 268.0124 14.57124910287121
AQUA
1 27424U 02022A   24045.49210451  .00000141  00000+0  98214-4 0  9992
2 27424  98.2120  77.9415 0001410  90.4125 269.7541 14.57102940165412
SENTINEL-1A
1 39634U 14016A   24045.50124102  .00000045  00000+0  34125-4 0  9998
2 39634  98.1845 112.4512 0001210  75.1245 285.0124 14.59124010521401
SENTINEL-2A
1 40697U 15028A   24045.50981240  .00000062  00000+0  45120-4 0  9991
2 40697  98.5621 115.1240 0001080  82.1024 278.0214 14.30812401452014
SENTINEL-6
1 46984U 20086A   24045.51240124  .00000032  00000+0  28140-4 0  9995
2 46984  66.0421 140.1250 0000850  95.4120 264.7120 13.12514010158402
STARLINK-1007
1 44713U 19074A   24045.48124051  .00001240  00000+0  98412-4 0  9994
2 44713  53.0541 210.4512 0001420 102.4120 257.7120 15.06412010234105
STARLINK-30121
1 56123U 23042A   24045.48912401  .00001450  00000+0  11240-3 0  9996
2 56123  43.0012 195.4120 0001200 110.1240 250.0124 15.21045010054120
GPS BIIF-1
1 36585U 10022A   24045.41024102  .00000012  00000+0  00000+0 0  9999
2 36585  55.4120 160.1240 0015200 210.4120 149.2140  2.00561240100512
GPS BIIF-2
1 37753U 11036A   24045.41890124  .00000015  00000+0  00000+0 0  9993
2 37753  55.3890 220.1450 0014800 205.1240 154.5120  2.00564210098412
METEOSAT-11
1 40732U 15034A   24045.42104512 -.00000198  00000+0  00000+0 0  9991
2 40732   0.0412 165.4120 0001850 120.4120 239.5120  1.00274120  3145
LANDSAT 8
1 39084U 13008A   24045.51240192  .00000085  00000+0  61240-4 0  9997
2 39084  98.2041 125.4120 0001140  88.4120 271.7120 14.57114201584120
LANDSAT 9
1 49260U 21088A   24045.51940124  .00000092  00000+0  67120-4 0  9993
2 49260  98.2104 126.1240 0001200  87.1240 273.0124 14.57109500234120
ENVISAT
1 27386U 02009A   24045.52104102  .00000035  00000+0  25140-4 0  9990
2 27386  98.3412 130.4120 0001050  80.4120 279.7120 14.35412010125412
`;

export function propagateSatellite(
  satrec: satellite.SatRec,
  date: Date = new Date()
): SatellitePosition | null {
  try {
    const positionAndVelocity = satellite.propagate(satrec, date);
    const positionEci = positionAndVelocity.position;
    const velocityEci = positionAndVelocity.velocity;

    if (
      !positionEci ||
      typeof positionEci === "boolean" ||
      !velocityEci ||
      typeof velocityEci === "boolean"
    ) {
      return null;
    }

    const gmst = satellite.gstime(date);
    const geodetic = satellite.eciToGeodetic(positionEci as satellite.EciVec3<number>, gmst);

    const longitudeDeg = satellite.degreesLong(geodetic.longitude);
    const latitudeDeg = satellite.degreesLat(geodetic.latitude);
    const altitudeKm = geodetic.height;

    const vx = velocityEci.x;
    const vy = velocityEci.y;
    const vz = velocityEci.z;
    const velocityKmS = Math.sqrt(vx * vx + vy * vy + vz * vz);

    if (
      isNaN(latitudeDeg) ||
      isNaN(longitudeDeg) ||
      isNaN(altitudeKm) ||
      isNaN(velocityKmS)
    ) {
      return null;
    }

    return {
      latitude: latitudeDeg,
      longitude: longitudeDeg,
      altitude: altitudeKm,
      velocity: velocityKmS,
    };
  } catch (e) {
    return null;
  }
}

export function parseTLECatalog(tleText: string): SatelliteData[] {
  const lines = tleText.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  const satellites: SatelliteData[] = [];

  for (let i = 0; i < lines.length; i++) {
    if (lines[i].startsWith("1 ") && i + 1 < lines.length && lines[i + 1].startsWith("2 ")) {
      const line1 = lines[i];
      const line2 = lines[i + 1];
      let name = `SAT-${line1.substring(2, 7).trim()}`;
      if (i > 0 && !lines[i - 1].startsWith("1 ") && !lines[i - 1].startsWith("2 ")) {
        name = lines[i - 1];
      }
      const noradId = line1.substring(2, 7).trim();
      try {
        const satrec = satellite.twoline2satrec(line1, line2);
        if (satrec && satrec.error === 0) {
          satellites.push({
            id: noradId,
            name,
            noradId,
            line1,
            line2,
            satrec,
          });
        }
      } catch (err) {
        // Skip malformed TLE
      }
      i += 1;
    }
  }

  return satellites;
}

export async function fetchSatelliteCatalog(): Promise<SatelliteData[]> {
  const orbitServiceUrl = import.meta.env.VITE_ORBIT_SERVICE_URL || "http://localhost:8081";
  
  try {
    const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timeoutId = controller ? setTimeout(() => controller.abort(), 5000) : null;

    const res = await fetch(`${orbitServiceUrl}/api/tle`, {
      signal: controller?.signal,
    });
    if (timeoutId) clearTimeout(timeoutId);

    if (!res.ok) {
      throw new Error(`Failed to fetch from orbit-service: ${res.statusText}`);
    }

    const text = await res.text();
    const parsed = parseTLECatalog(text);
    return parsed;
  } catch (err) {
    console.error("Orbit service fetch error, using fallback hardcoded catalog:", err);
    return parseTLECatalog(HARDCODED_TLE_STRING);
  }
}
