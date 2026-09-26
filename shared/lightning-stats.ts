/**
 * Citable lightning statistics for the Track B severe-weather dashboard.
 *
 * Every figure below was read directly in the linked primary source (Prompt 9
 * citation check, 2026-09-25). Rules for adding to or using this list:
 *   • Never mix SRC Odisha (financial year) and NCRB (calendar year) figures in
 *     one series — the two count different periods.
 *   • No CROPC or IMD figure exists for Mayurbhanj or the Chota Nagpur plateau
 *     as a region; do not attribute one to them.
 *   • Not included because no primary source was found: "119 Mayurbhanj deaths
 *     2023-25" (news only) and "297 Odisha deaths FY 2022-23" (unverified).
 */

export interface LightningStat {
  figure: string;
  region: string;
  period: string;
  source: string;
  publisher: string;
  url: string;
  location: string; // page / table within the source
  caveat?: string;
}

const SRC_ODISHA_2021_22 =
  "https://srcodisha.nic.in/annualReport/4vP2yUSqANNUAL%20REPORT%20ON%20NATURAL%20CALAMITIES,2021-22.pdf";
const NCRB_ADSI_2022 =
  "https://ncrb.gov.in/uploads/nationalcrimerecordsbureau/custom/adsiyearwise2022/1701611156012ADSI2022Publication2022.pdf";
const CROPC_2023_24 =
  "https://www.cropc.org/static/media/Annual_Lightning_Report_2023-2024_Ex_Summary.1edff6ec97a35d6c3de9.pdf";

export const LIGHTNING_STATS: LightningStat[] = [
  {
    figure: "18 lightning deaths",
    region: "Mayurbhanj district, Odisha",
    period: "FY 2021-22",
    source: "Annual Report on Natural Calamities 2021-22",
    publisher: "Special Relief Commissioner, Govt. of Odisha",
    url: SRC_ODISHA_2021_22,
    location: "Sec. 3.7.ii, p. 64 (district table)",
    caveat: "Deaths column of the district table; ex-gratia was paid in 18 of the 18 cases.",
  },
  {
    figure: "281 lightning deaths across 30 districts",
    region: "Odisha",
    period: "FY 2021-22",
    source: "Annual Report on Natural Calamities 2021-22",
    publisher: "Special Relief Commissioner, Govt. of Odisha",
    url: SRC_ODISHA_2021_22,
    location: "Sec. 3.7.ii, p. 64",
  },
  {
    figure: "316 lightning deaths",
    region: "Odisha",
    period: "2022",
    source: "Accidental Deaths & Suicides in India 2022",
    publisher: "National Crime Records Bureau (MHA)",
    url: NCRB_ADSI_2022,
    location: "Table 1.9, p. 40",
  },
  {
    figure: "267 lightning deaths",
    region: "Jharkhand",
    period: "2022",
    source: "Accidental Deaths & Suicides in India 2022",
    publisher: "National Crime Records Bureau (MHA)",
    url: NCRB_ADSI_2022,
    location: "Table 1.9, p. 40",
  },
  {
    figure: "161 lightning deaths",
    region: "West Bengal",
    period: "2022",
    source: "Accidental Deaths & Suicides in India 2022",
    publisher: "National Crime Records Bureau (MHA)",
    url: NCRB_ADSI_2022,
    location: "Table 1.9, p. 40",
  },
  {
    figure: "2,887 lightning deaths (35.8% of deaths from forces of nature)",
    region: "India",
    period: "2022",
    source: "Accidental Deaths & Suicides in India 2022",
    publisher: "National Crime Records Bureau (MHA)",
    url: NCRB_ADSI_2022,
    location: "Table 1.0, p. 13",
  },
  {
    figure: "Cloud-to-ground strikes fell from 72 lakh to 57 lakh (−21%)",
    region: "India",
    period: "2022-23 → 2023-24",
    source: "Annual Lightning Report 2023-24 (Executive Summary)",
    publisher: "CROPC / Lightning Resilient India Campaign (IITM data)",
    url: CROPC_2023_24,
    location: "PDF p. 13, Major Highlights",
  },
  {
    figure: "Cumulative lightning deaths: Odisha 5,787 · Jharkhand 3,145 · West Bengal 3,042",
    region: "Odisha, Jharkhand, West Bengal",
    period: "2001–2024",
    source: "Annual Lightning Report 2023-24 (Executive Summary)",
    publisher: "CROPC / Lightning Resilient India Campaign (credits NCRB)",
    url: CROPC_2023_24,
    location: "PDF p. 14, map",
    caveat: "Values read from a map graphic.",
  },
];
