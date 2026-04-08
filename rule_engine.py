import os
import pandas as pd
import re
import json

JSON_FOLDER = "json_files"

# =========================
# Load Company File (JSON)
# =========================

def get_company_file(user_input, folder=JSON_FOLDER):
    user_input = user_input.lower()

    # "all" → return all company files
    if user_input == "all":
        files = [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if f.endswith(".json") and f.startswith("od_tp_")
        ]
        print(f"🏢 ALL companies selected: {[os.path.basename(f) for f in files]}")
        return files

    for file in os.listdir(folder):
        if file.endswith(".json") and file.startswith("od_tp_"):
            clean_name = file.lower().replace("od_tp_", "").replace(".json", "")
            if clean_name in user_input:
                return os.path.join(folder, file)

    raise ValueError("❌ Company not supported")

def load_and_clean(file_path):
    # multiple files (all companies)
    if isinstance(file_path, list):
        dfs = []
        for fp in file_path:
            with open(fp, "r", encoding="utf-8") as f:
                records = json.load(f)
            df = pd.DataFrame(records)
            df.columns = df.columns.str.strip().str.lower()
            # Track which company this row belongs to
            company_name = os.path.basename(fp).replace("od_tp_", "").replace(".json", "")
            df["_company_source"] = company_name
            dfs.append(df)
        combined = pd.concat(dfs, ignore_index=True)
        print(f"📊 Combined Records from all companies: {len(combined)}")
        return combined

    # Single file (normal flow)
    with open(file_path, "r", encoding="utf-8") as f:
        records = json.load(f)
    df = pd.DataFrame(records)
    df.columns = df.columns.str.strip().str.lower()
    return df

# =========================
# Load Vehicle Mapping (JSON)
# =========================

def load_vehicle_mapping(path=f"{JSON_FOLDER}/vehicle_type_master.json"):
    with open(path, "r", encoding="utf-8") as f:
        records = json.load(f)
    df_map = pd.DataFrame(records)
    df_map.columns = df_map.columns.str.strip().str.lower()
    df_map["vehicle_type"] = df_map["vehicle_type"].astype(str).str.lower().str.strip()
    df_map["sub_product_name"] = df_map["sub_product_name"].astype(str).str.lower().str.strip()
    return df_map

# =========================
# Load RTO Mapping (JSON)
# =========================

def load_rto_mapping(path=f"{JSON_FOLDER}/rto_mapping.json"):
    with open(path, "r", encoding="utf-8") as f:
        records = json.load(f)
    df_rto = pd.DataFrame(records)
    df_rto.columns = df_rto.columns.str.strip().str.lower()
    df_rto["rto_code"] = df_rto["rto_code"].astype(str).str.upper().str.strip()
    return df_rto


# =========================
# Normalize Text
# =========================

def normalize_text(text):
    return str(text).strip().lower()

# Alias mapping — user input 
ALIASES = {
    "gvw": "goods vehicle",
    "goods vehicle weight": "goods vehicle",
    "gcv": "goods vehicle",
    "pcv": "passenger vehicle",
    "misc": "miscellaneous vehicle",
    "misc": "miscellaneous",
    "miscellaneous": "miscellaneous vehicle",
    "miscellaneous vehicle": "miscellaneous vehicle",
    "misd": "miscellaneous vehicle",
    "msv": "miscellaneous vehicle",
    "cv": "commercial vehicle",
}

def word_in_text(word, text):
    """Whole word match only"""
    return bool(re.search(r'\b' + re.escape(word) + r'\b', text))

# Keyword → specific IDs (bypass normal matching)
DIRECT_VEHICLE_MAP = {
    "harvester": [29],
    "agriculture harvester": [29],
    "tractor": [1, 4],        
    "agriculture tractor": [1],
    "good carring tractor": [4],
    "non tractor": [2],
    "truck": [3],
    "tanker": [5],
    "pickup": [6],
    "tipper": [14, 25],
    "trailer": [23],
    "staff bus": [28],
    "route bus": [32],
    "school bus": [11],
    "taxi": [8, 31],           
    "cab": [8, 31],
    "electric rikshaw": [9],
    "auto rikshaw": [13],
    "tempo traveller": [10],
    "delivery van": [7, 21],   
}

def get_vehicle_ids_from_input(user_input, df_map):
    user_input_original = normalize_text(user_input)
    user_input = user_input_original

    # Step 1: Alias replace
    for alias, replacement in ALIASES.items():
        if re.search(r'\b' + re.escape(alias) + r'\b', user_input):
            user_input = user_input.replace(alias, replacement)
            print(f"🔄 Alias replaced: '{alias}' → '{replacement}'")
            break

    # Step 2: Direct map check (specific keywords)
    for keyword, ids in DIRECT_VEHICLE_MAP.items():
        if keyword in user_input:
            print(f"🎯 Direct map hit: '{keyword}' → IDs {ids}")
            return ids

    matched_ids = []

    # Step 3: Wheel detection
    wheel_match = re.search(
        r'\b(2w|3w|4w|2\s*wheel|3\s*wheel|4\s*wheel|two\s*wheel|three\s*wheel|four\s*wheel)\b',
        user_input
    )
    explicit_wheels = wheel_match.group(1).replace(" ", "") if wheel_match else None

    WHEEL_KEYWORDS = ["2w", "3w", "4w", "2 wheel", "3 wheel", "4 wheel",
                      "two wheel", "three wheel", "four wheel"]

    # Step 4: Detect electric
    is_electric = "electric" in user_input

    for _, row in df_map.iterrows():
        vehicle = row["vehicle_type"]       
        sub_product = row["sub_product_name"]  
        vehicle_id = row["id"]

        # Skip wheel-specific rows if user didn't mention wheels
        if not explicit_wheels:
            vehicle_has_wheel = any(kw in vehicle for kw in WHEEL_KEYWORDS)
            if vehicle_has_wheel:
                continue

        # Wheel must match if explicitly given
        if explicit_wheels:
            if explicit_wheels not in vehicle.replace(" ", "") and \
               explicit_wheels not in sub_product.replace(" ", ""):
                continue

        # Electric filtering:
        # If user said electric → skip non-electric rows
        # If user didn't say electric → skip electric rows
        vehicle_is_electric = "electric" in vehicle
        if is_electric and not vehicle_is_electric:
            continue
        if not is_electric and vehicle_is_electric:
            continue

        # Step 5: Word matching — ALL words must match (not ANY)
        user_words = [w for w in user_input.split() if len(w) >= 2]

        # Remove generic words that cause false matches
        STOP_WORDS = {"vehicle", "all", "best", "rate", "highest", "comp",
                      "tp", "saod", "for", "and", "with", "without"}
        user_words = [w for w in user_words if w not in STOP_WORDS]

        if not user_words:
            continue

        # Check if ALL user words appear in vehicle_type (whole word match)
        vehicle_match = all(word_in_text(w, vehicle) for w in user_words)
        sub_match = all(word_in_text(w, sub_product) for w in user_words)

        if vehicle_match or sub_match:
            matched_ids.append(vehicle_id)

    matched_ids = list(set(matched_ids))
    print(f"🎯 Vehicle IDs: {matched_ids} (explicit_wheels: {explicit_wheels}, electric: {is_electric})")
    return matched_ids

