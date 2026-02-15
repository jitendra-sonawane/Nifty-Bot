/* ═══════════════════════════════════════════
   NIFTY 50 CONSTITUENTS
   Static data: symbol, name, sector, weightage, ISIN
   Weightage is approximate % from latest NSE data.
   ISIN is used to form Upstox instrument key: NSE_EQ|{isin}
   ═══════════════════════════════════════════ */

export interface Nifty50Company {
    symbol: string;
    name: string;
    sector: string;
    weightage: number;   // % weight in Nifty 50 index
    isin: string;        // ISIN for Upstox instrument key
}

export const NIFTY50_COMPANIES: Nifty50Company[] = [
    // ── Financials ──
    { symbol: 'HDFCBANK', name: 'HDFC Bank', sector: 'Financials', weightage: 13.10, isin: 'INE040A01034' },
    { symbol: 'ICICIBANK', name: 'ICICI Bank', sector: 'Financials', weightage: 8.30, isin: 'INE090A01021' },
    { symbol: 'SBIN', name: 'State Bank of India', sector: 'Financials', weightage: 3.20, isin: 'INE062A01020' },
    { symbol: 'KOTAKBANK', name: 'Kotak Mahindra Bank', sector: 'Financials', weightage: 2.60, isin: 'INE237A01028' },
    { symbol: 'AXISBANK', name: 'Axis Bank', sector: 'Financials', weightage: 2.40, isin: 'INE238A01034' },
    { symbol: 'BAJFINANCE', name: 'Bajaj Finance', sector: 'Financials', weightage: 2.10, isin: 'INE296A01024' },
    { symbol: 'BAJAJFINSV', name: 'Bajaj Finserv', sector: 'Financials', weightage: 0.80, isin: 'INE918I01018' },
    { symbol: 'HDFCLIFE', name: 'HDFC Life Insurance', sector: 'Financials', weightage: 0.80, isin: 'INE795G01014' },
    { symbol: 'SBILIFE', name: 'SBI Life Insurance', sector: 'Financials', weightage: 0.70, isin: 'INE123W01016' },
    { symbol: 'SHRIRAMFIN', name: 'Shriram Finance', sector: 'Financials', weightage: 0.60, isin: 'INE721A01013' },

    // ── Information Technology ──
    { symbol: 'INFY', name: 'Infosys', sector: 'IT', weightage: 6.20, isin: 'INE009A01021' },
    { symbol: 'TCS', name: 'Tata Consultancy Services', sector: 'IT', weightage: 4.50, isin: 'INE467B01029' },
    { symbol: 'HCLTECH', name: 'HCL Technologies', sector: 'IT', weightage: 1.80, isin: 'INE860A01027' },
    { symbol: 'WIPRO', name: 'Wipro', sector: 'IT', weightage: 0.90, isin: 'INE075A01022' },
    { symbol: 'TECHM', name: 'Tech Mahindra', sector: 'IT', weightage: 0.80, isin: 'INE669C01036' },

    // ── Energy & Oil ──
    { symbol: 'RELIANCE', name: 'Reliance Industries', sector: 'Energy', weightage: 8.80, isin: 'INE002A01018' },
    { symbol: 'ONGC', name: 'Oil & Natural Gas Corp', sector: 'Energy', weightage: 1.10, isin: 'INE213A01029' },
    { symbol: 'NTPC', name: 'NTPC', sector: 'Energy', weightage: 1.20, isin: 'INE733E01010' },
    { symbol: 'POWERGRID', name: 'Power Grid Corp', sector: 'Energy', weightage: 0.90, isin: 'INE752E01010' },
    { symbol: 'BPCL', name: 'Bharat Petroleum', sector: 'Energy', weightage: 0.60, isin: 'INE029A01011' },
    { symbol: 'COALINDIA', name: 'Coal India', sector: 'Energy', weightage: 0.60, isin: 'INE522F01014' },
    { symbol: 'ADANIENT', name: 'Adani Enterprises', sector: 'Energy', weightage: 1.00, isin: 'INE423A01024' },
    { symbol: 'ADANIPORTS', name: 'Adani Ports & SEZ', sector: 'Infrastructure', weightage: 1.10, isin: 'INE742F01042' },

    // ── Consumer & FMCG ──
    { symbol: 'HINDUNILVR', name: 'Hindustan Unilever', sector: 'FMCG', weightage: 2.30, isin: 'INE030A01027' },
    { symbol: 'ITC', name: 'ITC', sector: 'FMCG', weightage: 3.90, isin: 'INE154A01025' },
    { symbol: 'NESTLEIND', name: 'Nestle India', sector: 'FMCG', weightage: 0.70, isin: 'INE239A01016' },
    { symbol: 'TATACONSUM', name: 'Tata Consumer Products', sector: 'FMCG', weightage: 0.50, isin: 'INE192A01025' },
    { symbol: 'BRITANNIA', name: 'Britannia Industries', sector: 'FMCG', weightage: 0.50, isin: 'INE216A01030' },

    // ── Automobile ──
    { symbol: 'M&M', name: 'Mahindra & Mahindra', sector: 'Automobile', weightage: 2.70, isin: 'INE101A01026' },
    { symbol: 'MARUTI', name: 'Maruti Suzuki', sector: 'Automobile', weightage: 1.50, isin: 'INE585B01010' },
    { symbol: 'TATAMOTORS', name: 'Tata Motors', sector: 'Automobile', weightage: 1.30, isin: 'INE155A01022' },
    { symbol: 'BAJAJ-AUTO', name: 'Bajaj Auto', sector: 'Automobile', weightage: 0.90, isin: 'INE917I01010' },
    { symbol: 'EICHERMOT', name: 'Eicher Motors', sector: 'Automobile', weightage: 0.60, isin: 'INE066A01021' },
    { symbol: 'HEROMOTOCO', name: 'Hero MotoCorp', sector: 'Automobile', weightage: 0.60, isin: 'INE158A01026' },

    // ── Metals & Materials ──
    { symbol: 'TATASTEEL', name: 'Tata Steel', sector: 'Metals', weightage: 0.90, isin: 'INE081A01020' },
    { symbol: 'JSWSTEEL', name: 'JSW Steel', sector: 'Metals', weightage: 0.80, isin: 'INE019A01038' },
    { symbol: 'HINDALCO', name: 'Hindalco Industries', sector: 'Metals', weightage: 0.70, isin: 'INE038A01020' },

    // ── Pharma & Healthcare ──
    { symbol: 'SUNPHARMA', name: 'Sun Pharma', sector: 'Pharma', weightage: 1.50, isin: 'INE044A01036' },
    { symbol: 'DRREDDY', name: "Dr. Reddy's Labs", sector: 'Pharma', weightage: 0.80, isin: 'INE089A01023' },
    { symbol: 'CIPLA', name: 'Cipla', sector: 'Pharma', weightage: 0.70, isin: 'INE059A01026' },
    { symbol: 'APOLLOHOSP', name: 'Apollo Hospitals', sector: 'Healthcare', weightage: 0.70, isin: 'INE437A01024' },

    // ── Telecom ──
    { symbol: 'BHARTIARTL', name: 'Bharti Airtel', sector: 'Telecom', weightage: 3.40, isin: 'INE397D01024' },

    // ── Cement & Construction ──
    { symbol: 'ULTRACEMCO', name: 'UltraTech Cement', sector: 'Cement', weightage: 1.00, isin: 'INE481G01011' },
    { symbol: 'GRASIM', name: 'Grasim Industries', sector: 'Cement', weightage: 0.70, isin: 'INE047A01021' },

    // ── Conglomerate ──
    { symbol: 'LT', name: 'Larsen & Toubro', sector: 'Construction', weightage: 2.80, isin: 'INE018A01030' },
    { symbol: 'TITAN', name: 'Titan Company', sector: 'Consumer', weightage: 1.20, isin: 'INE280A01028' },

    // ── Diversified ──
    { symbol: 'ASIANPAINT', name: 'Asian Paints', sector: 'Consumer', weightage: 1.00, isin: 'INE021A01026' },
    { symbol: 'INDUSINDBK', name: 'IndusInd Bank', sector: 'Financials', weightage: 0.60, isin: 'INE095A01012' },
    { symbol: 'DIVISLAB', name: "Divi's Laboratories", sector: 'Pharma', weightage: 0.60, isin: 'INE361B01024' },
    { symbol: 'TRENT', name: 'Trent', sector: 'Consumer', weightage: 0.60, isin: 'INE849A01020' },
    { symbol: 'BEL', name: 'Bharat Electronics', sector: 'Defence', weightage: 0.70, isin: 'INE263A01024' },
];

/** Build Upstox instrument key from ISIN */
export function toInstrumentKey(isin: string): string {
    return `NSE_EQ|${isin}`;
}

/** All unique ISINs (deduplicated) */
export const NIFTY50_ISINS = [...new Set(NIFTY50_COMPANIES.map(c => c.isin))];

/** Lookup map: ISIN → company */
export const ISIN_TO_COMPANY = new Map(
    NIFTY50_COMPANIES.map(c => [c.isin, c])
);

/** Lookup map: symbol → company */
export const SYMBOL_TO_COMPANY = new Map(
    NIFTY50_COMPANIES.map(c => [c.symbol, c])
);
