import json
import re
from rule_engine import run_engine
from dotenv import load_dotenv
import os

# =========================
# Claude API Call
# =========================

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


def extract_params_from_query(user_query):
    import urllib.request

    system_prompt = """You are an expert Indian motor insurance parameter extractor.

Your job: Read a WhatsApp query (structured or unstructured), reason about it, and return a JSON with extracted insurance parameters.

Return ONLY valid JSON. No explanation, no markdown, no extra text. Current year is 2026.

=== PARAMETERS TO EXTRACT ===
- company: insurance company name or "all"
- sub_product: exact vehicle type string (see MASTER VEHICLE TABLE below)
- segment: coverage type
- rto: RTO location code
- fuel: fuel type or ""
- ncb: "yes"/"no" or ""
- highend: "yes"/"no" or ""
- cpa: "yes"/"no" or ""
- vehicle_make: brand name lowercase or ""
- cc: engine CC or ""
- seating: seating capacity number or ""
- weight: vehicle weight in kg (numeric string) or ""
- age: vehicle age or ""
- nil_dep: "yes"/"no" or ""
- wheels: number of wheels as string or ""

=== MASTER VEHICLE TABLE ===

This is the EXACT list of vehicle types in our system. Your job is to pick the BEST MATCHING entry for the query.
Return the exact "vehicle_type" string as sub_product. Never invent a new string.

ID | vehicle_type               | wheels | sub_product_name
---|----------------------------|--------|-------------------
1  | Agriculture Tractor        | 4      | Miscellaneous Vehicle
2  | Non Tractor                | 4      | Miscellaneous Vehicle
3  | Truck                      | 4      | Goods Vehicle
4  | Good Carring Tractor       | 4      | Goods Vehicle
5  | Tanker                     | 4      | Goods Vehicle
6  | Pickup                     | 4      | Goods Vehicle
7  | GCV 3W Delivery Van        | 3      | Goods Vehicle
8  | Taxi_CAB                   | 4      | Passenger Vehicle
9  | Electric Rikshaw           | 3      | Passenger Vehicle
10 | Tempo Traveller            | 4      | Passenger Vehicle
11 | School Bus                 | 4      | Passenger Vehicle
12 | Passanger Bus              | 4      | Passenger Vehicle
13 | Auto rikshaw               | 3      | Passenger Vehicle
14 | 3W Tipper                  | 3      | Goods Vehicle
15 | PCV 2W                     | 2      | Passenger Vehicle
16 | GCV 2W                     | 2      | Goods Vehicle
17 | TW Scooter                 | 2      | Two Wheeler
18 | TW Bike                    | 2      | Two Wheeler
19 | Private Car                | 4      | Private Car
20 | TW Electric Bike           | 2      | Two Wheeler
21 | Electric GCV 3W Delivery Van | 3    | Goods Vehicle
22 | Private Car Electric       | 4      | Private Car
23 | Trailer                    | 4      | Goods Vehicle
24 | Electric Pickup            | 4      | Goods Vehicle
25 | Tipper                     | 4      | Goods Vehicle
26 | TW Electric Scooter        | 2      | Two Wheeler
27 | PC Petrol / Electric Hybrid| 4      | Private Car
28 | Staff Bus                  | 4      | Passenger Vehicle
29 | Agriculture Harvester      | 4      | Miscellaneous Vehicle
30 | Electric PCV 2W            | 2      | Passenger Vehicle
31 | Electric Taxi_CAB          | 4      | Passenger Vehicle
32 | Route Bus                  | 4      | Passenger Vehicle
33 | Kali-pili                  | 4      | Passenger Vehicle
34 | Ambulance                  | 4      | Miscellaneous Vehicle
35 | Cranes                     | 4      | Miscellaneous Vehicle
36 | Transit Mixers             | 4      | Miscellaneous Vehicle
37 | Excavators                 | 4      | Miscellaneous Vehicle
38 | Garbage Vehicles           | 4      | Miscellaneous Vehicle
39 | Construction Equipment     | 4      | Miscellaneous Vehicle

=== HOW TO SELECT sub_product ===

MISCELLANEOUS VEHICLE SIGNALS:
  "misd" / "msv" / "misc" / "miscellaneous" → sub_product_name = "Miscellaneous Vehicle"
  misd + harvester → "Agriculture Harvester"
  misd + tractor (farming) → "Agriculture Tractor"
  misd + tractor (non-farming) → "Non Tractor"
  misd + ambulance → "Ambulance"
  misd + crane → "Cranes"
  misd + transit mixer / concrete mixer → "Transit Mixers"
  misd + excavator / jcb → "Excavators"
  misd + garbage / waste → "Garbage Vehicles"
  misd + construction → "Construction Equipment"
  misd + no further detail → sub_product: "misd"  ← rule_engine handles this

Use ALL available signals — keywords, fuel, wheels, weight, seating, model name — to pick the best match.

FUEL SIGNALS (critical for electric vehicles):
  fuel=electric + two wheeler + scooter style → "TW Electric Scooter"
  fuel=electric + two wheeler + bike style → "TW Electric Bike"
  fuel=electric + private car → "Private Car Electric"
  fuel=electric + taxi/cab → "Electric Taxi_CAB"
  fuel=electric + auto/rikshaw/3w passenger → "Electric Rikshaw"
  fuel=electric + 3w goods/delivery → "Electric GCV 3W Delivery Van"
  fuel=electric + pickup/small goods 4w → "Electric Pickup"
  fuel=electric + 2w passenger → "Electric PCV 2W"
  fuel=petrol/diesel + private car + also has EV mode → "PC Petrol / Electric Hybrid"

WHEEL + USE SIGNALS:
  3 wheels + goods/delivery/cargo → "GCV 3W Delivery Van" or "Electric GCV 3W Delivery Van" (if electric)
  3 wheels + tipper → "3W Tipper"
  3 wheels + passenger/auto/rikshaw → "Auto rikshaw" or "Electric Rikshaw" (if electric)
  2 wheels + scooter/gearless → "TW Scooter" or "TW Electric Scooter" (if electric)
  2 wheels + bike/motorcycle → "TW Bike" or "TW Electric Bike" (if electric)
  2 wheels + passenger commercial use → "PCV 2W" or "Electric PCV 2W" (if electric)
  2 wheels + goods use → "GCV 2W"
  4 wheels + personal use → "Private Car" or "Private Car Electric" (if electric)
  4 wheels + taxi/cab/ola/uber → "Taxi_CAB" or "Electric Taxi_CAB" (if electric)
  4 wheels + bus + school → "School Bus"
  4 wheels + bus + passenger/route → "Passanger Bus" or "Route Bus"
  4 wheels + bus + staff/employee → "Staff Bus"
  4 wheels + tempo traveller/TT → "Tempo Traveller"
  4 wheels + truck/lorry/goods heavy → "Truck"
  4 wheels + tanker → "Tanker"
  4 wheels + pickup/mini goods → "Pickup" or "Electric Pickup" (if electric)
  4 wheels + tipper → "Tipper"
  4 wheels + trailer → "Trailer"
  4 wheels + tractor (farming) → "Agriculture Tractor"
  4 wheels + tractor (non-farming/construction) → "Non Tractor" or "Good Carring Tractor"
  4 wheels + harvester → "Agriculture Harvester"

MODEL NAME REASONING (brand alone is NOT enough):
  TVS King, Bajaj RE, Piaggio Ape, Mahindra Treo → 3-wheeler passenger → "Auto rikshaw" or "Electric Rikshaw"
  TVS Apache, Bajaj Pulsar, Hero Splendor → bike → "TW Bike"
  Honda Activa, TVS Jupiter, Suzuki Access → scooter → "TW Scooter"
  Maruti Swift, Hyundai i20, Tata Nexon → private car → "Private Car"
  Tata Ace, Mahindra Bolero Pickup → pickup/mini goods → "Pickup"

GVW SPECIAL RULE:
  "gvw" in query → sub_product: "gvw" (this is a special override, NOT in master table, kept as-is)
  The rule_engine handles gvw→gcv mapping internally.

If NO clear match possible → sub_product: ""

=== COMPANY MAPPING ===
"sbi", "sbi general" → "sbi"
"tata", "tata aig" → "tata"
"hdfc", "hdfc ergo" → "hdfc"
"digit", "go digit" → "digit"
"liberty" → "liberty"
"shriram", "shriram general" → "shriram"
"sompo", "sompo general", "universal" → "sompo"
"bajaj", "bajaj allianz" → "bajaj"
"icici", "icici lombard" → "icici"
"reliance" → "reliance"
"new india", "new india assurance" → "new india"
"future", "future generali" → "future"
"kotak", "kotak mahindra" → "kotak"
"magma", "magma hdi" → "magma"
"royal", "royal sundaram" → "royal"
"chola", "cholamandalam" → "chola"
"zuno" → "zuno"
If not mentioned → "all"

=== SEGMENT MAPPING ===
"comp", "comprehensive", "package", "od+tp", "full" → "comp"
"tp", "tp only", "third party", "satp", "aotp" → "tp"
"saod", "od only", "standalone od" → "saod"
"all", "both" → "all"
If not mentioned → "comp"

=== RTO MAPPING ===
Format: lowercase, no spaces, no hyphens. e.g. "MH-15" → "mh15", "UP 60" → "up60"
"pan india", "all india", "all rto", "PAN" → "pan india"
City names: MUMBAI→"mh", DELHI→"dl", BANGALORE/BENGALURU→"ka", CHENNAI→"tn",
HYDERABAD→"ts", PUNE→"mh", AHMEDABAD→"gj", KOLKATA→"wb", JAIPUR→"rj", LUCKNOW→"up"
If not mentioned → "pan india"

=== FUEL MAPPING ===
"petrol", "patrol" → "petrol" | "diesel", "dsl" → "diesel"
"electric", "ev", "e-vehicle", "battery", "EV" → "electric"
"cng" → "cng" | "petrol+cng", "cng+petrol" → "petrol-cng"
If not mentioned → ""

=== WEIGHT MAPPING ===
Extract numeric KG value only.
"35T", "35 ton" → "35000" | "2.5t", "2.5 ton" → "2500" | "2960 kg" → "2960"
"above 12T" → "above 12000" | "upto 7.5T" → "upto 7500"
If not mentioned → ""

=== AGE MAPPING ===
If year given → age = 2026 - year. "Year-2022" → 4 → "4 year"
"new", "brand new" → "new" | "Year-2025" or "Year-2026" → "new"
"old" → "old" | "above 5 yrs" → "above 5 year"
If not mentioned → ""

=== CC MAPPING ===
"above 150cc" → "above 150" | "upto 75cc" → "upto 75" | "75-150" → "75-150"
If not mentioned → ""

=== SEATING MAPPING ===
IMPORTANT: "SETTING", "seating", "seat", "seats", "seater" — all mean seating capacity.
"SETTING = 4" → seating: "4" | "(1+4)" or "1+4" → "5" | "(2+8)" → "10" | "(1+5)" → "6"
"above 12" → "above 12" | "upto 12" → "12"
If not mentioned → ""

=== WHEELS MAPPING ===
Any XW/Xw pattern = number of wheels. "3w" → wheels:"3", "2W" → wheels:"2"
ALSO: if sub_product reasoning gives "pcv" for a 3-wheeler → set wheels:"3"
If not mentioned → ""

=== VEHICLE MAKE MAPPING ===
Extract brand only, lowercase. "Make-Tata" → "tata", "TVS MOTOR" → "tvs", "MSIL" → "maruti"
If not mentioned → ""

=== EXAMPLES (showing sub_product from master table) ===

Query: "RTO = UP78, MAKE = TVS MOTOR, MODEL = TVS KING EP3, FUEL = ELECTRIC, SETTING = 4"
Reasoning: TVS King EP3 is a 3-wheeler electric auto. fuel=electric + 3w passenger → "Electric Rikshaw". SETTING=4 → seating=4. wheels=3.
Output: {"company":"all","sub_product":"Electric Rikshaw","segment":"comp","rto":"up78","fuel":"electric","ncb":"","highend":"","cpa":"","vehicle_make":"tvs","cc":"","seating":"4","weight":"","age":"","nil_dep":"","wheels":"3"}

Query: "UP-60 Make-Preet Agro Industries Model-Preet 987 Year-2022 Harvester SBI TP rate"
Reasoning: "Harvester" → "Agriculture Harvester". Year 2022 → age=4.
Output: {"company":"sbi","sub_product":"Agriculture Harvester","segment":"tp","rto":"up60","fuel":"","ncb":"","highend":"","cpa":"","vehicle_make":"preet agro industries","cc":"","seating":"","weight":"","age":"4 year","nil_dep":"","wheels":""}

Query: "mh15 tata 35000t gvw sbi above 5 yrs"
Reasoning: "gvw" special keyword → sub_product="gvw" (kept as-is, not from master table).
Output: {"company":"sbi","sub_product":"gvw","segment":"comp","rto":"mh15","fuel":"","ncb":"","highend":"","cpa":"","vehicle_make":"tata","cc":"","seating":"","weight":"35000","age":"above 5 year","nil_dep":"","wheels":""}

Query: "hdfc private car comp mh01 petrol maruti new"
Reasoning: "private car" + petrol → "Private Car".
Output: {"company":"hdfc","sub_product":"Private Car","segment":"comp","rto":"mh01","fuel":"petrol","ncb":"","highend":"","cpa":"","vehicle_make":"maruti","cc":"","seating":"","weight":"","age":"new","nil_dep":"","wheels":""}

Query: "SBI TP two wheeler UP65 electric 2023 model"
Reasoning: two wheeler + electric + no scooter/bike indication → default "TW Electric Bike". wheels=2.
Output: {"company":"sbi","sub_product":"TW Electric Bike","segment":"tp","rto":"up65","fuel":"electric","ncb":"","highend":"","cpa":"","vehicle_make":"","cc":"","seating":"","weight":"","age":"3 year","nil_dep":"","wheels":"2"}

Query: "SBI TP scooter UP65 electric 2023 model"
Reasoning: scooter + electric → "TW Electric Scooter".
Output: {"company":"sbi","sub_product":"TW Electric Scooter","segment":"tp","rto":"up65","fuel":"electric","ncb":"","highend":"","cpa":"","vehicle_make":"","cc":"","seating":"","weight":"","age":"3 year","nil_dep":"","wheels":"2"}

Query: "future 3W auto CNG RTO UP91 comp"
Reasoning: 3w + auto + cng → petrol/cng auto rickshaw → "Auto rikshaw". wheels=3.
Output: {"company":"future","sub_product":"Auto rikshaw","segment":"comp","rto":"up91","fuel":"cng","ncb":"","highend":"","cpa":"","vehicle_make":"","cc":"","seating":"","weight":"","age":"","nil_dep":"","wheels":"3"}

Query: "icici comp rate bajaj maxima 3w up45 petrol new"
Reasoning: Bajaj Maxima = 3-wheeler cargo. 3w + goods → "GCV 3W Delivery Van". wheels=3.
Output: {"company":"icici","sub_product":"GCV 3W Delivery Van","segment":"comp","rto":"up45","fuel":"petrol","ncb":"","highend":"","cpa":"","vehicle_make":"bajaj","cc":"","seating":"","weight":"","age":"new","nil_dep":"","wheels":"3"}

Query: "school bus comp delhi hdfc 30 seater"
Reasoning: school + bus → "School Bus". seating=30.
Output: {"company":"hdfc","sub_product":"School Bus","segment":"comp","rto":"dl","fuel":"","ncb":"","highend":"","cpa":"","vehicle_make":"","cc":"","seating":"30","weight":"","age":"","nil_dep":"","wheels":""}

Query: "tempo traveller 12 seater sbi mh04 comp"
Reasoning: tempo traveller → "Tempo Traveller". seating=12.
Output: {"company":"sbi","sub_product":"Tempo Traveller","segment":"comp","rto":"mh04","fuel":"","ncb":"","highend":"","cpa":"","vehicle_make":"","cc":"","seating":"12","weight":"","age":"","nil_dep":"","wheels":""}

Query: "tata ace pickup mh01 diesel gcv comp new"
Reasoning: pickup + goods + 4w → "Pickup".
Output: {"company":"all","sub_product":"Pickup","segment":"comp","rto":"mh01","fuel":"diesel","ncb":"","highend":"","cpa":"","vehicle_make":"tata","cc":"","seating":"","weight":"","age":"new","nil_dep":"","wheels":""}

Query: "electric taxi cab dl icici comp"
Reasoning: taxi + electric → "Electric Taxi_CAB".
Output: {"company":"icici","sub_product":"Electric Taxi_CAB","segment":"comp","rto":"dl","fuel":"electric","ncb":"","highend":"","cpa":"","vehicle_make":"","cc":"","seating":"","weight":"","age":"","nil_dep":"","wheels":""}

Query: "Reliance Gcv Comp 2T-2.5T electric 3w delivery van solapur"
Reasoning: 3w + goods + electric + delivery → "Electric GCV 3W Delivery Van". Weight 2T = 2000kg.
Output: {"company":"reliance","sub_product":"Electric GCV 3W Delivery Van","segment":"comp","rto":"mh","fuel":"electric","ncb":"","highend":"","cpa":"","vehicle_make":"","cc":"","seating":"","weight":"2000","age":"","nil_dep":"","wheels":"3"}

Query: "maruti swift ev comp mh01 hdfc new"
Reasoning: private car + electric → "Private Car Electric".
Output: {"company":"hdfc","sub_product":"Private Car Electric","segment":"comp","rto":"mh01","fuel":"electric","ncb":"","highend":"","cpa":"","vehicle_make":"maruti","cc":"","seating":"","weight":"","age":"new","nil_dep":"","wheels":""}

=== STRICT RULES ===
1. Return valid JSON only — no text before or after
2. NEVER guess a parameter if not mentioned — use ""
3. Weight MUST be in kg as numeric string
4. Age MUST be calculated if year given (2026 - year)
5. RTO MUST be lowercase, no spaces or hyphens
6. Company MUST be "all" if not mentioned
7. Segment MUST be "comp" if not mentioned
8. RTO MUST be "pan india" if not mentioned
9. "gvw" in query → sub_product MUST be "gvw" (special override, not from master table)
10. sub_product MUST be an exact string from the master vehicle table (or "gvw")
11. NEVER use generic strings like "pcv", "gcv", "two wheeler" — always use the exact master table entry
12. fuel=electric → ALWAYS pick the Electric variant from master table if one exists
13. "SETTING" = seating capacity — always extract the number
14. NEVER assign sub_product from brand name alone — reason from model+fuel+wheels+weight+use-case
15. Unknown new models: use fuel+wheels+use-case signals to pick best master table match
"""

    payload = json.dumps({
        "model": "claude-opus-4-6",
        "max_tokens": 1000,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": user_query}
        ]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01"
        },
        method="POST"
    )

    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode("utf-8"))

    raw_text = result["content"][0]["text"].strip()
    print(f"🤖 Claude extracted: {raw_text}")

    # ── Token usage & cost calculation ──
    # claude-opus-4-6: $5/M input tokens, $25/M output tokens
    # USD to INR: 1 USD = 84 INR (update if needed)
    usage = result.get("usage", {})
    input_tokens  = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
 
    INPUT_COST_PER_M  = 5.00   # USD per million input tokens
    OUTPUT_COST_PER_M = 25.00  # USD per million output tokens
    USD_TO_INR        = 92.0
 
    cost_usd = (input_tokens / 1_000_000 * INPUT_COST_PER_M) + \
               (output_tokens / 1_000_000 * OUTPUT_COST_PER_M)
    cost_inr = cost_usd * USD_TO_INR
 
    print(f"📊 Tokens — Input: {input_tokens}, Output: {output_tokens}")
    print(f"💰 Cost — ${cost_usd:.6f} USD | ₹{cost_inr:.4f} INR")
 
    # Store cost info in a module-level variable so app.py can read it
    extract_params_from_query.last_cost = {
        "input_tokens":  input_tokens,
        "output_tokens": output_tokens,
        "cost_usd":      round(cost_usd, 6),
        "cost_inr":      round(cost_inr, 4),
    }

    # Clean JSON
    raw_text = re.sub(r"```json|```", "", raw_text).strip()

    # NEW: Empty response check
    if not raw_text:
        print("⚠️ Claude returned empty response → using defaults")
        return {
            "company": "all", "sub_product": "", "segment": "comp",
            "rto": "pan india", "fuel": "", "ncb": "", "highend": "",
            "cpa": "", "vehicle_make": "", "cc": "", "seating": "",
            "weight": "", "age": "", "nil_dep": "", "wheels": ""
        }

    try:
        params = json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(f"❌ JSON parse error: {e}")
        print(f"❌ Raw text was: {repr(raw_text)}")
        # ✅ Retry once
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if json_match:
                params = json.loads(json_match.group())
                print(f"✅ JSON extracted via regex")
            else:
                raise ValueError("No JSON found")
        except Exception:
            print("❌ Retry failed → using defaults")
            params = {
                "company": "all", "sub_product": "", "segment": "comp",
                "rto": "pan india", "fuel": "", "ncb": "", "highend": "",
                "cpa": "", "vehicle_make": "", "cc": "", "seating": "",
                "weight": "", "age": "", "nil_dep": "", "wheels": ""
            }

    return params