# =========================
# Normalize Segment
# =========================

def normalize_segment(user_input):
    user_input = normalize_text(user_input)

    if "all" in user_input:
        return "all"  # ✅ NEW
    elif "tp" in user_input:
        return "tp only"
    elif "comp" in user_input:
        return "comprehensive"
    elif "saod" in user_input:
        return "saod"

    return user_input

# Normalize RTO Codes

def normalize_rto_input(rto_input):
    rto_input = str(rto_input).upper().strip()
    rto_input = rto_input.replace("-", "").replace(" ", "") 

    letters = "".join(re.findall(r"[A-Z]+", rto_input))
    numbers = "".join(re.findall(r"\d+", rto_input))

    # Case 1: Only state (MH)
    if not numbers:
        return letters, None

    # Case 2: MH1 → MH01
    numbers = numbers.zfill(2)
    return letters, letters + numbers


# =========================
# Filters - Sub Product & Segment
# =========================

def filter_sub_product(df, sub_product):
    return df[
        df["sub_product_name"].str.lower().str.contains(sub_product, na=False)
    ]

# ===========================
# Sub Product Name Filter (FALLBACK)
# ===========================

def apply_sub_product_name_filter(df, user_input):
    """
    Fallback: Match user input against sub_product_name column in the dataframe.
    Example: user enters 'pcv' → match rows where sub_product_name contains 'pcv'
    """
    print(f"🔍 Sub Product Name Fallback Filter: {user_input}")

    if "sub_product_name" not in df.columns:
        print("⚠️ sub_product_name column not found → skipping")
        return df

    df["sub_product_name"] = df["sub_product_name"].fillna("").astype(str).str.lower().str.strip()

    keywords = [w.strip() for w in user_input.lower().split() if len(w.strip()) > 1]
    print(f"🔑 Keywords to match in sub_product_name: {keywords}")

    if not keywords:
        return df

   
    mask = pd.Series([True] * len(df), index=df.index)
    for kw in keywords:
        mask = mask & df["sub_product_name"].str.contains(kw, na=False)

    df_filtered = df[mask]

    # OR fallback
    if df_filtered.empty:
        print("⚠️ AND match empty → trying OR match")
        mask = pd.Series([False] * len(df), index=df.index)
        for kw in keywords:
            mask = mask | df["sub_product_name"].str.contains(kw, na=False)
        df_filtered = df[mask]

    print(f"🔽 After Sub Product Name Filter: {len(df_filtered)}")
    if not df_filtered.empty:
        print(f"📋 Sample sub_product_names matched: {df_filtered['sub_product_name'].unique()[:5]}")

    return df_filtered


def filter_segment(df, segment):
    if segment == "all":
        print("📋 ALL segment → returning all, prioritizing comprehensive")
        # Sort so comprehensive rows come first
        df = df.copy()
        df["_seg_priority"] = df["segment"].str.lower().str.contains("comp").astype(int)
        df = df.sort_values("_seg_priority", ascending=False).drop(columns=["_seg_priority"])
        return df

    return df[
        df["segment"].str.lower().str.contains(segment, na=False)
    ]

# =========================
# Get RTOs Group Ids
# =========================

def get_rto_group_ids(df_rto, state, full_rto):
    
    # Case 1: Full RTO (MH01)
    if full_rto:
        match = df_rto[df_rto["rto_code"] == full_rto]

    # Case 2: State (MH)
    else:
        match = df_rto[df_rto["rto_code"].str.startswith(state)]

    if match.empty:
        print("⚠️ No RTO match found")
        return []

    return match["rto_group_id"].unique().tolist()

# =========================
# PRELOAD MAPPINGS (performance boost)
# =========================

df_vehicle_map = load_vehicle_mapping()
df_rto_map = load_rto_mapping()


# =========================
# MAIN ENGINE - PHASE 1
# =========================
def run_phase1(company, sub_product, segment):
    print("🚀 Starting Phase 1...")

    file_path = get_company_file(company)
    print(f"📂 Using File: {file_path}")

    df = load_and_clean(file_path)
    print(f"📊 Total Records: {len(df)}")

    # Direct sub_product_name filter — vehicle_type_id bypass
    DIRECT_SUB_PRODUCT_KEYWORDS = {
        "misc": "miscellaneous vehicle",
        "miscellaneous": "miscellaneous vehicle",
        "miscellaneous vehicle": "miscellaneous vehicle",
        "msv": "miscellaneous vehicle",
    }

    sub_lower = sub_product.lower().strip()
    direct_sub = None
    for keyword, target in DIRECT_SUB_PRODUCT_KEYWORDS.items():
        if keyword in sub_lower.split() or sub_lower == keyword:
            direct_sub = target
            print(f"🎯 Direct sub_product filter: '{sub_lower}' → '{target}'")
            break

    if direct_sub:
        df["sub_product_name"] = df["sub_product_name"].fillna("").astype(str).str.lower().str.strip()
        df = df[df["sub_product_name"].str.contains(direct_sub, na=False)]
        print(f"🔽 After Direct Sub Product Filter: {len(df)}")
        
        segment = normalize_segment(segment)
        df = filter_segment(df, segment)
        print(f"🔽 After Segment: {len(df)}")
        return df 

    vehicle_ids = get_vehicle_ids_from_input(sub_product, df_vehicle_map)

    # Get master sub_product_names (only for fallback use)
    master_sub_products = []
    if vehicle_ids:
        master_sub_products = df_vehicle_map[
            df_vehicle_map["id"].isin(vehicle_ids)
        ]["sub_product_name"].dropna().unique().tolist()
        print(f"📋 Master sub_product_names (fallback only): {master_sub_products}")

    if "_company_source" in df.columns:
        company_dfs = []

        for company_name, company_df in df.groupby("_company_source"):
            result_df = pd.DataFrame()

            # Try 1: vehicle_type_id filter
            if vehicle_ids and "vehicle_type_id" in company_df.columns:
                temp = company_df[company_df["vehicle_type_id"].isin(vehicle_ids)]
                if not temp.empty:
                    result_df = temp
                    print(f"✅ {company_name}: vehicle_type_id match → {len(temp)} rows")

            # Try 2: sub_product_name from master
            # ONLY if vehicle_type_id filter returned nothing
            if result_df.empty and master_sub_products:
                company_df_copy = company_df.copy()
                company_df_copy["sub_product_name"] = (
                    company_df_copy["sub_product_name"]
                    .fillna("")
                    .astype(str)
                    .str.lower()
                    .str.strip()
                )
                mask = pd.Series([False] * len(company_df_copy), index=company_df_copy.index)
                for sp in master_sub_products:
                    mask = mask | company_df_copy["sub_product_name"].str.contains(sp, na=False)
                temp = company_df_copy[mask]
                if not temp.empty:
                    result_df = temp
                    print(f"✅ {company_name}: sub_product_name fallback → {len(temp)} rows")

            # Try 3: lob_name fallback
            # ONLY if both above failed
            if result_df.empty:
                company_df_copy = company_df.copy()
                company_df_copy["lob_name"] = (
                    company_df_copy["lob_name"]
                    .fillna("")
                    .astype(str)
                    .str.lower()
                    .str.strip()
                )
                keywords = [
                    w.strip()
                    for w in sub_product.lower().split()
                    if len(w.strip()) > 1
                ]
                mask = pd.Series([False] * len(company_df_copy), index=company_df_copy.index)
                for kw in keywords:
                    mask = mask | company_df_copy["lob_name"].str.contains(kw, na=False)
                temp = company_df_copy[mask]
                if not temp.empty:
                    result_df = temp
                    print(f"✅ {company_name}: lob_name fallback → {len(temp)} rows")

            if result_df.empty:
                print(f"❌ {company_name}: no match → skipping")
            else:
                company_dfs.append(result_df)

        if company_dfs:
            df = pd.concat(company_dfs, ignore_index=True)
            print(f"📊 After per-company filter: {len(df)} rows from {df['_company_source'].unique().tolist()}")
        else:
            df = pd.DataFrame()

    else:
        # Single company flow
        if vehicle_ids:
            df_by_vehicle = apply_vehicle_type_filter(df, vehicle_ids)
            if not df_by_vehicle.empty:
                # Vehicle ID match mila → directly use, no sub_product filter
                df = df_by_vehicle
                print(f"✅ Single company: vehicle_type_id match → {len(df)} rows")
            elif master_sub_products:
                # Only fallback if vehicle filter empty
                df["sub_product_name"] = (
                    df["sub_product_name"]
                    .fillna("")
                    .astype(str)
                    .str.lower()
                    .str.strip()
                )
                mask = pd.Series([False] * len(df), index=df.index)
                for sp in master_sub_products:
                    mask = mask | df["sub_product_name"].str.contains(sp, na=False)
                df_filtered = df[mask]
                if not df_filtered.empty:
                    df = df_filtered
                    print(f"✅ sub_product_name fallback → {len(df)} rows")
                else:
                    print(f"⚠️ sub_product_name fallback empty → trying lob_name")
                    df = apply_lob_name_filter(df, sub_product)
            else:
                df = apply_lob_name_filter(df, sub_product)
        else:
            print(f"⚠️ No master match → trying lob_name fallback for: {sub_product}")
            df_lob = apply_lob_name_filter(df, sub_product)
            if not df_lob.empty:
                df = df_lob
            else:
                print(f"⚠️ LOB fallback empty → trying sub_product_name column")
                df = apply_sub_product_name_filter(df, sub_product)

    segment = normalize_segment(segment)
    df = filter_segment(df, segment)
    print(f"🔽 After Segment: {len(df)}")
    return df

# =========================
# PHASE 2 - RTO FILTER
# =========================

def apply_vehicle_type_filter(df, vehicle_ids):
    print(f"🚗 Applying Vehicle Type Filter: {vehicle_ids}")

    if not vehicle_ids:
        print("⚠️ No vehicle match → skipping")
        return df

    if "vehicle_type_id" not in df.columns:
        print("⚠️ vehicle_type_id column missing")
        return df

    df = df[df["vehicle_type_id"].isin(vehicle_ids)]

    print(f"🔽 After Vehicle Filter: {len(df)}")

    return df

def apply_lob_name_filter(df, user_input):
    """
    Fallback: jab vehicle master mein match na mile,
    toh lob_name column mein user keywords dhundho.
    Example: user ne 'pcv' diya → lob_name mein 'pcv' wale rows rakho
    """
    print(f"🔍 LOB Name Fallback Filter: {user_input}")

    if "lob_name" not in df.columns:
        print("⚠️ lob_name column not found → skipping fallback")
        return df

    # Normalize
    df["lob_name"] = df["lob_name"].fillna("").astype(str).str.lower().str.strip()

    # User input ke har word ko lob_name mein dhundho
    keywords = [w.strip() for w in user_input.lower().split() if len(w.strip()) > 1]
    print(f"🔑 Keywords to match in lob_name: {keywords}")

    if not keywords:
        print("⚠️ No keywords extracted → skipping fallback")
        return df


    mask = pd.Series([True] * len(df), index=df.index)
    for kw in keywords:
        mask = mask & df["lob_name"].str.contains(kw, na=False)

    df_filtered = df[mask]

  
    if df_filtered.empty:
        print("⚠️ AND match empty → trying OR match")
        mask = pd.Series([False] * len(df), index=df.index)
        for kw in keywords:
            mask = mask | df["lob_name"].str.contains(kw, na=False)
        df_filtered = df[mask]

    print(f"🔽 After LOB Name Filter: {len(df_filtered)}")
    if not df_filtered.empty:
        print(f"📋 Sample lob_names matched: {df_filtered['lob_name'].unique()[:5]}")

    return df_filtered