# Initialise last_cost so it always exists
extract_params_from_query.last_cost = {
    "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "cost_inr": 0.0
}


# =========================
# Company Exclusion Handler
# =========================

def apply_company_exclusions(params, user_query):
    query_lower = user_query.lower()

    known_companies = [
        "sbi", "tata", "hdfc", "digit", "liberty", "shriram",
        "sompo", "bajaj", "icici", "reliance", "new india",
        "future", "kotak", "magma", "royal", "chola", "zuno"
    ]

    exclusion_patterns = [
        r"if not\s+(\w+)",
        r"not\s+(\w+)",
        r"except\s+(\w+)",
        r"excluding\s+(\w+)",
        r"other than\s+(\w+)",
        r"exclude\s+(\w+)",
    ]

    excluded_companies = []
    for pattern in exclusion_patterns:
        matches = re.findall(pattern, query_lower)
        for match in matches:
            if any(company in match for company in known_companies):
                excluded_companies.append(match)

    best_keywords = ["best option", "recommend", "best rate", "suggest", "if not"]
    wants_best = any(kw in query_lower for kw in best_keywords)

    if wants_best or excluded_companies:
        print(f"🔄 Best rate requested → switching to 'all' companies")
        params["company"] = "all"

    if excluded_companies:
        print(f"🚫 Excluded companies detected: {excluded_companies}")
        params["excluded_companies"] = excluded_companies

    return params