def apply_rto_filter(df, rto_input):
    print(f"🚀 Applying RTO Filter: {rto_input}")

    rto_lower = str(rto_input).lower().strip()

    if "pan india" in rto_lower or "all india" in rto_lower or "all rto" in rto_lower:
        print("✅ Pan India → no RTO filter")

        # Extract ALL excl. values — could be "excl. mh02, mh03, tn"
        excl_pattern = re.findall(r"excl[.\s]+([a-z0-9,\s]+)", rto_lower)
        
        if excl_pattern:
            
            excl_raw = excl_pattern[0]
            excl_items = [x.strip() for x in re.split(r"[,&]", excl_raw) if x.strip()]
            print(f"🚫 Exclusion items: {excl_items}")

            excl_group_ids = set()

            for item in excl_items:
                item = item.upper().strip()
                item = item.replace("-", "").replace(" ", "")

                letters = "".join(re.findall(r"[A-Z]+", item))
                numbers = "".join(re.findall(r"\d+", item))

                if numbers:
                    # Specific RTO like MH02
                    numbers = numbers.zfill(2)
                    full_rto = letters + numbers
                    print(f"🎯 Excluding specific RTO: {full_rto}")
                    ids = get_rto_group_ids(df_rto_map, letters, full_rto)
                else:
                    # Whole state like TN, MH
                    print(f"🎯 Excluding whole state: {letters}")
                    ids = get_rto_group_ids(df_rto_map, letters, None)

                excl_group_ids.update(ids)

            if excl_group_ids:
                before = len(df)
                df = df[~df["rto_group_id"].isin(excl_group_ids)]
                print(f"🔽 Excluded {before - len(df)} rows → remaining: {len(df)}")

        return df
        

    # Normal RTO flow 
    state, full_rto = normalize_rto_input(rto_input)
    mapping_group_ids = get_rto_group_ids(df_rto_map, state, full_rto)

    if not mapping_group_ids:
        print("⚠️ No mapping found")
        return df.iloc[0:0]

    phase1_group_ids = df["rto_group_id"].unique().tolist()
    final_group_ids = [g for g in phase1_group_ids if g in mapping_group_ids]

    if not final_group_ids:
        print("⚠️ No valid RTO groups")
        return df.iloc[0:0]

    df = df[df["rto_group_id"].isin(final_group_ids)]
    print(f"🔽 After RTO Filter: {len(df)}")
    return df

# ========================
# Fuel Filter (EXTRA)
# ========================

def apply_fuel_filter(df, fuel):
    print(f"⛽ Applying Fuel Filter: {fuel}")

    if df.empty:
        print("⚠️ Data empty before Fuel filter → skipping")
        return df

    # Case 1: No fuel OR ALL → skip
    if not fuel or str(fuel).lower() in ["all", "all fuel"]:
        print("⚠️ ALL fuel → skipping filter")
        return df
    
    # Inside apply_fuel_filter, before the filter line, add:
    if "fuel_type_id" in df.columns:
        df["fuel_type_id"] = pd.to_numeric(df["fuel_type_id"], errors="coerce").fillna(0).astype(int)

    fuel = str(fuel).lower().strip()

    # Normalize column
    if "fuel_type" not in df.columns:
        print("⚠️ fuel_type column not found → skipping")
        return df

    df["fuel_type"] = (
    df["fuel_type"]
    .fillna("")
    .astype(str)
    .str.lower()
    .str.strip()
)
    df["fuel_type"] = df["fuel_type"].replace("nan", "")
    
    fuel_list = [f.strip() for f in fuel.split("-")]

    df = df[
        (df["fuel_type"].isin(fuel_list)) |           # exact match
        (df["fuel_type"] == "") |             # blank = all
        (df["fuel_type_id"] == -1)       # explicit all
    ]


    print(f"🔽 After Fuel Filter: {len(df)}")
    return df

# ========================
# NCB Filter (EXTRA)
# ========================

def apply_ncb_filter(df, ncb):
    print(f"🧾 Applying NCB Filter: {ncb}")

    if not ncb or str(ncb).lower().strip() in ["all", ""]:
        print("⚠️ No NCB filter → skipping")
        return df
    
    ncb = str(ncb).lower().strip()

    target=None

    if ncb in ["with ncb", "with", "yes","true","1"]:
        target = 1
    elif ncb in ["without ncb", "without", "no","false","0"]:
        target = 0
    else:
        print("⚠️ Invalid NCB input → skipping")
        return df

    if "is_with_ncb" not in df.columns:
        print("⚠️ Column not found → skipping")
        return df
    
    # IMPORTANT FIX: normalize column

    df["is_with_ncb"] = pd.to_numeric(
        df["is_with_ncb"], errors="coerce"
    ).fillna(-1).astype(int)

    df_specific = df[df["is_with_ncb"] == target]

    if not df_specific.empty:
        print(f"✅ Specific match found: {len(df_specific)}")
        return df_specific

    # fallback
    df_all = df[df["is_with_ncb"] == -1]

    if not df_all.empty:
        print(f"⚠️ Using ALL (-1): {len(df_all)}")
        return df_all
    
# IMPORTANT: last fallback
    print("❌ No NCB match at all → returning original df")
    return df

# ========================
# High-End Filter (EXTRA)
# ========================

def apply_highend_filter(df, highend):
    print(f"🚗 Applying High-End Filter: {highend}")

    if not highend:
        print("⚠️ No High-End filter → skipping")
        return df

    val = str(highend).lower().strip()

    # normalize input
    if val in ["yes", "true", "1"]:
        target = "true"
    elif val in ["no", "false", "0"]:
        target = "false"
    else:
        print("⚠️ Invalid High-End input → skipping")
        return df

    if "is_highend_lob" not in df.columns:
        print("⚠️ Column not found → skipping")
        return df

    # normalize column
    df["is_highend_lob"] = df["is_highend_lob"].astype(str).str.lower().str.strip()

    # FINAL FILTER
    df = df[
        (df["is_highend_lob"] == target) |
        (df["is_highend_lob"] == "-1")   # not consider
    ]

    print(f"🔽 After High-End Filter: {len(df)}")
    return df
    
    
# ===========================
# Vehicle Make Filter (EXTRA)
# ===========================
    
def apply_make_filter(df, make):
    print(f"🚘 Applying Make Filter: {make}")

    if not make:
        print("⚠️ No Make filter → skipping")
        return df

    make = str(make).lower().strip()

    if "vehicle_make" not in df.columns:
        print("⚠️ vehicle_make column not found → skipping")
        return df

    df["vehicle_make"] = df["vehicle_make"].fillna("").astype(str).str.lower().str.strip()

    df = df[
        (df["vehicle_make"].str.contains(make, na=False)) |  
        (df["vehicle_make"] == "")
    ]

    print(f"🔽 After Make Filter: {len(df)}")
    return df

# ===========================
# CPA Filter (EXTRA)
# ===========================

def apply_cpa_filter(df, cpa):
    print(f"🛡️ Applying CPA Filter: {cpa}")

    if cpa is None or str(cpa).strip() == "":
        print("⚠️ No CPA filter → skipping")
        return df

    cpa_str = str(cpa).lower().strip()

    if cpa_str in ["with", "yes", "true", "1", "with cpa", "haa"]:
        cpa_value = 1
    elif cpa_str in ["without", "no", "false", "0", "without cpa"]:
        cpa_value = 0
    else:
        print("⚠️ Invalid CPA input → skipping")
        return df

    df["is_cpa_included"] = pd.to_numeric(
        df["is_cpa_included"], errors="coerce"
    ).fillna(-1).astype(int)

    
    df = df[df["is_cpa_included"] == cpa_value]

    print(f"🔽 After CPA Filter: {len(df)}")
    return df

    
# ===========================
# cc Filter (EXTRA)
# ==========================

def parse_cc_input(cc):
    cc = str(cc).lower().strip()

    # "above 150", "more than 150", ">150"
    if "above" in cc or "more than" in cc or cc.startswith(">"):
        nums = re.findall(r"\d+", cc)
        if nums:
            return int(nums[0]) + 1, 999999
        return None, None

    # "upto 75", "up to 75", "below 75", "<75"
    if "upto" in cc or "up to" in cc or "below" in cc or cc.startswith("<"):
        nums = re.findall(r"\d+", cc)
        if nums:
            return 0, int(nums[0])
        return None, None

    # "0-73", "75-150" → range
    nums = re.findall(r"\d+", cc)
    if len(nums) >= 2:
        return int(nums[0]), int(nums[1])

    # "85" → exact single value
    if len(nums) == 1:
        return int(nums[0]), int(nums[0])

    return None, None


def apply_cc_filter(df, cc):
    print(f"🔢 Applying CC Filter: {cc}")

    if not cc or str(cc).lower().strip() in ["all", "", "-1"]:
        print("⚠️ No CC filter → skipping")
        return df

    min_cc, max_cc = parse_cc_input(cc)

    if min_cc is None:
        print("⚠️ Invalid CC input")
        return df

    print(f"📊 CC Range: {min_cc} - {max_cc}")

    required_cols = ["from_cc", "to_cc", "is_cc_considered"]
    if not all(col in df.columns for col in required_cols):
        print("⚠️ CC columns missing → skipping")
        return df

    df = df.copy()
    df["from_cc"] = pd.to_numeric(df["from_cc"], errors="coerce").fillna(0)
    df["to_cc"] = pd.to_numeric(df["to_cc"], errors="coerce").fillna(999999)
    df["is_cc_considered"] = pd.to_numeric(df["is_cc_considered"], errors="coerce").fillna(-1).astype(int)

    
    df_specific = df[
        (df["is_cc_considered"] != -1) &
        (df["from_cc"] <= max_cc) &
        (df["to_cc"] >= min_cc)
    ]

    # -1 wale rows (CC not considered)
    df_all = df[df["is_cc_considered"] == -1]

    if not df_specific.empty:
        print(f"✅ Specific CC range matched: {len(df_specific)} rows")
        df = df_specific
    else:
        print(f"⚠️ No specific CC range → using -1 rows: {len(df_all)}")
        df = df_all

    print(f"🔽 After CC Filter: {len(df)}")
    return df

# ===========================
# Seating Capacity Filter (EXTRA)
# ===========================

def apply_seating_filter(df, seating):
    print(f"🪑 Applying Seating Filter: {seating}")

    if seating is None or str(seating).strip() == "":
        print("⚠️ No Seating → skipping")
        return df

    seating_str = str(seating).lower().strip()

    # Extract number
    nums = re.findall(r"\d+", seating_str)
    if not nums:
        print("⚠️ No number found in seating")
        return df

    seating_val = int(nums[0])

    # "above 12" → 13+, "upto 12" → use as-is
    if "above" in seating_str or "more than" in seating_str or ">" in seating_str:
        seating_val = seating_val + 1
        print(f"📊 'Above' detected → using {seating_val}")
    elif "upto" in seating_str or "up to" in seating_str or "below" in seating_str:
        print(f"📊 'Upto' detected → using {seating_val}")

    required_cols = ["from_seating_cap", "to_seating_cap", "is_seating_cap_consider"]
    if not all(col in df.columns for col in required_cols):
        print("⚠️ Seating columns missing → skipping")
        return df

    df["from_seating_cap"] = pd.to_numeric(df["from_seating_cap"], errors="coerce").fillna(0)
    df["to_seating_cap"] = pd.to_numeric(df["to_seating_cap"], errors="coerce").fillna(999)
    df["is_seating_cap_consider"] = pd.to_numeric(df["is_seating_cap_consider"], errors="coerce").fillna(-1).astype(int)

    # Debug print
    print(f"📊 is_seating_cap_consider unique: {df['is_seating_cap_consider'].unique()}")

    df_specific = df[
        (df["is_seating_cap_consider"] == 1) &
        (df["from_seating_cap"] <= seating_val) &
        (df["to_seating_cap"] >= seating_val)
    ]

    df_specific = df[
        (df["is_seating_cap_consider"] != -1) &
        (df["from_seating_cap"] <= seating_val) &
        (df["to_seating_cap"] >= seating_val)
    ]
    df_all = df[df["is_seating_cap_consider"] == -1]

    # NEW: 0 = not considered = treat as "all" 
    df_not_considered = df[df["is_seating_cap_consider"] == 0]

    print(f"📊 df_specific: {len(df_specific)}, df_all: {len(df_all)}, df_not_considered: {len(df_not_considered)}")

    if not df_specific.empty:
        print("✅ Using specific seating match")
        df = df_specific
    elif not df_all.empty:
        print("⚠️ Using -1 (all) rows")
        df = df_all
    else:
        # ✅ 0 = seating not applicable for this company → treat as pass-through
        print("⚠️ is_seating_cap_consider=0 → not applicable, returning all rows")
        df = df_not_considered

    print(f"🔽 After Seating Filter: {len(df)}")
    return df