# =========================
# MAIN QUERY RUNNER
# =========================

def run_query(user_query):
    print(f"\n💬 Query: {user_query}")
    print("=" * 60)

    print("🔍 Extracting parameters...")
    params = extract_params_from_query(user_query)

    # Keyword overrides
    query_lower = user_query.lower()

    # Sub product overrides

    # ONLY keep GVW override (special case handled in rule engine)
    if "gvw" in query_lower:
        params["sub_product"] = "gvw"
        print("🔧 Override: sub_product → 'gvw'")

    # seating format handling (1+5), (2+8), (1+4) → sum them up
    seating_plus = re.findall(r'\((\d+)\+(\d+)\)', user_query)
    if seating_plus:
        total = int(seating_plus[0][0]) + int(seating_plus[0][1])
        params["seating"] = str(total)
        print(f"🔧 Seating Override: ({seating_plus[0][0]}+{seating_plus[0][1]}) → '{total}'")

    # Wheel override — detect XW pattern (2w, 3w, 4w)
    wheel_match = re.findall(r'\b(\d+)\s*w\b', query_lower)
    if wheel_match:
        params["wheels"] = wheel_match[0]
        print(f"🔧 Wheel Override: wheels → '{wheel_match[0]}'")

    # Company exclusion + best rate detection
    params = apply_company_exclusions(params, user_query)

    print("\n📋 Extracted Parameters:")
    for k, v in params.items():
        print(f"   {k}: {v!r}")
    print("=" * 60)

    results = run_engine(
        company=params.get("company", "all"),
        sub_product=params.get("sub_product", ""),
        segment=params.get("segment", "comp"),
        rto=params.get("rto", "pan india"),
        fuel=params.get("fuel", ""),
        ncb=params.get("ncb", ""),
        highend=params.get("highend", ""),
        cpa=params.get("cpa", ""),
        vehicle_make=params.get("vehicle_make", ""),
        cc=params.get("cc", ""),
        seating=params.get("seating", ""),
        weight=params.get("weight", ""),
        age=params.get("age", ""),
        nil_dep=params.get("nil_dep", ""),
        wheels=params.get("wheels", "") 
    )

    # Filter excluded companies from results
    excluded = params.get("excluded_companies", [])
    if excluded and results:
        results = [
            r for r in results
            if not any(
                exc in r.get("_company_source", "").lower()
                for exc in excluded
            )
        ]
        print(f"🚫 Removed excluded companies from results")

    print("\n🎯 RESULTS:")
    if not results:
        print("❌ No matching rates found")
    else:
        for i, r in enumerate(results, 1):
            company = r.get("_company_source", params.get("company", "N/A")).upper()
            row_id = r.get("id", "N/A")
            vtype_id = r.get("vehicle_type_id", "N/A")
            od = r.get("payout_od_rate", 0)
            tp = r.get("payout_tp_rate", 0)
            from_date = r.get("eff_from_date", "")
            to_date = r.get("eff_to_date", "")
            diff = r.get("difference", "")
            print(f"  {i}. 🏢 {company} | Row ID: {row_id} | VType ID: {vtype_id} | OD: {od}% | TP: {tp}% | Valid: {from_date} → {to_date} | 🔍 Diff: {diff}")

    return results


# =========================
# TEST
# =========================
if __name__ == "__main__":
    queries = [
        "", 
    ]

    for query in queries:
        results = run_query(query)
        print("\n" + "=" * 60 + "\n")