# ===========================
# No of Wheels Filter (EXTRA)
# ===========================

def apply_wheel_filter(df, wheels):
    print(f"🛞 Applying Wheel Filter: {wheels}")

    if wheels is None or str(wheels).strip() == "":
        print("⚠️ No Wheels → skipping")
        return df

    wheels_str = str(wheels).lower().strip()

    # Extract number
    nums = re.findall(r"\d+", wheels_str)
    if not nums:
        print("⚠️ No number found in wheels")
        return df

    wheels_val = int(nums[0])
    print(f"📊 Wheel value: {wheels_val}")

    required_cols = ["from_no_of_wheel", "to_no_of_wheel", "is_no_of_wheel_consider"]
    if not all(col in df.columns for col in required_cols):
        print("⚠️ Wheel columns missing → skipping")
        return df

    df["from_no_of_wheel"] = pd.to_numeric(df["from_no_of_wheel"], errors="coerce").fillna(0)
    df["to_no_of_wheel"] = pd.to_numeric(df["to_no_of_wheel"], errors="coerce").fillna(999)
    df["is_no_of_wheel_consider"] = pd.to_numeric(df["is_no_of_wheel_consider"], errors="coerce").fillna(-1).astype(int)

    # Specific wheel rows
    df_specific = df[
        (df["is_no_of_wheel_consider"] != -1) &
        (df["from_no_of_wheel"] <= wheels_val) &
        (df["to_no_of_wheel"] >= wheels_val)
    ]

    # -1 rows (not considered = applies to all)
    df_all = df[df["is_no_of_wheel_consider"] == -1]

    if not df_specific.empty:
        print(f"✅ Specific wheel match: {len(df_specific)} rows")
        df = df_specific
    else:
        print(f"⚠️ No specific wheel range → using -1 rows: {len(df_all)}")
        df = df_all

    print(f"🔽 After Wheel Filter: {len(df)}")
    return df

# ============================
# weight Filter (EXTRA)
# ===========================

def normalize_weight_input(weight):
    weight_str = str(weight).lower().strip()

    # Already a number
    if weight_str.replace(".", "").isdigit():
        return float(weight_str)

    # Extract number from string like "2120 kg" or "2.5 ton"
    nums = re.findall(r"[\d.]+", weight_str)
    if not nums:
        return None

    value = float(nums[0])

    # Convert ton to kg
    if "ton" in weight_str or "tonne" in weight_str:
        value = value * 1000

    return value

def apply_weight_filter(df, weight, sub_product=""):
    print(f"⚖️ Applying Weight Filter: {weight}")

    weight_str = str(weight).lower().strip() if weight else ""

    # NEW CONDITION: weight empty + gcv/goods vehicle
    # exclude rows where weightage IS considered (= 1)
    # keep only is_weightage_considered = -1 rows
    if not weight_str or weight_str == "":
        sub = str(sub_product).lower().strip()
        is_gcv = any(kw in sub for kw in ["gcv", "goods", "goods vehicle", "gvw"])

        if is_gcv:
            print("⚠️ GCV detected + no weight given → keeping only is_weightage_considered = -1 rows")

            if "is_weightage_considered" in df.columns:
                df["is_weightage_considered"] = pd.to_numeric(
                    df["is_weightage_considered"], errors="coerce"
                ).fillna(-1).astype(int)

                df = df[df["is_weightage_considered"] == -1]
                print(f"🔽 After GCV No-Weight Filter: {len(df)}")

            return df

        # Non-GCV + no weight → skip filter entirely
        print("⚠️ No weight filter → skipping")
        return df

    if weight_str in ["all", "all weight"]:
        print("⚠️ ALL weight → skipping")
        return df

    if weight_str in ["no", "not applicable", "na"]:
        df = df[df["is_weightage_considered"] == -1]
        print(f"🔽 Weight NOT considered: {len(df)}")
        return df

    weight_val = normalize_weight_input(weight)

    if weight_val is None:
        print("⚠️ Invalid weight input")
        return df

    required_cols = ["from_weightage_kg", "to_weightage_kg", "is_weightage_considered"]
    if not all(col in df.columns for col in required_cols):
        print("⚠️ Weight columns missing → skipping")
        return df

    df["from_weightage_kg"] = pd.to_numeric(df["from_weightage_kg"], errors="coerce").fillna(0)
    df["to_weightage_kg"] = pd.to_numeric(df["to_weightage_kg"], errors="coerce").fillna(999999)
    df["is_weightage_considered"] = pd.to_numeric(df["is_weightage_considered"], errors="coerce").fillna(-1).astype(int)

    df_specific = df[
        (df["is_weightage_considered"] != -1) &
        (df["from_weightage_kg"] <= weight_val) &
        (df["to_weightage_kg"] >= weight_val)
    ]
    df_all = df[df["is_weightage_considered"] == -1]

    if not df_specific.empty:
        print(f"✅ Specific weight range matched: {len(df_specific)} rows")
        df = df_specific
    else:
        print(f"⚠️ No specific range → using -1 (all) rows: {len(df_all)}")
        df = df_all

    print(f"🔽 After Weight Filter: {len(df)}")
    return df


# ===========================
# Age Filter (EXTRA)
# ==========================

def normalize_age_input(age):
    if isinstance(age, (int, float)):
        return int(age), int(age)

    age_str = str(age).lower().strip()

    if not age_str or age_str in ["all", "none"]:
        return 0, 700

    if age_str in ["new", "new vehicle"]:
        return 0, 8

    if age_str in ["old", "old vehicle"]:
        return 9, 700

    # Detect direction FIRST
    is_above = any(kw in age_str for kw in ["above", "more than", "older than", ">"])
    is_upto  = any(kw in age_str for kw in ["upto", "up to", "below", "less than", "under", "<"])

    # Extract number
    nums = re.findall(r"\d+", age_str)
    if not nums:
        return None, None

    value = int(nums[0])

    # Check if it's a year (4 digits = manufacturing year)
    if value > 1900:
        from datetime import datetime
        age_years = datetime.now().year - value
        value = age_years * 12
        print(f"🗓️ Year detected → {age_years} years = {value} months")
    elif "year" in age_str or "yr" in age_str:
        value = value * 12
        print(f"📅 Years → months: {value}")
    # else already in months

    # Apply direction
    if is_above:
        print(f"⬆️ ABOVE detected → min={value+1}, max=700")
        return value + 1, 700      # above 15 yrs → 181 months to 700

    elif is_upto:
        print(f"⬇️ UPTO detected → min=0, max={value}")
        return 0, value            # upto 15 yrs → 0 to 180 months

    else:
        print(f"🎯 Exact age → {value} months")
        return value, value       


def apply_age_filter(df, age):
    print(f"🎂 Applying Age Filter: {age}")

    if age is None or str(age).lower().strip() in ["", "all", "none", "-1"]:
        print("⚠️ No age filter → skipping")
        return df

    min_age, max_age = normalize_age_input(age)

    if min_age is None:
        print("⚠️ Invalid age input")
        return df

    required_cols = ["from_age_month", "to_age_month"]

    if not all(col in df.columns for col in required_cols):
        print("⚠️ Age columns missing → skipping")
        return df

    # normalize
    df["from_age_month"] = pd.to_numeric(df["from_age_month"], errors="coerce").fillna(0)
    df["to_age_month"] = pd.to_numeric(df["to_age_month"], errors="coerce").fillna(700)

    # STEP 1: valid matches
    df_valid = df[
        (
            (df["from_age_month"] <= max_age) &
            (df["to_age_month"] >= min_age)
        )
    ].copy()

    if df_valid.empty:
        print("⚠️ No matching age range")
        return df_valid
    
    print(f"✅ Valid age matches: {len(df_valid)}")

    return df_valid   

    # KEEP ALL VALID MATCHES (NO RANGE PRIORITY)

# ===========================
# nil_dep Filter (EXTRA)
# ==========================

def apply_nil_dep_filter(df, nil_dep):
    print(f"🛠️ Applying Nil Dep Filter: {nil_dep}")

    val = str(nil_dep).lower().strip()

    # CASE 1: no filter
    if not val or val in ["all", ""]:
        print("⚠️ No Nil Dep filter → skipping")
        return df

    # CASE 2: normalize input
    if val in ["yes", "with", "true", "1"]:
        target = 1
    elif val in ["no", "without", "false", "0"]:
        target = 0
    else:
        print("⚠️ Invalid Nil Dep → skipping")
        return df

    if "is_nil_dep_considered" not in df.columns:
        print("⚠️ Column missing → skipping")
        return df

    # normalize column
    df["is_nil_dep_considered"] = pd.to_numeric(
        df["is_nil_dep_considered"], errors="coerce"
    ).fillna(-1).astype(int)

    print("🔍 Unique Nil Dep:", df["is_nil_dep_considered"].unique())

    # ✅ STEP 1: exact match
    df_specific = df[df["is_nil_dep_considered"] == target]

    if not df_specific.empty:
        print(f"✅ Exact Nil Dep match: {len(df_specific)}")
        return df_specific

    # ✅ STEP 2: fallback to -1 (ALL)
    df_all = df[df["is_nil_dep_considered"] == -1]

    if not df_all.empty:
        print(f"⚠️ Using ALL (-1): {len(df_all)}")
        return df_all

    # ✅ STEP 3: last fallback
    print("❌ No Nil Dep match → returning original df")
    return df

# =========================
# Score Calculation (EXTRA - can be used for ranking if multiple matches)
# =========================

def calculate_match_score(row, fuel, ncb, cpa, highend, make):
    score = 0

    # fuel
    if fuel and str(row.get("fuel_type", "")).lower() == str(fuel).lower():
        score += 1

    # ncb
    if ncb is not None:
        val = 1 if str(ncb).lower() in ["yes","with","1","true"] else 0
        if row.get("is_with_ncb") == val:
            score += 1

    # cpa
    if cpa is not None:
        val = 1 if str(cpa).lower() in ["yes","with","1","true"] else 0
        if row.get("is_cpa_included") == val:
            score += 1

    # highend
    if highend is not None:
        val = str(highend).lower() in ["yes","true","1"]
        if str(row.get("is_highend_lob")).lower() == str(val).lower():
            score += 1

    # make
    if make and str(row.get("vehicle_make","")).lower() == str(make).lower():
        score += 1

    return score

# =========================
# Apply all filters and then calculate a match score for ranking (if needed)
# =========================

def extract_lob_tags(lob_name):
    """Extract clean tags from lob_name brackets like (With Ncb)(Nil Dep)"""
    # Brackets ke andar se content nikalo
    tags = re.findall(r'\(([^)]+)\)', str(lob_name))
    return [t.strip() for t in tags if t.strip()]

def get_diff_tags(row_lob, all_lobs):
    """Compare tags of this row vs all rows — return only different ones"""
    row_tags = extract_lob_tags(row_lob)
    
    
    all_tags_list = [extract_lob_tags(l) for l in all_lobs]
    
  
    if all_tags_list:
        common_tags = set(all_tags_list[0])
        for tags in all_tags_list[1:]:
            common_tags &= set(tags)
    else:
        common_tags = set()
    
    
    diff_tags = [t for t in row_tags if t not in common_tags]
    return diff_tags

def get_best_match(df, fuel=None, ncb=None, cpa=None, highend=None, make=None, top_n=5):

    if df.empty:
        print("❌ No data found")
        return []

    print(f"📊 Total rows before rate filter: {len(df)}")

    # 1. ZERO RATE HANDLING (FIXED)
    df_valid = df[
        (df["payout_od_rate"] > 0) |
        (df["payout_tp_rate"] > 0)
    ].copy()

    if not df_valid.empty:
        print(f"✅ Using non-zero rate rows: {len(df_valid)}")
        df = df_valid
    else:
        print("⚠️ All rates are 0 → keeping 0 rate rows")

    # 2. MATCH SCORE
    df["match_score"] = df.apply(
        lambda row: calculate_match_score(row, fuel, ncb, cpa, highend, make),
        axis=1
    )

    # Highest rate priority

    df["final_rate"] = df[["payout_od_rate", "payout_tp_rate"]].max(axis=1)

    df = df.sort_values(
        by=["final_rate", "payout_od_rate", "payout_tp_rate"],
        ascending=[False, False, False]
    )

    # 4. MULTI COMPANY SAFE HANDLING
    if "_company_source" in df.columns:

        df_best_per_company = (
            df.sort_values(
                by=["payout_od_rate", "payout_tp_rate"],
                ascending=[False, False]
            )
            .groupby("_company_source", sort=False)
            .first()
            .reset_index()
        )

        # IMPORTANT FALLBACK
        if df_best_per_company.empty:
            print("⚠️ Grouping failed → using raw df")
            df_top_full = df.head(top_n).copy()
        else:
            df_top_full = df_best_per_company.sort_values(
                by=["payout_tp_rate", "payout_od_rate"],
                ascending=[False, False]
            ).head(top_n).copy()

    else:
        # SINGLE COMPANY FLOW
        df_top_full = df.head(top_n).copy()

    # 5. DIFFERENCE LOGIC FIX (0 allowed)
    meaningful_cols = [
        "lob_name", "rto_group_name", "fuel_type", "vehicle_make",
        "is_highend_lob", "is_cpa_included", "is_with_ncb",
        "is_nil_dep_considered"
    ]

    # REMOVED 0 FROM SKIP
    skip_values = {"", "nan", "None", "-1", "-1.0"}

    diff_notes = []

    for _, row in df_top_full.iterrows():
        row_diffs = []

        for col in meaningful_cols:
            if col not in df_top_full.columns:
                continue

            val = str(row[col]).strip()

            if val not in skip_values:
                if col == "is_with_ncb":
                    row_diffs.append("With NCB" if val == "1" else "Without NCB")
                elif col == "is_nil_dep_considered":
                    row_diffs.append("Nil Dep" if val == "1" else "Non Nil Dep")
                elif col == "is_cpa_included":
                    row_diffs.append("With CPA" if val == "1" else "Without CPA")
                elif col == "is_highend_lob":
                    row_diffs.append("High End" if val.lower() == "true" else "Non High End")
                elif col == "fuel_type":
                    row_diffs.append(f"Fuel: {val}")
                elif col == "vehicle_make":
                    row_diffs.append(f"Make: {val}")
                elif col == "rto_group_name":
                    row_diffs.append(f"RTO: {val}")

        diff_notes.append(" | ".join(row_diffs) if row_diffs else "—")

    df_top_full["difference"] = diff_notes

    # FINAL OUTPUT
    base_cols = ["payout_od_rate", "payout_tp_rate", "eff_from_date", "eff_to_date", "difference"]

    if "_company_source" in df_top_full.columns:
        base_cols = ["_company_source"] + base_cols

    df_clean = df_top_full[base_cols].copy()

    print("🔥 FINAL OUTPUT ROWS:", len(df_clean))
    print(df_clean.to_string())

    return df_clean.to_dict(orient="records")


# =========================
# FINAL ENGINE
# =========================
def run_engine(company, sub_product, segment, rto,fuel=None, ncb=None, highend=None,cpa=None,vehicle_make=None, cc=None, seating=None, weight=None, age=None, nil_dep=None, wheels=None):
    print("🚀 Starting Full Engine...")

    # Phase 1
    df = run_phase1(company, sub_product, segment)

    # Phase 2
    df = apply_rto_filter(df, rto)

    # Phase 3 - Fuel (EXTRA)
    df = apply_fuel_filter(df, fuel)

    # Phase 4 - NCB (EXTRA)
    df = apply_ncb_filter(df, ncb)

    # Phase 5 - High-End (EXTRA)
    df = apply_highend_filter(df, highend)

    # Phase 6 - CPA (EXTRA)
    df = apply_cpa_filter(df, cpa)

    # Phase 7 - Make (EXTRA)
    df = apply_make_filter(df, vehicle_make)

    # Phase 8 - CC (EXTRA)
    df = apply_cc_filter(df, cc)

    # Phase 9 - Seating (EXTRA)
    df = apply_seating_filter(df, seating)

    # Phase 9.5 - Wheels (EXTRA)
    df = apply_wheel_filter(df, wheels)

    # Phase 10 - Weight (EXTRA)
    df = apply_weight_filter(df, weight, sub_product=sub_product)

    # Phase 11 - Age (EXTRA)
    df = apply_age_filter(df, age)

    # Phase 12 - Nil Dep (EXTRA)
    df = apply_nil_dep_filter(df, nil_dep)

    # GVW alias → sub_product fix + weight flag set
    sub_product_normalized = sub_product.lower().strip()
    if "gvw" in sub_product_normalized and not weight:
        print("⚠️ GVW detected but no weight → weight filter will use is_weightage_considered=-1 only")

    # FINAL STEP
    best_result = get_best_match(
        df, fuel, ncb, cpa, highend, vehicle_make
    )
    
    return best_result

# =========================
# TEST
# =========================
if __name__ == "__main__":
    results = run_engine(
        company="",
        sub_product="",
        segment="",
        rto="",
        fuel="",
        ncb="",
        highend="",
        cpa="",
        vehicle_make="",
        cc="",
        seating="",
        wheels="",
        weight="",
        age="",
        nil_dep=""
    )
    print(results)